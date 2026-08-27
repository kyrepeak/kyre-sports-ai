"""WNBA Step 5L: verified daily-slate candidate generation and automatic Top-5 assembly.

Step 5L orchestrates already-frozen WNBA layers. It verifies the official daily
slate and current roster, maps caller-supplied real prop lines to the correct
scheduled game, generates Step 5F probabilities, optionally adds Step 5H
multi-book market context, optionally attaches stored Step 5I/5J calibration,
and finally delegates ranking/qualification to frozen Step 5K.

Step 5L never invents sportsbook prop lines. A real player/stat/line input is
required for every threshold candidate. Market quotes are optional and can
never alter the primary Step 5K probability board.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
from typing import Any, Callable

from sports_api.database.wnba_pregame_prediction_store import (
    WNBAPregameStoreError,
    WNBAPregameStoreNotReadyError,
    evaluate_stored_calibration,
)
from sports_api.wnba_historical_backtest_calibration import (
    MODEL_VERSION as BACKTEST_CALIBRATION_MODEL_VERSION,
)
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_model_input_readiness import DEFAULT_MAX_SNAPSHOT_AGE_MINUTES
from sports_api.wnba_multi_sportsbook_market_consensus import (
    DEFAULT_MAX_MARKET_AGE_MINUTES,
    MIN_SPORTSBOOK_QUOTES,
    WNBAMultiSportsbookModelInputError,
    WNBAMultiSportsbookNotReadyError,
    WNBAMultiSportsbookUpstreamError,
    build_multi_sportsbook_market_consensus,
)
from sports_api.wnba_player_prop_top_five_board import (
    DEFAULT_MAXIMUM_SCENARIO_SPAN_PERCENTAGE_POINTS,
    DEFAULT_MINIMUM_BASE_PROBABILITY,
    DEFAULT_MINIMUM_WORST_SCENARIO_PROBABILITY,
    DEFAULT_TOP_N,
    MODEL_VERSION as TOP_FIVE_MODEL_VERSION,
    build_player_prop_top_five_board,
)
from sports_api.wnba_prop_threshold_probability import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_COUNT,
    MAX_PROP_LINE,
    MODEL_VERSION as THRESHOLD_MODEL_VERSION,
    SUPPORTED_STATS,
    WNBAPropThresholdModelInputError,
    WNBAPropThresholdNotFoundError,
    WNBAPropThresholdNotReadyError,
    WNBAPropThresholdUpstreamError,
    get_player_game_prop_threshold_probability,
)
from sports_api.wnba_rosters import (
    WNBAStatsUpstreamError,
    get_current_players_dataset,
)
from sports_api.wnba_schedule import (
    ARIZONA_TZ,
    WNBAScheduleUpstreamError,
    verify_daily_slate_dataset,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5L daily-slate candidate generation and Top-5 assembly"
MODEL_VERSION = "wnba_step_5l_daily_slate_top_five_v1"
SCHEMA_VERSION = "wnba_step_5l_daily_slate_top_five_v1"
MODEL_FAMILY = "verified_slate_orchestration_over_frozen_step_5f_5h_5i_5j_5k"

MIN_PROP_LINES = 1
MAX_PROP_LINES = 500


class WNBADailySlateTopFiveNotReadyError(RuntimeError):
    pass


class WNBADailySlateTopFiveUpstreamError(RuntimeError):
    pass


class WNBADailySlateTopFiveModelInputError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"WNBA Step 5L {label} must be a positive integer.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"WNBA Step 5L {label} must be a positive integer.") from exc
    if number <= 0:
        raise ValueError(f"WNBA Step 5L {label} must be a positive integer.")
    return number


def _line(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"WNBA Step 5L prop line must be a number from 0 through {MAX_PROP_LINE:g}.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"WNBA Step 5L prop line must be a number from 0 through {MAX_PROP_LINE:g}."
        ) from exc
    if not isfinite(number) or not 0.0 <= number <= MAX_PROP_LINE:
        raise ValueError(f"WNBA Step 5L prop line must be a number from 0 through {MAX_PROP_LINE:g}.")
    return round(number, 6)


def _stat(value: Any) -> str:
    text = " ".join(str(value).strip().casefold().split())
    aliases = {
        "points": "points", "point": "points", "pts": "points",
        "rebounds": "rebounds", "rebound": "rebounds", "reb": "rebounds", "rebs": "rebounds",
        "assists": "assists", "assist": "assists", "ast": "assists", "asts": "assists",
        "pra": "pra", "points+rebounds+assists": "pra", "points rebounds assists": "pra",
    }
    result = aliases.get(text)
    if result not in SUPPORTED_STATS:
        raise ValueError(
            "Unsupported WNBA Step 5L prop stat "
            f"{value!r}. Allowed canonical values: {', '.join(SUPPORTED_STATS)}."
        )
    return result


def _bool(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"WNBA Step 5L {label} must be boolean.")
    return value


def _target_date(value: str | None) -> str:
    if value is None:
        return datetime.now(ARIZONA_TZ).date().isoformat()
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("WNBA Step 5L date must use YYYY-MM-DD format.") from exc
    return text


def _normalize_prop_lines(prop_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(prop_lines, list) or not MIN_PROP_LINES <= len(prop_lines) <= MAX_PROP_LINES:
        raise ValueError(
            f"WNBA Step 5L prop_lines must contain {MIN_PROP_LINES} through {MAX_PROP_LINES} records."
        )
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[int, str, float]] = set()
    for index, row in enumerate(prop_lines):
        if not isinstance(row, dict):
            raise WNBADailySlateTopFiveModelInputError(
                f"WNBA Step 5L prop_lines[{index}] must be an object."
            )
        player_id = _positive_int(row.get("player_id"), f"prop_lines[{index}].player_id")
        stat = _stat(row.get("stat"))
        line = _line(row.get("line"))
        key = (player_id, stat, line)
        if key in seen:
            raise WNBADailySlateTopFiveModelInputError(
                "Duplicate WNBA Step 5L player/stat/line input is not allowed."
            )
        seen.add(key)
        quotes = row.get("sportsbook_quotes")
        if quotes is not None and not isinstance(quotes, list):
            raise WNBADailySlateTopFiveModelInputError(
                f"WNBA Step 5L prop_lines[{index}].sportsbook_quotes must be a list when supplied."
            )
        normalized.append(
            {
                "input_index": index,
                "player_id": player_id,
                "stat": stat,
                "line": line,
                "sportsbook_quotes": deepcopy(quotes) if quotes is not None else None,
            }
        )
    return normalized


def _validate_slate(slate: dict[str, Any], *, target_date: str, season: int, require_integrity: bool) -> list[dict[str, Any]]:
    if not isinstance(slate, dict):
        raise WNBADailySlateTopFiveUpstreamError("Step 5L official slate payload is malformed.")
    if slate.get("date") != target_date or int(slate.get("season", -1)) != season:
        raise WNBADailySlateTopFiveUpstreamError("Step 5L official slate date/season identity mismatch.")
    summary = slate.get("slate")
    games = slate.get("games")
    if not isinstance(summary, dict) or not isinstance(games, list):
        raise WNBADailySlateTopFiveUpstreamError("Step 5L official slate verification fields are missing.")
    if require_integrity and summary.get("slate_integrity_pass") is not True:
        reasons = summary.get("blocking_reasons") or []
        raise WNBADailySlateTopFiveNotReadyError(
            "Step 5L requires verified daily-slate integrity; blocking reasons: "
            + (", ".join(map(str, reasons)) if reasons else "unknown")
        )
    playable = [
        game for game in games
        if isinstance(game, dict)
        and isinstance(game.get("verification"), dict)
        and game["verification"].get("playable_pregame") is True
    ]
    return playable


def _roster_index(roster: dict[str, Any], *, season: int) -> dict[int, dict[str, Any]]:
    if not isinstance(roster, dict) or int(roster.get("season", -1)) != season:
        raise WNBADailySlateTopFiveUpstreamError("Step 5L current-roster payload is malformed or wrong season.")
    players = roster.get("players")
    if not isinstance(players, list):
        raise WNBADailySlateTopFiveUpstreamError("Step 5L current-roster player list is missing.")
    index: dict[int, dict[str, Any]] = {}
    for row in players:
        if not isinstance(row, dict):
            continue
        try:
            player_id = int(row.get("player_id"))
        except (TypeError, ValueError):
            continue
        if player_id <= 0:
            continue
        if player_id in index:
            raise WNBADailySlateTopFiveUpstreamError(
                f"Step 5L current roster contains duplicate player_id {player_id}."
            )
        index[player_id] = row
    return index


def _team_game_index(playable_games: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for game in playable_games:
        game_id = _clean(game.get("game_id"))
        if not game_id:
            continue
        for side in ("away", "home"):
            team = game.get(side)
            team_key = _clean(team.get("team_key")) if isinstance(team, dict) else None
            if team_key:
                result.setdefault(team_key, []).append(game)
    return result


def _game_context(game: dict[str, Any] | None) -> dict[str, Any] | None:
    if game is None:
        return None
    return {
        "game_id": game.get("game_id"),
        "game_datetime_utc": game.get("game_datetime_utc"),
        "game_datetime_eastern": game.get("game_datetime_eastern"),
        "status": deepcopy(game.get("status")),
        "venue": deepcopy(game.get("venue")),
        "away_team_key": (game.get("away") or {}).get("team_key"),
        "home_team_key": (game.get("home") or {}).get("team_key"),
    }


def _empty_line_audit(line: dict[str, Any]) -> dict[str, Any]:
    quotes = line.get("sportsbook_quotes")
    return {
        "input_index": line["input_index"],
        "player_id": line["player_id"],
        "stat": line["stat"],
        "line": line["line"],
        "sportsbook_quote_count": len(quotes) if isinstance(quotes, list) else 0,
        "player": None,
        "game": None,
        "candidate_status": "pending",
        "exclusion_reason": None,
        "threshold_status": "not_attempted",
        "threshold_error": None,
        "market_status": "not_attempted",
        "market_error": None,
        "step_5f_probability_id": None,
        "step_5f_probability_fingerprint_sha256": None,
        "step_5h_market_consensus_id": None,
        "step_5h_market_consensus_fingerprint_sha256": None,
    }


def _calibration_context(
    include_stored_calibration: bool,
    getter: Callable[..., dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if not include_stored_calibration:
        return None, {
            "requested": False,
            "available": False,
            "status": "disabled",
            "reason": "include_stored_calibration_false",
        }
    try:
        report = getter(
            probability_model_version=THRESHOLD_MODEL_VERSION,
            require_single_probability_model_version=True,
        )
        return report, {
            "requested": True,
            "available": True,
            "status": "loaded",
            "reason": None,
            "calibration_report_id": report.get("calibration_report_id"),
            "calibration_report_fingerprint_sha256": report.get(
                "calibration_report_fingerprint_sha256"
            ),
            "observation_count": report.get("observation_count"),
        }
    except WNBAPregameStoreNotReadyError as exc:
        return None, {
            "requested": True,
            "available": False,
            "status": "not_ready",
            "reason": str(exc),
        }
    except WNBAPregameStoreError as exc:
        return None, {
            "requested": True,
            "available": False,
            "status": "store_error",
            "reason": str(exc),
        }


def build_daily_slate_top_five(
    prop_lines: list[dict[str, Any]],
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
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
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    exclude_stale_quotes: bool = True,
    include_stored_calibration: bool = True,
    require_slate_integrity: bool = True,
    top_n: int = DEFAULT_TOP_N,
    minimum_base_probability: float = DEFAULT_MINIMUM_BASE_PROBABILITY,
    minimum_worst_scenario_probability: float = DEFAULT_MINIMUM_WORST_SCENARIO_PROBABILITY,
    maximum_scenario_span_percentage_points: float = DEFAULT_MAXIMUM_SCENARIO_SPAN_PERCENTAGE_POINTS,
    require_same_favored_side_all_scenarios: bool = True,
    require_strict_numerical_readiness: bool = True,
    require_mature_calibration: bool = False,
    one_line_per_player_stat: bool = True,
    slate_getter: Callable[..., dict[str, Any]] = verify_daily_slate_dataset,
    roster_getter: Callable[..., dict[str, Any]] = get_current_players_dataset,
    threshold_getter: Callable[..., dict[str, Any]] = get_player_game_prop_threshold_probability,
    market_builder: Callable[..., dict[str, Any]] = build_multi_sportsbook_market_consensus,
    calibration_getter: Callable[..., dict[str, Any]] = evaluate_stored_calibration,
    board_builder: Callable[..., dict[str, Any]] = build_player_prop_top_five_board,
) -> dict[str, Any]:
    normalized_lines = _normalize_prop_lines(prop_lines)
    target_date = _target_date(date)
    require_slate_integrity = _bool(require_slate_integrity, "require_slate_integrity")
    include_stored_calibration = _bool(include_stored_calibration, "include_stored_calibration")

    try:
        slate = slate_getter(target_date, season)
    except ValueError as exc:
        raise WNBADailySlateTopFiveModelInputError(str(exc)) from exc
    except WNBAScheduleUpstreamError as exc:
        raise WNBADailySlateTopFiveUpstreamError(str(exc)) from exc
    playable_games = _validate_slate(
        slate,
        target_date=target_date,
        season=season,
        require_integrity=require_slate_integrity,
    )

    try:
        roster = roster_getter(season, current_roster_only=True)
    except ValueError as exc:
        raise WNBADailySlateTopFiveModelInputError(str(exc)) from exc
    except WNBAStatsUpstreamError as exc:
        raise WNBADailySlateTopFiveUpstreamError(str(exc)) from exc
    players = _roster_index(roster, season=season)
    team_games = _team_game_index(playable_games)

    calibration_report, calibration_status = _calibration_context(
        include_stored_calibration,
        calibration_getter,
    )

    generated_candidates: list[dict[str, Any]] = []
    line_audit: list[dict[str, Any]] = []
    threshold_success_count = 0
    market_success_count = 0

    for line_input in normalized_lines:
        audit = _empty_line_audit(line_input)
        player = players.get(line_input["player_id"])
        if player is None:
            audit["candidate_status"] = "excluded"
            audit["exclusion_reason"] = "player_not_on_current_official_roster"
            line_audit.append(audit)
            continue
        team_key = _clean(player.get("team_key"))
        audit["player"] = {
            "player_id": line_input["player_id"],
            "full_name": player.get("full_name"),
            "team_key": team_key,
            "is_current_roster": player.get("is_current_roster"),
        }
        if not team_key:
            audit["candidate_status"] = "excluded"
            audit["exclusion_reason"] = "current_roster_team_identity_missing"
            line_audit.append(audit)
            continue

        games = team_games.get(team_key, [])
        if not games:
            audit["candidate_status"] = "excluded"
            audit["exclusion_reason"] = "player_team_not_on_playable_pregame_slate"
            line_audit.append(audit)
            continue
        if len(games) > 1:
            audit["candidate_status"] = "excluded"
            audit["exclusion_reason"] = "player_team_maps_to_multiple_playable_games"
            line_audit.append(audit)
            continue
        game = games[0]
        game_id = _clean(game.get("game_id"))
        audit["game"] = _game_context(game)
        if not game_id:
            audit["candidate_status"] = "excluded"
            audit["exclusion_reason"] = "playable_game_id_missing"
            line_audit.append(audit)
            continue

        try:
            threshold = threshold_getter(
                line_input["player_id"],
                game_id,
                season,
                stat=line_input["stat"],
                line=line_input["line"],
                season_type=season_type,
                last_n_games=last_n_games,
                distribution_last_n_games=distribution_last_n_games,
                simulation_count=simulation_count,
                batch_size=batch_size,
                random_seed=random_seed,
                require_current_availability=require_current_availability,
                max_snapshot_age_minutes=max_snapshot_age_minutes,
                require_convergence=require_convergence,
            )
            audit["threshold_status"] = "generated"
            audit["step_5f_probability_id"] = threshold.get("probability_id")
            audit["step_5f_probability_fingerprint_sha256"] = threshold.get(
                "probability_fingerprint_sha256"
            )
            threshold_success_count += 1
        except WNBAPropThresholdNotFoundError as exc:
            audit["candidate_status"] = "excluded"
            audit["exclusion_reason"] = "step_5f_not_found"
            audit["threshold_status"] = "not_found"
            audit["threshold_error"] = str(exc)
            line_audit.append(audit)
            continue
        except WNBAPropThresholdNotReadyError as exc:
            audit["candidate_status"] = "excluded"
            audit["exclusion_reason"] = "step_5f_not_ready"
            audit["threshold_status"] = "not_ready"
            audit["threshold_error"] = str(exc)
            line_audit.append(audit)
            continue
        except WNBAPropThresholdModelInputError as exc:
            audit["candidate_status"] = "excluded"
            audit["exclusion_reason"] = "step_5f_model_input_error"
            audit["threshold_status"] = "model_input_error"
            audit["threshold_error"] = str(exc)
            line_audit.append(audit)
            continue
        except WNBAPropThresholdUpstreamError as exc:
            audit["candidate_status"] = "excluded"
            audit["exclusion_reason"] = "step_5f_upstream_error"
            audit["threshold_status"] = "upstream_error"
            audit["threshold_error"] = str(exc)
            line_audit.append(audit)
            continue

        candidate: dict[str, Any] = {
            "threshold": threshold,
            "player_name": player.get("full_name"),
        }
        quotes = line_input.get("sportsbook_quotes")
        if quotes is None or len(quotes) == 0:
            audit["market_status"] = "not_supplied"
        elif len(quotes) < MIN_SPORTSBOOK_QUOTES:
            audit["market_status"] = "insufficient_quotes"
            audit["market_error"] = (
                f"Step 5H requires at least {MIN_SPORTSBOOK_QUOTES} distinct sportsbook quotes."
            )
        else:
            try:
                market = market_builder(
                    threshold,
                    quotes,
                    minimum_required_ev=minimum_required_ev,
                    max_market_age_minutes=max_market_age_minutes,
                    exclude_stale_quotes=exclude_stale_quotes,
                )
                candidate["market_consensus"] = market
                audit["market_status"] = "generated"
                audit["step_5h_market_consensus_id"] = market.get("market_consensus_id")
                audit["step_5h_market_consensus_fingerprint_sha256"] = market.get(
                    "market_consensus_fingerprint_sha256"
                )
                market_success_count += 1
            except WNBAMultiSportsbookNotReadyError as exc:
                audit["market_status"] = "not_ready"
                audit["market_error"] = str(exc)
            except WNBAMultiSportsbookModelInputError as exc:
                audit["market_status"] = "model_input_error"
                audit["market_error"] = str(exc)
            except WNBAMultiSportsbookUpstreamError as exc:
                audit["market_status"] = "upstream_error"
                audit["market_error"] = str(exc)

        audit["candidate_status"] = "generated"
        generated_candidates.append(candidate)
        line_audit.append(audit)

    if generated_candidates:
        board = board_builder(
            generated_candidates,
            calibration_report=calibration_report,
            top_n=top_n,
            minimum_base_probability=minimum_base_probability,
            minimum_worst_scenario_probability=minimum_worst_scenario_probability,
            maximum_scenario_span_percentage_points=maximum_scenario_span_percentage_points,
            require_same_favored_side_all_scenarios=require_same_favored_side_all_scenarios,
            require_strict_numerical_readiness=require_strict_numerical_readiness,
            require_mature_calibration=require_mature_calibration,
            one_line_per_player_stat=one_line_per_player_stat,
        )
        probability_board = deepcopy(board.get("probability_board") or [])
        value_board = deepcopy(board.get("value_board") or [])
        all_candidates = deepcopy(board.get("all_candidates") or [])
        board_reference = {
            "model_version": board.get("model_version"),
            "board_id": board.get("board_id"),
            "board_fingerprint_sha256": board.get("board_fingerprint_sha256"),
        }
    else:
        board = None
        probability_board = []
        value_board = []
        all_candidates = []
        board_reference = None

    config = {
        "model_version": MODEL_VERSION,
        "season": season,
        "season_type": season_type,
        "date": target_date,
        "last_n_games": last_n_games,
        "distribution_last_n_games": distribution_last_n_games,
        "simulation_count": simulation_count,
        "batch_size": batch_size,
        "random_seed": random_seed,
        "require_current_availability": require_current_availability,
        "max_snapshot_age_minutes": max_snapshot_age_minutes,
        "require_convergence": require_convergence,
        "minimum_required_ev": minimum_required_ev,
        "max_market_age_minutes": max_market_age_minutes,
        "exclude_stale_quotes": exclude_stale_quotes,
        "include_stored_calibration": include_stored_calibration,
        "require_slate_integrity": require_slate_integrity,
        "top_n": top_n,
        "minimum_base_probability": minimum_base_probability,
        "minimum_worst_scenario_probability": minimum_worst_scenario_probability,
        "maximum_scenario_span_percentage_points": maximum_scenario_span_percentage_points,
        "require_same_favored_side_all_scenarios": require_same_favored_side_all_scenarios,
        "require_strict_numerical_readiness": require_strict_numerical_readiness,
        "require_mature_calibration": require_mature_calibration,
        "one_line_per_player_stat": one_line_per_player_stat,
    }
    fingerprint_payload = {
        "normalized_prop_lines": normalized_lines,
        "playable_game_ids": sorted(
            str(game.get("game_id")) for game in playable_games if game.get("game_id")
        ),
        "generated_step_5f_fingerprints": sorted(
            row["step_5f_probability_fingerprint_sha256"]
            for row in line_audit
            if row.get("step_5f_probability_fingerprint_sha256")
        ),
        "generated_step_5h_fingerprints": sorted(
            row["step_5h_market_consensus_fingerprint_sha256"]
            for row in line_audit
            if row.get("step_5h_market_consensus_fingerprint_sha256")
        ),
        "calibration_fingerprint": (
            calibration_report.get("calibration_report_fingerprint_sha256")
            if calibration_report is not None else None
        ),
        "step_5k_board_fingerprint": (
            board.get("board_fingerprint_sha256") if board is not None else None
        ),
        "line_audit": line_audit,
        "model_config": config,
    }
    fingerprint = _hash(fingerprint_payload)
    excluded_count = sum(row["candidate_status"] == "excluded" for row in line_audit)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_verified_daily_slate_automatic_player_prop_top_five_board",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _now_iso(),
        "daily_board_id": f"wnba-5l-{target_date}-{fingerprint[:20]}",
        "daily_board_fingerprint_sha256": fingerprint,
        "season": season,
        "season_type": season_type,
        "date": target_date,
        "slate_verification": {
            "slate_integrity_pass": (slate.get("slate") or {}).get("slate_integrity_pass"),
            "blocking_reasons": deepcopy((slate.get("slate") or {}).get("blocking_reasons")),
            "official_game_count": len(slate.get("games") or []),
            "playable_pregame_game_count": len(playable_games),
            "playable_game_ids": [game.get("game_id") for game in playable_games],
            "source_retrieved_at_utc": slate.get("source_retrieved_at_utc"),
            "verified_at_utc": slate.get("verified_at_utc"),
        },
        "roster_verification": {
            "current_roster_only": roster.get("current_roster_only"),
            "official_current_player_count": roster.get("player_count"),
            "source_retrieved_at_utc": roster.get("retrieved_at_utc"),
        },
        "calibration_status": calibration_status,
        "input_prop_line_count": len(normalized_lines),
        "generated_candidate_count": len(generated_candidates),
        "excluded_prop_line_count": excluded_count,
        "step_5f_success_count": threshold_success_count,
        "step_5h_market_enriched_candidate_count": market_success_count,
        "probability_board_count": len(probability_board),
        "value_board_count": len(value_board),
        "probability_board": probability_board,
        "value_board": value_board,
        "all_step_5k_candidates": all_candidates,
        "line_generation_audit": line_audit,
        "step_5k_board_reference": board_reference,
        "model_config": config,
        "orchestration_semantics": {
            "official_slate_is_verified_before_candidate_generation": True,
            "current_official_roster_maps_player_to_team": True,
            "game_identity_is_derived_from_verified_slate_not_caller_supplied": True,
            "real_prop_line_is_required_for_every_candidate": True,
            "sportsbook_prop_lines_are_never_invented": True,
            "step_5f_probability_is_generated_before_optional_market_context": True,
            "step_5h_market_failure_does_not_destroy_valid_probability_candidate": True,
            "stored_calibration_is_optional_evidence": True,
            "step_5k_remains_authoritative_for_qualification_and_ranking": True,
        },
        "guardrails": {
            "no_live_or_final_game_is_treated_as_playable_pregame": True,
            "schedule_changed_games_are_not_playable_pregame": True,
            "player_team_game_identity_is_not_invented": True,
            "ambiguous_multiple_game_team_mapping_is_excluded": True,
            "player_not_on_current_roster_is_excluded": True,
            "duplicate_player_stat_line_inputs_rejected": True,
            "market_quotes_are_optional_and_post_probability_only": True,
            "market_price_cannot_move_step_5k_probability_rank": True,
            "historical_calibration_cannot_rescale_current_probability": True,
            "no_forced_five_recommendations": True,
            "no_forced_value_recommendations": True,
        },
        "references": {
            "step_5f_model_version": THRESHOLD_MODEL_VERSION,
            "step_5i_model_version": BACKTEST_CALIBRATION_MODEL_VERSION,
            "step_5k_model_version": TOP_FIVE_MODEL_VERSION,
        },
    }
