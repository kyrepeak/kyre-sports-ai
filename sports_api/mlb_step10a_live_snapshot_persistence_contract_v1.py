"""MLB Step 10A — durable live snapshot persistence contract.

Step 10A starts a new MLB persistence block without writing to any database.
It defines the exact, append-only record contract that a later storage adapter
may use for certified Step 9 live game-state and live-market snapshots.

The contract is intentionally downstream-only. Persisted data may not alter the
frozen Step 9 runtime, model/projection math, simulation/probability math,
run-expectancy, line/edge grading, ranking, selection, or sportsbook inputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step9g_postfreeze_handoff_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP9G_FINAL_CERTIFICATION_MARKER,
    HANDOFF_STATUS as STEP9G_HANDOFF_STATUS,
)

DATA_TYPE = "mlb_live_snapshot_persistence_record_v1"
SCHEMA_VERSION = 1
STEP10A_BASE_MAIN_SHA = "21e96c8fece99fc49feff0768d5cd9602f57afda"
CONTRACT_STATUS = "STEP10A_DURABLE_LIVE_SNAPSHOT_PERSISTENCE_CONTRACT_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP10A_DURABLE_LIVE_SNAPSHOT_PERSISTENCE_CONTRACT_GREEN"

SNAPSHOT_SOURCE_CONTRACTS = {
    "live_game_state": {
        "source_data_type": "mlb_live_game_state_api_response_v1",
        "source_schema_version": 1,
    },
    "live_market": {
        "source_data_type": "mlb_inplay_odds_api_response_v1",
        "source_schema_version": 1,
    },
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _utc_rfc3339(value: Any) -> str | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def persistence_contract_manifest() -> dict[str, Any]:
    """Return the immutable Step 10A contract declaration."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step10a_base_main_sha": STEP10A_BASE_MAIN_SHA,
        "contract_status": CONTRACT_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step9g_handoff_status_required": STEP9G_HANDOFF_STATUS,
        "step9g_handoff_marker_required": STEP9G_FINAL_CERTIFICATION_MARKER,
        "snapshot_source_contracts": {
            key: dict(value) for key, value in SNAPSHOT_SOURCE_CONTRACTS.items()
        },
        "database_writes_enabled_by_step10a": False,
        "database_adapter_added_by_step10a": False,
        "runtime_files_changed_by_step10a": False,
        "append_only_required": True,
        "overwrite_allowed": False,
        "upsert_allowed": False,
        "delete_allowed": False,
        "backfill_fabrication_allowed": False,
        "exact_official_game_id_required": True,
        "source_payload_hash_required": True,
        "utc_observation_timestamp_required": True,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        **PROTECTED_INVARIANTS,
    }


def build_live_snapshot_persistence_record(
    *,
    snapshot_kind: str,
    official_game_id: int,
    observed_at_utc: str,
    source_data_type: str,
    source_schema_version: int,
    payload_sha256: str,
    source_complete: bool,
    step9g_handoff_status: str,
    step9g_handoff_marker: str,
) -> dict[str, Any]:
    """Build one validated append-only persistence record without doing I/O."""
    if snapshot_kind not in SNAPSHOT_SOURCE_CONTRACTS:
        raise ValueError("unsupported snapshot_kind")
    if not isinstance(official_game_id, int) or isinstance(official_game_id, bool) or official_game_id <= 0:
        raise ValueError("official_game_id must be a positive integer")

    canonical_timestamp = _utc_rfc3339(observed_at_utc)
    if canonical_timestamp is None:
        raise ValueError("observed_at_utc must be a valid UTC RFC3339 timestamp ending in Z")

    expected_source = SNAPSHOT_SOURCE_CONTRACTS[snapshot_kind]
    if source_data_type != expected_source["source_data_type"]:
        raise ValueError("source_data_type does not match snapshot_kind")
    if (
        not isinstance(source_schema_version, int)
        or isinstance(source_schema_version, bool)
        or source_schema_version != expected_source["source_schema_version"]
    ):
        raise ValueError("source_schema_version does not match snapshot_kind")
    if not isinstance(payload_sha256, str) or _SHA256_RE.fullmatch(payload_sha256) is None:
        raise ValueError("payload_sha256 must be exactly 64 lowercase hex characters")
    if type(source_complete) is not bool:
        raise ValueError("source_complete must be an exact boolean")
    if step9g_handoff_status != STEP9G_HANDOFF_STATUS:
        raise ValueError("Step 9G handoff status is not certified")
    if step9g_handoff_marker != STEP9G_FINAL_CERTIFICATION_MARKER:
        raise ValueError("Step 9G certification marker is not certified")

    record_key = (
        f"mlb:{official_game_id}:{snapshot_kind}:"
        f"{canonical_timestamp}:{payload_sha256}"
    )
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "snapshot_kind": snapshot_kind,
        "official_game_id": official_game_id,
        "observed_at_utc": canonical_timestamp,
        "source_data_type": source_data_type,
        "source_schema_version": source_schema_version,
        "payload_sha256": payload_sha256,
        "source_complete": source_complete,
        "step9g_handoff_status": step9g_handoff_status,
        "step9g_handoff_marker": step9g_handoff_marker,
        "record_key": record_key,
        "append_only_required": True,
        "overwrite_allowed": False,
        "upsert_allowed": False,
        "delete_allowed": False,
        "backfill_fabrication_allowed": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
    }


def validate_live_snapshot_persistence_record(record: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate a candidate record and fail closed without mutation or I/O."""
    failures: list[str] = []
    if not isinstance(record, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "record_valid": False,
            "failures": ["STEP10A_RECORD_MISSING_OR_NOT_MAPPING"],
        }

    try:
        expected = build_live_snapshot_persistence_record(
            snapshot_kind=record.get("snapshot_kind"),
            official_game_id=record.get("official_game_id"),
            observed_at_utc=record.get("observed_at_utc"),
            source_data_type=record.get("source_data_type"),
            source_schema_version=record.get("source_schema_version"),
            payload_sha256=record.get("payload_sha256"),
            source_complete=record.get("source_complete"),
            step9g_handoff_status=record.get("step9g_handoff_status"),
            step9g_handoff_marker=record.get("step9g_handoff_marker"),
        )
    except ValueError as exc:
        failures.append(f"STEP10A_RECORD_CONTRACT_INVALID:{exc}")
        expected = None

    if record.get("data_type") != DATA_TYPE:
        failures.append("STEP10A_DATA_TYPE_MISMATCH")
    if record.get("schema_version") != SCHEMA_VERSION or type(record.get("schema_version")) is not int:
        failures.append("STEP10A_SCHEMA_VERSION_MISMATCH")

    for key, expected_value in {
        "append_only_required": True,
        "overwrite_allowed": False,
        "upsert_allowed": False,
        "delete_allowed": False,
        "backfill_fabrication_allowed": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
    }.items():
        if record.get(key) is not expected_value:
            failures.append(f"STEP10A_INVARIANT_MISMATCH:{key}")

    if expected is not None and record.get("record_key") != expected["record_key"]:
        failures.append("STEP10A_RECORD_KEY_MISMATCH")

    failures = list(dict.fromkeys(failures))
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "record_valid": not failures,
        "record_key": record.get("record_key"),
        "failures": failures,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP10A_BASE_MAIN_SHA",
    "CONTRACT_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "SNAPSHOT_SOURCE_CONTRACTS",
    "persistence_contract_manifest",
    "build_live_snapshot_persistence_record",
    "validate_live_snapshot_persistence_record",
]
