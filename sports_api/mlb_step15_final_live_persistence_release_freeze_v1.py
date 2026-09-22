"""MLB Step 15C — final live persistence release freeze.

Step 15A proved the real Supabase PostgreSQL schema matches the frozen Step-14
persistence contract. Step 15B then executed the frozen checkpoint and lease SQL
semantics against the live database inside one explicit transaction and rolled
everything back.

Step 15C adds no runtime behavior. It freezes that certified live schema,
transaction semantics, access boundary, and clean-table state as the final
Step-15 persistence release. Production scheduling, global persistence runtime,
automatic restart execution, background workers, public persistence APIs,
Supabase REST writes, actionable outputs, wagering, provider/sportsbook calls,
and all protected model/ranking behavior remain OFF.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sports_api import mlb_step14_final_persistence_freeze_v1 as step14d
from sports_api import mlb_step15a_live_postgresql_preflight_v1 as step15a
from sports_api import mlb_step15b_live_adapter_transaction_smoke_v1 as step15b
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step15_final_live_persistence_release_v1"
SCHEMA_VERSION = 1
RELEASE_VERSION = "mlb_step15c_final_live_supabase_persistence_freeze_2026_v1"
RELEASE_STATUS = "STEP15_FINAL_LIVE_PERSISTENCE_FROZEN"
FINAL_CERTIFICATION_MARKER = "MLB_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_GREEN"
RUNTIME_MODE = "SHADOW_ONLY"
RELEASE_ID = "mlb_step15_live_supabase_persistence_2026_regular_season_frozen_v1"

STEP15C_BASE_MAIN_SHA = "315d47be1089c95f45087d6537a8a7e9ac86d9ef"
STEP15B_HEAD_SHA = "260673f312fd556ac245a124bc06dfb2aa4c0d4c"
STEP15B_SOURCE_BLOB_SHA = "568227a4be41cdeb0f7ba8b33468eab738424dca"
STEP15B_SMOKE_MANIFEST_SHA256 = "7262435e2bd5cef26f9205dd756fab254f868722a0c3a089bd0d1212ffd8b41d"
STEP15B_LIVE_EVIDENCE_CONTENT_SHA256 = "e167582075d845b807505a3988fad35fb1a29a7aa3e18de5eb843971aba30af7"
STEP15A_SOURCE_BLOB_SHA = "9000c54df1a9d1bac4aeb143e354fc554129725c"
STEP14D_SOURCE_BLOB_SHA = "8d346c2fb3abf71742c048d5489ac88124b990b6"

FINAL_LIVE_EVIDENCE_PATH = (
    "sports_api/certification/mlb_step15c_final_live_persistence_freeze_evidence.json"
)
FINAL_LIVE_EVIDENCE_CONTENT_SHA256 = (
    "41a40143f212aee44ff263118dcf9d8da398700bf55bd2ce9a58d1157e79c360"
)

EXPECTED_SUPABASE_PROJECT_REF = "jqajcdckalsfizbvngiu"
EXPECTED_MIGRATIONS = {
    "20260901202829": "mlb_step15a_install_frozen_step14_checkpoint_schema",
    "20260901202835": "mlb_step15a_install_frozen_step14_lease_schema",
    "20260901202842": "mlb_step15a_restore_frozen_step14_schema_comments",
}
EXPECTED_TABLES = (
    "mlb_runtime_checkpoints",
    "mlb_runtime_checkpoint_heads",
    "mlb_runtime_leases",
)

STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV = (
    "MLB_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED"
)

DEFAULT_ENABLED = False
LIVE_SCHEMA_DEPLOYMENT_CERTIFIED = True
LIVE_TRANSACTION_SEMANTICS_CERTIFIED = True
FINAL_LIVE_CLEAN_STATE_CERTIFIED = True
LIVE_ACCESS_BOUNDARY_CERTIFIED = True
FROZEN_SQL_FINGERPRINTS_CERTIFIED = True
STEP15_RELEASE_FROZEN = True
DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED = False

PRODUCTION_ACTIVATION_ALLOWED = False
PRODUCTION_SCHEDULER_ALLOWED = False
GLOBAL_PERSISTENCE_RUNTIME_ENABLED = False
AUTOMATIC_RESTART_EXECUTION_ALLOWED = False
BACKGROUND_WORKER_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False
WAGERING_ALLOWED = False
PROVIDER_NETWORK_CALLS_ALLOWED = False
SPORTSBOOK_NETWORK_CALLS_ALLOWED = False
RUNTIME_MUTATION_ALLOWED = False

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
)


class MLBStep15CReleaseFreezeDisabledError(RuntimeError):
    """Raised unless the final Step-15 freeze gate is explicit."""


class MLBStep15CReleaseFreezeIntegrityError(RuntimeError):
    """Raised when frozen lineage, live evidence, or safety boundaries drift."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def step15c_final_live_persistence_freeze_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV))


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(evidence))
    result.pop("observed_at_utc", None)
    result.pop("evidence_content_sha256", None)
    return result


def load_final_live_evidence(
    path: str = FINAL_LIVE_EVIDENCE_PATH,
) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C could not load final live persistence evidence"
        ) from exc
    if not isinstance(evidence, dict):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C evidence must be an object"
        )
    observed = str(evidence.get("evidence_content_sha256") or "").lower()
    expected = _hash(_evidence_hash_surface(evidence))
    if observed != expected or expected != FINAL_LIVE_EVIDENCE_CONTENT_SHA256:
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C final live evidence hash drift"
        )
    return evidence


def validate_final_live_evidence(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    if evidence.get("data_type") != (
        "mlb_step15c_final_live_persistence_freeze_evidence"
    ):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C evidence data_type drift"
        )

    project = evidence.get("supabase_project")
    lineage = evidence.get("frozen_lineage")
    live = evidence.get("live_final_state")
    access = evidence.get("access_boundary")
    activation = evidence.get("activation_boundary")
    scope = evidence.get("scope_notes")
    values = (project, lineage, live, access, activation, scope)
    if not all(isinstance(value, Mapping) for value in values):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C evidence object shape drift"
        )

    if (
        project.get("ref") != EXPECTED_SUPABASE_PROJECT_REF
        or project.get("status") != "ACTIVE_HEALTHY"
        or project.get("region") != "us-west-1"
        or project.get("database_name") != "postgres"
        or str(project.get("postgres_engine")) != "17"
        or project.get("postgres_version") != "17.6"
        or project.get("primary") is not True
    ):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C live project identity/health drift"
        )

    expected_lineage = {
        "step15b_merge_sha": STEP15C_BASE_MAIN_SHA,
        "step15b_head_sha": STEP15B_HEAD_SHA,
        "step15b_source_blob_sha": STEP15B_SOURCE_BLOB_SHA,
        "step15b_smoke_manifest_sha256": STEP15B_SMOKE_MANIFEST_SHA256,
        "step15b_live_evidence_content_sha256": (
            STEP15B_LIVE_EVIDENCE_CONTENT_SHA256
        ),
        "step15a_source_blob_sha": STEP15A_SOURCE_BLOB_SHA,
        "step14d_source_blob_sha": STEP14D_SOURCE_BLOB_SHA,
    }
    if any(lineage.get(key) != value for key, value in expected_lineage.items()):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C frozen lineage evidence drift"
        )

    migrations = live.get("migrations_present")
    tables = live.get("tables_present")
    rows = live.get("row_counts")
    expected_tables = {name: True for name in EXPECTED_TABLES}
    expected_rows = {name: 0 for name in EXPECTED_TABLES}
    if migrations != EXPECTED_MIGRATIONS:
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C migration evidence drift"
        )
    if tables != expected_tables or rows != expected_rows:
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C final live table state drift"
        )
    if live.get("smoke_cleanup_reverified") is not True:
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C smoke cleanup was not reverified"
        )

    for key in (
        "anon_schema_usage",
        "anon_schema_create",
        "authenticated_schema_usage",
        "authenticated_schema_create",
        "service_role_schema_usage",
        "service_role_schema_create",
    ):
        if access.get(key) is not False:
            raise MLBStep15CReleaseFreezeIntegrityError(
                f"Step 15C client schema access drift: {key}"
            )
    if (
        access.get("postgres_schema_usage") is not True
        or access.get("postgres_schema_create") is not True
    ):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C postgres ownership/access drift"
        )
    if access.get("kyre_runtime_security_advisor_finding_count") != 0:
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C kyre_runtime security advisor findings detected"
        )

    if not activation or any(value is not False for value in activation.values()):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C activation boundary drift"
        )

    expected_scope = {
        "connected_supabase_sql_surface_used_for_live_verification": True,
        "direct_psycopg_live_connection_certified": False,
        "live_sql_semantics_certified_by_step15b": True,
        "step15c_adds_runtime_behavior": False,
        "step15c_adds_database_writes": False,
    }
    if any(scope.get(key) != value for key, value in expected_scope.items()):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C scope boundary drift"
        )
    return deepcopy(dict(evidence))


def _assert_integrity(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step15c_final_live_persistence_freeze_enabled(source):
        raise MLBStep15CReleaseFreezeDisabledError(
            f"Step 15C requires "
            f"{STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV}=true"
        )
    forbidden = [
        key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))
    ]
    if forbidden:
        raise MLBStep15CReleaseFreezeDisabledError(
            "Step 15C refuses production/actionable switches: "
            + ", ".join(forbidden)
        )
    if not step15b.step15b_live_adapter_smoke_enabled(source):
        raise MLBStep15CReleaseFreezeDisabledError(
            "Step 15C requires MLB_STEP15B_LIVE_ADAPTER_SMOKE_ENABLED=true"
        )

    smoke = step15b.live_adapter_transaction_smoke_manifest(
        env=source,
        generated_at_utc="2026-09-01T20:48:54.222998+00:00",
    )
    if smoke.get("smoke_manifest_sha256") != STEP15B_SMOKE_MANIFEST_SHA256:
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C Step-15B smoke manifest hash drift"
        )
    if step15b.FINAL_CERTIFICATION_MARKER != (
        "MLB_STEP15B_LIVE_ADAPTER_TRANSACTION_SMOKE_GREEN"
    ):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C Step-15B marker drift"
        )
    if step15a.FINAL_CERTIFICATION_MARKER != (
        "MLB_STEP15A_LIVE_POSTGRESQL_PREFLIGHT_GREEN"
    ):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C Step-15A marker drift"
        )
    if step14d.FINAL_CERTIFICATION_MARKER != (
        "MLB_STEP14D_FINAL_PERSISTENCE_FREEZE_GREEN"
    ):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C Step-14D marker drift"
        )

    preflight = step15a.live_postgresql_preflight_manifest()
    if preflight.get("final_certification_marker") != step15a.FINAL_CERTIFICATION_MARKER:
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C Step-15A manifest drift"
        )
    frozen = step14d.final_persistence_freeze_manifest()
    if frozen.get("final_certification_marker") != step14d.FINAL_CERTIFICATION_MARKER:
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C Step-14D manifest drift"
        )
    step15b.validate_frozen_sql_fingerprints()

    required_true = (
        LIVE_SCHEMA_DEPLOYMENT_CERTIFIED,
        LIVE_TRANSACTION_SEMANTICS_CERTIFIED,
        FINAL_LIVE_CLEAN_STATE_CERTIFIED,
        LIVE_ACCESS_BOUNDARY_CERTIFIED,
        FROZEN_SQL_FINGERPRINTS_CERTIFIED,
        STEP15_RELEASE_FROZEN,
    )
    if any(value is not True for value in required_true):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C certification constant drift"
        )
    forbidden_capabilities = (
        DEFAULT_ENABLED,
        DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED,
        PRODUCTION_ACTIVATION_ALLOWED,
        PRODUCTION_SCHEDULER_ALLOWED,
        GLOBAL_PERSISTENCE_RUNTIME_ENABLED,
        AUTOMATIC_RESTART_EXECUTION_ALLOWED,
        BACKGROUND_WORKER_ALLOWED,
        PUBLIC_PERSISTENCE_API_ALLOWED,
        SUPABASE_REST_WRITE_ALLOWED,
        ACTIONABLE_OUTPUT_ALLOWED,
        WAGERING_ALLOWED,
        PROVIDER_NETWORK_CALLS_ALLOWED,
        SPORTSBOOK_NETWORK_CALLS_ALLOWED,
        RUNTIME_MUTATION_ALLOWED,
    )
    if any(value is not False for value in forbidden_capabilities):
        raise MLBStep15CReleaseFreezeIntegrityError(
            "Step 15C safety constant drift"
        )
    for key, value in PROTECTED_INVARIANTS.items():
        if value is not False:
            raise MLBStep15CReleaseFreezeIntegrityError(
                f"Step 15C protected invariant drift: {key}"
            )

    return validate_final_live_evidence(load_final_live_evidence())


def final_live_persistence_release_manifest(
    *,
    env: Mapping[str, str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    evidence = _assert_integrity(env)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    manifest: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step15c_base_main_sha": STEP15C_BASE_MAIN_SHA,
        "release_id": RELEASE_ID,
        "release_version": RELEASE_VERSION,
        "release_status": RELEASE_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "runtime_mode": RUNTIME_MODE,
        "generated_at_utc": generated,
        "lineage": {
            "step15b_head_sha": STEP15B_HEAD_SHA,
            "step15b_source_blob_sha": STEP15B_SOURCE_BLOB_SHA,
            "step15b_smoke_manifest_sha256": STEP15B_SMOKE_MANIFEST_SHA256,
            "step15b_live_evidence_content_sha256": (
                STEP15B_LIVE_EVIDENCE_CONTENT_SHA256
            ),
            "step15a_source_blob_sha": STEP15A_SOURCE_BLOB_SHA,
            "step14d_source_blob_sha": STEP14D_SOURCE_BLOB_SHA,
            "final_live_evidence_content_sha256": (
                FINAL_LIVE_EVIDENCE_CONTENT_SHA256
            ),
        },
        "live_database_contract": {
            "provider": "Supabase PostgreSQL",
            "project_ref": evidence["supabase_project"]["ref"],
            "project_status_at_freeze": evidence["supabase_project"]["status"],
            "postgres_engine": evidence["supabase_project"]["postgres_engine"],
            "postgres_version": evidence["supabase_project"]["postgres_version"],
            "migrations_present": deepcopy(
                evidence["live_final_state"]["migrations_present"]
            ),
            "all_required_tables_present": True,
            "all_runtime_tables_empty_at_freeze": True,
        },
        "persistence_contract": {
            "checkpoint_create_load_idempotency_live_certified": True,
            "append_only_checkpoint_advance_live_certified": True,
            "checkpoint_cas_and_stale_rollback_live_certified": True,
            "lease_contention_and_renew_live_certified": True,
            "lease_expiry_takeover_and_fencing_live_certified": True,
            "lease_release_live_certified": True,
            "frozen_adapter_sql_fingerprints": deepcopy(step15b.SQL_FINGERPRINTS),
            "direct_psycopg_live_connection_certified": False,
        },
        "access_contract": {
            "anon_schema_usage": False,
            "authenticated_schema_usage": False,
            "service_role_schema_usage": False,
            "postgres_schema_usage": True,
            "kyre_runtime_security_advisor_findings": 0,
        },
        "activation_contract": {
            "step15_release_frozen": True,
            "production_runtime_enabled": False,
            "production_scheduler_started": False,
            "global_persistence_runtime_enabled": False,
            "automatic_restart_execution": False,
            "background_worker_started": False,
            "public_persistence_api_exposed": False,
            "supabase_rest_write_path_enabled": False,
            "actionable_output_enabled": False,
            "wagering_enabled": False,
            "runtime_cycle_executed": False,
            "provider_calls": 0,
            "sportsbook_calls": 0,
        },
        "phase_boundary": {
            "step15a_complete": True,
            "step15b_complete": True,
            "step15c_complete": True,
            "step15_complete_and_frozen": True,
            "live_schema_deployment_complete": True,
            "live_transaction_smoke_complete": True,
            "live_tables_clean_at_final_freeze": True,
            "production_runtime_activation_not_started": True,
            "global_persistence_autostart_not_started": True,
            "next_work_must_start_from_new_post_step15_branch": True,
        },
        **PROTECTED_INVARIANTS,
    }
    surface = deepcopy(manifest)
    surface.pop("generated_at_utc", None)
    manifest["release_manifest_sha256"] = _hash(surface)
    _assert_integrity(env)
    return manifest


__all__ = [
    "DATA_TYPE",
    "FINAL_CERTIFICATION_MARKER",
    "FINAL_LIVE_EVIDENCE_CONTENT_SHA256",
    "FINAL_LIVE_EVIDENCE_PATH",
    "MLBStep15CReleaseFreezeDisabledError",
    "MLBStep15CReleaseFreezeIntegrityError",
    "RELEASE_ID",
    "STEP15B_SMOKE_MANIFEST_SHA256",
    "STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV",
    "final_live_persistence_release_manifest",
    "load_final_live_evidence",
    "step15c_final_live_persistence_freeze_enabled",
    "validate_final_live_evidence",
]
