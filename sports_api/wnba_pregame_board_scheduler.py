"""WNBA Step 5P scheduled pregame collection and current-board publication.

Step 5P orchestrates frozen layers without changing their model semantics:
- official WNBA slate verification determines whether pregame work is allowed;
- Step 5O collects/persists/fails over sportsbook feeds;
- Step 5L builds candidates and delegates probability ranking to Step 5K;
- the exact Step 4W snapshot consumed by the frozen 5C/5D/5E/5F chain is
  captured alongside each generated threshold so Step 5J can create a genuine
  signed pregame archive;
- Step 5P persists immutable publication envelopes and scheduler-run history.

Provider polling and model rebuilding deliberately use separate cadences.  An
unchanged Step-5M line-board fingerprint can skip an expensive model rebuild
until the model-refresh window is due.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from sports_api.database.wnba_current_board_store import (
    STORE_PATH_ENV as BOARD_STORE_PATH_ENV,
    WNBACurrentBoardStoreError,
    WNBACurrentBoardStoreNotReadyError,
    append_scheduler_run,
    get_latest_publication,
    get_latest_scheduler_run,
    get_store_status as get_board_store_status,
    list_scheduler_runs,
    persist_publication,
)
from sports_api.database.wnba_pregame_prediction_store import (
    STORE_PATH_ENV as BACKTEST_STORE_PATH_ENV,
    WNBAPregameStoreError,
    archive_and_persist_prediction,
    initialize_store as initialize_backtest_store,
    resolve_store_path as resolve_backtest_store_path,
)
from sports_api.database.wnba_prop_feed_store import STORE_PATH_ENV as FEED_STORE_PATH_ENV
from sports_api.wnba_correlated_monte_carlo import (
    WNBACorrelatedMonteCarloModelInputError,
    WNBACorrelatedMonteCarloNotFoundError,
    WNBACorrelatedMonteCarloNotReadyError,
    WNBACorrelatedMonteCarloUpstreamError,
    simulate_correlated_outcomes,
)
from sports_api.wnba_daily_slate_top_five import build_daily_slate_top_five
from sports_api.wnba_empirical_outcome_distribution import (
    WNBAEmpiricalDistributionModelInputError,
    WNBAEmpiricalDistributionNotFoundError,
    WNBAEmpiricalDistributionNotReadyError,
    WNBAEmpiricalDistributionUpstreamError,
    build_empirical_outcome_distribution,
)
from sports_api.wnba_game_history import (
    WNBAHistoryNotFoundError,
    WNBAHistoryUpstreamError,
    get_player_game_log_dataset,
)
from sports_api.wnba_historical_backtest_calibration import (
    ARCHIVE_SIGNING_ENV,
    WNBAHistoricalBacktestModelInputError,
    WNBAHistoricalBacktestNotReadyError,
    WNBAHistoricalBacktestUpstreamError,
)
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_model_input_readiness import (
    DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    WNBAModelInputReadinessNotFoundError,
    WNBAModelInputReadinessUpstreamError,
    get_player_game_model_input_readiness,
)
from sports_api.wnba_projection_scenarios import (
    WNBAProjectionScenarioModelInputError,
    WNBAProjectionScenarioNotReadyError,
    WNBAProjectionScenarioUpstreamError,
    project_scenarios_from_readiness,
)
from sports_api.wnba_prop_feed_failover import (
    DEFAULT_MINIMUM_NORMALIZED_LINES,
    WNBAPropFeedFailoverModelInputError,
    WNBAPropFeedFailoverNotReadyError,
    WNBAPropFeedFailoverStoreError,
    WNBAPropFeedFailoverUpstreamError,
    collect_failover_line_board,
    describe_provider_onboarding,
)
from sports_api.wnba_prop_line_feed_adapter import DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS
from sports_api.wnba_prop_threshold_probability import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_COUNT,
    WNBAPropThresholdModelInputError,
    WNBAPropThresholdNotFoundError,
    WNBAPropThresholdNotReadyError,
    WNBAPropThresholdUpstreamError,
    evaluate_prop_threshold,
)
from sports_api.wnba_schedule import (
    ARIZONA_TZ,
    WNBAScheduleUpstreamError,
    verify_daily_slate_dataset,
)
from sports_api.wnba_sportsbook_market_edge import DEFAULT_MAX_MARKET_AGE_MINUTES

MODEL_SOURCE = "Kyre Sports API WNBA Step 5P scheduled pregame board publisher"
MODEL_VERSION = "wnba_step_5p_scheduled_pregame_board_v1"
SCHEMA_VERSION = "wnba_step_5p_scheduled_pregame_board_v1"
MODEL_FAMILY = "scheduled_official_slate_collection_deduped_model_refresh_and_publication"

SCHEDULER_ENABLED_ENV = "WNBA_BOARD_SCHEDULER_ENABLED"
AUTO_ARCHIVE_ENABLED_ENV = "WNBA_BOARD_AUTO_ARCHIVE_ENABLED"
LOOP_SECONDS_ENV = "WNBA_BOARD_SCHEDULER_LOOP_SECONDS"
MIN_PROVIDER_SPACING_ENV = "WNBA_BOARD_MIN_PROVIDER_SPACING_SECONDS"

DEFAULT_LOOP_SECONDS = 30
MIN_LOOP_SECONDS = 15
MAX_LOOP_SECONDS = 300
DEFAULT_MIN_PROVIDER_SPACING_SECONDS = 60
MIN_PROVIDER_SPACING_SECONDS = 30
MAX_PROVIDER_SPACING_SECONDS = 900

FAR_FROM_TIP_SECONDS = 6 * 60 * 60
MID_FROM_TIP_SECONDS = 2 * 60 * 60
FINAL_FROM_TIP_SECONDS = 30 * 60
POLL_FAR_SECONDS = 30 * 60
POLL_MID_SECONDS = 15 * 60
POLL_NEAR_SECONDS = 5 * 60
MODEL_REFRESH_FAR_SECONDS = 60 * 60
MODEL_REFRESH_MID_SECONDS = 30 * 60
MODEL_REFRESH_NEAR_SECONDS = 15 * 60
MODEL_REFRESH_FINAL_SECONDS = 10 * 60
PUBLICATION_EXPIRY_GRACE_SECONDS = 120
FAILURE_RETRY_SECONDS = 5 * 60
EMPTY_SLATE_RECHECK_SECONDS = 30 * 60
MAX_ARCHIVE_RESULTS_IN_RESPONSE = 500


class WNBAPregameBoardSchedulerNotReadyError(RuntimeError):
    pass


class WNBAPregameBoardSchedulerUpstreamError(RuntimeError):
    pass


class WNBAPregameBoardSchedulerModelInputError(ValueError):
    pass


class WNBAPregameBoardSchedulerStoreError(RuntimeError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: Any, label: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise WNBAPregameBoardSchedulerUpstreamError(
            f"WNBA Step 5P {label} must be timezone-aware ISO-8601."
        ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBAPregameBoardSchedulerUpstreamError(
            f"WNBA Step 5P {label} must include a timezone offset or Z."
        )
    return result.astimezone(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy_env(environment: Mapping[str, str], name: str, default: bool) -> bool:
    raw = environment.get(name)
    if raw is None:
        return default
    return str(raw).strip().casefold() not in {"0", "false", "no", "off", "disabled"}


def _bounded_int_env(
    environment: Mapping[str, str],
    name: str,
    default: int,
    low: int,
    high: int,
) -> int:
    raw = environment.get(name)
    if raw is None:
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return min(high, max(low, value))


def _target_date(value: str | None, now_utc: datetime) -> str:
    if value is None:
        return now_utc.astimezone(ARIZONA_TZ).date().isoformat()
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise WNBAPregameBoardSchedulerModelInputError(
            "WNBA Step 5P date must use YYYY-MM-DD format."
        ) from exc
    return text


def _positive_season(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise WNBAPregameBoardSchedulerModelInputError(
            "WNBA Step 5P season must be a positive integer."
        )
    return value


def _seconds_since(timestamp: Any, now_utc: datetime) -> float | None:
    if timestamp is None:
        return None
    try:
        return max(0.0, (now_utc - _dt(timestamp, "stored timestamp")).total_seconds())
    except Exception:
        return None


def _secret_ready(environment: Mapping[str, str]) -> bool:
    secret = environment.get(ARCHIVE_SIGNING_ENV)
    return bool(secret and len(str(secret).encode("utf-8")) >= 32)


def get_scheduler_configuration(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = _environment(env)
    requested = _truthy_env(environment, SCHEDULER_ENABLED_ENV, True)
    board_store_ready = bool(_clean(environment.get(BOARD_STORE_PATH_ENV)))
    feed_store_ready = bool(_clean(environment.get(FEED_STORE_PATH_ENV)))
    try:
        onboarding = describe_provider_onboarding(environment)
        provider_ready = onboarding.get("ready") is True
        provider_reason = onboarding.get("order_error")
    except Exception as exc:
        onboarding = None
        provider_ready = False
        provider_reason = str(exc)
    enabled = requested and board_store_ready and feed_store_ready and provider_ready
    if enabled:
        disabled_reason = None
    elif not requested:
        disabled_reason = "disabled by environment"
    elif not board_store_ready:
        disabled_reason = f"{BOARD_STORE_PATH_ENV} must point to a persistent SQLite path"
    elif not feed_store_ready:
        disabled_reason = f"{FEED_STORE_PATH_ENV} must point to the persistent Step 5O SQLite path"
    else:
        disabled_reason = provider_reason or "no ready Step 5O provider"

    archive_requested = _truthy_env(environment, AUTO_ARCHIVE_ENABLED_ENV, True)
    backtest_store_ready = bool(_clean(environment.get(BACKTEST_STORE_PATH_ENV)))
    signing_ready = _secret_ready(environment)
    archive_enabled = archive_requested and backtest_store_ready and signing_ready
    if archive_enabled:
        archive_disabled_reason = None
    elif not archive_requested:
        archive_disabled_reason = "disabled by environment"
    elif not backtest_store_ready:
        archive_disabled_reason = f"{BACKTEST_STORE_PATH_ENV} must point to a persistent SQLite path"
    else:
        archive_disabled_reason = f"{ARCHIVE_SIGNING_ENV} must contain at least 32 bytes"

    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "requested": requested,
        "enabled": enabled,
        "disabled_reason": disabled_reason,
        "loop_seconds": _bounded_int_env(
            environment,
            LOOP_SECONDS_ENV,
            DEFAULT_LOOP_SECONDS,
            MIN_LOOP_SECONDS,
            MAX_LOOP_SECONDS,
        ),
        "minimum_provider_spacing_seconds": _bounded_int_env(
            environment,
            MIN_PROVIDER_SPACING_ENV,
            DEFAULT_MIN_PROVIDER_SPACING_SECONDS,
            MIN_PROVIDER_SPACING_SECONDS,
            MAX_PROVIDER_SPACING_SECONDS,
        ),
        "persistent_board_store_configured": board_store_ready,
        "persistent_feed_store_configured": feed_store_ready,
        "provider_onboarding": onboarding,
        "automatic_archive": {
            "requested": archive_requested,
            "enabled": archive_enabled,
            "disabled_reason": archive_disabled_reason,
            "persistent_backtest_store_configured": backtest_store_ready,
            "signing_secret_ready": signing_ready,
        },
        "cadence_seconds": {
            "provider_poll_far": POLL_FAR_SECONDS,
            "provider_poll_mid": POLL_MID_SECONDS,
            "provider_poll_near": POLL_NEAR_SECONDS,
            "model_refresh_far": MODEL_REFRESH_FAR_SECONDS,
            "model_refresh_mid": MODEL_REFRESH_MID_SECONDS,
            "model_refresh_near": MODEL_REFRESH_NEAR_SECONDS,
            "model_refresh_final": MODEL_REFRESH_FINAL_SECONDS,
        },
        "guardrails": {
            "provider_polling_and_model_refresh_are_separate": True,
            "no_provider_collection_when_official_slate_has_no_playable_pregame_games": True,
            "publication_expires_no_later_than_official_tip": True,
            "automatic_archive_requires_hmac_and_persistent_backtest_store": True,
            "background_worker_starts_only_when_effectively_enabled": True,
        },
    }


def _validate_official_slate(
    slate: dict[str, Any],
    *,
    target_date: str,
    season: int,
    now_utc: datetime,
) -> dict[str, Any]:
    if not isinstance(slate, dict):
        raise WNBAPregameBoardSchedulerUpstreamError(
            "WNBA Step 5P official slate payload is malformed."
        )
    try:
        returned_season = int(slate.get("season", -1))
    except (TypeError, ValueError):
        returned_season = -1
    if slate.get("date") != target_date or returned_season != season:
        raise WNBAPregameBoardSchedulerUpstreamError(
            "WNBA Step 5P official slate date/season identity mismatch."
        )
    summary = slate.get("slate")
    games = slate.get("games")
    if not isinstance(summary, dict) or not isinstance(games, list):
        raise WNBAPregameBoardSchedulerUpstreamError(
            "WNBA Step 5P official slate verification fields are missing."
        )
    if summary.get("slate_integrity_pass") is not True:
        reasons = summary.get("blocking_reasons") or []
        raise WNBAPregameBoardSchedulerNotReadyError(
            "WNBA Step 5P requires official slate integrity; blocking reasons: "
            + (", ".join(map(str, reasons)) if reasons else "unknown")
        )

    playable: list[dict[str, Any]] = []
    future_nonplayable: list[dict[str, Any]] = []
    parsed_times: list[datetime] = []
    for game in games:
        if not isinstance(game, dict):
            continue
        verification = game.get("verification")
        game_dt_raw = game.get("game_datetime_utc")
        if game_dt_raw is None and isinstance(game.get("game"), dict):
            game_dt_raw = game["game"].get("game_datetime_utc")
        game_dt: datetime | None = None
        if game_dt_raw is not None:
            try:
                game_dt = _dt(game_dt_raw, "official game tip")
                parsed_times.append(game_dt)
            except WNBAPregameBoardSchedulerUpstreamError:
                game_dt = None
        is_playable = (
            isinstance(verification, dict)
            and verification.get("playable_pregame") is True
        )
        if is_playable:
            if game_dt is None:
                raise WNBAPregameBoardSchedulerUpstreamError(
                    "WNBA Step 5P playable official game is missing a valid tip time."
                )
            if game_dt <= now_utc:
                raise WNBAPregameBoardSchedulerNotReadyError(
                    "WNBA Step 5P official slate marked a game playable at/after its tip time."
                )
            playable.append(game)
        elif game_dt is None or game_dt > now_utc:
            future_nonplayable.append(game)

    if games and not playable and future_nonplayable:
        raise WNBAPregameBoardSchedulerNotReadyError(
            "WNBA Step 5P has future official games that are not verified as playable pregame."
        )
    earliest_tip = min(
        (_dt(game.get("game_datetime_utc"), "official playable game tip") for game in playable),
        default=None,
    )
    if not games:
        state = "empty_official_slate"
    elif not playable:
        state = "pregame_closed"
    else:
        state = "playable_pregame"
    return {
        "state": state,
        "official_game_count": len(games),
        "playable_games": playable,
        "playable_game_ids": [game.get("game_id") for game in playable],
        "earliest_tip_utc": earliest_tip,
        "source_retrieved_at_utc": slate.get("source_retrieved_at_utc"),
        "verified_at_utc": slate.get("verified_at_utc"),
    }


def _poll_seconds(seconds_to_tip: float) -> int:
    if seconds_to_tip > FAR_FROM_TIP_SECONDS:
        return POLL_FAR_SECONDS
    if seconds_to_tip > MID_FROM_TIP_SECONDS:
        return POLL_MID_SECONDS
    return POLL_NEAR_SECONDS


def _model_refresh_seconds(seconds_to_tip: float) -> int:
    if seconds_to_tip > FAR_FROM_TIP_SECONDS:
        return MODEL_REFRESH_FAR_SECONDS
    if seconds_to_tip > MID_FROM_TIP_SECONDS:
        return MODEL_REFRESH_MID_SECONDS
    if seconds_to_tip > FINAL_FROM_TIP_SECONDS:
        return MODEL_REFRESH_NEAR_SECONDS
    return MODEL_REFRESH_FINAL_SECONDS


def _closed_state_valid_until(target_date: str) -> datetime:
    date_value = datetime.strptime(target_date, "%Y-%m-%d").date()
    next_day_local = datetime.combine(
        date_value + timedelta(days=1),
        time(hour=6, minute=0),
        tzinfo=ARIZONA_TZ,
    )
    return next_day_local.astimezone(timezone.utc)


def _run_id(
    *,
    target_date: str,
    season: int,
    started_at_utc: datetime,
    outcome_seed: str,
) -> str:
    digest = _hash(
        {
            "date": target_date,
            "season": season,
            "started_at_utc": _iso(started_at_utc),
            "outcome_seed": outcome_seed,
        }
    )
    return f"wnba-5p-run-{digest[:24]}"


def _build_scheduler_run(
    *,
    target_date: str,
    season: int,
    started_at_utc: datetime,
    completed_at_utc: datetime,
    outcome: str,
    provider_collection_attempted: bool,
    board_rebuild_attempted: bool,
    next_due_at_utc: datetime | None,
    publication_id: str | None = None,
    selected_provider_id: str | None = None,
    source_feed_fingerprint_sha256: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source": MODEL_SOURCE,
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "run_id": _run_id(
            target_date=target_date,
            season=season,
            started_at_utc=started_at_utc,
            outcome_seed=outcome,
        ),
        "started_at_utc": _iso(started_at_utc),
        "completed_at_utc": _iso(completed_at_utc),
        "date": target_date,
        "season": season,
        "outcome": outcome,
        "provider_collection_attempted": provider_collection_attempted,
        "board_rebuild_attempted": board_rebuild_attempted,
        "publication_id": publication_id,
        "selected_provider_id": selected_provider_id,
        "source_feed_fingerprint_sha256": source_feed_fingerprint_sha256,
        "next_due_at_utc": _iso(next_due_at_utc) if next_due_at_utc is not None else None,
        "detail": deepcopy(detail) if detail is not None else None,
    }


def _provider_spacing_blocked(
    runs: list[dict[str, Any]],
    *,
    now_utc: datetime,
    minimum_spacing_seconds: int,
) -> tuple[bool, float | None]:
    for run in runs:
        if run.get("provider_collection_attempted") is not True:
            continue
        age = _seconds_since(run.get("completed_at_utc"), now_utc)
        if age is None:
            continue
        return age < minimum_spacing_seconds, age
    return False, None


def _publication_age_seconds(publication: dict[str, Any] | None, now_utc: datetime) -> float | None:
    if not isinstance(publication, dict):
        return None
    content = publication.get("content")
    if not isinstance(content, dict):
        return None
    return _seconds_since(content.get("published_at_utc"), now_utc)


def _capture_threshold_getter(
    capture: dict[str, dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    """Return a Step-5L-compatible threshold getter that preserves exact Step-4W evidence."""

    def getter(
        player_id: int,
        game_id: str,
        season: int,
        *,
        stat: str,
        line: float,
        season_type: str = "Regular Season",
        last_n_games: int = 5,
        distribution_last_n_games: int = 10,
        simulation_count: int = DEFAULT_SIMULATION_COUNT,
        batch_size: int = DEFAULT_BATCH_SIZE,
        random_seed: int = DEFAULT_RANDOM_SEED,
        require_current_availability: bool = True,
        max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
        require_convergence: bool = True,
    ) -> dict[str, Any]:
        try:
            readiness = get_player_game_model_input_readiness(
                player_id,
                game_id,
                season,
                season_type=season_type,
                last_n_games=last_n_games,
                require_current_availability=require_current_availability,
                include_shot_context=True,
                include_advanced_context=True,
                include_officiating_context=False,
                max_snapshot_age_minutes=max_snapshot_age_minutes,
                include_snapshot=True,
            )
        except WNBAModelInputReadinessNotFoundError as exc:
            raise WNBAPropThresholdNotFoundError(str(exc)) from exc
        except WNBAModelInputReadinessUpstreamError as exc:
            raise WNBAPropThresholdUpstreamError(str(exc)) from exc
        snapshot = readiness.get("snapshot")
        if not isinstance(snapshot, dict):
            raise WNBAPropThresholdUpstreamError(
                "WNBA Step 5P exact Step-4W snapshot capture is missing."
            )

        try:
            scenarios = project_scenarios_from_readiness(readiness)
        except WNBAProjectionScenarioNotReadyError as exc:
            raise WNBAPropThresholdNotReadyError(str(exc)) from exc
        except WNBAProjectionScenarioModelInputError as exc:
            raise WNBAPropThresholdModelInputError(str(exc)) from exc
        except WNBAProjectionScenarioUpstreamError as exc:
            raise WNBAPropThresholdUpstreamError(str(exc)) from exc

        try:
            game_log = get_player_game_log_dataset(
                player_id,
                season,
                season_type=season_type,
            )
        except WNBAHistoryNotFoundError as exc:
            raise WNBAPropThresholdNotFoundError(str(exc)) from exc
        except WNBAHistoryUpstreamError as exc:
            raise WNBAPropThresholdUpstreamError(str(exc)) from exc

        try:
            distribution = build_empirical_outcome_distribution(
                readiness,
                scenarios,
                game_log,
                season=season,
                season_type=season_type,
                distribution_last_n_games=distribution_last_n_games,
            )
        except WNBAEmpiricalDistributionNotFoundError as exc:
            raise WNBAPropThresholdNotFoundError(str(exc)) from exc
        except WNBAEmpiricalDistributionNotReadyError as exc:
            raise WNBAPropThresholdNotReadyError(str(exc)) from exc
        except WNBAEmpiricalDistributionModelInputError as exc:
            raise WNBAPropThresholdModelInputError(str(exc)) from exc
        except WNBAEmpiricalDistributionUpstreamError as exc:
            raise WNBAPropThresholdUpstreamError(str(exc)) from exc

        try:
            monte_carlo = simulate_correlated_outcomes(
                scenarios,
                distribution,
                simulation_count=simulation_count,
                batch_size=batch_size,
                random_seed=random_seed,
            )
        except WNBACorrelatedMonteCarloNotFoundError as exc:
            raise WNBAPropThresholdNotFoundError(str(exc)) from exc
        except WNBACorrelatedMonteCarloNotReadyError as exc:
            raise WNBAPropThresholdNotReadyError(str(exc)) from exc
        except WNBACorrelatedMonteCarloModelInputError as exc:
            raise WNBAPropThresholdModelInputError(str(exc)) from exc
        except WNBACorrelatedMonteCarloUpstreamError as exc:
            raise WNBAPropThresholdUpstreamError(str(exc)) from exc

        threshold = evaluate_prop_threshold(
            monte_carlo,
            stat=stat,
            line=line,
            require_convergence=require_convergence,
        )
        reference = threshold.get("snapshot_reference")
        if (
            not isinstance(reference, dict)
            or reference.get("content_sha256") != snapshot.get("content_sha256")
            or reference.get("snapshot_id") != snapshot.get("snapshot_id")
        ):
            raise WNBAPropThresholdUpstreamError(
                "WNBA Step 5P captured snapshot does not match the Step-5F snapshot reference."
            )
        fingerprint = str(threshold.get("probability_fingerprint_sha256") or "")
        if len(fingerprint) != 64:
            raise WNBAPropThresholdUpstreamError(
                "WNBA Step 5P generated Step-5F fingerprint is missing."
            )
        capture[fingerprint] = {
            "threshold": deepcopy(threshold),
            "snapshot": deepcopy(snapshot),
        }
        return threshold

    return getter


def _existing_archive_for_line(
    *,
    threshold: dict[str, Any],
    db_path: str | os.PathLike[str] | None,
) -> dict[str, Any] | None:
    prop = threshold.get("prop") or {}
    try:
        game_id = str(threshold["game_id"])
        player_id = int(threshold["player_id"])
        stat = str(prop["stat"])
        line = float(prop["line"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WNBAPregameBoardSchedulerStoreError(
            "WNBA Step 5P archive lookup identity is malformed."
        ) from exc
    initialize_backtest_store(db_path)
    resolved = resolve_backtest_store_path(db_path)
    conn = sqlite3.connect(str(resolved), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT archive_id,content_sha256,archived_at_utc,probability_fingerprint_sha256
            FROM wnba_pregame_archives
            WHERE game_id=? AND player_id=? AND stat=? AND ABS(line-?) < 0.000000001
            ORDER BY archived_at_utc ASC,archive_id ASC LIMIT 1""",
            (game_id, player_id, stat, line),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def _archive_captured_predictions(
    capture: dict[str, dict[str, Any]],
    *,
    enabled: bool,
    backtest_store_path: str | os.PathLike[str] | None,
    signing_secret: str | bytes | None,
    archived_at_utc: datetime,
    archive_writer: Callable[..., dict[str, Any]] = archive_and_persist_prediction,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "requested": enabled,
        "attempted_count": 0,
        "stored_count": 0,
        "existing_count": 0,
        "stored_or_existing_count": 0,
        "failed_count": 0,
        "first_prediction_per_game_player_stat_line": True,
        "results": [],
    }
    if not enabled:
        summary["status"] = "disabled"
        return summary
    ordered = sorted(
        capture.values(),
        key=lambda item: (
            str(item["threshold"].get("game_id")),
            int(item["threshold"].get("player_id") or 0),
            str((item["threshold"].get("prop") or {}).get("stat")),
            float((item["threshold"].get("prop") or {}).get("line") or 0.0),
        ),
    )
    for item in ordered:
        threshold = item["threshold"]
        snapshot = item["snapshot"]
        prop = threshold.get("prop") or {}
        logical = {
            "game_id": threshold.get("game_id"),
            "player_id": threshold.get("player_id"),
            "stat": prop.get("stat"),
            "line": prop.get("line"),
            "probability_fingerprint_sha256": threshold.get("probability_fingerprint_sha256"),
        }
        summary["attempted_count"] += 1
        try:
            existing = _existing_archive_for_line(
                threshold=threshold,
                db_path=backtest_store_path,
            )
            if existing is not None:
                summary["existing_count"] += 1
                summary["results"].append(
                    {**logical, "outcome": "existing_first_pregame_archive", "archive_id": existing["archive_id"]}
                )
                continue
            stored = archive_writer(
                threshold,
                snapshot,
                db_path=backtest_store_path,
                archived_at_utc=archived_at_utc,
                signing_secret=signing_secret,
            )
            persistence = stored.get("persistence") or {}
            archive = stored.get("archive") or {}
            if persistence.get("stored") is True:
                summary["stored_count"] += 1
                outcome = "stored"
            else:
                summary["existing_count"] += 1
                outcome = "idempotent_existing"
            summary["results"].append(
                {**logical, "outcome": outcome, "archive_id": archive.get("archive_id")}
            )
        except (
            WNBAPregameStoreError,
            WNBAHistoricalBacktestNotReadyError,
            WNBAHistoricalBacktestModelInputError,
            WNBAHistoricalBacktestUpstreamError,
            ValueError,
        ) as exc:
            summary["failed_count"] += 1
            summary["results"].append(
                {**logical, "outcome": "archive_failed", "error_type": type(exc).__name__, "detail": str(exc)}
            )
        if len(summary["results"]) >= MAX_ARCHIVE_RESULTS_IN_RESPONSE:
            break
    summary["stored_or_existing_count"] = summary["stored_count"] + summary["existing_count"]
    summary["status"] = "complete" if summary["failed_count"] == 0 else "partial_failure"
    return summary


def _build_publication(
    *,
    target_date: str,
    season: int,
    season_type: str,
    published_at_utc: datetime,
    valid_until_utc: datetime,
    serving_state: str,
    source_reference: dict[str, Any],
    daily_board: dict[str, Any] | None,
    archive_summary: dict[str, Any],
    scheduling: dict[str, Any],
) -> dict[str, Any]:
    if daily_board is None:
        board = {
            "daily_board_id": None,
            "daily_board_fingerprint_sha256": None,
            "probability_board_count": 0,
            "value_board_count": 0,
            "probability_board": [],
            "value_board": [],
            "step_5l_daily_top_five": None,
        }
    else:
        board = {
            "daily_board_id": daily_board.get("daily_board_id"),
            "daily_board_fingerprint_sha256": daily_board.get("daily_board_fingerprint_sha256"),
            "probability_board_count": int(daily_board.get("probability_board_count") or 0),
            "value_board_count": int(daily_board.get("value_board_count") or 0),
            "probability_board": deepcopy(daily_board.get("probability_board") or []),
            "value_board": deepcopy(daily_board.get("value_board") or []),
            "step_5l_daily_top_five": deepcopy(daily_board),
        }
    content = {
        "date": target_date,
        "season": season,
        "season_type": season_type,
        "published_at_utc": _iso(published_at_utc),
        "valid_until_utc": _iso(valid_until_utc),
        "serving_state": serving_state,
        "source_reference": deepcopy(source_reference),
        "board": board,
        "archive_summary": deepcopy(archive_summary),
        "scheduling": deepcopy(scheduling),
        "semantics": {
            "publication_is_immutable": True,
            "current_board_is_latest_unexpired_publication": True,
            "provider_feed_is_persisted_by_frozen_step_5o_before_publication": True,
            "step_5k_probability_rank_remains_authoritative": True,
            "publication_does_not_rescale_probability": True,
        },
    }
    digest = _hash(content)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_current_official_pregame_top_five_publication",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _iso(published_at_utc),
        "publication_id": f"wnba-5p-publication-{target_date}-{digest[:20]}",
        "content_sha256": digest,
        "content": content,
    }


def _empty_source_reference(slate_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_provider_id": None,
        "selected_failover_rank": None,
        "failover_fingerprint_sha256": None,
        "line_board_fingerprint_sha256": None,
        "feed_snapshot_reference": None,
        "official_slate_state": {
            "state": slate_state["state"],
            "official_game_count": slate_state["official_game_count"],
            "playable_game_ids": deepcopy(slate_state["playable_game_ids"]),
            "source_retrieved_at_utc": slate_state.get("source_retrieved_at_utc"),
            "verified_at_utc": slate_state.get("verified_at_utc"),
        },
    }


def _failover_source_reference(failover: dict[str, Any], slate_state: dict[str, Any]) -> dict[str, Any]:
    line_board = failover.get("line_board") or {}
    return {
        "selected_provider_id": failover.get("selected_provider_id"),
        "selected_failover_rank": failover.get("selected_failover_rank"),
        "failover_fingerprint_sha256": failover.get("failover_fingerprint_sha256"),
        "line_board_fingerprint_sha256": line_board.get("line_board_fingerprint_sha256"),
        "feed_snapshot_reference": deepcopy(failover.get("snapshot_reference")),
        "official_slate_state": {
            "state": slate_state["state"],
            "official_game_count": slate_state["official_game_count"],
            "playable_game_ids": deepcopy(slate_state["playable_game_ids"]),
            "earliest_tip_utc": (
                _iso(slate_state["earliest_tip_utc"])
                if slate_state.get("earliest_tip_utc") is not None
                else None
            ),
        },
    }


def run_pregame_board_cycle(
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    provider_ids: Sequence[str] | None = None,
    force: bool = False,
    now_utc: datetime | None = None,
    env: Mapping[str, str] | None = None,
    board_store_path: str | os.PathLike[str] | None = None,
    feed_store_path: str | os.PathLike[str] | None = None,
    backtest_store_path: str | os.PathLike[str] | None = None,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    exclude_stale_quotes: bool = True,
    max_side_pair_skew_seconds: int = DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
    minimum_normalized_lines: int = DEFAULT_MINIMUM_NORMALIZED_LINES,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    distribution_last_n_games: int = 10,
    simulation_count: int = DEFAULT_SIMULATION_COUNT,
    batch_size: int = DEFAULT_BATCH_SIZE,
    random_seed: int = DEFAULT_RANDOM_SEED,
    require_current_availability: bool = True,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    require_convergence: bool = True,
    minimum_required_ev: float = 0.0,
    include_stored_calibration: bool = True,
    require_slate_integrity: bool = True,
    top_n: int = 5,
    minimum_base_probability: float = 0.55,
    minimum_worst_scenario_probability: float = 0.50,
    maximum_scenario_span_percentage_points: float = 20.0,
    require_same_favored_side_all_scenarios: bool = True,
    require_strict_numerical_readiness: bool = True,
    require_mature_calibration: bool = False,
    one_line_per_player_stat: bool = True,
    slate_getter: Callable[..., dict[str, Any]] = verify_daily_slate_dataset,
    failover_collector: Callable[..., dict[str, Any]] = collect_failover_line_board,
    daily_builder: Callable[..., dict[str, Any]] = build_daily_slate_top_five,
    publication_persister: Callable[..., dict[str, Any]] = persist_publication,
    run_appender: Callable[..., dict[str, Any]] = append_scheduler_run,
    latest_publication_getter: Callable[..., dict[str, Any] | None] = get_latest_publication,
    latest_run_getter: Callable[..., dict[str, Any] | None] = get_latest_scheduler_run,
    run_history_getter: Callable[..., list[dict[str, Any]]] = list_scheduler_runs,
    archive_writer: Callable[..., dict[str, Any]] = archive_and_persist_prediction,
) -> dict[str, Any]:
    if not isinstance(force, bool):
        raise WNBAPregameBoardSchedulerModelInputError("WNBA Step 5P force must be boolean.")
    environment = _environment(env)
    now = now_utc or _now()
    if not isinstance(now, datetime):
        raise WNBAPregameBoardSchedulerModelInputError(
            "WNBA Step 5P now_utc must be a datetime when supplied."
        )
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    target_date = _target_date(date, now)
    season = _positive_season(season)
    started_at = now
    config = get_scheduler_configuration(environment)

    if board_store_path is None and not _clean(environment.get(BOARD_STORE_PATH_ENV)):
        raise WNBAPregameBoardSchedulerNotReadyError(
            f"WNBA Step 5P requires {BOARD_STORE_PATH_ENV} or an explicit board_store_path."
        )
    if feed_store_path is not None:
        environment = dict(environment)
        environment[FEED_STORE_PATH_ENV] = str(feed_store_path)
    if feed_store_path is None and not _clean(environment.get(FEED_STORE_PATH_ENV)):
        raise WNBAPregameBoardSchedulerNotReadyError(
            f"WNBA Step 5P requires {FEED_STORE_PATH_ENV} or an explicit feed_store_path."
        )

    latest_run = latest_run_getter(
        date=target_date,
        season=season,
        path=board_store_path,
        env=environment,
    )
    if not force and isinstance(latest_run, dict) and latest_run.get("next_due_at_utc"):
        next_due = _dt(latest_run["next_due_at_utc"], "scheduler next due")
        if now < next_due:
            return {
                "source": MODEL_SOURCE,
                "data_type": "wnba_step_5p_scheduler_cycle",
                "schema_version": SCHEMA_VERSION,
                "model_version": MODEL_VERSION,
                "date": target_date,
                "season": season,
                "outcome": "skipped_not_due",
                "next_due_at_utc": _iso(next_due),
                "seconds_until_due": round((next_due - now).total_seconds(), 3),
                "provider_collection_attempted": False,
                "board_rebuild_attempted": False,
            }

    try:
        slate = slate_getter(target_date, season)
    except ValueError as exc:
        raise WNBAPregameBoardSchedulerModelInputError(str(exc)) from exc
    except WNBAScheduleUpstreamError as exc:
        raise WNBAPregameBoardSchedulerUpstreamError(str(exc)) from exc
    slate_state = _validate_official_slate(
        slate,
        target_date=target_date,
        season=season,
        now_utc=now,
    )

    if slate_state["state"] in {"empty_official_slate", "pregame_closed"}:
        valid_until = _closed_state_valid_until(target_date)
        if valid_until <= now:
            valid_until = now + timedelta(hours=6)
        next_due = now + timedelta(seconds=EMPTY_SLATE_RECHECK_SECONDS)
        archive_summary = {
            "requested": config["automatic_archive"]["enabled"],
            "status": "not_applicable_no_playable_pregame_candidates",
            "attempted_count": 0,
            "stored_count": 0,
            "existing_count": 0,
            "stored_or_existing_count": 0,
            "failed_count": 0,
            "results": [],
        }
        publication = _build_publication(
            target_date=target_date,
            season=season,
            season_type=season_type,
            published_at_utc=now,
            valid_until_utc=valid_until,
            serving_state=slate_state["state"],
            source_reference=_empty_source_reference(slate_state),
            daily_board=None,
            archive_summary=archive_summary,
            scheduling={
                "provider_poll_seconds": None,
                "model_refresh_seconds": None,
                "next_due_at_utc": _iso(next_due),
                "provider_collection_skipped": True,
            },
        )
        persistence = publication_persister(publication, path=board_store_path, env=environment)
        publication_id = persistence["publication_id"]
        run = _build_scheduler_run(
            target_date=target_date,
            season=season,
            started_at_utc=started_at,
            completed_at_utc=_now() if now_utc is None else now,
            outcome=slate_state["state"],
            provider_collection_attempted=False,
            board_rebuild_attempted=False,
            next_due_at_utc=next_due,
            publication_id=publication_id,
            detail={"slate_state": deepcopy(slate_state), "publication_persistence": persistence},
        )
        run_appender(run, path=board_store_path, env=environment)
        return {
            "source": MODEL_SOURCE,
            "data_type": "wnba_step_5p_scheduler_cycle",
            "schema_version": SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "date": target_date,
            "season": season,
            "outcome": slate_state["state"],
            "provider_collection_attempted": False,
            "board_rebuild_attempted": False,
            "publication": publication,
            "publication_persistence": persistence,
            "scheduler_run": run,
        }

    earliest_tip = slate_state["earliest_tip_utc"]
    if not isinstance(earliest_tip, datetime):
        raise WNBAPregameBoardSchedulerUpstreamError(
            "WNBA Step 5P playable slate is missing earliest tip."
        )
    seconds_to_tip = max(0.0, (earliest_tip - now).total_seconds())
    poll_seconds = _poll_seconds(seconds_to_tip)
    refresh_seconds = _model_refresh_seconds(seconds_to_tip)
    next_due = now + timedelta(seconds=poll_seconds)
    minimum_spacing = config["minimum_provider_spacing_seconds"]
    recent_runs = run_history_getter(
        date=target_date,
        season=season,
        limit=50,
        path=board_store_path,
        env=environment,
    )
    spacing_blocked, spacing_age = _provider_spacing_blocked(
        recent_runs,
        now_utc=now,
        minimum_spacing_seconds=minimum_spacing,
    )
    if spacing_blocked:
        next_allowed = now + timedelta(seconds=max(1.0, minimum_spacing - float(spacing_age or 0.0)))
        return {
            "source": MODEL_SOURCE,
            "data_type": "wnba_step_5p_scheduler_cycle",
            "schema_version": SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "date": target_date,
            "season": season,
            "outcome": "skipped_provider_rate_guard",
            "provider_collection_attempted": False,
            "board_rebuild_attempted": False,
            "minimum_provider_spacing_seconds": minimum_spacing,
            "seconds_since_last_provider_collection": spacing_age,
            "next_due_at_utc": _iso(next_allowed),
        }

    try:
        failover = failover_collector(
            provider_ids,
            date=target_date,
            season=season,
            max_market_age_minutes=max_market_age_minutes,
            exclude_stale_quotes=exclude_stale_quotes,
            max_side_pair_skew_seconds=max_side_pair_skew_seconds,
            minimum_normalized_lines=minimum_normalized_lines,
            require_persistent_store=True,
            env=environment,
            store_path=feed_store_path,
        )
    except (
        WNBAPropFeedFailoverNotReadyError,
        WNBAPropFeedFailoverUpstreamError,
        WNBAPropFeedFailoverStoreError,
        WNBAPropFeedFailoverModelInputError,
        ValueError,
    ) as exc:
        retry_at = now + timedelta(seconds=FAILURE_RETRY_SECONDS)
        run = _build_scheduler_run(
            target_date=target_date,
            season=season,
            started_at_utc=started_at,
            completed_at_utc=_now() if now_utc is None else now,
            outcome="provider_cycle_failed",
            provider_collection_attempted=True,
            board_rebuild_attempted=False,
            next_due_at_utc=retry_at,
            detail={"error_type": type(exc).__name__, "detail": str(exc)},
        )
        run_appender(run, path=board_store_path, env=environment)
        raise WNBAPregameBoardSchedulerNotReadyError(str(exc)) from exc

    line_board = failover.get("line_board")
    if not isinstance(line_board, dict):
        raise WNBAPregameBoardSchedulerUpstreamError(
            "WNBA Step 5P Step-5O failover response is missing line_board."
        )
    line_fingerprint = _clean(line_board.get("line_board_fingerprint_sha256"))
    if not line_fingerprint or len(line_fingerprint) != 64:
        raise WNBAPregameBoardSchedulerUpstreamError(
            "WNBA Step 5P Step-5O line-board fingerprint is missing."
        )
    selected_provider = _clean(failover.get("selected_provider_id"))
    latest_publication = latest_publication_getter(
        date=target_date,
        season=season,
        now_utc=now,
        require_current=False,
        path=board_store_path,
        env=environment,
    )
    same_feed = False
    if isinstance(latest_publication, dict):
        latest_content = latest_publication.get("content") or {}
        latest_source = latest_content.get("source_reference") or {}
        same_feed = latest_source.get("line_board_fingerprint_sha256") == line_fingerprint
    publication_age = _publication_age_seconds(latest_publication, now)
    latest_current = bool(
        isinstance(latest_publication, dict)
        and isinstance(latest_publication.get("serving"), dict)
        and latest_publication["serving"].get("is_current") is True
    )
    if (
        same_feed
        and latest_current
        and publication_age is not None
        and publication_age < refresh_seconds
    ):
        run = _build_scheduler_run(
            target_date=target_date,
            season=season,
            started_at_utc=started_at,
            completed_at_utc=_now() if now_utc is None else now,
            outcome="feed_unchanged_model_refresh_not_due",
            provider_collection_attempted=True,
            board_rebuild_attempted=False,
            next_due_at_utc=next_due,
            publication_id=latest_publication.get("publication_id"),
            selected_provider_id=selected_provider,
            source_feed_fingerprint_sha256=line_fingerprint,
            detail={
                "publication_age_seconds": publication_age,
                "model_refresh_seconds": refresh_seconds,
                "failover_id": failover.get("failover_id"),
            },
        )
        run_appender(run, path=board_store_path, env=environment)
        return {
            "source": MODEL_SOURCE,
            "data_type": "wnba_step_5p_scheduler_cycle",
            "schema_version": SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "date": target_date,
            "season": season,
            "outcome": "feed_unchanged_model_refresh_not_due",
            "provider_collection_attempted": True,
            "board_rebuild_attempted": False,
            "selected_provider_id": selected_provider,
            "source_feed_fingerprint_sha256": line_fingerprint,
            "current_publication": latest_publication,
            "scheduler_run": run,
        }

    prop_lines = deepcopy(line_board.get("step_5l_prop_lines") or [])
    if not prop_lines:
        raise WNBAPregameBoardSchedulerNotReadyError(
            "WNBA Step 5P playable slate has no Step-5L prop lines after Step-5O validation."
        )
    capture: dict[str, dict[str, Any]] = {}
    threshold_getter = _capture_threshold_getter(capture)
    try:
        daily = daily_builder(
            prop_lines,
            date=target_date,
            season=season,
            season_type=season_type,
            last_n_games=last_n_games,
            distribution_last_n_games=distribution_last_n_games,
            simulation_count=simulation_count,
            batch_size=batch_size,
            random_seed=random_seed,
            require_current_availability=require_current_availability,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
            require_convergence=require_convergence,
            minimum_required_ev=minimum_required_ev,
            max_market_age_minutes=max_market_age_minutes,
            exclude_stale_quotes=exclude_stale_quotes,
            include_stored_calibration=include_stored_calibration,
            require_slate_integrity=require_slate_integrity,
            top_n=top_n,
            minimum_base_probability=minimum_base_probability,
            minimum_worst_scenario_probability=minimum_worst_scenario_probability,
            maximum_scenario_span_percentage_points=maximum_scenario_span_percentage_points,
            require_same_favored_side_all_scenarios=require_same_favored_side_all_scenarios,
            require_strict_numerical_readiness=require_strict_numerical_readiness,
            require_mature_calibration=require_mature_calibration,
            one_line_per_player_stat=one_line_per_player_stat,
            threshold_getter=threshold_getter,
        )
    except Exception as exc:
        retry_at = now + timedelta(seconds=FAILURE_RETRY_SECONDS)
        run = _build_scheduler_run(
            target_date=target_date,
            season=season,
            started_at_utc=started_at,
            completed_at_utc=_now() if now_utc is None else now,
            outcome="board_rebuild_failed",
            provider_collection_attempted=True,
            board_rebuild_attempted=True,
            next_due_at_utc=retry_at,
            selected_provider_id=selected_provider,
            source_feed_fingerprint_sha256=line_fingerprint,
            detail={"error_type": type(exc).__name__, "detail": str(exc)},
        )
        run_appender(run, path=board_store_path, env=environment)
        raise

    archive_enabled = config["automatic_archive"]["enabled"]
    secret = environment.get(ARCHIVE_SIGNING_ENV)
    archive_db_path = backtest_store_path or environment.get(BACKTEST_STORE_PATH_ENV)
    archive_summary = _archive_captured_predictions(
        capture,
        enabled=archive_enabled,
        backtest_store_path=archive_db_path,
        signing_secret=secret,
        archived_at_utc=now,
        archive_writer=archive_writer,
    )

    valid_until = min(
        earliest_tip,
        now + timedelta(seconds=refresh_seconds + PUBLICATION_EXPIRY_GRACE_SECONDS),
    )
    if valid_until <= now:
        raise WNBAPregameBoardSchedulerNotReadyError(
            "WNBA Step 5P will not publish a board at or after official tip."
        )
    source_reference = _failover_source_reference(failover, slate_state)
    publication = _build_publication(
        target_date=target_date,
        season=season,
        season_type=season_type,
        published_at_utc=now,
        valid_until_utc=valid_until,
        serving_state="playable_pregame",
        source_reference=source_reference,
        daily_board=daily,
        archive_summary=archive_summary,
        scheduling={
            "seconds_to_earliest_tip_at_publication": round(seconds_to_tip, 3),
            "provider_poll_seconds": poll_seconds,
            "model_refresh_seconds": refresh_seconds,
            "next_due_at_utc": _iso(next_due),
            "feed_changed_since_last_publication": not same_feed,
            "previous_publication_age_seconds": publication_age,
        },
    )
    try:
        persistence = publication_persister(
            publication,
            path=board_store_path,
            env=environment,
        )
    except WNBACurrentBoardStoreError as exc:
        raise WNBAPregameBoardSchedulerStoreError(str(exc)) from exc
    publication_id = persistence["publication_id"]
    completed_at = _now() if now_utc is None else now
    outcome = "published_new_board" if persistence.get("stored") else "publication_idempotent_replay"
    run = _build_scheduler_run(
        target_date=target_date,
        season=season,
        started_at_utc=started_at,
        completed_at_utc=completed_at,
        outcome=outcome,
        provider_collection_attempted=True,
        board_rebuild_attempted=True,
        next_due_at_utc=next_due,
        publication_id=publication_id,
        selected_provider_id=selected_provider,
        source_feed_fingerprint_sha256=line_fingerprint,
        detail={
            "failover_id": failover.get("failover_id"),
            "daily_board_id": daily.get("daily_board_id"),
            "archive_status": archive_summary.get("status"),
            "archive_stored_or_existing_count": archive_summary.get("stored_or_existing_count"),
            "publication_persistence": persistence,
        },
    )
    run_appender(run, path=board_store_path, env=environment)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step_5p_scheduler_cycle",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "date": target_date,
        "season": season,
        "outcome": outcome,
        "provider_collection_attempted": True,
        "board_rebuild_attempted": True,
        "selected_provider_id": selected_provider,
        "source_feed_fingerprint_sha256": line_fingerprint,
        "captured_threshold_snapshot_pair_count": len(capture),
        "archive_summary": archive_summary,
        "publication": publication,
        "publication_persistence": persistence,
        "scheduler_run": run,
        "guardrails": {
            "official_slate_checked_before_provider_collection": True,
            "provider_collection_rate_guard_applied": True,
            "unchanged_feed_can_skip_expensive_model_rebuild": True,
            "exact_step_4w_snapshot_captured_in_same_projection_orchestration": True,
            "first_archive_per_game_player_stat_line_prevents_refresh_overweighting": True,
            "publication_expires_no_later_than_earliest_official_tip": True,
            "market_data_cannot_change_step_5k_probability_rank": True,
        },
    }


def get_current_published_board(
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    now_utc: datetime | None = None,
    require_current: bool = True,
    env: Mapping[str, str] | None = None,
    board_store_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    now = now_utc or _now()
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    target_date = _target_date(date, now)
    try:
        publication = get_latest_publication(
            date=target_date,
            season=season,
            now_utc=now,
            require_current=require_current,
            path=board_store_path,
            env=env,
        )
    except WNBACurrentBoardStoreNotReadyError as exc:
        raise WNBAPregameBoardSchedulerNotReadyError(str(exc)) from exc
    if publication is None:
        raise WNBAPregameBoardSchedulerNotReadyError(
            "WNBA Step 5P has not published a board for this date/season yet."
        )
    content = publication.get("content") or {}
    board = content.get("board") or {}
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_current_official_pregame_top_five_board",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "date": target_date,
        "season": season,
        "serving_state": content.get("serving_state"),
        "serving": deepcopy(publication.get("serving")),
        "publication_id": publication.get("publication_id"),
        "publication_content_sha256": publication.get("content_sha256"),
        "published_at_utc": content.get("published_at_utc"),
        "valid_until_utc": content.get("valid_until_utc"),
        "selected_provider_id": (content.get("source_reference") or {}).get("selected_provider_id"),
        "probability_board_count": int(board.get("probability_board_count") or 0),
        "value_board_count": int(board.get("value_board_count") or 0),
        "probability_board": deepcopy(board.get("probability_board") or []),
        "value_board": deepcopy(board.get("value_board") or []),
        "archive_summary": deepcopy(content.get("archive_summary")),
        "publication": publication,
        "serving_semantics": {
            "no_network_call_required": True,
            "no_model_rebuild_required": True,
            "expired_publication_is_rejected_when_require_current_true": True,
            "pregame_publication_never_remains_current_at_or_after_earliest_tip": True,
        },
    }


def get_scheduler_status(
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    env: Mapping[str, str] | None = None,
    board_store_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    environment = _environment(env)
    now = _now()
    target_date = _target_date(date, now)
    status: dict[str, Any] = {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step_5p_scheduler_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso(now),
        "date": target_date,
        "season": season,
        "configuration": get_scheduler_configuration(environment),
    }
    try:
        status["board_store"] = get_board_store_status(
            path=board_store_path,
            env=environment,
        )
        status["latest_scheduler_run"] = get_latest_scheduler_run(
            date=target_date,
            season=season,
            path=board_store_path,
            env=environment,
        )
        status["latest_publication"] = get_latest_publication(
            date=target_date,
            season=season,
            now_utc=now,
            require_current=False,
            path=board_store_path,
            env=environment,
        )
    except WNBACurrentBoardStoreError as exc:
        status["board_store"] = {"ready": False, "error": str(exc)}
        status["latest_scheduler_run"] = None
        status["latest_publication"] = None
    return status
