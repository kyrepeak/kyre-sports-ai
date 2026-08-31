"""Step 8D exact-ID integration for MLB player-hits sportsbook context.

This module is a pure, read-only adapter between the frozen Step 8A player-prop
contract and already-produced MLB Hit Model result objects. FanDuel line/price
metadata is attached only after a result has been identified by exact official
MLB game ID + official MLB player ID. Display names never participate in
identity and sportsbook data never changes model output.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from sports_api.mlb_step8a_player_prop_api_contract_v1 import (
    API_CONNECTED as STEP8A_API_CONNECTED,
    CONTEXT_DATA_TYPE as STEP8A_CONTEXT_DATA_TYPE,
    EXPECTED_SOURCE,
    MATCH_METHOD as STEP8A_MATCH_METHOD,
    PLAYER_HITS,
    player_prop_context_for_identity,
)

DATA_TYPE = "mlb_step8d_player_hits_integration_v1"
SCHEMA_VERSION = 1
INTEGRATED = "PLAYER_HITS_API_CONTEXT_ATTACHED"
FALLBACK = "PLAYER_HITS_PREEXISTING_MODEL_FALLBACK"
ATTACHMENT_KEY = "step8d_player_hits_context"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _positive_int(value: Any) -> int | None:
    """Accept only positive integer IDs or digit-only serialized integer IDs."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            parsed = int(text)
            return parsed if parsed > 0 else None
    return None


def _result_identity(row: Mapping[str, Any]) -> tuple[int, int, str] | None:
    """Build identity from official IDs only; display names are intentionally ignored."""
    game_id = _positive_int(row.get("game_pk"))
    player_id = _positive_int(row.get("player_id"))
    if game_id is None or player_id is None:
        return None
    return (game_id, player_id, PLAYER_HITS)


def _step8a_boundary_failures(api_state: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if api_state.get("integration_status") != STEP8A_API_CONNECTED:
        failures.append("step8a_api_integration_inactive")
    if api_state.get("api_integration_active") is not True:
        failures.append("step8a_api_integration_not_active")
    if api_state.get("source") != EXPECTED_SOURCE:
        failures.append("unexpected_player_prop_source")
    if api_state.get("match_method") != STEP8A_MATCH_METHOD:
        failures.append("exact_player_prop_match_method_not_proven")
    if api_state.get("feed_fresh") is not True:
        failures.append("player_prop_feed_freshness_not_proven")
    if api_state.get("fallback_matching_used") is not False:
        failures.append("fallback_matching_detected")
    if api_state.get("player_name_matching_used") is not False:
        failures.append("player_name_matching_detected")
    if api_state.get("fuzzy_matching_allowed") is not False:
        failures.append("fuzzy_matching_detected")
    if api_state.get("sportsbook_price_model_input") is not False:
        failures.append("sportsbook_price_model_input_drift")
    return failures


def build_player_hits_integration(
    hitter_results: Sequence[Mapping[str, Any]] | None,
    api_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build display-only exact-ID attachments without modifying hit-model rows."""
    original_rows = list(hitter_results or [])
    rows = deepcopy(original_rows)
    state = deepcopy(_mapping(api_state))
    failures = _step8a_boundary_failures(state)

    attachments: dict[int, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    duplicate = False

    identities: dict[int, tuple[int, int, str]] = {}
    for index, raw_row in enumerate(rows):
        row = _mapping(raw_row)
        identity = _result_identity(row)
        if identity is None:
            invalid.append({"index": index, "reason": "invalid_or_missing_exact_result_identity"})
            continue
        if identity in seen:
            duplicate = True
            invalid.append(
                {
                    "index": index,
                    "reason": "duplicate_exact_player_hits_result_identity",
                    "official_game_id": identity[0],
                    "official_player_id": identity[1],
                    "market_type": identity[2],
                }
            )
            continue
        seen.add(identity)
        identities[index] = identity

    if duplicate:
        failures.append("duplicate_exact_player_hits_result_identity")

    if not failures:
        for index, identity in identities.items():
            game_id, player_id, market_type = identity
            context = player_prop_context_for_identity(
                state,
                official_game_id=game_id,
                official_player_id=player_id,
                market_type=market_type,
            )
            if context is None:
                unmatched.append(
                    {
                        "index": index,
                        "official_game_id": game_id,
                        "official_player_id": player_id,
                        "market_type": market_type,
                        "reason": "exact_player_hits_context_unavailable",
                    }
                )
                continue
            if context.get("data_type") != STEP8A_CONTEXT_DATA_TYPE:
                unmatched.append(
                    {
                        "index": index,
                        "official_game_id": game_id,
                        "official_player_id": player_id,
                        "market_type": market_type,
                        "reason": "unexpected_step8a_context_data_type",
                    }
                )
                continue
            attachments[index] = {
                "data_type": "mlb_step8d_player_hits_attachment_v1",
                "schema_version": SCHEMA_VERSION,
                "official_game_id": game_id,
                "official_player_id": player_id,
                "market_type": PLAYER_HITS,
                "source": EXPECTED_SOURCE,
                "sportsbook": EXPECTED_SOURCE,
                "player_name": context.get("player_name"),
                "line": context.get("line"),
                "over_odds": context.get("over_odds"),
                "under_odds": context.get("under_odds"),
                "source_event_id": context.get("source_event_id"),
                "source_market_id": context.get("source_market_id"),
                "collected_at_utc": context.get("collected_at_utc"),
                "snapshot_age_seconds": context.get("snapshot_age_seconds"),
                "feed_fresh": context.get("feed_fresh") is True,
                "match_method": STEP8A_MATCH_METHOD,
                "fallback_matching_used": False,
                "player_name_matching_used": False,
                "display_only": True,
                "model_math_impact": False,
                "projection_impact": False,
                "simulation_impact": False,
                "probability_impact": False,
                "line_grading_impact": False,
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

    active = bool(attachments) and not failures
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "integration_status": INTEGRATED if active else FALLBACK,
        "api_integration_active": active,
        "source": EXPECTED_SOURCE,
        "market_type": PLAYER_HITS,
        "match_method": STEP8A_MATCH_METHOD,
        "fallback_matching_used": False,
        "player_name_matching_used": False,
        "fuzzy_matching_allowed": False,
        "candidate_result_count": len(rows),
        "valid_exact_identity_count": len(identities),
        "attached_count": len(attachments),
        "unmatched_count": len(unmatched),
        "invalid_result_count": len(invalid),
        "attachments_by_result_index": attachments,
        "unmatched_results": unmatched,
        "invalid_results": invalid,
        "preexisting_hit_model_preserved": True,
        "model_math_impact": False,
        "projection_impact": False,
        "simulation_impact": False,
        "probability_impact": False,
        "line_grading_impact": False,
        "history_adjustment_impact": False,
        "ranking_impact": False,
        "selection_impact": False,
        "fair_odds_impact": False,
        "sportsbook_price_model_input": False,
        "production_exposure_impact": False,
        "streamlit_presentation_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
        "failures": failures,
    }


def enrich_player_hit_results(
    hitter_results: Sequence[Mapping[str, Any]] | None,
    integration_state: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return deep-copied hit-model rows with display-only context where proven."""
    rows = deepcopy(list(hitter_results or []))
    state = deepcopy(_mapping(integration_state))
    if state.get("api_integration_active") is not True:
        return rows
    if state.get("integration_status") != INTEGRATED:
        return rows
    if state.get("match_method") != STEP8A_MATCH_METHOD:
        return rows
    if state.get("player_name_matching_used") is not False:
        return rows
    if state.get("sportsbook_price_model_input") is not False:
        return rows

    attachments = state.get("attachments_by_result_index")
    if not isinstance(attachments, Mapping):
        return rows

    for raw_index, raw_context in attachments.items():
        if isinstance(raw_index, bool):
            continue
        if isinstance(raw_index, int):
            index = raw_index
        elif isinstance(raw_index, str) and raw_index.strip().isdigit():
            index = int(raw_index.strip())
        else:
            continue
        if index < 0 or index >= len(rows):
            continue
        row = _mapping(rows[index])
        identity = _result_identity(row)
        context = _mapping(raw_context)
        if identity is None:
            continue
        if (
            _positive_int(context.get("official_game_id")) != identity[0]
            or _positive_int(context.get("official_player_id")) != identity[1]
            or context.get("market_type") != PLAYER_HITS
            or context.get("source") != EXPECTED_SOURCE
            or context.get("match_method") != STEP8A_MATCH_METHOD
            or context.get("feed_fresh") is not True
            or context.get("display_only") is not True
            or context.get("sportsbook_price_model_input") is not False
        ):
            continue
        row[ATTACHMENT_KEY] = context
        rows[index] = row
    return rows


__all__ = [
    "ATTACHMENT_KEY",
    "DATA_TYPE",
    "FALLBACK",
    "INTEGRATED",
    "SCHEMA_VERSION",
    "build_player_hits_integration",
    "enrich_player_hit_results",
]
