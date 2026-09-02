"""WNBA Step 14A: durable persistence contract and PostgreSQL schema boundary.

Step 13 is frozen and returns a validated controller-state handoff. Step 14A does
not write a database. It defines the only checkpoint envelope and relational
schema that later Step-14 adapters may persist. This keeps the first persistence
change content-addressed, release-pinned, JSON-safe, slate-scoped, and fail-closed.

Actual PostgreSQL/Supabase reads and writes, durable restart recovery, and
cross-process leases are intentionally deferred to later Step-14 substeps.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import os
from typing import Any

from sports_api import wnba_step13_release_freeze as step13_release
from sports_api import wnba_step13c_reliability_recovery as step13c

SOURCE = "Kyre Sports API WNBA Step 14A durable persistence contract"
SCHEMA_VERSION = "wnba_step_14a_persistence_contract_v1"
ENVELOPE_SCHEMA_VERSION = "wnba_step_14a_checkpoint_envelope_v1"
CONTRACT_ID = "wnba_step14a_durable_checkpoint_contract_2026_regular_v1"
SEASON = 2026
SEASON_TYPE = "Regular Season"
BRANCH = "wnba-step14a-persistence-contract-20260828"

STEP13D_FROZEN_SHA = "41d1ce4a3a88020199a3de42514b3cd744b1e831"
STEP13C_FROZEN_SHA = "23c1a9d4bb977a38048073ce7937b8efd983b998"
STEP13B_FROZEN_SHA = "0a0e4381d0a4deac6bbd3741f893214e99afef7b"
STEP13A_FROZEN_SHA = "eaa744ae097a94d5f54c490ab13ca7d66bb725c2"
STEP13_RELEASE_ID = "wnba_step13_scheduler_refresh_automation_2026_regular_season_frozen_v1"
STEP13_RELEASE_CONTENT_SHA256 = "7857651813d8114de58d21163fdb8f3eceb695a43834c3eb48b55bb5c01c9046"
STEP12_RELEASE_CONTENT_SHA256 = step13_release.STEP12_RELEASE_CONTENT_SHA256

STEP14A_PERSISTENCE_CONTRACT_ENABLED_ENV = "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED"

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
DATABASE_SCHEMA_DEFINITION_ALLOWED = True
DURABLE_CHECKPOINT_ENVELOPE_ALLOWED = True
DATABASE_READ_ALLOWED = False
DATABASE_WRITE_ALLOWED = False
PERSISTENCE_RUNTIME_ENABLED = False
SUPABASE_WRITE_ALLOWED = False
DURABLE_RESTART_RECOVERY_ALLOWED = False
DURABLE_DISTRIBUTED_LEASE_ALLOWED = False
CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
BASKETBALL_MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False

DATABASE_DIALECT = "postgresql"
DATABASE_SCHEMA_NAME = "kyre_runtime"
CHECKPOINT_TABLE_NAME = "wnba_runtime_checkpoints"
CHECKPOINT_HEAD_TABLE_NAME = "wnba_runtime_checkpoint_heads"
SQL_SCHEMA_PATH = "sports_api/sql/wnba_step14a_persistence_schema.sql"

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)

_REQUIRED_TRUE_ENV_KEYS = (
    "WNBA_STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED",
    "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED",
    "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED",
    "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED",
    "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
    "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
    "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
    "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
    "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
)

_ENVELOPE_REQUIRED_FIELDS = {
    "data_type",
    "schema_version",
    "contract_id",
    "season",
    "season_type",
    "slate_date",
    "checkpoint_key",
    "step13d_frozen_sha",
    "step13_release_id",
    "step13_release_content_sha256",
    "source_step13c_frozen_sha",
    "source_reliability_content_sha256",
    "source_status",
    "source_health",
    "controller_state",
    "controller_state_sha256",
    "created_at_utc",
    "envelope_content_sha256",
}


class WNBAStep14PersistenceContractDisabledError(RuntimeError):
    """Raised when Step 14A or its frozen parent gates are not isolated."""


class WNBAStep14PersistenceContractInputError(ValueError):
    """Raised when source state or checkpoint metadata is malformed."""


class WNBAStep14PersistenceContractIntegrityError(RuntimeError):
    """Raised when frozen lineage, content hashes, or safety boundaries drift."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step14a_persistence_contract_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP14A_PERSISTENCE_CONTRACT_ENABLED_ENV))


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _valid_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _parse_slate_date(value: Any) -> date:
    text = str(value or "").strip()
    try:
        result = date.fromisoformat(text)
    except ValueError as exc:
        raise WNBAStep14PersistenceContractInputError(
            "Step 14A slate_date must be YYYY-MM-DD."
        ) from exc
    if result.year != SEASON:
        raise WNBAStep14PersistenceContractInputError(
            "Step 14A is certified only for the 2026 WNBA Regular Season."
        )
    return result


def _parse_timestamp(value: Any, label: str) -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WNBAStep14PersistenceContractInputError(
            f"Step 14A {label} must be an ISO-8601 timestamp."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WNBAStep14PersistenceContractInputError(
            f"Step 14A {label} must be timezone-aware."
        )
    return parsed.astimezone(timezone.utc)


def _strict_json_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WNBAStep14PersistenceContractInputError(
            f"Step 14A {label} must be a JSON object."
        )
    try:
        raw = json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        normalized = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise WNBAStep14PersistenceContractInputError(
            f"Step 14A {label} must be strict JSON-compatible."
        ) from exc
    if not isinstance(normalized, dict):
        raise WNBAStep14PersistenceContractInputError(
            f"Step 14A {label} must normalize to a JSON object."
        )
    return normalized


def _assert_contract_integrity(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step14a_persistence_contract_enabled(source):
        raise WNBAStep14PersistenceContractDisabledError(
            f"Step 14A requires {STEP14A_PERSISTENCE_CONTRACT_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep14PersistenceContractDisabledError(
            "Step 14A refuses production/runtime-persistence/write switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep14PersistenceContractDisabledError(
            "Step 14A requires the frozen Step-13/Step-12 runtime gates: "
            + ", ".join(missing)
        )

    exact = {
        "step13_release_parent": step13_release.STEP13C_FROZEN_SHA == STEP13C_FROZEN_SHA,
        "step13c_parent": step13c.STEP13B_FROZEN_SHA == STEP13B_FROZEN_SHA,
        "step13c_step13a": step13c.STEP13A_FROZEN_SHA == STEP13A_FROZEN_SHA,
        "step13_release_id": step13_release.RELEASE_ID == STEP13_RELEASE_ID,
        "step12_release_hash": (
            step13_release.STEP12_RELEASE_CONTENT_SHA256
            == STEP12_RELEASE_CONTENT_SHA256
        ),
    }
    failed = [name for name, ok in exact.items() if not ok]
    if failed:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A frozen lineage drift: " + ", ".join(failed)
        )

    false_constants = {
        "production": PRODUCTION_ACTIVATION_ALLOWED,
        "public_api": PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "database_read": DATABASE_READ_ALLOWED,
        "database_write": DATABASE_WRITE_ALLOWED,
        "persistence_runtime": PERSISTENCE_RUNTIME_ENABLED,
        "supabase_write": SUPABASE_WRITE_ALLOWED,
        "durable_restart": DURABLE_RESTART_RECOVERY_ALLOWED,
        "distributed_lease": DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        "cross_process_guard": CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
        "wagering": WAGERING_ALLOWED,
        "authentication": AUTHENTICATION_ALLOWED,
        "cookies": COOKIES_ALLOWED,
        "background_daemon": BACKGROUND_DAEMON_ALLOWED,
        "background_thread": BACKGROUND_THREAD_ALLOWED,
        "basketball_model_mutation": BASKETBALL_MODEL_MUTATION_ALLOWED,
        "ranking_mutation": RANKING_MUTATION_ALLOWED,
    }
    drift = [name for name, value in false_constants.items() if value is not False]
    if drift:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A safety constant drift: " + ", ".join(drift)
        )
    if DATABASE_SCHEMA_DEFINITION_ALLOWED is not True:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A schema-definition capability drift."
        )
    if DURABLE_CHECKPOINT_ENVELOPE_ALLOWED is not True:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A checkpoint-envelope capability drift."
        )

    manifest = step13_release.build_step13d_release_manifest(
        env=source,
        generated_at_utc="2026-08-28T00:00:00+00:00",
    )
    if manifest.get("release_content_sha256") != STEP13_RELEASE_CONTENT_SHA256:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A frozen Step-13 release hash drift."
        )


def _verify_step13c_response(response: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    if not isinstance(response, Mapping):
        raise WNBAStep14PersistenceContractInputError(
            "Step 14A requires a Step-13C response object."
        )
    if response.get("data_type") != "wnba_step13c_reliability_recovery_response":
        raise WNBAStep14PersistenceContractInputError(
            "Step 14A requires a frozen Step-13C reliability response."
        )
    if response.get("schema_version") != step13c.SCHEMA_VERSION:
        raise WNBAStep14PersistenceContractInputError(
            "Step 14A Step-13C response schema drift."
        )
    observed = str(response.get("reliability_content_sha256") or "").strip().lower()
    surface = {
        key: deepcopy(value)
        for key, value in response.items()
        if key not in {"generated_at_utc", "reliability_content_sha256"}
    }
    expected = _canonical_hash(surface)
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A detected Step-13C reliability content-hash mismatch."
        )
    lineage = response.get("lineage")
    if not isinstance(lineage, Mapping):
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A Step-13C lineage is missing."
        )
    expected_lineage = {
        "step13b_frozen_sha": STEP13B_FROZEN_SHA,
        "step13a_frozen_sha": STEP13A_FROZEN_SHA,
        "step12d_frozen_sha": step13_release.STEP12D_FROZEN_SHA,
    }
    for key, expected_value in expected_lineage.items():
        if lineage.get(key) != expected_value:
            raise WNBAStep14PersistenceContractIntegrityError(
                f"Step 14A frozen source lineage drift: {key}."
            )
    state = response.get("final_controller_state_for_restart_handoff")
    normalized_state = _strict_json_object(state, "controller state")
    return normalized_state, observed


def checkpoint_key_for_slate(slate_date: str | date) -> str:
    parsed = _parse_slate_date(
        slate_date.isoformat() if isinstance(slate_date, date) else slate_date
    )
    return f"wnba:runtime:{SEASON}:regular-season:{parsed.isoformat()}"


def _envelope_hash_surface(envelope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in envelope.items()
        if key not in {"created_at_utc", "envelope_content_sha256"}
    }


def build_step14a_checkpoint_envelope(
    *,
    step13c_response: Mapping[str, Any],
    slate_date: str | date,
    env: Mapping[str, str] | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic, JSON-safe durable-checkpoint candidate envelope."""
    _assert_contract_integrity(env)
    parsed_slate = _parse_slate_date(
        slate_date.isoformat() if isinstance(slate_date, date) else slate_date
    )
    state, source_hash = _verify_step13c_response(step13c_response)

    state_slate = state.get("slate_date")
    if state_slate is not None and str(state_slate) != parsed_slate.isoformat():
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A refuses controller state from a different slate."
        )
    state_season = state.get("season")
    if state_season is not None and state_season != SEASON:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A refuses controller state from a different season."
        )

    created = (
        _parse_timestamp(created_at_utc, "created_at_utc")
        if created_at_utc is not None
        else datetime.now(timezone.utc)
    )
    controller_state_sha256 = _canonical_hash(state)
    envelope = {
        "data_type": "wnba_step14a_checkpoint_envelope",
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "slate_date": parsed_slate.isoformat(),
        "checkpoint_key": checkpoint_key_for_slate(parsed_slate),
        "step13d_frozen_sha": STEP13D_FROZEN_SHA,
        "step13_release_id": STEP13_RELEASE_ID,
        "step13_release_content_sha256": STEP13_RELEASE_CONTENT_SHA256,
        "source_step13c_frozen_sha": STEP13C_FROZEN_SHA,
        "source_reliability_content_sha256": source_hash,
        "source_status": str(step13c_response.get("status") or "").strip(),
        "source_health": str(step13c_response.get("health") or "").strip(),
        "controller_state": state,
        "controller_state_sha256": controller_state_sha256,
        "created_at_utc": created.isoformat(),
    }
    envelope["envelope_content_sha256"] = _canonical_hash(
        _envelope_hash_surface(envelope)
    )
    _assert_contract_integrity(env)
    return envelope


def validate_step14a_checkpoint_envelope(
    envelope: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    expected_slate_date: str | date | None = None,
) -> dict[str, Any]:
    """Validate an envelope before any later adapter may read or write it."""
    _assert_contract_integrity(env)
    if not isinstance(envelope, Mapping):
        raise WNBAStep14PersistenceContractInputError(
            "Step 14A checkpoint envelope must be an object."
        )
    keys = set(envelope)
    missing = sorted(_ENVELOPE_REQUIRED_FIELDS - keys)
    unknown = sorted(keys - _ENVELOPE_REQUIRED_FIELDS)
    if missing:
        raise WNBAStep14PersistenceContractInputError(
            "Missing Step-14A checkpoint fields: " + ", ".join(missing)
        )
    if unknown:
        raise WNBAStep14PersistenceContractInputError(
            "Unknown Step-14A checkpoint fields: " + ", ".join(unknown)
        )
    exact = {
        "data_type": envelope.get("data_type") == "wnba_step14a_checkpoint_envelope",
        "schema_version": envelope.get("schema_version") == ENVELOPE_SCHEMA_VERSION,
        "contract_id": envelope.get("contract_id") == CONTRACT_ID,
        "season": envelope.get("season") == SEASON,
        "season_type": envelope.get("season_type") == SEASON_TYPE,
        "step13d_frozen_sha": envelope.get("step13d_frozen_sha") == STEP13D_FROZEN_SHA,
        "step13_release_id": envelope.get("step13_release_id") == STEP13_RELEASE_ID,
        "step13_release_hash": (
            envelope.get("step13_release_content_sha256")
            == STEP13_RELEASE_CONTENT_SHA256
        ),
        "source_step13c_sha": (
            envelope.get("source_step13c_frozen_sha") == STEP13C_FROZEN_SHA
        ),
    }
    failed = [name for name, ok in exact.items() if not ok]
    if failed:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A checkpoint release/lineage drift: " + ", ".join(failed)
        )

    parsed_slate = _parse_slate_date(envelope.get("slate_date"))
    expected_key = checkpoint_key_for_slate(parsed_slate)
    if envelope.get("checkpoint_key") != expected_key:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A checkpoint key does not match slate identity."
        )
    if expected_slate_date is not None:
        expected_date = _parse_slate_date(
            expected_slate_date.isoformat()
            if isinstance(expected_slate_date, date)
            else expected_slate_date
        )
        if parsed_slate != expected_date:
            raise WNBAStep14PersistenceContractIntegrityError(
                "Step 14A checkpoint belongs to a different requested slate."
            )

    _parse_timestamp(envelope.get("created_at_utc"), "created_at_utc")
    state = _strict_json_object(envelope.get("controller_state"), "controller state")
    expected_state_hash = _canonical_hash(state)
    observed_state_hash = str(envelope.get("controller_state_sha256") or "").strip().lower()
    if not _valid_sha256(observed_state_hash) or observed_state_hash != expected_state_hash:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A controller-state content hash mismatch."
        )
    source_hash = str(
        envelope.get("source_reliability_content_sha256") or ""
    ).strip().lower()
    if not _valid_sha256(source_hash):
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A source reliability hash is invalid."
        )
    observed_envelope_hash = str(
        envelope.get("envelope_content_sha256") or ""
    ).strip().lower()
    expected_envelope_hash = _canonical_hash(_envelope_hash_surface(envelope))
    if (
        not _valid_sha256(observed_envelope_hash)
        or observed_envelope_hash != expected_envelope_hash
    ):
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A checkpoint envelope content hash mismatch."
        )

    state_slate = state.get("slate_date")
    if state_slate is not None and str(state_slate) != parsed_slate.isoformat():
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A checkpoint state/slate mismatch."
        )
    state_season = state.get("season")
    if state_season is not None and state_season != SEASON:
        raise WNBAStep14PersistenceContractIntegrityError(
            "Step 14A checkpoint state/season mismatch."
        )

    _assert_contract_integrity(env)
    return deepcopy(dict(envelope))


def build_step14a_schema_manifest(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return the frozen relational contract; this function performs no I/O."""
    _assert_contract_integrity(env)
    manifest = {
        "data_type": "wnba_step14a_persistence_schema_manifest",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "contract_id": CONTRACT_ID,
        "database_dialect": DATABASE_DIALECT,
        "database_schema": DATABASE_SCHEMA_NAME,
        "sql_schema_path": SQL_SCHEMA_PATH,
        "tables": {
            "checkpoints": {
                "name": CHECKPOINT_TABLE_NAME,
                "append_only_contract": True,
                "checkpoint_key_slate_scoped": True,
                "version_must_be_positive": True,
                "envelope_json_required": True,
                "envelope_hash_required": True,
                "controller_state_hash_required": True,
                "unique_key_version": True,
                "unique_key_envelope_hash": True,
            },
            "heads": {
                "name": CHECKPOINT_HEAD_TABLE_NAME,
                "one_head_per_checkpoint_key": True,
                "points_to_checkpoint": True,
                "compare_and_swap_version_boundary": True,
            },
        },
        "lineage": {
            "step13d_frozen_sha": STEP13D_FROZEN_SHA,
            "step13c_frozen_sha": STEP13C_FROZEN_SHA,
            "step13_release_id": STEP13_RELEASE_ID,
            "step13_release_content_sha256": STEP13_RELEASE_CONTENT_SHA256,
            "step12_release_content_sha256": STEP12_RELEASE_CONTENT_SHA256,
        },
        "capability_boundary": {
            "schema_definition_allowed": True,
            "checkpoint_envelope_allowed": True,
            "database_read_allowed": False,
            "database_write_allowed": False,
            "persistence_runtime_enabled": False,
            "supabase_write_allowed": False,
            "durable_restart_recovery_allowed": False,
            "durable_distributed_lease_allowed": False,
            "cross_process_duplicate_run_guard_allowed": False,
            "production_activation_allowed": False,
        },
        "phase_boundary": {
            "step14_started": True,
            "step14a_contract_complete_candidate": True,
            "database_adapter_not_started": True,
            "database_writes_not_started": True,
            "durable_restart_recovery_not_started": True,
            "distributed_lease_not_started": True,
            "production_not_started": True,
        },
    }
    manifest["manifest_content_sha256"] = _canonical_hash(manifest)
    return manifest


__all__ = [
    "BRANCH",
    "CHECKPOINT_HEAD_TABLE_NAME",
    "CHECKPOINT_TABLE_NAME",
    "CONTRACT_ID",
    "DATABASE_DIALECT",
    "DATABASE_SCHEMA_DEFINITION_ALLOWED",
    "DATABASE_SCHEMA_NAME",
    "DATABASE_READ_ALLOWED",
    "DATABASE_WRITE_ALLOWED",
    "DEFAULT_ENABLED",
    "DURABLE_CHECKPOINT_ENVELOPE_ALLOWED",
    "DURABLE_DISTRIBUTED_LEASE_ALLOWED",
    "DURABLE_RESTART_RECOVERY_ALLOWED",
    "ENVELOPE_SCHEMA_VERSION",
    "PERSISTENCE_RUNTIME_ENABLED",
    "SCHEMA_VERSION",
    "SEASON",
    "SEASON_TYPE",
    "SOURCE",
    "SQL_SCHEMA_PATH",
    "STEP13C_FROZEN_SHA",
    "STEP13D_FROZEN_SHA",
    "STEP13_RELEASE_CONTENT_SHA256",
    "STEP13_RELEASE_ID",
    "STEP14A_PERSISTENCE_CONTRACT_ENABLED_ENV",
    "SUPABASE_WRITE_ALLOWED",
    "WNBAStep14PersistenceContractDisabledError",
    "WNBAStep14PersistenceContractInputError",
    "WNBAStep14PersistenceContractIntegrityError",
    "build_step14a_checkpoint_envelope",
    "build_step14a_schema_manifest",
    "checkpoint_key_for_slate",
    "step14a_persistence_contract_enabled",
    "validate_step14a_checkpoint_envelope",
]
