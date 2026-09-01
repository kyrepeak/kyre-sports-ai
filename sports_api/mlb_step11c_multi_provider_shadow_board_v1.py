"""MLB Step 11C — deterministic FanDuel + DraftKings shadow board."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import (
    CONTRACT_STATUS as STEP11A_STATUS,
    DATA_TYPE as STEP11A_DATA_TYPE,
    FINAL_CERTIFICATION_MARKER as STEP11A_MARKER,
    SCHEMA_VERSION as STEP11A_SCHEMA_VERSION,
    SUPPORTED_CORE_MARKETS,
    SUPPORTED_MARKET_PHASES,
    validate_market_provider_game_snapshot,
)
from sports_api.collectors.mlb_draftkings_provider import (
    ADAPTER_STATUS as STEP11B_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP11B_MARKER,
)

DATA_TYPE = "mlb_multi_provider_shadow_board_v1"
SCHEMA_VERSION = 1
STEP11C_BASE_MAIN_SHA = "05aa8b6299f6300146666bcbb1601158d0ce364d"
BOARD_STATUS = "STEP11C_MULTI_PROVIDER_SHADOW_BOARD_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP11C_MULTI_PROVIDER_SHADOW_BOARD_GREEN"
SUPPORTED_PROVIDERS = ("fanduel", "draftkings")
PROVIDER_NAMES = {"fanduel": "FanDuel", "draftkings": "DraftKings"}
MAX_INPUT_SNAPSHOTS = 500
_PROVIDER_ORDER = {key: i for i, key in enumerate(SUPPORTED_PROVIDERS)}


class MLBMultiProviderShadowBoardError(ValueError):
    pass


def shadow_board_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step11c_base_main_sha": STEP11C_BASE_MAIN_SHA,
        "board_status": BOARD_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step10_final_freeze_status_required": STEP10_STATUS,
        "step10_final_certification_marker_required": STEP10_MARKER,
        "step11a_contract_status_required": STEP11A_STATUS,
        "step11a_final_certification_marker_required": STEP11A_MARKER,
        "step11a_data_type_required": STEP11A_DATA_TYPE,
        "step11a_schema_version_required": STEP11A_SCHEMA_VERSION,
        "step11b_adapter_status_required": STEP11B_STATUS,
        "step11b_final_certification_marker_required": STEP11B_MARKER,
        "supported_providers": list(SUPPORTED_PROVIDERS),
        "supported_provider_names": dict(PROVIDER_NAMES),
        "supported_market_phases": list(SUPPORTED_MARKET_PHASES),
        "supported_core_markets": list(SUPPORTED_CORE_MARKETS),
        "exact_official_game_id_only": True,
        "group_key_fields": ["official_game_id", "market_phase"],
        "exact_record_duplicate_deduplication_allowed": True,
        "ambiguous_provider_slot_selection_allowed": False,
        "cross_provider_event_id_join_allowed": False,
        "team_name_join_allowed": False,
        "player_name_join_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "price_fabrication_allowed": False,
        "fallback_price_fabrication_allowed": False,
        "best_price_selection_enabled": False,
        "provider_consensus_enabled": False,
        "provider_failover_enabled": False,
        "provider_weighting_enabled": False,
        "network_io_added_by_step11c": False,
        "production_api_wiring_added_by_step11c": False,
        "production_runtime_wiring_added_by_step11c": False,
        "persistence_schema_changed_by_step11c": False,
        "production_database_writes_enabled": False,
        "shadow_board_only": True,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        **PROTECTED_INVARIANTS,
    }


def _utc_z(value: Any, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MLBMultiProviderShadowBoardError(f"{field} must be UTC RFC3339 ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBMultiProviderShadowBoardError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBMultiProviderShadowBoardError(f"{field} must be UTC")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _provider_rank(key: Any) -> int:
    return _PROVIDER_ORDER[str(key)]


def _normalize_snapshot(snapshot: Any, assembled_at: datetime) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise MLBMultiProviderShadowBoardError("every source snapshot must be a mapping")
    validation = validate_market_provider_game_snapshot(snapshot)
    if validation.get("snapshot_valid") is not True:
        raise MLBMultiProviderShadowBoardError(
            f"invalid Step 11A source snapshot: {validation.get('failures')}"
        )
    row = deepcopy(dict(snapshot))
    key = row.get("provider_key")
    if key not in SUPPORTED_PROVIDERS:
        raise MLBMultiProviderShadowBoardError(f"unsupported provider_key: {key!r}")
    if row.get("provider_name") != PROVIDER_NAMES[key]:
        raise MLBMultiProviderShadowBoardError(f"provider_name mismatch for {key}")
    _, observed = _utc_z(row.get("observed_at_utc"), "source_snapshot.observed_at_utc")
    if observed > assembled_at:
        raise MLBMultiProviderShadowBoardError(
            "source snapshot observed_at_utc cannot be after assembled_at_utc"
        )
    return row


def _provider_view(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(row[key])
        for key in (
            "provider_key", "provider_name", "provider_event_id", "record_key",
            "snapshot_sha256", "observed_at_utc", "source_collected_at_utc",
            "transport", "source_payload_sha256", "source_complete", "market_count",
            "fully_priced", "market_availability", "markets",
        )
    }


def _market_view(name: str, providers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for row in providers:
        if name not in row["markets"]:
            continue
        rows.append({
            "provider_key": row["provider_key"],
            "provider_name": row["provider_name"],
            "provider_event_id": row["provider_event_id"],
            "record_key": row["record_key"],
            "observed_at_utc": row["observed_at_utc"],
            "market": deepcopy(row["markets"][name]),
        })
    rows.sort(key=lambda row: _provider_rank(row["provider_key"]))
    return {
        "market_name": name,
        "provider_count": len(rows),
        "provider_keys": [row["provider_key"] for row in rows],
        "cross_provider_overlap": len(rows) > 1,
        "providers": rows,
    }


def build_multi_provider_shadow_board(
    source_snapshots: Sequence[Mapping[str, Any]],
    *,
    assembled_at_utc: str,
) -> dict[str, Any]:
    if not isinstance(source_snapshots, Sequence) or isinstance(source_snapshots, (str, bytes)):
        raise MLBMultiProviderShadowBoardError("source_snapshots must be a sequence")
    if not source_snapshots:
        raise MLBMultiProviderShadowBoardError("source_snapshots must not be empty")
    if len(source_snapshots) > MAX_INPUT_SNAPSHOTS:
        raise MLBMultiProviderShadowBoardError(
            f"at most {MAX_INPUT_SNAPSHOTS} source snapshots are allowed"
        )

    assembled, assembled_dt = _utc_z(assembled_at_utc, "assembled_at_utc")
    inputs = [_normalize_snapshot(row, assembled_dt) for row in source_snapshots]
    inputs.sort(key=lambda row: (
        int(row["official_game_id"]),
        str(row["market_phase"]),
        _provider_rank(row["provider_key"]),
        str(row["record_key"]),
    ))

    seen_keys: set[str] = set()
    slots: dict[tuple[int, str, str], str] = {}
    unique: list[dict[str, Any]] = []
    duplicates = 0
    for row in inputs:
        record_key = str(row["record_key"])
        slot = (int(row["official_game_id"]), str(row["market_phase"]), str(row["provider_key"]))
        previous = slots.get(slot)
        if record_key in seen_keys:
            if previous not in (None, record_key):
                raise MLBMultiProviderShadowBoardError("duplicate record_key conflicts with provider slot")
            duplicates += 1
            continue
        if previous is not None and previous != record_key:
            raise MLBMultiProviderShadowBoardError(
                "multiple distinct current snapshots for the same provider/gamePk/market_phase are ambiguous"
            )
        seen_keys.add(record_key)
        slots[slot] = record_key
        unique.append(row)

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for row in unique:
        grouped.setdefault((int(row["official_game_id"]), str(row["market_phase"])), []).append(row)

    groups = []
    for (game_id, phase), providers in sorted(grouped.items()):
        providers.sort(key=lambda row: _provider_rank(row["provider_key"]))
        keys = [row["provider_key"] for row in providers]
        market_views = [_market_view(name, providers) for name in SUPPORTED_CORE_MARKETS]
        groups.append({
            "official_game_id": game_id,
            "market_phase": phase,
            "provider_count": len(providers),
            "provider_keys": keys,
            "all_supported_providers_present": set(keys) == set(SUPPORTED_PROVIDERS),
            "fully_priced_provider_count": sum(row["fully_priced"] is True for row in providers),
            "all_present_providers_fully_priced": all(row["fully_priced"] is True for row in providers),
            "market_overlap_count": sum(row["cross_provider_overlap"] for row in market_views),
            "providers": [_provider_view(row) for row in providers],
            "market_views": market_views,
        })

    input_counts = {
        key: sum(row["provider_key"] == key for row in inputs)
        for key in SUPPORTED_PROVIDERS
    }
    unique_counts = {
        key: sum(row["provider_key"] == key for row in unique)
        for key in SUPPORTED_PROVIDERS
    }
    present = [key for key in SUPPORTED_PROVIDERS if unique_counts[key] > 0]

    board: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "board_status": BOARD_STATUS,
        "assembled_at_utc": assembled,
        "supported_provider_keys": list(SUPPORTED_PROVIDERS),
        "provider_keys_present": present,
        "input_snapshot_count": len(inputs),
        "unique_snapshot_count": len(unique),
        "exact_duplicate_count": duplicates,
        "unique_game_count": len({int(row["official_game_id"]) for row in unique}),
        "game_phase_group_count": len(groups),
        "dual_provider_game_phase_group_count": sum(
            row["all_supported_providers_present"] for row in groups
        ),
        "provider_input_counts": input_counts,
        "provider_unique_counts": unique_counts,
        "source_record_keys": [str(row["record_key"]) for row in inputs],
        "source_snapshots": deepcopy(inputs),
        "game_phase_groups": groups,
        "cross_provider_event_id_join_used": False,
        "team_name_join_used": False,
        "player_name_join_used": False,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "price_fabrication_used": False,
        "fallback_price_fabrication_used": False,
        "best_price_selection_used": False,
        "provider_consensus_used": False,
        "provider_failover_used": False,
        "provider_weighting_used": False,
        "network_io_performed": False,
        "production_runtime_wiring": False,
        "production_database_writes": False,
        "persisted_snapshot_as_model_input": False,
        "persisted_snapshot_as_sportsbook_input": False,
    }
    board["board_sha256"] = _hash(board)
    return board


def validate_multi_provider_shadow_board(board: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(board, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "board_valid": False,
            "failures": ["STEP11C_BOARD_NOT_MAPPING"],
        }
    failures: list[str] = []
    try:
        rebuilt = build_multi_provider_shadow_board(
            board.get("source_snapshots"),
            assembled_at_utc=board.get("assembled_at_utc"),
        )
    except Exception as exc:
        failures.append(f"STEP11C_REBUILD_FAILED:{type(exc).__name__}:{exc}")
    else:
        if dict(board) != rebuilt:
            failures.append("STEP11C_BOARD_EXACT_CONTRACT_MISMATCH")
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "board_valid": not failures,
        "failures": failures,
    }


__all__ = [
    "DATA_TYPE", "SCHEMA_VERSION", "STEP11C_BASE_MAIN_SHA", "BOARD_STATUS",
    "FINAL_CERTIFICATION_MARKER", "SUPPORTED_PROVIDERS", "PROVIDER_NAMES",
    "MAX_INPUT_SNAPSHOTS", "MLBMultiProviderShadowBoardError",
    "shadow_board_manifest", "build_multi_provider_shadow_board",
    "validate_multi_provider_shadow_board",
]
