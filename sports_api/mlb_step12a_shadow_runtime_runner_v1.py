"""MLB Step 12A — deterministic shadow runtime runner.

Step 11 froze the provider-neutral contract, DraftKings shadow adapter,
multi-provider shadow board, and consensus/failover shadow policy. Step 12A is
the first runtime-assembly step: it executes those already-certified pure
components as one deterministic shadow cycle over caller-supplied provider
snapshots.

This module deliberately performs no network I/O, no production API/runtime
wiring, no persistence writes, no best-price selection, and no production
provider consensus/failover. It does not feed shadow output into model or
sportsbook inputs. A later Step 12 stage must explicitly authorize any live
runtime integration.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step11_final_provider_expansion_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP11_FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS as STEP11_FINAL_FREEZE_STATUS,
    final_provider_expansion_freeze_manifest,
)
from sports_api.mlb_step11c_multi_provider_shadow_board_v1 import (
    MAX_INPUT_SNAPSHOTS,
    build_multi_provider_shadow_board,
    validate_multi_provider_shadow_board,
)
from sports_api.mlb_step11d_provider_consensus_failover_shadow_policy_v1 import (
    DEFAULT_FALLBACK_PROVIDER,
    DEFAULT_MAX_AGE_SECONDS,
    DEFAULT_PRIMARY_PROVIDER,
    MAX_MAX_AGE_SECONDS,
    build_provider_consensus_failover_shadow_policy,
    validate_provider_consensus_failover_shadow_policy,
)

DATA_TYPE = "mlb_step12a_shadow_runtime_cycle_v1"
SCHEMA_VERSION = 1
STEP12A_BASE_MAIN_SHA = "388c79480e916f7d9123b4f6deef6b6938ac8d2b"
RUNTIME_STATUS = "STEP12A_SHADOW_RUNTIME_RUNNER_READY"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP12A_SHADOW_RUNTIME_RUNNER_GREEN"


class MLBStep12AShadowRuntimeError(ValueError):
    """Raised when Step 12A cannot safely assemble a shadow runtime cycle."""


def shadow_runtime_manifest() -> dict[str, Any]:
    """Return the immutable Step 12A runtime boundary."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step12a_base_main_sha": STEP12A_BASE_MAIN_SHA,
        "runtime_status": RUNTIME_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step11_final_freeze_status_required": STEP11_FINAL_FREEZE_STATUS,
        "step11_final_certification_marker_required": STEP11_FINAL_CERTIFICATION_MARKER,
        "max_input_snapshots": MAX_INPUT_SNAPSHOTS,
        "default_max_age_seconds": DEFAULT_MAX_AGE_SECONDS,
        "maximum_max_age_seconds": MAX_MAX_AGE_SECONDS,
        "primary_provider": DEFAULT_PRIMARY_PROVIDER,
        "fallback_provider": DEFAULT_FALLBACK_PROVIDER,
        "provider_snapshots_supplied_by_caller": True,
        "step11c_shadow_board_executed": True,
        "step11d_shadow_policy_executed": True,
        "deterministic_runtime_cycle": True,
        "exact_official_game_id_required": True,
        "freshness_gate_required": True,
        "source_complete_gate_required": True,
        "same_line_required_for_run_line_total_consensus": True,
        "network_io_added_by_step12a": False,
        "live_secondary_provider_network_calls_enabled": False,
        "production_api_wiring_added_by_step12a": False,
        "production_runtime_wiring_added_by_step12a": False,
        "production_provider_consensus_enabled": False,
        "production_provider_failover_enabled": False,
        "best_price_selection_enabled": False,
        "provider_weighting_enabled": False,
        "production_database_writes_enabled": False,
        "persistence_schema_changed_by_step12a": False,
        "price_fabrication_allowed": False,
        "fallback_price_fabrication_allowed": False,
        "team_name_join_allowed": False,
        "player_name_join_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "shadow_output_as_model_input_allowed": False,
        "shadow_output_as_sportsbook_input_allowed": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        "future_live_runtime_activation_required": True,
        **PROTECTED_INVARIANTS,
    }


def _utc_z(value: Any, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MLBStep12AShadowRuntimeError(f"{field} must be UTC RFC3339 ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBStep12AShadowRuntimeError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBStep12AShadowRuntimeError(f"{field} must be UTC")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_source_sequence(source_snapshots: Any) -> Sequence[Mapping[str, Any]]:
    if not isinstance(source_snapshots, Sequence) or isinstance(source_snapshots, (str, bytes)):
        raise MLBStep12AShadowRuntimeError("source_snapshots must be a sequence")
    if not source_snapshots:
        raise MLBStep12AShadowRuntimeError("source_snapshots must not be empty")
    if len(source_snapshots) > MAX_INPUT_SNAPSHOTS:
        raise MLBStep12AShadowRuntimeError(
            f"at most {MAX_INPUT_SNAPSHOTS} source snapshots are allowed"
        )
    if any(not isinstance(row, Mapping) for row in source_snapshots):
        raise MLBStep12AShadowRuntimeError("every source snapshot must be a mapping")
    return source_snapshots


def run_shadow_runtime_cycle(
    source_snapshots: Sequence[Mapping[str, Any]],
    *,
    assembled_at_utc: str,
    evaluated_at_utc: str,
    step11_final_manifest: Mapping[str, Any],
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    primary_provider: str = DEFAULT_PRIMARY_PROVIDER,
    fallback_provider: str = DEFAULT_FALLBACK_PROVIDER,
) -> dict[str, Any]:
    """Execute one pure Step 12A shadow cycle over already-normalized snapshots."""
    snapshots = _validate_source_sequence(source_snapshots)
    if not isinstance(step11_final_manifest, Mapping):
        raise MLBStep12AShadowRuntimeError("step11_final_manifest must be a mapping")
    if dict(step11_final_manifest) != final_provider_expansion_freeze_manifest():
        raise MLBStep12AShadowRuntimeError("Step 11 final provider freeze manifest mismatch")

    assembled, assembled_dt = _utc_z(assembled_at_utc, "assembled_at_utc")
    evaluated, evaluated_dt = _utc_z(evaluated_at_utc, "evaluated_at_utc")
    if evaluated_dt < assembled_dt:
        raise MLBStep12AShadowRuntimeError(
            "evaluated_at_utc cannot be before assembled_at_utc"
        )

    # Step 11C/11D own the exact provider, official-gamePk, market, freshness,
    # line-comparability, and fail-closed validation rules. Step 12A only
    # composes those certified pure functions into a single shadow cycle.
    board = build_multi_provider_shadow_board(
        deepcopy(list(snapshots)),
        assembled_at_utc=assembled,
    )
    board_validation = validate_multi_provider_shadow_board(board)
    if board_validation.get("board_valid") is not True:
        raise MLBStep12AShadowRuntimeError(
            f"Step 11C shadow board validation failed: {board_validation.get('failures')}"
        )

    policy = build_provider_consensus_failover_shadow_policy(
        board,
        evaluated_at_utc=evaluated,
        max_age_seconds=max_age_seconds,
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
    )
    policy_validation = validate_provider_consensus_failover_shadow_policy(policy)
    if policy_validation.get("policy_valid") is not True:
        raise MLBStep12AShadowRuntimeError(
            f"Step 11D shadow policy validation failed: {policy_validation.get('failures')}"
        )

    source_record_keys = list(board["source_record_keys"])
    result: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "runtime_status": RUNTIME_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "assembled_at_utc": assembled,
        "evaluated_at_utc": evaluated,
        "max_age_seconds": policy["max_age_seconds"],
        "primary_provider": policy["primary_provider"],
        "fallback_provider": policy["fallback_provider"],
        "step11_final_freeze_status": STEP11_FINAL_FREEZE_STATUS,
        "step11_final_certification_marker": STEP11_FINAL_CERTIFICATION_MARKER,
        "source_snapshot_count": len(snapshots),
        "source_record_keys": source_record_keys,
        "source_record_key_count": len(source_record_keys),
        "board_sha256": board["board_sha256"],
        "policy_sha256": policy["policy_sha256"],
        "unique_game_count": board["unique_game_count"],
        "game_phase_group_count": board["game_phase_group_count"],
        "dual_provider_game_phase_group_count": board[
            "dual_provider_game_phase_group_count"
        ],
        "consensus_ready_market_count": policy["consensus_ready_market_count"],
        "shadow_failover_candidate_count": policy["shadow_failover_candidate_count"],
        "stale_provider_slot_count": policy["stale_provider_slot_count"],
        "shadow_board": board,
        "shadow_policy": policy,
        "shadow_board_validation_green": True,
        "shadow_policy_validation_green": True,
        "shadow_cycle_completed": True,
        "network_io_performed": False,
        "live_secondary_provider_network_calls": 0,
        "production_api_wiring": False,
        "production_runtime_wiring": False,
        "production_provider_consensus_used": False,
        "production_provider_failover_used": False,
        "best_price_selection_used": False,
        "provider_weighting_used": False,
        "production_database_writes": 0,
        "price_fabrication_used": False,
        "fallback_price_fabrication_used": False,
        "team_name_join_used": False,
        "player_name_join_used": False,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "shadow_output_as_model_input": False,
        "shadow_output_as_sportsbook_input": False,
        "persisted_snapshot_as_model_input": False,
        "persisted_snapshot_as_sportsbook_input": False,
    }
    result["cycle_sha256"] = _hash(result)
    return result


def validate_shadow_runtime_cycle(cycle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Rebuild and exact-compare a Step 12A shadow cycle."""
    if not isinstance(cycle, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "cycle_valid": False,
            "failures": ["STEP12A_CYCLE_NOT_MAPPING"],
        }

    failures: list[str] = []
    try:
        source_board = cycle.get("shadow_board")
        if not isinstance(source_board, Mapping):
            raise MLBStep12AShadowRuntimeError("shadow_board must be a mapping")
        rebuilt = run_shadow_runtime_cycle(
            source_board.get("source_snapshots"),
            assembled_at_utc=cycle.get("assembled_at_utc"),
            evaluated_at_utc=cycle.get("evaluated_at_utc"),
            step11_final_manifest=final_provider_expansion_freeze_manifest(),
            max_age_seconds=cycle.get("max_age_seconds"),
            primary_provider=cycle.get("primary_provider"),
            fallback_provider=cycle.get("fallback_provider"),
        )
    except Exception as exc:
        failures.append(f"STEP12A_REBUILD_FAILED:{type(exc).__name__}:{exc}")
    else:
        if dict(cycle) != rebuilt:
            failures.append("STEP12A_CYCLE_EXACT_CONTRACT_MISMATCH")

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "cycle_valid": not failures,
        "failures": failures,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP12A_BASE_MAIN_SHA",
    "RUNTIME_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "MLBStep12AShadowRuntimeError",
    "shadow_runtime_manifest",
    "run_shadow_runtime_cycle",
    "validate_shadow_runtime_cycle",
]
