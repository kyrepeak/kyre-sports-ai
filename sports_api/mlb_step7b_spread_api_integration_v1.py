"""Step 7B exact-ID FanDuel Run Line context for the MLB Spread page.

This module is pure and read-only. It validates the existing Kyre Sports API
MLB live-odds response and maps its Run Line market to an already-produced
Spread result by exact official MLB game ID plus the model result's away/home
team identity. It never changes projection, simulation, probability, ranking,
selection, history adjustment, fair odds, or production exposure.

Bad or incomplete evidence is never fabricated. A caller can simply retain the
frozen Spread V15.6 presentation for any result that does not have a proven
exact-ID context.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping

DATA_TYPE = "mlb_step7b_spread_api_integration_v1"
RESULT_DATA_TYPE = "mlb_step7b_spread_api_result_context_v1"
SCHEMA_VERSION = 1
EXPECTED_API_DATA_TYPE = "mlb_live_odds_api_response_v1"
EXPECTED_API_SCHEMA_VERSION = 1
EXPECTED_SOURCE = "FanDuel"
MATCH_METHOD = "official_mlb_game_id_exact"
API_CONNECTED = "API_RUN_LINE_CONTEXT_AVAILABLE"
FALLBACK = "FROZEN_SPREAD_PRESENTATION_FALLBACK"


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


def _american_odds(value: Any) -> int | None:
    number = _finite_number(value)
    if number is None or number == 0 or not float(number).is_integer():
        return None
    return int(number)


def build_spread_api_state(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate one API payload and retain only exact, usable Run Line contexts."""
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
        run_line = _mapping(markets.get("run_line"))
        away_line = _finite_number(run_line.get("away_line"))
        home_line = _finite_number(run_line.get("home_line"))
        away_odds = _american_odds(run_line.get("away_odds"))
        home_odds = _american_odds(run_line.get("home_odds"))
        if None in (away_line, home_line, away_odds, home_odds):
            unusable_game_ids.append(game_id)
            continue

        contexts[game_id] = {
            "official_game_id": game_id,
            "sportsbook": EXPECTED_SOURCE,
            "scheduled_start_utc": row.get("scheduled_start_utc"),
            "source_event_id": row.get("source_event_id"),
            "away_team": _mapping(row.get("away_team")),
            "home_team": _mapping(row.get("home_team")),
            "away_line": away_line,
            "away_odds": away_odds,
            "home_line": home_line,
            "home_odds": home_odds,
            "match_method": MATCH_METHOD,
            "fallback_matching_used": False,
        }

    if not games:
        failures.append("empty_api_slate")
    if not contexts:
        failures.append("no_usable_run_line_contexts")

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
        "usable_run_line_game_count": len(contexts),
        "unusable_game_ids": sorted(set(unusable_game_ids)),
        "contexts_by_game_id": contexts,
        "frozen_spread_fallback_preserved": True,
        "model_math_impact": False,
        "simulation_impact": False,
        "probability_impact": False,
        "history_adjustment_impact": False,
        "ranking_impact": False,
        "selection_impact": False,
        "fair_odds_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
        "failures": failures,
    }


def spread_api_context_for_result(
    result: Mapping[str, Any] | None,
    api_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Map one existing Spread result to its exact live FanDuel Run Line side."""
    row = deepcopy(_mapping(result))
    state = deepcopy(_mapping(api_state))
    if state.get("api_integration_active") is not True:
        return None
    if state.get("match_method") != MATCH_METHOD or state.get("fallback_matching_used") is not False:
        return None

    game_id = _positive_int(row.get("game_pk"))
    team_id = _positive_int(row.get("team_id"))
    away_id = _positive_int(row.get("away_team_id"))
    home_id = _positive_int(row.get("home_team_id"))
    if None in (game_id, team_id, away_id, home_id):
        return None

    contexts = state.get("contexts_by_game_id")
    if not isinstance(contexts, Mapping):
        return None
    context = _mapping(contexts.get(game_id))
    if _positive_int(context.get("official_game_id")) != game_id:
        return None

    if team_id == away_id:
        side = "away"
    elif team_id == home_id:
        side = "home"
    else:
        return None

    live_line = _finite_number(context.get(f"{side}_line"))
    live_odds = _american_odds(context.get(f"{side}_odds"))
    model_line = _finite_number(row.get("line"))
    if live_line is None or live_odds is None or model_line is None:
        return None

    line_match = abs(live_line - model_line) <= 1e-9
    return {
        "data_type": RESULT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "official_game_id": game_id,
        "source": EXPECTED_SOURCE,
        "match_method": MATCH_METHOD,
        "fallback_matching_used": False,
        "selected_side": side,
        "model_selected_line": model_line,
        "live_fanduel_line": live_line,
        "live_fanduel_odds": live_odds,
        "line_match": line_match,
        "collected_at_utc": state.get("collected_at_utc"),
        "display_only": True,
        "model_math_impact": False,
        "simulation_impact": False,
        "probability_impact": False,
        "history_adjustment_impact": False,
        "ranking_impact": False,
        "selection_impact": False,
        "fair_odds_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
    }


__all__ = [
    "API_CONNECTED",
    "DATA_TYPE",
    "FALLBACK",
    "MATCH_METHOD",
    "RESULT_DATA_TYPE",
    "SCHEMA_VERSION",
    "build_spread_api_state",
    "spread_api_context_for_result",
]
