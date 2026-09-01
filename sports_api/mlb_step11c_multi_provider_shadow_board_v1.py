"""MLB Step 11C — multi-provider normalization shadow board.

Step 11A froze the provider-neutral game-market snapshot contract and Step 11B
added a shadow-only DraftKings adapter. Step 11C combines already-certified
FanDuel and DraftKings Step 11A snapshots into one deterministic, read-only
shadow board keyed only by exact official MLB gamePk plus market phase.

This layer deliberately does *not* choose a best price, compute consensus,
fail over between books, call a network, write persistence, or feed sportsbook
prices into model math. It is a comparison/visibility boundary only.
"""
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
PROVIDER_NAMES = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
}
MAX_INPUT_SNAPSHOTS = 500


class MLBMultiProviderShadowBoardError(ValueError):
    """Step 11C input violates the certified shadow-board boundary."""


def shadow_board_manifest() -> dict[str, Any]:
    """Return the immutable Step 11C behavior boundary."""
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
        raise MLBMultiProviderShadowBoardError(
            f"{field} must be UTC RFC3339 ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBMultiProviderShadowBoardError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBMultiProviderShadowBoardError(f"{field} must be UTC")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_source_snapshot(
    snapshot: Any,
    *,
    assembled_at: datetime,
) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise MLBMultiProviderShadowBoardError(
            "every source snapshot must be a mapping"
        )

    validation = validate_market_provider_game_snapshot(snapshot)
    if validation.get("snapshot_valid") is not True:
        raise MLBMultiProviderShadowBoardError(
            f"invalid Step 11A source snapshot: {validation.get('failures')}"
        )

    normalized = deepcopy(dict(snapshot))
    provider_key = normalized.get("provider_key")
    if provider_key not in SUPPORTED_PROVIDERS:
        raise MLBMultiProviderShadowBoardError(
            f"unsupported provider_key: {provider_key!r}"
        )
    if normalized.get("provider_name") != PROVIDER_NAMES[provider_key]:
        raise MLBMultiProviderShadowBoardError(
            f"provider_name mismatch for {provider_key}"
        )

    _, observed_at = _utc_z(
        normalized.get("observed_at_utc"), "source_snapshot.observed_at_utc"
    )
    if observed_at > assembled_at:
        raise MLBMultiProviderShadowBoardError(
            "source snapshot observed_at_utc cannot be after assembled_at_utc"
        )
    return normalized


def _provider_view(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider_key": snapshot["provider_key"],
        "provider_name": snapshot["provider_name"],
        "provider_event_id": snapshot["provider_event_id"],
        "record_key": snapshot["record_key"],
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "observed_at_utc": snapshot["observed_at_utc"],
        "source_collected_at_utc": snapshot["source_collected_at_utc"],
        "transport": snapshot["transport"],
        "source_payload_sha256": snapshot["source_payload_sha256"],
        "source_complete": snapshot["source_complete"],
        "market_count": snapshot["market_count"],
        "fully_priced": snapshot["fully_priced"],
        "market_availability": deepcopy(snapshot["market_availability"]),
        "markets": deepcopy(snapshot["markets"]),
    }


def _market_view(
    market_name: str,
    providers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for snapshot in providers:
        market = snapshot["markets"].get(market_name)
        if market is None:
            continue
        rows.append(
            {
                "provider_key": snapshot["provider_key"],
                "provider_name": snapshot["provider_name"],
                "provider_event_id": snapshot["provider_event_id"],
                "record_key": snapshot["record_key"],
                "observed_at_utc": snapshot["observed_at_utc"],
                "market": deepcopy(market),
            }
        )
    rows.sort(key=lambda row: row["provider_key"])
    return {
        "market_name": market_name,
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
    """Build a deterministic shadow board from current certified provider records.

    One distinct current record per provider/gamePk/phase is allowed. Repeated
    copies of the exact same record_key are harmless and deduplicated for board
    views. Two different record_keys for the same provider/gamePk/phase are
    rejected rather than choosing a "latest" record implicitly.
    """
    if not isinstance(source_snapshots, Sequence) or isinstance(
        source_snapshots, (str, bytes)
    ):
        raise MLBMultiProviderShadowBoardError(
            "source_snapshots must be a sequence"
        )
    if not source_snapshots:
        raise MLBMultiProviderShadowBoardError(
            "source_snapshots must not be empty"
        )
    if len(source_snapshots) > MAX_INPUT_SNAPSHOTS:
        raise MLBMultiProviderShadowBoardError(
            f"at most {MAX_INPUT_SNAPSHOTS} source snapshots are allowed"
        )

    assembled, assembled_dt = _utc_z(assembled_at_utc, "assembled_at_utc")
    normalized_inputs = [
        _normalize_source_snapshot(snapshot, assembled_at=assembled_dt)
        for snapshot in source_snapshots
    ]
    normalized_inputs.sort(
        key=lambda row: (
            int(row["official_game_id"]),
            str(row["market_phase"]),
            str(row["provider_key"]),
            str(row["record_key"]),
        )
    )

    seen_record_keys: set[str] = set()
    slot_record_keys: dict[tuple[int, str, str], str] = {}
    unique_snapshots: list[dict[str, Any]] = []
    exact_duplicate_count = 0

    for snapshot in normalized_inputs:
        record_key = str(snapshot["record_key"])
        slot = (
            int(snapshot["official_game_id"]),
            str(snapshot["market_phase"]),
            str(snapshot["provider_key"]),
        )
        previous_slot_record = slot_record_keys.get(slot)

        if record_key in seen_record_keys:
            if previous_slot_record not in (None, record_key):
                raise MLBMultiProviderShadowBoardError(
                    "duplicate record_key conflicts with provider slot"
                )
            exact_duplicate_count += 1
            continue

        if previous_slot_record is not None and previous_slot_record != record_key:
            raise MLBMultiProviderShadowBoardError(
                "multiple distinct current snapshots for the same "
                "provider/gamePk/market_phase are ambiguous"
            )

        seen_record_keys.add(record_key)
        slot_record_keys[slot] = record_key
        unique_snapshots.append(snapshot)

    groups: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for snapshot in unique_snapshots:
        group_key = (
            int(snapshot["official_game_id"]),
            str(snapshot["market_phase"]),
        )
        groups.setdefault(group_key, []).append(snapshot)

    group_rows: list[dict[str, Any]] = []
    for (game_id, phase), providers in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][1])
    ):
        providers.sort(key=lambda row: str(row["provider_key"]))
        provider_keys = [str(row["provider_key"]) for row in providers]
        market_views = [
            _market_view(market_name, providers)
            for market_name in SUPPORTED_CORE_MARKETS
        ]
        group_rows.append(
            {
                "official_game_id": game_id,
                "market_phase": phase,
                "provider_count": len(providers),
                "provider_keys": provider_keys,
                "all_supported_providers_present": set(provider_keys)
                == set(SUPPORTED_PROVIDERS),
                "fully_priced_provider_count": sum(
                    1 for row in providers if row["fully_priced"] is True
                ),
                "all_present_providers_fully_priced": all(
                    row["fully_priced"] is True for row in providers
                ),
                "market_overlap_count": sum(
                    1 for row in market_views if row["cross_provider_overlap"]
                ),
                "providers": [_provider_view(row) for row in providers],
                "market_views": market_views,
            }
        )

    provider_input_counts = {
        key: sum(1 for row in normalized_inputs if row["provider_key"] == key)
        for key in SUPPORTED_PROVIDERS
    }
    provider_unique_counts = {
        key: sum(1 for row in unique_snapshots if row["provider_key"] == key)
        for key in SUPPORTED_PROVIDERS
    }
    provider_keys_present = [
        key for key in SUPPORTED_PROVIDERS if provider_unique_counts[key] > 0
    ]

    board: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "board_status": BOARD_STATUS,
        "assembled_at_utc": assembled,
        "supported_provider_keys": list(SUPPORTED_PROVIDERS),
        "provider_keys_present": provider_keys_present,
        "input_snapshot_count": len(normalized_inputs),
        "unique_snapshot_count": len(unique_snapshots),
        "exact_duplicate_count": exact_duplicate_count,
        "unique_game_count": len(
            {int(row["official_game_id"]) for row in unique_snapshots}
        ),
        "game_phase_group_count": len(group_rows),
        "dual_provider_game_phase_group_count": sum(
            1 for row in group_rows if row["all_supported_providers_present"]
        ),
        "provider_input_counts": provider_input_counts,
        "provider_unique_counts": provider_unique_counts,
        "source_record_keys": [
            str(row["record_key"]) for row in normalized_inputs
        ],
        "source_snapshots": deepcopy(normalized_inputs),
        "game_phase_groups": group_rows,
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
    board["board_sha256"] = _sha256(board)
    return board


def validate_multi_provider_shadow_board(
    board: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Fail closed and non-mutatingly rebuild the full Step 11C board."""
    failures: list[str] = []
    if not isinstance(board, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "board_valid": False,
            "failures": ["STEP11C_BOARD_NOT_MAPPING"],
        }

    try:
        rebuilt = build_multi_provider_shadow_board(
            board.get("source_snapshots"),
            assembled_at_utc=board.get("assembled_at_utc"),
        )
    except Exception as exc:
        failures.append(
            f"STEP11C_REBUILD_FAILED:{type(exc).__name__}:{exc}"
        )
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
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP11C_BASE_MAIN_SHA",
    "BOARD_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "SUPPORTED_PROVIDERS",
    "PROVIDER_NAMES",
    "MAX_INPUT_SNAPSHOTS",
    "MLBMultiProviderShadowBoardError",
    "shadow_board_manifest",
    "build_multi_provider_shadow_board",
    "validate_multi_provider_shadow_board",
]
