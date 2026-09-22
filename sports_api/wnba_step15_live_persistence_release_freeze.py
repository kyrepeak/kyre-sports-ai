"""WNBA Step 15C: final live persistence release freeze.

This module adds no runtime behavior. It freezes the certified live Supabase
schema deployment from Step 15A and the certified live PostgreSQL transaction
smoke from Step 15B on top of the frozen Step-14 persistence release.

Production scheduling, global persistence autostart, automatic restart
activation, background workers, public persistence APIs, Supabase REST writes,
wagering, authentication, cookies, and basketball model/ranking mutation remain
OFF. The final live runtime tables are empty at certification.
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
from sports_api import wnba_step15a_live_postgres_preflight as step15a
from sports_api import wnba_step15b_live_adapter_transaction_smoke as step15b

SOURCE = "Kyre Sports API WNBA Step 15 final live persistence release freeze"
SCHEMA_VERSION = "wnba_step_15_final_live_persistence_release_freeze_v1"
INTEGRATION_VERSION = "wnba_step15c_final_live_supabase_persistence_freeze_v1"
RELEASE_ID = "wnba_step15_live_supabase_persistence_2026_regular_season_frozen_v1"
BRANCH = "wnba-step15c-final-live-persistence-freeze-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP15B_FROZEN_SHA = "df509a78a30bc5f05980407cca07bc4a712bae4b"
STEP15B_SMOKE_CONTENT_SHA256 = "5b000b68c1b1f5acb569dfa788b94aea538b7895eb71c3e0e91ed34b0defcdbf"
STEP15B_LIVE_EVIDENCE_CONTENT_SHA256 = "d99bc29535f4bfc09a6d38858beb9b8faf8646fdf37b01aa3a86a9b18c4ff75c"
STEP15A_CERTIFIED_SHA = "9cc30b96c4583f6b18306910ca4a7fb70d93c325"
STEP15A_PREFLIGHT_CONTENT_SHA256 = "33a2c431a202b791180d6cca0aa8ad12f46ca6d561749c5753918f90b145223e"
STEP14D_FROZEN_SHA = "d5a7378d94fb1aa51a6bc5fbf5e5c0384f34a9d6"
STEP14_RELEASE_CONTENT_SHA256 = "70082ab06a58ddee4dce567626ff83bc64e67bf89f04e5f402d820a414b25e59"

FINAL_LIVE_EVIDENCE_PATH = "sports_api/certification/wnba_step15c_final_live_persistence_freeze_evidence.json"
FINAL_LIVE_EVIDENCE_CONTENT_SHA256 = "5b022af580295f9ad863e875493ba6f6620f71bf48cd0ce04f032f68a3d47ce4"
EXPECTED_SUPABASE_PROJECT_REF = "jqajcdckalsfizbvngiu"
EXPECTED_MIGRATION_VERSION = "20260828191445"
EXPECTED_MIGRATION_NAME = "wnba_step15a_install_frozen_step14_persistence_schema"

STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV = "WNBA_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED"

DEFAULT_ENABLED = False
LIVE_SCHEMA_DEPLOYMENT_CERTIFIED = True
LIVE_TRANSACTION_SEMANTICS_CERTIFIED = True
FINAL_LIVE_CLEAN_STATE_CERTIFIED = True
LIVE_ACCESS_BOUNDARY_CERTIFIED = True
FROZEN_SQL_FINGERPRINTS_CERTIFIED = True
STEP15_RELEASE_FROZEN = True
DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED = False
UNRELATED_CONNECTOR_PROBE_EDGE_FUNCTION_PRESENT = True
EDGE_FUNCTION_PART_OF_PERSISTENCE_RELEASE = False

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
    "WNBA_STEP15B_LIVE_ADAPTER_SMOKE_ENABLED",
    "WNBA_STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED",
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


class WNBAStep15ReleaseFreezeDisabledError(RuntimeError):
    pass


class WNBAStep15ReleaseFreezeIntegrityError(RuntimeError):
    pass


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def step15c_final_live_persistence_freeze_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV))


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


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(evidence))
    result.pop("observed_at_utc", None)
    result.pop("evidence_content_sha256", None)
    return result


def load_step15c_final_live_evidence(path: str = FINAL_LIVE_EVIDENCE_PATH) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WNBAStep15ReleaseFreezeIntegrityError(
            "Step 15C cannot load final live persistence evidence."
        ) from exc
    if not isinstance(evidence, dict):
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C evidence must be an object.")
    observed = str(evidence.get("evidence_content_sha256") or "").lower()
    expected = _canonical_hash(_evidence_hash_surface(evidence))
    if observed != expected or expected != FINAL_LIVE_EVIDENCE_CONTENT_SHA256:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C evidence content hash drift.")
    return evidence


def validate_step15c_final_live_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C evidence must be an object.")
    if evidence.get("data_type") != "wnba_step15c_final_live_persistence_freeze_evidence":
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C evidence data_type drift.")

    project = evidence.get("supabase_project")
    lineage = evidence.get("frozen_lineage")
    live = evidence.get("live_final_state")
    access = evidence.get("access_boundary")
    activation = evidence.get("activation_boundary")
    scope = evidence.get("scope_notes")
    if not all(isinstance(x, Mapping) for x in (project, lineage, live, access, activation, scope)):
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C evidence object shape drift.")

    if (
        project.get("ref") != EXPECTED_SUPABASE_PROJECT_REF
        or project.get("status") != "ACTIVE_HEALTHY"
        or project.get("region") != "us-west-1"
        or str(project.get("postgres_engine")) != "17"
    ):
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C project identity/health drift.")

    expected_lineage = {
        "step15b_certified_sha": STEP15B_FROZEN_SHA,
        "step15b_smoke_content_sha256": STEP15B_SMOKE_CONTENT_SHA256,
        "step15b_live_evidence_content_sha256": STEP15B_LIVE_EVIDENCE_CONTENT_SHA256,
        "step15a_certified_sha": STEP15A_CERTIFIED_SHA,
        "step15a_preflight_content_sha256": STEP15A_PREFLIGHT_CONTENT_SHA256,
        "step14d_frozen_sha": STEP14D_FROZEN_SHA,
        "step14_release_content_sha256": STEP14_RELEASE_CONTENT_SHA256,
    }
    if any(lineage.get(key) != value for key, value in expected_lineage.items()):
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C frozen lineage evidence drift.")

    if (
        live.get("migration_version") != EXPECTED_MIGRATION_VERSION
        or live.get("migration_name") != EXPECTED_MIGRATION_NAME
        or live.get("migration_present") is not True
        or live.get("smoke_cleanup_reverified") is not True
    ):
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C live migration/cleanup drift.")
    tables = live.get("tables_present")
    rows = live.get("row_counts")
    expected_tables = {
        "wnba_runtime_checkpoints": True,
        "wnba_runtime_checkpoint_heads": True,
        "wnba_runtime_leases": True,
    }
    expected_rows = {
        "wnba_runtime_checkpoints": 0,
        "wnba_runtime_checkpoint_heads": 0,
        "wnba_runtime_leases": 0,
    }
    if tables != expected_tables or rows != expected_rows:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C final live table state drift.")

    for key in (
        "anon_schema_usage", "anon_schema_create",
        "authenticated_schema_usage", "authenticated_schema_create",
        "service_role_schema_usage", "service_role_schema_create",
    ):
        if access.get(key) is not False:
            raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C client schema access drift.")
    if access.get("postgres_schema_usage") is not True or access.get("postgres_schema_create") is not True:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C postgres ownership/access drift.")
    if access.get("kyre_runtime_security_advisor_finding_count") != 0:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C kyre_runtime security findings detected.")

    if not activation or any(value is not False for value in activation.values()):
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C activation boundary drift.")

    if scope.get("direct_psycopg_live_connection_certified") is not False:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C direct psycopg certification boundary drift.")
    if scope.get("live_sql_semantics_certified_by_step15b") is not True:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C Step-15B live SQL certification missing.")
    if scope.get("unrelated_connector_probe_edge_function_present") is not True:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C connector-probe scope record drift.")
    if scope.get("unrelated_connector_probe_edge_function_slug") != "noop-do-not-deploy":
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C connector-probe function identity drift.")
    if scope.get("edge_function_is_part_of_persistence_release") is not False:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C unrelated Edge Function entered release scope.")
    if scope.get("edge_function_has_kyre_runtime_access_certified") is not False:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C unsupported Edge Function access claim drift.")
    return deepcopy(dict(evidence))


def _assert_integrity(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step15c_final_live_persistence_freeze_enabled(source):
        raise WNBAStep15ReleaseFreezeDisabledError(
            f"Step 15C requires {STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep15ReleaseFreezeDisabledError(
            "Step 15C refuses production/global-persistence/write/wagering switches: " + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep15ReleaseFreezeDisabledError(
            "Step 15C requires frozen Step-15B/15A/14/13/12 gates: " + ", ".join(missing)
        )

    smoke = step15b.build_step15b_live_smoke_manifest(
        env=source,
        generated_at_utc="2026-08-28T19:31:00+00:00",
    )
    if smoke.get("smoke_content_sha256") != STEP15B_SMOKE_CONTENT_SHA256:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C Step-15B smoke hash drift.")
    preflight = step15a.build_step15a_live_preflight_manifest(
        env=source,
        generated_at_utc="2026-08-28T19:20:00+00:00",
    )
    if preflight.get("preflight_content_sha256") != STEP15A_PREFLIGHT_CONTENT_SHA256:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C Step-15A preflight hash drift.")
    if step14d.RELEASE_ID != step15a.STEP14_RELEASE_ID:
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C Step-14 release identity drift.")
    step15b.validate_frozen_sql_fingerprints()

    false_values = (
        DEFAULT_ENABLED,
        DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED,
        EDGE_FUNCTION_PART_OF_PERSISTENCE_RELEASE,
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
    if any(value is not False for value in false_values):
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C safety boundary constant drift.")
    true_values = (
        LIVE_SCHEMA_DEPLOYMENT_CERTIFIED,
        LIVE_TRANSACTION_SEMANTICS_CERTIFIED,
        FINAL_LIVE_CLEAN_STATE_CERTIFIED,
        LIVE_ACCESS_BOUNDARY_CERTIFIED,
        FROZEN_SQL_FINGERPRINTS_CERTIFIED,
        STEP15_RELEASE_FROZEN,
        UNRELATED_CONNECTOR_PROBE_EDGE_FUNCTION_PRESENT,
    )
    if any(value is not True for value in true_values):
        raise WNBAStep15ReleaseFreezeIntegrityError("Step 15C certification constant drift.")
    return validate_step15c_final_live_evidence(load_step15c_final_live_evidence())


def build_step15c_release_manifest(
    *, env: Mapping[str, str] | None = None, generated_at_utc: str | None = None
) -> dict[str, Any]:
    evidence = _assert_integrity(env)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    result = {
        "data_type": "wnba_step15_final_live_persistence_release",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "integration_version": INTEGRATION_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": generated,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "branch": BRANCH,
        "lineage": {
            "step15b_frozen_sha": STEP15B_FROZEN_SHA,
            "step15b_smoke_content_sha256": STEP15B_SMOKE_CONTENT_SHA256,
            "step15b_live_evidence_content_sha256": STEP15B_LIVE_EVIDENCE_CONTENT_SHA256,
            "step15a_certified_sha": STEP15A_CERTIFIED_SHA,
            "step15a_preflight_content_sha256": STEP15A_PREFLIGHT_CONTENT_SHA256,
            "step14d_frozen_sha": STEP14D_FROZEN_SHA,
            "step14_release_content_sha256": STEP14_RELEASE_CONTENT_SHA256,
            "final_live_evidence_content_sha256": FINAL_LIVE_EVIDENCE_CONTENT_SHA256,
        },
        "live_database_contract": {
            "provider": "Supabase PostgreSQL",
            "project_ref": evidence["supabase_project"]["ref"],
            "project_status_at_freeze": evidence["supabase_project"]["status"],
            "postgres_engine": evidence["supabase_project"]["postgres_engine"],
            "migration_version": evidence["live_final_state"]["migration_version"],
            "migration_name": evidence["live_final_state"]["migration_name"],
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
        "out_of_scope_contract": {
            "unrelated_connector_probe_edge_function_present": True,
            "unrelated_connector_probe_edge_function_slug": "noop-do-not-deploy",
            "edge_function_is_part_of_persistence_release": False,
            "edge_function_kyre_runtime_access_certified": False,
        },
        "activation_contract": {
            "step15_release_frozen": True,
            "production_runtime_enabled": False,
            "live_scheduler_started": False,
            "global_persistence_runtime_enabled": False,
            "automatic_restart_activation": False,
            "background_worker_started": False,
            "public_persistence_api_exposed": False,
            "supabase_rest_write_path_enabled": False,
            "wagering_enabled": False,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
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
    }
    surface = deepcopy(result)
    surface.pop("generated_at_utc", None)
    result["release_content_sha256"] = _canonical_hash(surface)
    _assert_integrity(env)
    return result


__all__ = [
    "BRANCH",
    "DEFAULT_ENABLED",
    "FINAL_LIVE_EVIDENCE_CONTENT_SHA256",
    "FINAL_LIVE_EVIDENCE_PATH",
    "INTEGRATION_VERSION",
    "RELEASE_ID",
    "SAFETY_CONTRACT",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP15A_CERTIFIED_SHA",
    "STEP15A_PREFLIGHT_CONTENT_SHA256",
    "STEP15B_FROZEN_SHA",
    "STEP15B_SMOKE_CONTENT_SHA256",
    "STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV",
    "WNBAStep15ReleaseFreezeDisabledError",
    "WNBAStep15ReleaseFreezeIntegrityError",
    "build_step15c_release_manifest",
    "load_step15c_final_live_evidence",
    "step15c_final_live_persistence_freeze_enabled",
    "validate_step15c_final_live_evidence",
]
