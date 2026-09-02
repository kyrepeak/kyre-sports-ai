"""WNBA Step 15A: live PostgreSQL/Supabase schema deployment preflight.

Step 15A does not add runtime behavior. It binds the frozen Step-14 persistence
release to one observed live Supabase/PostgreSQL schema deployment and validates
that the deployed tables, migration, access boundary, and activation boundary
match the frozen contract.

The live database remains empty at certification time. Production runtime,
global persistence autostart, automatic restart activation, background workers,
public persistence APIs, Supabase REST writes, wagering, and model/ranking
changes remain OFF.
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

from sports_api import wnba_step14_release_freeze as step14d
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step14c_durable_restart_lease as step14c

SOURCE = "Kyre Sports API WNBA Step 15A live PostgreSQL schema preflight"
SCHEMA_VERSION = "wnba_step_15a_live_postgres_preflight_v1"
INTEGRATION_VERSION = "wnba_step15a_live_supabase_schema_preflight_v1"
BRANCH = "wnba-step15a-live-postgres-preflight-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP14D_FROZEN_SHA = "d5a7378d94fb1aa51a6bc5fbf5e5c0384f34a9d6"
STEP14_RELEASE_ID = step14d.RELEASE_ID
STEP14_RELEASE_CONTENT_SHA256 = "70082ab06a58ddee4dce567626ff83bc64e67bf89f04e5f402d820a414b25e59"
STEP14A_SQL_SCHEMA_SHA256 = "308042f8196607a477158d348ba6e03e090267910cba749491534131b490a2eb"
STEP14C_LEASE_SQL_SCHEMA_SHA256 = "49376bd4de581606819dc70ace6d462aadb77e641b0344bcde61c69f5a03b5bb"

LIVE_EVIDENCE_PATH = "sports_api/certification/wnba_step15a_live_postgres_preflight_evidence.json"
LIVE_EVIDENCE_CONTENT_SHA256 = "2469c85f7de238cb61f435b5c429f4f7c38b6a2417d19e60bc03047f29573ee8"
EXPECTED_SUPABASE_PROJECT_REF = "jqajcdckalsfizbvngiu"
EXPECTED_SUPABASE_PROJECT_NAME = "kyre-sports-ai-wnba"
EXPECTED_REGION = "us-west-1"
EXPECTED_MIGRATION_VERSION = "20260828191445"
EXPECTED_MIGRATION_NAME = "wnba_step15a_install_frozen_step14_persistence_schema"

STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED_ENV = "WNBA_STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED"

DEFAULT_ENABLED = False
LIVE_DATABASE_SCHEMA_DEPLOYMENT_CERTIFIED = True
LIVE_POSTGRES_CONNECTIVITY_CERTIFIED = True
LIVE_SCHEMA_SHAPE_CERTIFIED = True
LIVE_SCHEMA_ACCESS_BOUNDARY_CERTIFIED = True
LIVE_SCHEMA_EMPTY_AT_CERTIFICATION = True
FROZEN_STEP14_DDL_REUSED_WITHOUT_MODIFICATION = True

PRODUCTION_ACTIVATION_ALLOWED = False
GLOBAL_PERSISTENCE_RUNTIME_ENABLED = False
AUTOMATIC_RESTART_ACTIVATION_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BASKETBALL_MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False
RUNTIME_MUTATION_ALLOWED = False

SAFETY_CONTRACT = {
    "default_enablement": False,
    "production_runtime": False,
    "production_activation": False,
    "global_persistence_runtime": False,
    "automatic_restart_activation": False,
    "background_daemon": False,
    "background_thread": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "wager_action": False,
    "authentication": False,
    "cookies": False,
    "basketball_model_change": False,
    "step8_distribution_change": False,
    "step9_ranking_change": False,
    "step9_qualification_change": False,
    "step12_presentation_change": False,
    "runtime_mutation": False,
}

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)

_REQUIRED_TRUE_ENV_KEYS = (
    "WNBA_STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED",
    "WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED",
    "WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
    "WNBA_STEP14B_DATABASE_READ_ENABLED",
    "WNBA_STEP14B_DATABASE_WRITE_ENABLED",
    "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED",
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

_EXPECTED_TABLES = {
    "wnba_runtime_checkpoints": {
        "column_count": 15,
        "constraint_count": 11,
        "index_count": 5,
        "row_count": 0,
    },
    "wnba_runtime_checkpoint_heads": {
        "column_count": 5,
        "constraint_count": 4,
        "index_count": 1,
        "row_count": 0,
    },
    "wnba_runtime_leases": {
        "column_count": 8,
        "constraint_count": 5,
        "index_count": 2,
        "row_count": 0,
    },
}


class WNBAStep15ALivePreflightDisabledError(RuntimeError):
    """Raised when Step 15A is not isolated behind its certification gate."""


class WNBAStep15ALivePreflightIntegrityError(RuntimeError):
    """Raised when frozen lineage or live deployment evidence drifts."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step15a_live_postgres_preflight_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED_ENV))


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha256(path: str) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise WNBAStep15ALivePreflightIntegrityError(
            f"Step 15A cannot read required file: {path}."
        ) from exc


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    surface = deepcopy(dict(evidence))
    surface.pop("observed_at_utc", None)
    surface.pop("evidence_content_sha256", None)
    return surface


def load_step15a_live_evidence(
    path: str = LIVE_EVIDENCE_PATH,
) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WNBAStep15ALivePreflightIntegrityError(
            "Step 15A cannot load the live preflight evidence."
        ) from exc
    if not isinstance(evidence, dict):
        raise WNBAStep15ALivePreflightIntegrityError(
            "Step 15A live evidence must be a JSON object."
        )
    observed_hash = str(evidence.get("evidence_content_sha256") or "").lower()
    expected_hash = _canonical_hash(_evidence_hash_surface(evidence))
    if observed_hash != expected_hash or expected_hash != LIVE_EVIDENCE_CONTENT_SHA256:
        raise WNBAStep15ALivePreflightIntegrityError(
            "Step 15A live evidence content hash drift."
        )
    return evidence


def _assert_parent_release(env: Mapping[str, str]) -> None:
    if step14d.RELEASE_ID != STEP14_RELEASE_ID:
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A Step-14 release ID drift.")
    manifest = step14d.build_step14d_release_manifest(
        env=env,
        generated_at_utc="2026-08-28T19:00:00+00:00",
    )
    if manifest.get("release_content_sha256") != STEP14_RELEASE_CONTENT_SHA256:
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A Step-14 release hash drift.")
    if _file_sha256(step14a.SQL_SCHEMA_PATH) != STEP14A_SQL_SCHEMA_SHA256:
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A frozen Step-14A SQL hash drift.")
    if _file_sha256(step14c.LEASE_SQL_SCHEMA_PATH) != STEP14C_LEASE_SQL_SCHEMA_SHA256:
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A frozen Step-14C lease SQL hash drift.")


def validate_step15a_live_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A live evidence must be an object.")
    if evidence.get("data_type") != "wnba_step15a_live_postgres_preflight_evidence":
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A evidence data_type drift.")
    project = evidence.get("supabase_project")
    migration = evidence.get("migration")
    lineage = evidence.get("frozen_lineage")
    live_schema = evidence.get("live_schema")
    access = evidence.get("access_boundary")
    activation = evidence.get("activation_boundary")
    if not all(isinstance(x, Mapping) for x in (project, migration, lineage, live_schema, access, activation)):
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A evidence object shape drift.")

    if (
        project.get("ref") != EXPECTED_SUPABASE_PROJECT_REF
        or project.get("name") != EXPECTED_SUPABASE_PROJECT_NAME
        or project.get("region") != EXPECTED_REGION
        or project.get("status") != "ACTIVE_HEALTHY"
        or str(project.get("postgres_engine")) != "17"
    ):
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A live project identity/health drift.")

    if (
        migration.get("version") != EXPECTED_MIGRATION_VERSION
        or migration.get("name") != EXPECTED_MIGRATION_NAME
        or migration.get("applied") is not True
    ):
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A live migration evidence drift.")

    if (
        lineage.get("step14d_frozen_sha") != STEP14D_FROZEN_SHA
        or lineage.get("step14_release_id") != STEP14_RELEASE_ID
        or lineage.get("step14_release_content_sha256") != STEP14_RELEASE_CONTENT_SHA256
        or lineage.get("step14a_sql_schema_sha256") != STEP14A_SQL_SCHEMA_SHA256
        or lineage.get("step14c_lease_sql_schema_sha256") != STEP14C_LEASE_SQL_SCHEMA_SHA256
    ):
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A frozen lineage evidence drift.")

    if live_schema.get("schema_name") != "kyre_runtime":
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A live schema name drift.")
    if live_schema.get("tables") != _EXPECTED_TABLES:
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A live table shape/count drift.")
    for key in (
        "required_foreign_key_present",
        "required_unique_constraints_present",
        "required_check_constraints_present",
        "required_indexes_present",
        "all_tables_empty_at_certification",
    ):
        if live_schema.get(key) is not True:
            raise WNBAStep15ALivePreflightIntegrityError(
                f"Step 15A live schema requirement failed: {key}."
            )

    forbidden_access_true = (
        "anon_schema_usage",
        "anon_schema_create",
        "authenticated_schema_usage",
        "authenticated_schema_create",
        "service_role_schema_usage",
        "service_role_schema_create",
    )
    if any(access.get(key) is not False for key in forbidden_access_true):
        raise WNBAStep15ALivePreflightIntegrityError(
            "Step 15A client/service-role schema access boundary drift."
        )
    if access.get("postgres_schema_usage") is not True or access.get("postgres_schema_create") is not True:
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A postgres schema ownership drift.")
    if access.get("schema_acl_explicit_entries") != 0:
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A unexpected schema ACL entries.")
    if access.get("non_postgres_table_grant_count") != 0:
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A unexpected non-postgres table grants.")
    if access.get("kyre_runtime_security_advisor_finding_count") != 0:
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A kyre_runtime security advisor findings detected.")

    if not activation or any(value is not False for value in activation.values()):
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A activation boundary drift.")

    return deepcopy(dict(evidence))


def _assert_integrity(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step15a_live_postgres_preflight_enabled(source):
        raise WNBAStep15ALivePreflightDisabledError(
            f"Step 15A requires {STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep15ALivePreflightDisabledError(
            "Step 15A refuses production/global-persistence/write/wagering switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep15ALivePreflightDisabledError(
            "Step 15A requires frozen Step-14/13/12 certification gates: "
            + ", ".join(missing)
        )
    own_false = (
        DEFAULT_ENABLED,
        PRODUCTION_ACTIVATION_ALLOWED,
        GLOBAL_PERSISTENCE_RUNTIME_ENABLED,
        AUTOMATIC_RESTART_ACTIVATION_ALLOWED,
        BACKGROUND_DAEMON_ALLOWED,
        BACKGROUND_THREAD_ALLOWED,
        PUBLIC_PERSISTENCE_API_ALLOWED,
        SUPABASE_REST_WRITE_ALLOWED,
        WAGERING_ALLOWED,
        AUTHENTICATION_ALLOWED,
        COOKIES_ALLOWED,
        BASKETBALL_MODEL_MUTATION_ALLOWED,
        RANKING_MUTATION_ALLOWED,
        RUNTIME_MUTATION_ALLOWED,
    )
    if any(value is not False for value in own_false):
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A safety constant drift.")
    own_true = (
        LIVE_DATABASE_SCHEMA_DEPLOYMENT_CERTIFIED,
        LIVE_POSTGRES_CONNECTIVITY_CERTIFIED,
        LIVE_SCHEMA_SHAPE_CERTIFIED,
        LIVE_SCHEMA_ACCESS_BOUNDARY_CERTIFIED,
        LIVE_SCHEMA_EMPTY_AT_CERTIFICATION,
        FROZEN_STEP14_DDL_REUSED_WITHOUT_MODIFICATION,
    )
    if any(value is not True for value in own_true):
        raise WNBAStep15ALivePreflightIntegrityError("Step 15A certification constant drift.")
    _assert_parent_release(source)
    evidence = validate_step15a_live_evidence(load_step15a_live_evidence())
    return evidence


def build_step15a_live_preflight_manifest(
    *,
    env: Mapping[str, str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Return the content-addressed Step-15A live schema preflight manifest."""
    evidence = _assert_integrity(env)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    result = {
        "data_type": "wnba_step15a_live_postgres_preflight",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "integration_version": INTEGRATION_VERSION,
        "generated_at_utc": generated,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "branch": BRANCH,
        "lineage": {
            "step14d_frozen_sha": STEP14D_FROZEN_SHA,
            "step14_release_id": STEP14_RELEASE_ID,
            "step14_release_content_sha256": STEP14_RELEASE_CONTENT_SHA256,
            "step14a_sql_schema_sha256": STEP14A_SQL_SCHEMA_SHA256,
            "step14c_lease_sql_schema_sha256": STEP14C_LEASE_SQL_SCHEMA_SHA256,
            "live_evidence_content_sha256": LIVE_EVIDENCE_CONTENT_SHA256,
        },
        "live_database_contract": {
            "provider": "Supabase PostgreSQL",
            "project_ref": evidence["supabase_project"]["ref"],
            "region": evidence["supabase_project"]["region"],
            "status_at_preflight": evidence["supabase_project"]["status"],
            "postgres_engine": evidence["supabase_project"]["postgres_engine"],
            "migration_version": evidence["migration"]["version"],
            "migration_name": evidence["migration"]["name"],
            "schema_name": evidence["live_schema"]["schema_name"],
            "tables": deepcopy(evidence["live_schema"]["tables"]),
            "frozen_step14_ddl_reused_without_modification": True,
            "all_tables_empty_at_certification": True,
        },
        "access_contract": {
            "anon_schema_usage": False,
            "authenticated_schema_usage": False,
            "service_role_schema_usage": False,
            "non_postgres_table_grants": False,
            "kyre_runtime_security_advisor_findings": 0,
            "direct_postgres_backend_required_for_next_live_adapter_test": True,
        },
        "activation_contract": {
            "live_schema_installed": True,
            "live_scheduler_started": False,
            "global_persistence_runtime_enabled": False,
            "automatic_restart_activation": False,
            "background_worker_started": False,
            "public_persistence_api_exposed": False,
            "supabase_rest_write_path_enabled": False,
            "production_runtime_enabled": False,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step15a_complete": True,
            "live_schema_deployment_complete": True,
            "live_adapter_transaction_smoke_test_not_started": True,
            "production_runtime_activation_not_started": True,
            "global_persistence_autostart_not_started": True,
            "public_persistence_api_not_started": True,
            "wagering_not_started": True,
        },
    }
    surface = deepcopy(result)
    surface.pop("generated_at_utc", None)
    result["preflight_content_sha256"] = _canonical_hash(surface)
    _assert_integrity(env)
    return result


__all__ = [
    "BRANCH",
    "DEFAULT_ENABLED",
    "EXPECTED_MIGRATION_NAME",
    "EXPECTED_MIGRATION_VERSION",
    "EXPECTED_REGION",
    "EXPECTED_SUPABASE_PROJECT_NAME",
    "EXPECTED_SUPABASE_PROJECT_REF",
    "INTEGRATION_VERSION",
    "LIVE_EVIDENCE_CONTENT_SHA256",
    "LIVE_EVIDENCE_PATH",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "SAFETY_CONTRACT",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP14D_FROZEN_SHA",
    "STEP14_RELEASE_CONTENT_SHA256",
    "STEP14_RELEASE_ID",
    "STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED_ENV",
    "WNBAStep15ALivePreflightDisabledError",
    "WNBAStep15ALivePreflightIntegrityError",
    "build_step15a_live_preflight_manifest",
    "load_step15a_live_evidence",
    "step15a_live_postgres_preflight_enabled",
    "validate_step15a_live_evidence",
]
