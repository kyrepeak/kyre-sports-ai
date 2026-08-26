"""WNBA Step 5O provider failover, durable snapshotting, and daily-board handoff."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from sports_api.collectors.wnba_prop_feed_collector import (
    WNBAPropFeedCollectorConfigError,
    WNBAPropFeedCollectorModelInputError,
    WNBAPropFeedCollectorNotReadyError,
    WNBAPropFeedCollectorUpstreamError,
    collect_provider_feed,
    describe_provider_registry,
)
from sports_api.collectors.wnba_sportsgameodds import (
    SPORTSGAMEODDS_PROVIDER_ID,
    WNBASportsGameOddsAdapterError,
    collect_sportsgameodds_feed,
    describe_sportsgameodds_onboarding,
    sportsgameodds_ready,
)
from sports_api.database.wnba_prop_feed_store import (
    STORE_PATH_ENV,
    WNBAPropFeedStoreError,
    append_feed_attempt,
    get_provider_health,
    get_store_status,
    persist_feed_snapshot,
)
from sports_api.wnba_daily_slate_top_five import build_daily_slate_top_five
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_prop_line_feed_adapter import (
    DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
    WNBAPropLineFeedModelInputError,
    WNBAPropLineFeedNotReadyError,
    WNBAPropLineFeedUpstreamError,
    build_prop_line_feed_board,
)
from sports_api.wnba_sportsbook_market_edge import DEFAULT_MAX_MARKET_AGE_MINUTES

MODEL_SOURCE = "Kyre Sports API WNBA Step 5O provider failover"
MODEL_VERSION = "wnba_step_5o_provider_failover_v1"
SCHEMA_VERSION = "wnba_step_5o_provider_failover_v1"
MODEL_FAMILY = "durable_multi_provider_collection_validation_and_failover"

FAILOVER_ORDER_ENV = "WNBA_PROP_FEED_FAILOVER_ORDER"
MAX_FAILOVER_PROVIDERS = 10
DEFAULT_MINIMUM_NORMALIZED_LINES = 1
_PROVIDER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class WNBAPropFeedFailoverNotReadyError(RuntimeError):
    pass


class WNBAPropFeedFailoverUpstreamError(RuntimeError):
    pass


class WNBAPropFeedFailoverModelInputError(ValueError):
    pass


class WNBAPropFeedFailoverStoreError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _provider_id(value: Any) -> str:
    text = (_clean(value) or "").casefold()
    if not _PROVIDER_ID_RE.fullmatch(text):
        raise WNBAPropFeedFailoverModelInputError(
            "WNBA Step 5O provider ids must match [a-z0-9][a-z0-9_-]{0,63}."
        )
    return text


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = _provider_id(raw)
        if value not in seen:
            result.append(value)
            seen.add(value)
    if len(result) > MAX_FAILOVER_PROVIDERS:
        raise WNBAPropFeedFailoverModelInputError(
            f"WNBA Step 5O failover chain cannot exceed {MAX_FAILOVER_PROVIDERS} providers."
        )
    return result


def resolve_failover_order(
    provider_ids: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    environment = _environment(env)
    if provider_ids is not None:
        result = _dedupe(list(provider_ids))
        if not result:
            raise WNBAPropFeedFailoverModelInputError("WNBA Step 5O explicit provider_ids cannot be empty.")
        return result

    configured_order = _clean(environment.get(FAILOVER_ORDER_ENV))
    if configured_order:
        result = _dedupe([item.strip() for item in configured_order.split(",") if item.strip()])
        if not result:
            raise WNBAPropFeedFailoverModelInputError(
                f"WNBA Step 5O {FAILOVER_ORDER_ENV} did not contain any provider ids."
            )
        return result

    result: list[str] = []
    if sportsgameodds_ready(environment):
        result.append(SPORTSGAMEODDS_PROVIDER_ID)
    registry = describe_provider_registry(environment)
    ready = [row for row in registry.get("providers", []) if row.get("enabled") and row.get("ready")]
    default_id = registry.get("default_provider_id")
    if default_id and any(row.get("provider_id") == default_id for row in ready):
        result.append(default_id)
    result.extend(sorted(row["provider_id"] for row in ready if row.get("provider_id") != default_id))
    result = _dedupe(result)
    if not result:
        raise WNBAPropFeedFailoverNotReadyError(
            "WNBA Step 5O has no ready providers. Configure SPORTSGAMEODDS_API_KEY, "
            "WNBA_PROP_FEED_PROVIDERS_JSON, or an explicit failover order."
        )
    return result


def describe_provider_onboarding(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _environment(env)
    sportsgameodds = describe_sportsgameodds_onboarding(environment)
    generic = describe_provider_registry(environment)
    try:
        order = resolve_failover_order(env=environment)
        ready = True
        order_error = None
    except Exception as exc:
        order = []
        ready = False
        order_error = str(exc)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_feed_onboarding_and_failover_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "ready": ready,
        "built_in_provider": sportsgameodds,
        "generic_step_5n_registry": generic,
        "resolved_failover_order": order,
        "failover_order_env": FAILOVER_ORDER_ENV,
        "store_path_env": STORE_PATH_ENV,
        "explicit_persistent_store_configured": bool(_clean(environment.get(STORE_PATH_ENV))),
        "order_error": order_error,
        "semantics": {
            "built_in_provider_uses_frozen_step_5n_transport": True,
            "generic_providers_use_frozen_step_5n_transport": True,
            "every_successful_http_collection_is_snapshotted_before_market_acceptance": True,
            "frozen_step_5m_decides_market_integrity": True,
            "http_200_alone_does_not_mark_provider_usable": True,
            "no_provider_can_modify_model_probability": True,
        },
    }


def _require_persistence(
    *,
    env: Mapping[str, str],
    store_path: str | Path | None,
    require_persistent_store: bool,
) -> None:
    if not isinstance(require_persistent_store, bool):
        raise ValueError("WNBA Step 5O require_persistent_store must be boolean.")
    if require_persistent_store and store_path is None and not _clean(env.get(STORE_PATH_ENV)):
        raise WNBAPropFeedFailoverNotReadyError(
            f"WNBA Step 5O durable mode requires {STORE_PATH_ENV} or an explicit store_path."
        )


def _generic_collection(
    provider_id: str,
    *,
    date: str | None,
    season: int,
    env: Mapping[str, str],
    requester: Callable[..., Any] | None,
    collector: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    collection = collector(
        provider_id,
        date=date,
        season=season,
        env=env,
        requester=requester,
    )
    return {
        "provider_id": collection["provider_id"],
        "collection": collection,
        "adapter": None,
        "feed_source": collection["feed_source"],
        "feed_format": collection["feed_format"],
        "odds_format": collection["odds_format"],
        "date": collection["date"],
        "season": collection["season"],
        "collected_at_utc": collection["collected_at_utc"],
        "raw_feed": collection["raw_feed"],
    }


def _collect_candidate(
    provider_id: str,
    *,
    date: str | None,
    season: int,
    env: Mapping[str, str],
    requester: Callable[..., Any] | None,
    generic_collector: Callable[..., dict[str, Any]],
    sportsgameodds_collector: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    if provider_id == SPORTSGAMEODDS_PROVIDER_ID:
        return sportsgameodds_collector(
            date=date,
            season=season,
            env=env,
            requester=requester,
        )
    return _generic_collection(
        provider_id,
        date=date,
        season=season,
        env=env,
        requester=requester,
        collector=generic_collector,
    )


def _attempt_summary(
    *,
    provider_id: str,
    rank: int,
    outcome: str,
    error_type: str | None = None,
    detail: str | None = None,
    snapshot_id: str | None = None,
    normalized_line_count: int | None = None,
    playable_game_count: int | None = None,
) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "failover_rank": rank,
        "outcome": outcome,
        "error_type": error_type,
        "detail": detail,
        "snapshot_id": snapshot_id,
        "normalized_line_count": normalized_line_count,
        "playable_game_count": playable_game_count,
    }


def _record_attempt(
    summary: dict[str, Any],
    *,
    started_at_utc: str,
    store_path: str | Path | None,
    env: Mapping[str, str],
    appender: Callable[..., dict[str, Any]],
) -> None:
    appender(
        provider_id=summary["provider_id"],
        failover_rank=summary["failover_rank"],
        started_at_utc=started_at_utc,
        outcome=summary["outcome"],
        error_type=summary.get("error_type"),
        snapshot_id=summary.get("snapshot_id"),
        normalized_line_count=summary.get("normalized_line_count"),
        playable_game_count=summary.get("playable_game_count"),
        detail={"detail": summary.get("detail")} if summary.get("detail") else None,
        path=store_path,
        env=env,
    )


def collect_failover_line_board(
    provider_ids: Sequence[str] | None = None,
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    exclude_stale_quotes: bool = True,
    max_side_pair_skew_seconds: int = DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
    minimum_normalized_lines: int = DEFAULT_MINIMUM_NORMALIZED_LINES,
    require_persistent_store: bool = True,
    env: Mapping[str, str] | None = None,
    store_path: str | Path | None = None,
    requester: Callable[..., Any] | None = None,
    generic_collector: Callable[..., dict[str, Any]] = collect_provider_feed,
    sportsgameodds_collector: Callable[..., dict[str, Any]] = collect_sportsgameodds_feed,
    line_board_builder: Callable[..., dict[str, Any]] = build_prop_line_feed_board,
    snapshot_persister: Callable[..., dict[str, Any]] = persist_feed_snapshot,
    attempt_appender: Callable[..., dict[str, Any]] = append_feed_attempt,
) -> dict[str, Any]:
    if not isinstance(minimum_normalized_lines, int) or isinstance(minimum_normalized_lines, bool) or not 0 <= minimum_normalized_lines <= 1_000:
        raise ValueError("WNBA Step 5O minimum_normalized_lines must be an integer from 0 through 1000.")
    environment = _environment(env)
    _require_persistence(
        env=environment,
        store_path=store_path,
        require_persistent_store=require_persistent_store,
    )
    order = resolve_failover_order(provider_ids, env=environment)
    attempts: list[dict[str, Any]] = []

    for rank, provider_id in enumerate(order, start=1):
        started_at = _utc_now_iso()
        snapshot_ref: dict[str, Any] | None = None
        try:
            candidate = _collect_candidate(
                provider_id,
                date=date,
                season=season,
                env=environment,
                requester=requester,
                generic_collector=generic_collector,
                sportsgameodds_collector=sportsgameodds_collector,
            )
        except (WNBAPropFeedCollectorNotReadyError,) as exc:
            summary = _attempt_summary(provider_id=provider_id, rank=rank, outcome="not_ready", error_type=type(exc).__name__, detail=str(exc))
            _record_attempt(summary, started_at_utc=started_at, store_path=store_path, env=environment, appender=attempt_appender)
            attempts.append(summary)
            continue
        except (WNBAPropFeedCollectorUpstreamError,) as exc:
            summary = _attempt_summary(provider_id=provider_id, rank=rank, outcome="upstream_error", error_type=type(exc).__name__, detail=str(exc))
            _record_attempt(summary, started_at_utc=started_at, store_path=store_path, env=environment, appender=attempt_appender)
            attempts.append(summary)
            continue
        except (WNBAPropFeedCollectorConfigError, WNBAPropFeedCollectorModelInputError, WNBASportsGameOddsAdapterError, ValueError) as exc:
            summary = _attempt_summary(provider_id=provider_id, rank=rank, outcome="provider_input_error", error_type=type(exc).__name__, detail=str(exc))
            _record_attempt(summary, started_at_utc=started_at, store_path=store_path, env=environment, appender=attempt_appender)
            attempts.append(summary)
            continue
        except Exception as exc:
            summary = _attempt_summary(provider_id=provider_id, rank=rank, outcome="unexpected_collection_error", error_type=type(exc).__name__, detail="provider collection failed unexpectedly")
            _record_attempt(summary, started_at_utc=started_at, store_path=store_path, env=environment, appender=attempt_appender)
            attempts.append(summary)
            continue

        collection = candidate["collection"]
        try:
            snapshot_ref = snapshot_persister(
                provider_id=provider_id,
                collection=collection,
                feed_source=candidate["feed_source"],
                feed_format=candidate["feed_format"],
                odds_format=candidate["odds_format"],
                normalized_input_feed=candidate["raw_feed"],
                adapter=candidate.get("adapter"),
                path=store_path,
                env=environment,
            )
        except WNBAPropFeedStoreError as exc:
            raise WNBAPropFeedFailoverStoreError(f"WNBA Step 5O could not persist successful provider snapshot: {exc}") from exc

        try:
            line_board = line_board_builder(
                candidate["raw_feed"],
                feed_source=candidate["feed_source"],
                feed_format=candidate["feed_format"],
                odds_format=candidate["odds_format"],
                feed_captured_at_utc=candidate["collected_at_utc"],
                date=candidate["date"],
                season=candidate["season"],
                max_market_age_minutes=max_market_age_minutes,
                exclude_stale_quotes=exclude_stale_quotes,
                max_side_pair_skew_seconds=max_side_pair_skew_seconds,
            )
        except WNBAPropLineFeedNotReadyError as exc:
            summary = _attempt_summary(provider_id=provider_id, rank=rank, outcome="market_not_ready", error_type=type(exc).__name__, detail=str(exc), snapshot_id=snapshot_ref["snapshot_id"])
            _record_attempt(summary, started_at_utc=started_at, store_path=store_path, env=environment, appender=attempt_appender)
            attempts.append(summary)
            continue
        except WNBAPropLineFeedUpstreamError as exc:
            summary = _attempt_summary(provider_id=provider_id, rank=rank, outcome="market_upstream_error", error_type=type(exc).__name__, detail=str(exc), snapshot_id=snapshot_ref["snapshot_id"])
            _record_attempt(summary, started_at_utc=started_at, store_path=store_path, env=environment, appender=attempt_appender)
            attempts.append(summary)
            continue
        except (WNBAPropLineFeedModelInputError, ValueError) as exc:
            summary = _attempt_summary(provider_id=provider_id, rank=rank, outcome="market_input_error", error_type=type(exc).__name__, detail=str(exc), snapshot_id=snapshot_ref["snapshot_id"])
            _record_attempt(summary, started_at_utc=started_at, store_path=store_path, env=environment, appender=attempt_appender)
            attempts.append(summary)
            continue

        line_count = int(line_board.get("normalized_line_count") or 0)
        playable_game_count = len((line_board.get("official_slate_reference") or {}).get("playable_game_ids") or [])
        if playable_game_count > 0 and line_count < minimum_normalized_lines:
            summary = _attempt_summary(
                provider_id=provider_id,
                rank=rank,
                outcome="unusable_empty_board",
                detail=f"provider produced {line_count} normalized lines for {playable_game_count} playable games",
                snapshot_id=snapshot_ref["snapshot_id"],
                normalized_line_count=line_count,
                playable_game_count=playable_game_count,
            )
            _record_attempt(summary, started_at_utc=started_at, store_path=store_path, env=environment, appender=attempt_appender)
            attempts.append(summary)
            continue

        outcome = "success_empty_slate" if playable_game_count == 0 else "success"
        summary = _attempt_summary(
            provider_id=provider_id,
            rank=rank,
            outcome=outcome,
            snapshot_id=snapshot_ref["snapshot_id"],
            normalized_line_count=line_count,
            playable_game_count=playable_game_count,
        )
        _record_attempt(summary, started_at_utc=started_at, store_path=store_path, env=environment, appender=attempt_appender)
        attempts.append(summary)
        fingerprint = _hash(
            {
                "provider_order": order,
                "selected_provider_id": provider_id,
                "snapshot_fingerprint_sha256": snapshot_ref["snapshot_fingerprint_sha256"],
                "line_board_fingerprint_sha256": line_board.get("line_board_fingerprint_sha256"),
                "attempts": attempts,
            }
        )
        return {
            "source": MODEL_SOURCE,
            "data_type": "wnba_prop_feed_failover_line_board",
            "schema_version": SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "model_family": MODEL_FAMILY,
            "generated_at_utc": _utc_now_iso(),
            "failover_id": f"wnba-5o-failover-{fingerprint[:20]}",
            "failover_fingerprint_sha256": fingerprint,
            "provider_order": order,
            "selected_provider_id": provider_id,
            "selected_failover_rank": rank,
            "attempt_count": len(attempts),
            "attempts": attempts,
            "snapshot_reference": snapshot_ref,
            "collection_reference": {
                "collection_id": collection.get("collection_id"),
                "collection_fingerprint_sha256": collection.get("collection_fingerprint_sha256"),
                "collected_at_utc": collection.get("collected_at_utc"),
                "feed_source": candidate["feed_source"],
                "feed_format": candidate["feed_format"],
                "odds_format": candidate["odds_format"],
            },
            "line_board": line_board,
            "semantics": {
                "successful_network_collections_are_persisted_before_market_acceptance": True,
                "frozen_step_5m_is_market_integrity_authority": True,
                "stale_or_unusable_provider_output_can_trigger_failover": True,
                "empty_slate_is_not_treated_as_provider_failure": True,
                "market_data_cannot_modify_model_probability": True,
            },
        }

    fingerprint = _hash({"provider_order": order, "attempts": attempts})
    detail = "; ".join(f"{row['provider_id']}={row['outcome']}" for row in attempts)
    raise WNBAPropFeedFailoverNotReadyError(
        f"WNBA Step 5O exhausted all configured providers ({fingerprint[:12]}): {detail}"
    )


def build_failover_daily_top_five(
    provider_ids: Sequence[str] | None = None,
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    exclude_stale_quotes: bool = True,
    max_side_pair_skew_seconds: int = DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
    minimum_normalized_lines: int = DEFAULT_MINIMUM_NORMALIZED_LINES,
    require_persistent_store: bool = True,
    env: Mapping[str, str] | None = None,
    store_path: str | Path | None = None,
    requester: Callable[..., Any] | None = None,
    failover_builder: Callable[..., dict[str, Any]] = collect_failover_line_board,
    daily_builder: Callable[..., dict[str, Any]] = build_daily_slate_top_five,
    **daily_kwargs: Any,
) -> dict[str, Any]:
    failover = failover_builder(
        provider_ids,
        date=date,
        season=season,
        max_market_age_minutes=max_market_age_minutes,
        exclude_stale_quotes=exclude_stale_quotes,
        max_side_pair_skew_seconds=max_side_pair_skew_seconds,
        minimum_normalized_lines=minimum_normalized_lines,
        require_persistent_store=require_persistent_store,
        env=env,
        store_path=store_path,
        requester=requester,
    )
    line_board = failover["line_board"]
    prop_lines = deepcopy(line_board.get("step_5l_prop_lines") or [])
    if prop_lines:
        daily = daily_builder(
            prop_lines,
            date=line_board.get("date"),
            season=line_board.get("season", season),
            max_market_age_minutes=max_market_age_minutes,
            exclude_stale_quotes=exclude_stale_quotes,
            **daily_kwargs,
        )
        probability_board = deepcopy(daily.get("probability_board") or [])
        value_board = deepcopy(daily.get("value_board") or [])
    else:
        daily = None
        probability_board = []
        value_board = []
    fingerprint = _hash(
        {
            "failover_fingerprint_sha256": failover["failover_fingerprint_sha256"],
            "daily_board_fingerprint_sha256": daily.get("daily_board_fingerprint_sha256") if daily else None,
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_feed_failover_daily_top_five",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "pipeline_id": f"wnba-5o-top5-{fingerprint[:20]}",
        "pipeline_fingerprint_sha256": fingerprint,
        "failover_reference": {
            "failover_id": failover["failover_id"],
            "failover_fingerprint_sha256": failover["failover_fingerprint_sha256"],
            "selected_provider_id": failover["selected_provider_id"],
            "selected_failover_rank": failover["selected_failover_rank"],
            "snapshot_reference": failover["snapshot_reference"],
        },
        "failover": failover,
        "step_5l_daily_top_five": daily,
        "probability_board_count": len(probability_board),
        "value_board_count": len(value_board),
        "probability_board": probability_board,
        "value_board": value_board,
        "semantics": {
            "provider_failover_finishes_before_step_5l": True,
            "frozen_step_5l_builds_daily_candidates": True,
            "frozen_step_5k_remains_primary_probability_rank_authority": True,
            "market_data_cannot_move_primary_probability_rank": True,
        },
    }


def get_failover_health(
    provider_id: str | None = None,
    *,
    attempts_per_provider: int = 20,
    env: Mapping[str, str] | None = None,
    store_path: str | Path | None = None,
) -> dict[str, Any]:
    health = get_provider_health(
        provider_id,
        attempts_per_provider=attempts_per_provider,
        path=store_path,
        env=env,
    )
    status = get_store_status(path=store_path, env=env)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_feed_failover_health",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "provider_health": health,
        "store_status": status,
    }
