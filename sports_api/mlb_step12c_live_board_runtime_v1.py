"""MLB Step 12C — deterministic live board runtime in shadow mode.

Step 12B certifies an exact-game live runtime assembly over the frozen Step 12A
shadow cycle. Step 12C turns that validated assembly into a deterministic,
consumer-shaped observational board while preserving every upstream gate.

The board is deliberately non-actionable. It exposes provider observations,
health, shadow routing, consensus readiness, and failover-candidate state for
inspection only. It performs no network I/O, no production API/runtime wiring,
no best-price selection, no provider weighting, no persistence writes, and no
model or sportsbook input changes. Exact official MLB ``gamePk`` remains the
only game identity key.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step11a_provider_contract_v1 import SUPPORTED_CORE_MARKETS
from sports_api.mlb_step12b_live_runtime_assembly_v1 import (
    ASSEMBLY_STATUS as STEP12B_ASSEMBLY_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP12B_FINAL_CERTIFICATION_MARKER,
    RUNTIME_MODE as STEP12B_RUNTIME_MODE,
    live_runtime_assembly_manifest,
    validate_live_runtime_assembly,
)

DATA_TYPE = "mlb_step12c_live_board_runtime_v1"
SCHEMA_VERSION = 1
STEP12C_BASE_MAIN_SHA = "5257a82c08f8ceea893a77c7963bd1a82b4db72b"
BOARD_STATUS = "STEP12C_LIVE_BOARD_RUNTIME_READY"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP12C_LIVE_BOARD_RUNTIME_GREEN"


class MLBStep12CLiveBoardRuntimeError(ValueError):
    """Raised when Step 12C cannot safely construct an observational board."""


def live_board_runtime_manifest() -> dict[str, Any]:
    """Return the immutable Step 12C shadow-only live board boundary."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step12c_base_main_sha": STEP12C_BASE_MAIN_SHA,
        "board_status": BOARD_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step12b_assembly_status_required": STEP12B_ASSEMBLY_STATUS,
        "step12b_runtime_mode_required": STEP12B_RUNTIME_MODE,
        "step12b_final_certification_marker_required": STEP12B_FINAL_CERTIFICATION_MARKER,
        "step12b_assembly_required": True,
        "step12b_assembly_revalidated": True,
        "deterministic_consumer_board": True,
        "exact_official_game_id_required": True,
        "market_row_identity_uses_exact_game_id_phase_market": True,
        "freshness_gate_preserved": True,
        "source_complete_gate_preserved": True,
        "same_line_gate_preserved": True,
        "observational_only": True,
        "actionable_output_enabled": False,
        "network_io_added_by_step12c": False,
        "live_secondary_provider_network_calls_enabled": False,
        "production_api_wiring_added_by_step12c": False,
        "production_runtime_wiring_added_by_step12c": False,
        "production_provider_consensus_enabled": False,
        "production_provider_failover_enabled": False,
        "best_price_selection_enabled": False,
        "provider_weighting_enabled": False,
        "production_database_writes_enabled": False,
        "persistence_schema_changed_by_step12c": False,
        "price_fabrication_allowed": False,
        "fallback_price_fabrication_allowed": False,
        "team_name_join_allowed": False,
        "player_name_join_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "live_board_as_model_input_allowed": False,
        "live_board_as_sportsbook_input_allowed": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        "future_controlled_runtime_activation_required": True,
        **PROTECTED_INVARIANTS,
    }


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise MLBStep12CLiveBoardRuntimeError(f"{field} must be a positive integer")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MLBStep12CLiveBoardRuntimeError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise MLBStep12CLiveBoardRuntimeError(f"{field} must be a sequence")
    return value


def _schedule_metadata(assembly: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    schedule = _mapping(assembly.get("official_schedule"), "assembly.official_schedule")
    games = _sequence(schedule.get("games"), "assembly.official_schedule.games")
    metadata: dict[int, dict[str, Any]] = {}
    for index, game_value in enumerate(games):
        game = _mapping(game_value, f"assembly.official_schedule.games[{index}]")
        game_id = _positive_int(
            game.get("game_pk"), f"assembly.official_schedule.games[{index}].game_pk"
        )
        if game_id in metadata:
            raise MLBStep12CLiveBoardRuntimeError("duplicate official gamePk in schedule metadata")
        metadata[game_id] = {
            "game_date_utc": game.get("game_date_utc"),
            "status": game.get("status"),
            "venue": game.get("venue"),
            "away_team": game.get("away_team"),
            "home_team": game.get("home_team"),
            "away_probable_pitcher": game.get("away_probable_pitcher"),
            "home_probable_pitcher": game.get("home_probable_pitcher"),
        }
    return metadata


def _group_key(group: Mapping[str, Any], field: str) -> tuple[int, str]:
    game_id = _positive_int(group.get("official_game_id"), f"{field}.official_game_id")
    phase = group.get("market_phase")
    if not isinstance(phase, str) or not phase:
        raise MLBStep12CLiveBoardRuntimeError(f"{field}.market_phase must be non-empty")
    return game_id, phase


def _index_groups(groups: Any, field: str) -> dict[tuple[int, str], Mapping[str, Any]]:
    rows = _sequence(groups, field)
    indexed: dict[tuple[int, str], Mapping[str, Any]] = {}
    for index, row_value in enumerate(rows):
        row = _mapping(row_value, f"{field}[{index}]")
        key = _group_key(row, f"{field}[{index}]")
        if key in indexed:
            raise MLBStep12CLiveBoardRuntimeError(
                f"duplicate gamePk/market_phase group in {field}: {key!r}"
            )
        indexed[key] = row
    return indexed


def _index_markets(markets: Any, field: str) -> dict[str, Mapping[str, Any]]:
    rows = _sequence(markets, field)
    indexed: dict[str, Mapping[str, Any]] = {}
    for index, row_value in enumerate(rows):
        row = _mapping(row_value, f"{field}[{index}]")
        name = row.get("market_name")
        if name not in SUPPORTED_CORE_MARKETS:
            raise MLBStep12CLiveBoardRuntimeError(
                f"{field}[{index}].market_name is unsupported: {name!r}"
            )
        if name in indexed:
            raise MLBStep12CLiveBoardRuntimeError(
                f"duplicate market {name!r} in {field}"
            )
        indexed[str(name)] = row
    if set(indexed) != set(SUPPORTED_CORE_MARKETS):
        raise MLBStep12CLiveBoardRuntimeError(
            f"{field} must contain each supported core market exactly once"
        )
    return indexed


def build_live_board_runtime(
    source_assembly: Mapping[str, Any],
    *,
    step12b_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a deterministic observational board from one validated Step 12B assembly."""
    if not isinstance(step12b_manifest, Mapping):
        raise MLBStep12CLiveBoardRuntimeError("step12b_manifest must be a mapping")
    if dict(step12b_manifest) != live_runtime_assembly_manifest():
        raise MLBStep12CLiveBoardRuntimeError("Step 12B live runtime manifest mismatch")
    if not isinstance(source_assembly, Mapping):
        raise MLBStep12CLiveBoardRuntimeError("source_assembly must be a mapping")

    validation = validate_live_runtime_assembly(source_assembly)
    if validation.get("assembly_valid") is not True:
        raise MLBStep12CLiveBoardRuntimeError(
            f"Step 12B live runtime assembly validation failed: {validation.get('failures')}"
        )

    assembly = deepcopy(dict(source_assembly))
    if assembly.get("assembly_status") != STEP12B_ASSEMBLY_STATUS:
        raise MLBStep12CLiveBoardRuntimeError("Step 12B assembly status mismatch")
    if assembly.get("runtime_mode") != STEP12B_RUNTIME_MODE:
        raise MLBStep12CLiveBoardRuntimeError("Step 12B runtime mode mismatch")

    cycle = _mapping(assembly.get("shadow_cycle"), "source_assembly.shadow_cycle")
    shadow_board = _mapping(cycle.get("shadow_board"), "source_assembly.shadow_cycle.shadow_board")
    shadow_policy = _mapping(cycle.get("shadow_policy"), "source_assembly.shadow_cycle.shadow_policy")
    board_groups = _index_groups(
        shadow_board.get("game_phase_groups"),
        "source_assembly.shadow_cycle.shadow_board.game_phase_groups",
    )
    policy_groups = _index_groups(
        shadow_policy.get("groups"),
        "source_assembly.shadow_cycle.shadow_policy.groups",
    )
    if set(board_groups) != set(policy_groups):
        raise MLBStep12CLiveBoardRuntimeError(
            "shadow board and shadow policy gamePk/market_phase groups must match exactly"
        )

    schedule = _schedule_metadata(assembly)
    output_groups: list[dict[str, Any]] = []
    flat_rows: list[dict[str, Any]] = []

    for key in sorted(board_groups):
        game_id, phase = key
        if game_id not in schedule:
            raise MLBStep12CLiveBoardRuntimeError(
                f"shadow group gamePk {game_id} is absent from official schedule"
            )
        board_group = board_groups[key]
        policy_group = policy_groups[key]
        board_markets = _index_markets(
            board_group.get("market_views"), f"shadow_board.group[{game_id},{phase}].market_views"
        )
        policy_markets = _index_markets(
            policy_group.get("markets"), f"shadow_policy.group[{game_id},{phase}].markets"
        )

        group_rows: list[dict[str, Any]] = []
        for market_name in SUPPORTED_CORE_MARKETS:
            observation = board_markets[market_name]
            policy = policy_markets[market_name]
            consensus = _mapping(policy.get("consensus"), f"policy.{market_name}.consensus")
            market_row = {
                "row_key": f"{game_id}:{phase}:{market_name}",
                "official_game_id": game_id,
                "market_phase": phase,
                "market_name": market_name,
                "provider_count": observation.get("provider_count"),
                "provider_keys": deepcopy(observation.get("provider_keys")),
                "provider_observations": deepcopy(observation.get("providers")),
                "available_provider_count": policy.get("available_provider_count"),
                "available_provider_keys": deepcopy(policy.get("available_provider_keys")),
                "shadow_route_provider": policy.get("shadow_route_provider"),
                "shadow_route_reason": policy.get("shadow_route_reason"),
                "shadow_failover_candidate": policy.get("shadow_failover_candidate"),
                "consensus_available": consensus.get("available"),
                "consensus_status": consensus.get("status"),
                "consensus_method": consensus.get("method"),
                "consensus_provider_count": consensus.get("provider_count"),
                "consensus_provider_keys": deepcopy(consensus.get("provider_keys")),
                "consensus": deepcopy(consensus.get("consensus")),
                "observational_only": True,
                "actionable": False,
                "best_price_selection_performed": False,
                "production_route_changed": False,
            }
            group_rows.append(market_row)
            flat_rows.append(deepcopy(market_row))

        output_groups.append(
            {
                "official_game_id": game_id,
                "market_phase": phase,
                "game_metadata": deepcopy(schedule[game_id]),
                "provider_count": board_group.get("provider_count"),
                "provider_keys": deepcopy(board_group.get("provider_keys")),
                "fully_priced_provider_count": board_group.get("fully_priced_provider_count"),
                "all_present_providers_fully_priced": board_group.get(
                    "all_present_providers_fully_priced"
                ),
                "provider_health": deepcopy(policy_group.get("provider_health")),
                "market_count": len(group_rows),
                "markets": group_rows,
            }
        )

    row_keys = [row["row_key"] for row in flat_rows]
    if len(set(row_keys)) != len(row_keys):
        raise MLBStep12CLiveBoardRuntimeError("duplicate live board row identity detected")

    result: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "board_status": BOARD_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "step12b_assembly_status": STEP12B_ASSEMBLY_STATUS,
        "step12b_runtime_mode": STEP12B_RUNTIME_MODE,
        "step12b_final_certification_marker": STEP12B_FINAL_CERTIFICATION_MARKER,
        "source_assembly_sha256": assembly.get("assembly_sha256"),
        "official_schedule_date": assembly.get("official_schedule_date"),
        "assembled_at_utc": assembly.get("assembled_at_utc"),
        "evaluated_at_utc": assembly.get("evaluated_at_utc"),
        "primary_provider": assembly.get("primary_provider"),
        "fallback_provider": assembly.get("fallback_provider"),
        "group_count": len(output_groups),
        "market_row_count": len(flat_rows),
        "row_keys": row_keys,
        "groups": output_groups,
        "market_rows": flat_rows,
        "consensus_ready_market_count": assembly.get("consensus_ready_market_count"),
        "shadow_failover_candidate_count": assembly.get("shadow_failover_candidate_count"),
        "stale_provider_slot_count": assembly.get("stale_provider_slot_count"),
        "exact_official_game_id_join_verified": True,
        "observational_only": True,
        "actionable_output": False,
        "source_assembly": assembly,
        "network_io_performed": False,
        "live_secondary_provider_network_calls": 0,
        "production_api_wiring": False,
        "production_runtime_wiring": False,
        "production_provider_consensus_used": False,
        "production_provider_failover_used": False,
        "best_price_selection_used": False,
        "provider_weighting_used": False,
        "production_database_writes": 0,
        "persistence_schema_changed": False,
        "price_fabrication_used": False,
        "fallback_price_fabrication_used": False,
        "team_name_join_used": False,
        "player_name_join_used": False,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "live_board_as_model_input": False,
        "live_board_as_sportsbook_input": False,
        "persisted_snapshot_as_model_input": False,
        "persisted_snapshot_as_sportsbook_input": False,
    }
    result["board_sha256"] = _hash(result)
    return result


def validate_live_board_runtime(board: Mapping[str, Any] | None) -> dict[str, Any]:
    """Rebuild and exact-compare one Step 12C live board."""
    if not isinstance(board, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "board_valid": False,
            "failures": ["STEP12C_BOARD_NOT_MAPPING"],
        }

    failures: list[str] = []
    try:
        rebuilt = build_live_board_runtime(
            board.get("source_assembly"),
            step12b_manifest=live_runtime_assembly_manifest(),
        )
    except Exception as exc:
        failures.append(f"STEP12C_REBUILD_FAILED:{type(exc).__name__}:{exc}")
    else:
        if dict(board) != rebuilt:
            failures.append("STEP12C_BOARD_EXACT_CONTRACT_MISMATCH")

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "board_valid": not failures,
        "failures": failures,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP12C_BASE_MAIN_SHA",
    "BOARD_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "MLBStep12CLiveBoardRuntimeError",
    "live_board_runtime_manifest",
    "build_live_board_runtime",
    "validate_live_board_runtime",
]
