"""Step 8A exact-identity MLB player-prop API contract.

This module defines the read-only boundary that later Step 8 stages may use to
transport sportsbook player-prop evidence into existing MLB pages. Step 8A does
not collect FanDuel player props, expose a production endpoint, or alter any
projection/model path.

Identity is deliberately strict: one prop is keyed only by exact official MLB
game ID + exact official MLB player ID + canonical market type. Player names are
metadata and are never a matching key. Duplicate exact identities, stale or
unproven snapshots, and structurally invalid payloads fail closed. Invalid
individual prop rows are isolated when the remaining rows are unambiguous.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any, Mapping

DATA_TYPE = "mlb_step8a_player_prop_api_contract_v1"
CONTEXT_DATA_TYPE = "mlb_step8a_player_prop_context_v1"
SCHEMA_VERSION = 1
EXPECTED_API_DATA_TYPE = "mlb_player_prop_api_response_v1"
EXPECTED_API_SCHEMA_VERSION = 1
EXPECTED_SOURCE = "FanDuel"
MATCH_METHOD = "official_mlb_game_id_player_id_market_exact"
API_CONNECTED = "API_PLAYER_PROP_CONTEXT_AVAILABLE"
FALLBACK = "PLAYER_PROP_API_CONTEXT_UNAVAILABLE"
DEFAULT_MAX_SNAPSHOT_AGE_SECONDS = 60.0

PITCHER_STRIKEOUTS = "pitcher_strikeouts"
PLAYER_HITS = "player_hits"
HITS_RUNS_RBI = "hits_runs_rbi"
SUPPORTED_MARKET_TYPES = frozenset({PITCHER_STRIKEOUTS, PLAYER_HITS, HITS_RUNS_RBI})


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


def _positive_line(value: Any) -> float | None:
    parsed = _finite_number(value)
    return parsed if parsed is not None and parsed > 0 else None


def _american_odds(value: Any) -> int | None:
    parsed = _finite_number(value)
    if parsed is None or parsed == 0 or not float(parsed).is_integer():
        return None
    return int(parsed)


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


def _market_type(value: Any) -> str | None:
    market = str(value or "").strip()
    return market if market in SUPPORTED_MARKET_TYPES else None


def _identity_key(game_id: int, player_id: int, market_type: str) -> tuple[int, int, str]:
    return (game_id, player_id, market_type)


def build_player_prop_api_state(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate one future MLB player-prop API payload into exact-ID contexts.

    Expected payload shape::

        {
          "data_type": "mlb_player_prop_api_response_v1",
          "schema_version": 1,
          "source": "FanDuel",
          "collected_at_utc": "...Z",
          "props": [
            {
              "official_game_id": 123,
              "official_player_id": 456,
              "player_name": "Display Name",
              "market_type": "pitcher_strikeouts",
              "line": 5.5,
              "over_odds": -115,
              "under_odds": -105,
              "sportsbook": "FanDuel"
            }
          ]
        }

    Player names are copied only as display metadata. They are never normalized,
    searched, or used to build the identity key.
    """
    body = deepcopy(_mapping(payload))
    failures: list[str] = []
    contexts: dict[tuple[int, int, str], dict[str, Any]] = {}
    unusable_rows: list[dict[str, Any]] = []

    if body.get("data_type") != EXPECTED_API_DATA_TYPE:
        failures.append("unexpected_api_data_type")
    if body.get("schema_version") != EXPECTED_API_SCHEMA_VERSION:
        failures.append("unexpected_api_schema_version")
    if body.get("source") != EXPECTED_SOURCE:
        failures.append("unexpected_api_source")
    if _utc_datetime(body.get("collected_at_utc")) is None:
        failures.append("invalid_or_missing_collected_at_utc")

    props = body.get("props")
    if not isinstance(props, list):
        failures.append("props_not_list")
        props = []

    seen: set[tuple[int, int, str]] = set()
    for index, raw_prop in enumerate(props):
        row = _mapping(raw_prop)
        game_id = _positive_int(row.get("official_game_id"))
        player_id = _positive_int(row.get("official_player_id"))
        market = _market_type(row.get("market_type"))

        if game_id is None or player_id is None or market is None:
            unusable_rows.append({"index": index, "reason": "invalid_exact_identity_or_market"})
            continue

        identity = _identity_key(game_id, player_id, market)
        if identity in seen:
            failures.append("duplicate_exact_prop_identity")
            unusable_rows.append({
                "index": index,
                "reason": "duplicate_exact_prop_identity",
                "official_game_id": game_id,
                "official_player_id": player_id,
                "market_type": market,
            })
            continue
        seen.add(identity)

        sportsbook = str(row.get("sportsbook") or "").strip()
        line = _positive_line(row.get("line"))
        over_odds = _american_odds(row.get("over_odds"))
        under_odds = _american_odds(row.get("under_odds"))
        if sportsbook != EXPECTED_SOURCE or None in (line, over_odds, under_odds):
            unusable_rows.append({
                "index": index,
                "reason": "invalid_or_incomplete_prop_market",
                "official_game_id": game_id,
                "official_player_id": player_id,
                "market_type": market,
            })
            continue

        contexts[identity] = {
            "official_game_id": game_id,
            "official_player_id": player_id,
            "player_name": str(row.get("player_name") or "").strip() or None,
            "market_type": market,
            "sportsbook": EXPECTED_SOURCE,
            "line": line,
            "over_odds": over_odds,
            "under_odds": under_odds,
            "source_event_id": row.get("source_event_id"),
            "source_market_id": row.get("source_market_id"),
            "match_method": MATCH_METHOD,
            "fallback_matching_used": False,
        }

    if not props:
        failures.append("empty_player_prop_slate")
    if not contexts:
        failures.append("no_usable_player_prop_contexts")

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
        "supported_market_types": sorted(SUPPORTED_MARKET_TYPES),
        "api_prop_count": len(props),
        "usable_player_prop_count": len(contexts),
        "unusable_player_prop_count": len(unusable_rows),
        "unusable_prop_rows": unusable_rows,
        "contexts_by_exact_identity": contexts,
        "snapshot_age_seconds": None,
        "feed_fresh": None,
        "max_snapshot_age_seconds": DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
        "player_name_matching_used": False,
        "fuzzy_matching_allowed": False,
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


def enforce_player_prop_api_freshness(
    api_state: Mapping[str, Any] | None,
    *,
    as_of_utc: datetime | str | None = None,
    max_age_seconds: float = DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
) -> dict[str, Any]:
    """Require explicitly proven freshness before any prop context can be exposed."""
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


def player_prop_context_for_identity(
    api_state: Mapping[str, Any] | None,
    *,
    official_game_id: Any,
    official_player_id: Any,
    market_type: Any,
) -> dict[str, Any] | None:
    """Return one prop only for an exact official game/player/market identity."""
    state = deepcopy(_mapping(api_state))
    if state.get("api_integration_active") is not True:
        return None
    if state.get("feed_fresh") is not True:
        return None
    if state.get("match_method") != MATCH_METHOD:
        return None
    if state.get("fallback_matching_used") is not False:
        return None
    if state.get("player_name_matching_used") is not False:
        return None
    if state.get("fuzzy_matching_allowed") is not False:
        return None

    game_id = _positive_int(official_game_id)
    player_id = _positive_int(official_player_id)
    market = _market_type(market_type)
    if game_id is None or player_id is None or market is None:
        return None

    contexts = state.get("contexts_by_exact_identity")
    if not isinstance(contexts, Mapping):
        return None
    identity = _identity_key(game_id, player_id, market)
    context = _mapping(contexts.get(identity))
    if (
        _positive_int(context.get("official_game_id")) != game_id
        or _positive_int(context.get("official_player_id")) != player_id
        or _market_type(context.get("market_type")) != market
    ):
        return None

    line = _positive_line(context.get("line"))
    over_odds = _american_odds(context.get("over_odds"))
    under_odds = _american_odds(context.get("under_odds"))
    if None in (line, over_odds, under_odds):
        return None

    return {
        "data_type": CONTEXT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "official_game_id": game_id,
        "official_player_id": player_id,
        "player_name": context.get("player_name"),
        "market_type": market,
        "source": EXPECTED_SOURCE,
        "match_method": MATCH_METHOD,
        "fallback_matching_used": False,
        "player_name_matching_used": False,
        "line": line,
        "over_odds": over_odds,
        "under_odds": under_odds,
        "source_event_id": context.get("source_event_id"),
        "source_market_id": context.get("source_market_id"),
        "collected_at_utc": state.get("collected_at_utc"),
        "snapshot_age_seconds": state.get("snapshot_age_seconds"),
        "feed_fresh": True,
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
    "CONTEXT_DATA_TYPE",
    "DATA_TYPE",
    "DEFAULT_MAX_SNAPSHOT_AGE_SECONDS",
    "EXPECTED_API_DATA_TYPE",
    "EXPECTED_SOURCE",
    "FALLBACK",
    "HITS_RUNS_RBI",
    "MATCH_METHOD",
    "PITCHER_STRIKEOUTS",
    "PLAYER_HITS",
    "SCHEMA_VERSION",
    "SUPPORTED_MARKET_TYPES",
    "build_player_prop_api_state",
    "enforce_player_prop_api_freshness",
    "player_prop_context_for_identity",
]
