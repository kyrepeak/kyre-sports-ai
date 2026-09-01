"""MLB Step 12B — exact-game live runtime assembly boundary.

Step 12A froze a deterministic shadow runtime cycle over caller-supplied,
provider-neutral market snapshots. Step 12B adds the next safe runtime layer:
it binds those snapshots to a caller-supplied official MLB schedule strictly by
exact official ``gamePk`` before Step 12A is allowed to execute.

This module is intentionally pure. It performs no network I/O, does not modify
the production API or runtime, does not activate DraftKings, does not enable
production consensus/failover, does not select best prices, and does not write
to persistence. Team/player names are carried only as schedule metadata and are
never used for identity. A later Step 12 stage must explicitly authorize any
production runtime activation.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step11_final_provider_expansion_freeze_v1 import (
    final_provider_expansion_freeze_manifest,
)
from sports_api.mlb_step11c_multi_provider_shadow_board_v1 import MAX_INPUT_SNAPSHOTS
from sports_api.mlb_step11d_provider_consensus_failover_shadow_policy_v1 import (
    DEFAULT_FALLBACK_PROVIDER,
    DEFAULT_MAX_AGE_SECONDS,
    DEFAULT_PRIMARY_PROVIDER,
)
from sports_api.mlb_step12a_shadow_runtime_runner_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP12A_FINAL_CERTIFICATION_MARKER,
    RUNTIME_MODE as STEP12A_RUNTIME_MODE,
    RUNTIME_STATUS as STEP12A_RUNTIME_STATUS,
    run_shadow_runtime_cycle,
    shadow_runtime_manifest,
    validate_shadow_runtime_cycle,
)

DATA_TYPE = "mlb_step12b_live_runtime_assembly_v1"
SCHEMA_VERSION = 1
STEP12B_BASE_MAIN_SHA = "886a839dab28a7da3c5a0d597d500d568c4a60fb"
ASSEMBLY_STATUS = "STEP12B_LIVE_RUNTIME_ASSEMBLY_READY"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP12B_LIVE_RUNTIME_ASSEMBLY_GREEN"
OFFICIAL_SCHEDULE_SOURCE = "MLB Stats API"
MAX_OFFICIAL_GAMES = 50

_SCHEDULE_KEYS = {"source", "date", "game_count", "games"}
_GAME_KEYS = {
    "game_pk",
    "game_date_utc",
    "status",
    "venue",
    "away_team",
    "home_team",
    "away_probable_pitcher",
    "home_probable_pitcher",
}


class MLBStep12BLiveRuntimeAssemblyError(ValueError):
    """Raised when Step 12B cannot safely assemble exact-game shadow inputs."""


def live_runtime_assembly_manifest() -> dict[str, Any]:
    """Return the immutable Step 12B shadow-only live assembly boundary."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step12b_base_main_sha": STEP12B_BASE_MAIN_SHA,
        "assembly_status": ASSEMBLY_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step12a_runtime_status_required": STEP12A_RUNTIME_STATUS,
        "step12a_runtime_mode_required": STEP12A_RUNTIME_MODE,
        "step12a_final_certification_marker_required": STEP12A_FINAL_CERTIFICATION_MARKER,
        "official_schedule_source_required": OFFICIAL_SCHEDULE_SOURCE,
        "max_official_games": MAX_OFFICIAL_GAMES,
        "max_provider_snapshots": MAX_INPUT_SNAPSHOTS,
        "official_schedule_supplied_by_caller": True,
        "provider_snapshots_supplied_by_caller": True,
        "exact_official_game_id_join_required": True,
        "every_provider_game_id_must_exist_in_official_schedule": True,
        "duplicate_official_game_ids_forbidden": True,
        "step12a_shadow_runtime_executed_after_identity_gate": True,
        "step12a_shadow_runtime_revalidated": True,
        "freshness_gate_preserved": True,
        "source_complete_gate_preserved": True,
        "same_line_gate_preserved": True,
        "deterministic_assembly": True,
        "network_io_added_by_step12b": False,
        "live_secondary_provider_network_calls_enabled": False,
        "production_api_wiring_added_by_step12b": False,
        "production_runtime_wiring_added_by_step12b": False,
        "production_provider_consensus_enabled": False,
        "production_provider_failover_enabled": False,
        "best_price_selection_enabled": False,
        "provider_weighting_enabled": False,
        "production_database_writes_enabled": False,
        "persistence_schema_changed_by_step12b": False,
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
        "future_controlled_runtime_activation_required": True,
        **PROTECTED_INVARIANTS,
    }


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise MLBStep12BLiveRuntimeAssemblyError(f"{field} must be a positive integer")
    return value


def _exact_nonnegative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MLBStep12BLiveRuntimeAssemblyError(
            f"{field} must be a non-negative integer"
        )
    return value


def _date(value: Any) -> str:
    if not isinstance(value, str):
        raise MLBStep12BLiveRuntimeAssemblyError("official_schedule.date must be a string")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise MLBStep12BLiveRuntimeAssemblyError(
            "official_schedule.date must be YYYY-MM-DD"
        ) from exc
    if parsed != value:
        raise MLBStep12BLiveRuntimeAssemblyError(
            "official_schedule.date must be canonical YYYY-MM-DD"
        )
    return parsed


def _optional_text(value: Any, field: str, *, max_length: int = 256) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MLBStep12BLiveRuntimeAssemblyError(f"{field} must be a string or None")
    normalized = value.strip()
    if not normalized:
        raise MLBStep12BLiveRuntimeAssemblyError(f"{field} must not be blank")
    if len(normalized) > max_length:
        raise MLBStep12BLiveRuntimeAssemblyError(f"{field} exceeds maximum length")
    if any(ord(char) < 32 for char in normalized):
        raise MLBStep12BLiveRuntimeAssemblyError(f"{field} contains control characters")
    return normalized


def _optional_utc_z(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.endswith("Z")
        or "T" not in value
        or " " in value
    ):
        raise MLBStep12BLiveRuntimeAssemblyError(
            f"{field} must be UTC RFC3339 ending in Z or None"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBStep12BLiveRuntimeAssemblyError(f"{field} is invalid") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise MLBStep12BLiveRuntimeAssemblyError(f"{field} must be UTC")
    return parsed.isoformat().replace("+00:00", "Z")


def _normalize_schedule_game(row: Any, index: int) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise MLBStep12BLiveRuntimeAssemblyError(
            f"official_schedule.games[{index}] must be a mapping"
        )
    unknown = set(row) - _GAME_KEYS
    if unknown:
        raise MLBStep12BLiveRuntimeAssemblyError(
            f"official_schedule.games[{index}] has unsupported keys: {sorted(unknown)!r}"
        )
    game_pk = _positive_int(row.get("game_pk"), f"official_schedule.games[{index}].game_pk")
    return {
        "game_pk": game_pk,
        "game_date_utc": _optional_utc_z(
            row.get("game_date_utc"),
            f"official_schedule.games[{index}].game_date_utc",
        ),
        "status": _optional_text(row.get("status"), f"official_schedule.games[{index}].status"),
        "venue": _optional_text(row.get("venue"), f"official_schedule.games[{index}].venue"),
        "away_team": _optional_text(
            row.get("away_team"), f"official_schedule.games[{index}].away_team"
        ),
        "home_team": _optional_text(
            row.get("home_team"), f"official_schedule.games[{index}].home_team"
        ),
        "away_probable_pitcher": _optional_text(
            row.get("away_probable_pitcher"),
            f"official_schedule.games[{index}].away_probable_pitcher",
        ),
        "home_probable_pitcher": _optional_text(
            row.get("home_probable_pitcher"),
            f"official_schedule.games[{index}].home_probable_pitcher",
        ),
    }


def _normalize_official_schedule(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MLBStep12BLiveRuntimeAssemblyError("official_schedule must be a mapping")
    unknown = set(value) - _SCHEDULE_KEYS
    if unknown:
        raise MLBStep12BLiveRuntimeAssemblyError(
            f"official_schedule has unsupported keys: {sorted(unknown)!r}"
        )
    if value.get("source") != OFFICIAL_SCHEDULE_SOURCE:
        raise MLBStep12BLiveRuntimeAssemblyError(
            f"official_schedule.source must equal {OFFICIAL_SCHEDULE_SOURCE!r}"
        )
    schedule_date = _date(value.get("date"))
    declared_count = _exact_nonnegative_int(value.get("game_count"), "official_schedule.game_count")
    games = value.get("games")
    if not isinstance(games, Sequence) or isinstance(games, (str, bytes)):
        raise MLBStep12BLiveRuntimeAssemblyError("official_schedule.games must be a sequence")
    if not games:
        raise MLBStep12BLiveRuntimeAssemblyError("official_schedule.games must not be empty")
    if len(games) > MAX_OFFICIAL_GAMES:
        raise MLBStep12BLiveRuntimeAssemblyError(
            f"official_schedule.games exceeds maximum {MAX_OFFICIAL_GAMES}"
        )
    if declared_count != len(games):
        raise MLBStep12BLiveRuntimeAssemblyError(
            "official_schedule.game_count must exactly equal len(official_schedule.games)"
        )

    normalized_games = [_normalize_schedule_game(row, index) for index, row in enumerate(games)]
    game_ids = [row["game_pk"] for row in normalized_games]
    if len(set(game_ids)) != len(game_ids):
        raise MLBStep12BLiveRuntimeAssemblyError(
            "duplicate official gamePk values are forbidden"
        )
    normalized_games.sort(key=lambda row: row["game_pk"])
    return {
        "source": OFFICIAL_SCHEDULE_SOURCE,
        "date": schedule_date,
        "game_count": len(normalized_games),
        "games": normalized_games,
    }


def _validate_provider_snapshots(value: Any, official_game_ids: set[int]) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise MLBStep12BLiveRuntimeAssemblyError("provider_snapshots must be a sequence")
    if not value:
        raise MLBStep12BLiveRuntimeAssemblyError("provider_snapshots must not be empty")
    if len(value) > MAX_INPUT_SNAPSHOTS:
        raise MLBStep12BLiveRuntimeAssemblyError(
            f"at most {MAX_INPUT_SNAPSHOTS} provider snapshots are allowed"
        )
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise MLBStep12BLiveRuntimeAssemblyError(
                f"provider_snapshots[{index}] must be a mapping"
            )
        game_id = _positive_int(
            row.get("official_game_id"),
            f"provider_snapshots[{index}].official_game_id",
        )
        if game_id not in official_game_ids:
            raise MLBStep12BLiveRuntimeAssemblyError(
                f"provider snapshot gamePk {game_id} is absent from official schedule"
            )
    return value


def assemble_live_runtime_shadow(
    official_schedule: Mapping[str, Any],
    provider_snapshots: Sequence[Mapping[str, Any]],
    *,
    assembled_at_utc: str,
    evaluated_at_utc: str,
    step12a_manifest: Mapping[str, Any],
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    primary_provider: str = DEFAULT_PRIMARY_PROVIDER,
    fallback_provider: str = DEFAULT_FALLBACK_PROVIDER,
) -> dict[str, Any]:
    """Bind live schedule/provider inputs by exact gamePk and run Step 12A in shadow."""
    if not isinstance(step12a_manifest, Mapping):
        raise MLBStep12BLiveRuntimeAssemblyError("step12a_manifest must be a mapping")
    if dict(step12a_manifest) != shadow_runtime_manifest():
        raise MLBStep12BLiveRuntimeAssemblyError("Step 12A shadow runtime manifest mismatch")

    schedule = _normalize_official_schedule(official_schedule)
    official_game_ids = {row["game_pk"] for row in schedule["games"]}
    snapshots = _validate_provider_snapshots(provider_snapshots, official_game_ids)

    cycle = run_shadow_runtime_cycle(
        deepcopy(list(snapshots)),
        assembled_at_utc=assembled_at_utc,
        evaluated_at_utc=evaluated_at_utc,
        step11_final_manifest=final_provider_expansion_freeze_manifest(),
        max_age_seconds=max_age_seconds,
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
    )
    cycle_validation = validate_shadow_runtime_cycle(cycle)
    if cycle_validation.get("cycle_valid") is not True:
        raise MLBStep12BLiveRuntimeAssemblyError(
            f"Step 12A shadow runtime validation failed: {cycle_validation.get('failures')}"
        )

    provider_game_ids = sorted({int(row["official_game_id"]) for row in snapshots})
    official_ids = sorted(official_game_ids)
    unmatched_official_ids = sorted(official_game_ids - set(provider_game_ids))

    result: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "assembly_status": ASSEMBLY_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "step12a_runtime_status": STEP12A_RUNTIME_STATUS,
        "step12a_runtime_mode": STEP12A_RUNTIME_MODE,
        "step12a_final_certification_marker": STEP12A_FINAL_CERTIFICATION_MARKER,
        "official_schedule": schedule,
        "official_schedule_source": schedule["source"],
        "official_schedule_date": schedule["date"],
        "official_schedule_game_count": schedule["game_count"],
        "official_game_ids": official_ids,
        "provider_snapshot_count": len(snapshots),
        "provider_game_ids": provider_game_ids,
        "matched_official_game_count": len(provider_game_ids),
        "unmatched_official_game_count": len(unmatched_official_ids),
        "unmatched_official_game_ids": unmatched_official_ids,
        "exact_official_game_id_join_verified": True,
        "assembled_at_utc": cycle["assembled_at_utc"],
        "evaluated_at_utc": cycle["evaluated_at_utc"],
        "max_age_seconds": cycle["max_age_seconds"],
        "primary_provider": cycle["primary_provider"],
        "fallback_provider": cycle["fallback_provider"],
        "shadow_cycle": cycle,
        "shadow_cycle_validated": True,
        "shadow_cycle_sha256": cycle["cycle_sha256"],
        "consensus_ready_market_count": cycle["consensus_ready_market_count"],
        "shadow_failover_candidate_count": cycle["shadow_failover_candidate_count"],
        "stale_provider_slot_count": cycle["stale_provider_slot_count"],
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
        "shadow_output_as_model_input": False,
        "shadow_output_as_sportsbook_input": False,
        "persisted_snapshot_as_model_input": False,
        "persisted_snapshot_as_sportsbook_input": False,
    }
    result["assembly_sha256"] = _hash(result)
    return result


def validate_live_runtime_assembly(assembly: Mapping[str, Any] | None) -> dict[str, Any]:
    """Rebuild and exact-compare a Step 12B live runtime assembly."""
    if not isinstance(assembly, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "assembly_valid": False,
            "failures": ["STEP12B_ASSEMBLY_NOT_MAPPING"],
        }

    failures: list[str] = []
    try:
        cycle = assembly.get("shadow_cycle")
        if not isinstance(cycle, Mapping):
            raise MLBStep12BLiveRuntimeAssemblyError("shadow_cycle must be a mapping")
        board = cycle.get("shadow_board")
        if not isinstance(board, Mapping):
            raise MLBStep12BLiveRuntimeAssemblyError("shadow_cycle.shadow_board must be a mapping")
        rebuilt = assemble_live_runtime_shadow(
            assembly.get("official_schedule"),
            board.get("source_snapshots"),
            assembled_at_utc=assembly.get("assembled_at_utc"),
            evaluated_at_utc=assembly.get("evaluated_at_utc"),
            step12a_manifest=shadow_runtime_manifest(),
            max_age_seconds=assembly.get("max_age_seconds"),
            primary_provider=assembly.get("primary_provider"),
            fallback_provider=assembly.get("fallback_provider"),
        )
    except Exception as exc:
        failures.append(f"STEP12B_REBUILD_FAILED:{type(exc).__name__}:{exc}")
    else:
        if dict(assembly) != rebuilt:
            failures.append("STEP12B_ASSEMBLY_EXACT_CONTRACT_MISMATCH")

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "assembly_valid": not failures,
        "failures": failures,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP12B_BASE_MAIN_SHA",
    "ASSEMBLY_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "OFFICIAL_SCHEDULE_SOURCE",
    "MAX_OFFICIAL_GAMES",
    "MLBStep12BLiveRuntimeAssemblyError",
    "live_runtime_assembly_manifest",
    "assemble_live_runtime_shadow",
    "validate_live_runtime_assembly",
]
