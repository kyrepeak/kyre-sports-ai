"""Step 7D exact-ID FanDuel Game Total context for MLB pages.

This module is pure and read-only. It validates the existing Kyre Sports API
MLB live-odds response and exposes the canonical FanDuel Total Runs market to
an existing page/game row by exact official MLB game ID. It does not create a
Game Total prediction engine and never changes projection, simulation,
probability, ranking, selection, history adjustment, fair odds, or production
exposure.

Bad, incomplete, duplicate, or stale evidence is never fabricated. Callers
retain their pre-existing presentation whenever exact API evidence is
unavailable.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any, Mapping

DATA_TYPE = "mlb_step7d_total_api_integration_v1"
RESULT_DATA_TYPE = "mlb_step7d_total_api_result_context_v1"
SCHEMA_VERSION = 1
EXPECTED_API_DATA_TYPE = "mlb_live_odds_api_response_v1"
EXPECTED_API_SCHEMA_VERSION = 1
EXPECTED_SOURCE = "FanDuel"
MATCH_METHOD = "official_mlb_game_id_exact"
API_CONNECTED = "API_GAME_TOTAL_CONTEXT_AVAILABLE"
FALLBACK = "GAME_TOTAL_API_CONTEXT_UNAVAILABLE"
DEFAULT_MAX_SNAPSHOT_AGE_SECONDS = 60.0


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if math.isfinite(parsed) else None


def _positive_total_line(value: Any) -> float | None:
    number = _finite_number(value)
    return number if number is not None and number > 0 else None


def _american_odds(value: Any) -> int | None:
    number = _finite_number(value)
    if number is None or number == 0 or not float(number).is_integer():
        return None
    return int(number)


def _utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_total_api_state(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate one API payload and retain only exact, usable Total Runs contexts."""
    body = deepcopy(_mapping(payload))
    failures: list[str] = []
    unusable_game_ids: list[int] = []
    contexts: dict[int, dict[str, Any]] = {}

    if body.get("data_type") != EXPECTED_API_DATA_TYPE:
        failures.append("unexpected_api_data_type")
    if body.get("schema_version") != EXPECTED_API_SCHEMA_VERSION:
        failures.append("unexpected_api_schema_version")
    if body.get("source") != EXPECTED_SOURCE:
        failures.append("unexpected_api_source")
    if _utc_datetime(body.get("collected_at_utc")) is None:
        failures.append("invalid_or_missing_collected_at_utc")

    games = body.get("games")
    if not isinstance(games, list):
        failures.append("games_not_list")
        games = []

    seen: set[int] = set()
    for game in games:
        row = _mapping(game)
        game_id = _positive_int(row.get("official_game_id"))
        if game_id is None:
            failures.append("invalid_official_game_id")
            continue
        if game_id in seen:
            failures.append("duplicate_official_game_id")
            continue
        seen.add(game_id)

        if row.get("sportsbook") != EXPECTED_SOURCE:
            unusable_game_ids.append(game_id)
            continue

        markets = _mapping(row.get("markets"))
        total = _mapping(markets.get("total"))
        line = _positive_total_line(total.get("line"))
        over_odds = _american_odds(total.get("over_odds"))
        under_odds = _american_odds(total.get("under_odds"))
        if None in (line, over_odds, under_odds):
            unusable_game_ids.append(game_id)
            continue

        contexts[game_id] = {
            "official_game_id": game_id,
            "sportsbook": EXPECTED_SOURCE,
            "scheduled_start_utc": row.get("scheduled_start_utc"),
            "source_event_id": row.get("source_event_id"),
            "away_team": _mapping(row.get("away_team")),
            "home_team": _mapping(row.get("home_team")),
            "line": line,
            "over_odds": over_odds,
            "under_odds": under_odds,
            "match_method": MATCH_METHOD,
            "fallback_matching_used": False,
        }

    if not games:
        failures.append("empty_api_slate")
    if not contexts:
        failures.append("no_usable_game_total_contexts")

    active = not failures
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "integration_status": API_CONNECTED if active else FALLBACK,
        "api_integration_active": active,
        "source": EXPECTED_SOURCE,
        "api_data_type": body.get("data_type"),
        "collected_at_utc": body.get("collected_at_utc"),
        "match_method": MATCH_METHOD,
        "fallback_matching_used": False,
        "api_game_count": len(games),
        "usable_game_total_game_count": len(contexts),
        "unusable_game_ids": sorted(set(unusable_game_ids)),
        "contexts_by_game_id": contexts,
        "snapshot_age_seconds": None,
        "feed_fresh": None,
        "max_snapshot_age_seconds": DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
        "preexisting_presentation_preserved": True,
        "model_math_impact": False,
        "simulation_impact": False,
        "probability_impact": False,
        "history_adjustment_impact": False,
        "ranking_impact": False,
        "selection_impact": False,
        "fair_odds_impact": False,
        "sportsbook_price_model_input": False,
        "production_exposure_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
        "failures": failures,
    }


def enforce_total_api_freshness(
    api_state: Mapping[str, Any] | None,
    *,
    as_of_utc: datetime | str | None = None,
    max_age_seconds: float = DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
) -> dict[str, Any]:
    """Fail the display claim closed when the API snapshot is stale or unparseable."""
    state = deepcopy(_mapping(api_state))
    failures = list(state.get("failures") or [])

    max_age = _finite_number(max_age_seconds)
    if max_age is None or max_age < 0:
        raise ValueError("max_age_seconds must be a finite non-negative number")

    collected = _utc_datetime(state.get("collected_at_utc"))
    as_of = _utc_datetime(as_of_utc) if as_of_utc is not None else datetime.now(timezone.utc)
    if as_of is None:
        raise ValueError("as_of_utc must be a parseable datetime")

    age: float | None = None
    fresh = False
    if collected is None:
        if "invalid_or_missing_collected_at_utc" not in failures:
            failures.append("invalid_or_missing_collected_at_utc")
    else:
        age = max(0.0, (as_of - collected).total_seconds())
        fresh = age <= max_age
        if not fresh:
            failures.append("api_snapshot_stale")

    if failures:
        state["integration_status"] = FALLBACK
        state["api_integration_active"] = False
    state["snapshot_age_seconds"] = age
    state["feed_fresh"] = fresh and not failures
    state["max_snapshot_age_seconds"] = max_age
    state["failures"] = failures
    state["preexisting_presentation_preserved"] = True
    return state


def total_api_context_for_result(
    result: Mapping[str, Any] | None,
    api_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Map one existing game/result row to its exact live FanDuel Total Runs market."""
    row = deepcopy(_mapping(result))
    state = deepcopy(_mapping(api_state))
    if state.get("api_integration_active") is not True:
        return None
    if state.get("feed_fresh") is not True:
        return None
    if state.get("match_method") != MATCH_METHOD or state.get("fallback_matching_used") is not False:
        return None

    game_id = _positive_int(row.get("game_pk"))
    if game_id is None:
        return None

    contexts = state.get("contexts_by_game_id")
    if not isinstance(contexts, Mapping):
        return None
    context = _mapping(contexts.get(game_id))
    if _positive_int(context.get("official_game_id")) != game_id:
        return None

    live_line = _positive_total_line(context.get("line"))
    over_odds = _american_odds(context.get("over_odds"))
    under_odds = _american_odds(context.get("under_odds"))
    if None in (live_line, over_odds, under_odds):
        return None

    return {
        "data_type": RESULT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "official_game_id": game_id,
        "source": EXPECTED_SOURCE,
        "match_method": MATCH_METHOD,
        "fallback_matching_used": False,
        "live_fanduel_total_line": live_line,
        "live_fanduel_over_odds": over_odds,
        "live_fanduel_under_odds": under_odds,
        "collected_at_utc": state.get("collected_at_utc"),
        "snapshot_age_seconds": state.get("snapshot_age_seconds"),
        "feed_fresh": state.get("feed_fresh"),
        "display_only": True,
        "model_math_impact": False,
        "simulation_impact": False,
        "probability_impact": False,
        "history_adjustment_impact": False,
        "ranking_impact": False,
        "selection_impact": False,
        "fair_odds_impact": False,
        "sportsbook_price_model_input": False,
        "production_exposure_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
    }


__all__ = [
    "API_CONNECTED",
    "DATA_TYPE",
    "DEFAULT_MAX_SNAPSHOT_AGE_SECONDS",
    "FALLBACK",
    "MATCH_METHOD",
    "RESULT_DATA_TYPE",
    "SCHEMA_VERSION",
    "build_total_api_state",
    "enforce_total_api_freshness",
    "total_api_context_for_result",
]
