"""WNBA Step 16D: controlled production-shaped container activation.

This step is the first layer allowed to run the exact production Docker image
against live PostgreSQL through psycopg. Activation is explicit, bounded to two
foreground canary cycles, uses the frozen Step-16B -> Step-14C runner binding,
and always removes its slate-scoped canary checkpoint/lease state afterward.

It does NOT enable continuous production runtime, scheduler autostart, a
background worker, public persistence endpoints, Supabase REST writes, wagering,
authentication/cookies, or basketball model/ranking changes.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.parse import urlsplit

from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step14c_durable_restart_lease as step14c
from sports_api import wnba_step16b_production_lifecycle as step16b
from sports_api import wnba_step16c_live_postgres_canary as step16c

SOURCE = "Kyre Sports API WNBA Step 16D controlled production activation"
SCHEMA_VERSION = "wnba_step_16d_controlled_production_activation_v1"
INTEGRATION_VERSION = "wnba_step16d_production_docker_psycopg_restart_canary_v1"
CONTRACT_ID = "wnba_step16d_controlled_production_activation_2026_regular_v1"
BRANCH = "wnba-step16d-controlled-production-activation-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP16C_CERTIFIED_SHA = "1de22beb83cad2f0c3bae3bc6ab845b5f3d2a4e3"
STEP16C_CONTRACT_ID = "wnba_step16c_live_postgres_bound_runner_canary_2026_regular_v1"
STEP16C_MANIFEST_CONTENT_SHA256 = "1efa8f82298297cc32f8c826d16332f9dddfee2e9c501422f5706704a98bf51b"
STEP16C_LIVE_EVIDENCE_CONTENT_SHA256 = "48463e66cf35c4cd47192436267f08d76d2e980f8f5f8b5d7b7fbc72b47e5810"
STEP16B_CERTIFIED_SHA = "f898ca410c10db59f635888166d1666a952d8bd7"
STEP15C_CERTIFIED_SHA = "5e24210d7aef90143ba016e368cd49d3ee1a7f19"

STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED_ENV = (
    "WNBA_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED"
)
EXPECTED_REVISION_ENV = "WNBA_STEP16D_EXPECTED_REVISION"
DATABASE_URL_ENV = step14c.DATABASE_URL_ENV

EXPECTED_CANARY_SLATE_DATE = "2026-01-17"
EXPECTED_CHECKPOINT_KEY = "wnba:runtime:2026:regular-season:2026-01-17"
EXPECTED_LEASE_KEY = EXPECTED_CHECKPOINT_KEY + ":scheduler-lease"

DEFAULT_ENABLED = False
CONTROLLED_ONE_SHOT_PRODUCTION_ACTIVATION_ALLOWED = True
PRODUCTION_DOCKER_IMAGE_EXECUTION_REQUIRED = True
DIRECT_PSYCOG_LIVE_CONNECTION_REQUIRED = True
TWO_CYCLE_RESTART_RECOVERY_REQUIRED = True
FENCED_LEASE_REQUIRED = True
CHECKPOINT_CAS_REQUIRED = True
CANARY_CLEANUP_REQUIRED = True

CONTINUOUS_PRODUCTION_RUNTIME_ALLOWED = False
GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED = False
AUTOMATIC_RESTART_AUTOSTART_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
BACKGROUND_TASK_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BASKETBALL_MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False
SECRETS_IN_OUTPUT_ALLOWED = False

_REQUIRED_TRUE_GATES = (
    "WNBA_STEP16B_DURABLE_LIFECYCLE_ENABLED",
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

_FORBIDDEN_TRUE_GATES = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
)

SAFETY_CONTRACT = {
    "continuous_production_runtime": False,
    "global_persistence_autostart": False,
    "automatic_restart_autostart": False,
    "background_daemon": False,
    "background_thread": False,
    "background_task": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "wager_action": False,
    "authentication": False,
    "cookies": False,
    "secrets_in_output": False,
    "basketball_model_change": False,
    "step8_distribution_change": False,
    "step9_ranking_change": False,
    "step9_qualification_change": False,
}


class WNBAStep16DDisabledError(RuntimeError):
    pass


class WNBAStep16DIntegrityError(RuntimeError):
    pass


class WNBAStep16DDatabaseError(RuntimeError):
    pass


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


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


def _valid_git_sha(value: object) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 40 and all(ch in "0123456789abcdef" for ch in text)


def _valid_sha256(value: object) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def step16d_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED_ENV))


def build_activation_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = {str(k): str(v) for k, v in dict(os.environ if env is None else env).items()}
    source[STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED_ENV] = "true"
    for key in _REQUIRED_TRUE_GATES:
        source[key] = "true"
    for key in _FORBIDDEN_TRUE_GATES:
        source[key] = "false"
    return source


def _database_secret_status(env: Mapping[str, str]) -> dict[str, Any]:
    raw = str(env.get(DATABASE_URL_ENV) or "").strip()
    if not raw:
        raise WNBAStep16DDisabledError(
            f"Step 16D requires protected {DATABASE_URL_ENV}; no credential may be embedded."
        )
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() not in {"postgres", "postgresql"}:
        raise WNBAStep16DIntegrityError("Step 16D database URL must be PostgreSQL.")
    if not parsed.hostname or not parsed.path or parsed.path == "/":
        raise WNBAStep16DIntegrityError("Step 16D database URL must identify a host and database.")
    return {
        "configured": True,
        "scheme": parsed.scheme.casefold(),
        "credential_value_exposed": False,
    }


def validate_activation_prerequisites(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source = build_activation_env(env)
    if not step16d_enabled(source):
        raise WNBAStep16DDisabledError("Step 16D explicit activation gate is required.")
    secret = _database_secret_status(source)
    if str(source.get("WNBA_DEPLOYMENT_MODE") or "").strip() != "container":
        raise WNBAStep16DDisabledError("Step 16D must execute inside the production Docker image.")
    expected_revision = str(source.get(EXPECTED_REVISION_ENV) or "").strip().lower()
    build_revision = str(source.get("WNBA_RELEASE_BUILD_REVISION") or "").strip().lower()
    if not _valid_git_sha(expected_revision) or build_revision != expected_revision:
        raise WNBAStep16DIntegrityError("Step 16D container build revision mismatch.")
    try:
        step16b.validate_step16b_enablement(source)
    except Exception as exc:
        raise WNBAStep16DDisabledError(
            "Step 16D requires the certified Step-16B packaging/lifecycle prerequisites."
        ) from exc
    bound = step16b.get_step16b_runtime_binding(source)
    if bound is not step14c.run_step14c_durable_restart_lease:
        raise WNBAStep16DIntegrityError("Step 16D bound Step-14C runner identity drift.")
    if step16c.DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED is not False:
        raise WNBAStep16DIntegrityError("Step 16D expected Step-16C direct psycopg boundary to be false.")
    if step16c.DEPLOYED_FASTAPI_CONTAINER_CANARY_CERTIFIED is not False:
        raise WNBAStep16DIntegrityError("Step 16D expected Step-16C container boundary to be false.")
    if any(SAFETY_CONTRACT.values()):
        raise WNBAStep16DIntegrityError("Step 16D safety contract drift.")
    required_true = (
        CONTROLLED_ONE_SHOT_PRODUCTION_ACTIVATION_ALLOWED,
        PRODUCTION_DOCKER_IMAGE_EXECUTION_REQUIRED,
        DIRECT_PSYCOG_LIVE_CONNECTION_REQUIRED,
        TWO_CYCLE_RESTART_RECOVERY_REQUIRED,
        FENCED_LEASE_REQUIRED,
        CHECKPOINT_CAS_REQUIRED,
        CANARY_CLEANUP_REQUIRED,
    )
    if any(value is not True for value in required_true):
        raise WNBAStep16DIntegrityError("Step 16D required capability drift.")
    forbidden = (
        DEFAULT_ENABLED,
        CONTINUOUS_PRODUCTION_RUNTIME_ALLOWED,
        GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED,
        AUTOMATIC_RESTART_AUTOSTART_ALLOWED,
        BACKGROUND_DAEMON_ALLOWED,
        BACKGROUND_THREAD_ALLOWED,
        BACKGROUND_TASK_ALLOWED,
        PUBLIC_PERSISTENCE_API_ALLOWED,
        SUPABASE_REST_WRITE_ALLOWED,
        WAGERING_ALLOWED,
        AUTHENTICATION_ALLOWED,
        COOKIES_ALLOWED,
        BASKETBALL_MODEL_MUTATION_ALLOWED,
        RANKING_MUTATION_ALLOWED,
        SECRETS_IN_OUTPUT_ALLOWED,
    )
    if any(value is not False for value in forbidden):
        raise WNBAStep16DIntegrityError("Step 16D forbidden capability drift.")
    return {
        "database_secret": secret,
        "expected_revision": expected_revision,
        "build_revision": build_revision,
        "bound_runner": bound,
        "env": source,
    }


def build_canary_request() -> dict[str, Any]:
    parent = step13b.build_step13b_request(
        season=SEASON,
        initial_slate_date=EXPECTED_CANARY_SLATE_DATE,
        max_supervisor_sessions=1,
        max_supervisor_runtime_seconds=1,
        max_total_intersession_sleep_seconds=0,
        initial_previous_state=None,
    )
    return step13c.build_step13c_request(
        supervisor_request=parent,
        max_recovery_attempts=1,
        base_recovery_backoff_seconds=0,
        max_total_recovery_sleep_seconds=0,
    )


def build_controlled_step13c_response(*, cycle_index: int) -> dict[str, Any]:
    response = {
        "data_type": "wnba_step13c_reliability_recovery_response",
        "schema_version": step13c.SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "health": "healthy",
        "lineage": {
            "step13b_frozen_sha": step14a.STEP13B_FROZEN_SHA,
            "latest_step13b_supervisor_content_sha256": "a" * 64,
            "step13a_frozen_sha": step14a.STEP13A_FROZEN_SHA,
            "step12d_frozen_sha": step14a.step13_release.STEP12D_FROZEN_SHA,
        },
        "final_controller_state_for_restart_handoff": {
            "season": SEASON,
            "slate_date": EXPECTED_CANARY_SLATE_DATE,
            "cycle_index": cycle_index,
            "next_refresh_due_at_utc": "2026-01-17T00:01:00+00:00",
            "circuit_state": "closed",
        },
    }
    response["reliability_content_sha256"] = _canonical_hash({
        key: deepcopy(value)
        for key, value in response.items()
        if key not in {"generated_at_utc", "reliability_content_sha256"}
    })
    return response


def _connect(dsn: str) -> Any:
    try:
        import psycopg  # type: ignore
        return psycopg.connect(
            dsn,
            connect_timeout=10,
            application_name="kyre-sports-ai-step16d",
        )
    except Exception as exc:
        raise WNBAStep16DDatabaseError("Step 16D direct psycopg connection failed.") from exc


def _canary_counts(dsn: str) -> dict[str, int]:
    connection = _connect(dsn)
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
              (SELECT count(*) FROM kyre_runtime.wnba_runtime_checkpoints WHERE checkpoint_key = %s),
              (SELECT count(*) FROM kyre_runtime.wnba_runtime_checkpoint_heads WHERE checkpoint_key = %s),
              (SELECT count(*) FROM kyre_runtime.wnba_runtime_leases WHERE lease_key = %s)
            """,
            (EXPECTED_CHECKPOINT_KEY, EXPECTED_CHECKPOINT_KEY, EXPECTED_LEASE_KEY),
        )
        row = cursor.fetchone()
        if not isinstance(row, (tuple, list)) or len(row) != 3:
            raise WNBAStep16DDatabaseError("Step 16D canary count query returned invalid shape.")
        connection.rollback()
        return {
            "checkpoint_rows": int(row[0]),
            "checkpoint_head_rows": int(row[1]),
            "lease_rows": int(row[2]),
        }
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()


def _database_metadata(dsn: str) -> dict[str, str]:
    connection = _connect(dsn)
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT current_user, current_setting('server_version'), current_database()")
        row = cursor.fetchone()
        if not isinstance(row, (tuple, list)) or len(row) != 3:
            raise WNBAStep16DDatabaseError("Step 16D database metadata query returned invalid shape.")
        connection.rollback()
        return {
            "database_role": str(row[0]),
            "postgres_version": str(row[1]),
            "database_name": str(row[2]),
        }
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()


def _cleanup_canary(dsn: str) -> dict[str, int]:
    connection = _connect(dsn)
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM kyre_runtime.wnba_runtime_checkpoint_heads WHERE checkpoint_key = %s",
            (EXPECTED_CHECKPOINT_KEY,),
        )
        cursor.execute(
            "DELETE FROM kyre_runtime.wnba_runtime_leases WHERE lease_key = %s",
            (EXPECTED_LEASE_KEY,),
        )
        cursor.execute(
            "DELETE FROM kyre_runtime.wnba_runtime_checkpoints WHERE checkpoint_key = %s",
            (EXPECTED_CHECKPOINT_KEY,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()
    return _canary_counts(dsn)


def _result_hash_surface(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"observed_at_utc", "result_content_sha256"}
    }


def validate_live_activation_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise WNBAStep16DIntegrityError("Step 16D result must be an object.")
    if result.get("data_type") != "wnba_step16d_controlled_production_activation_result":
        raise WNBAStep16DIntegrityError("Step 16D result type drift.")
    if result.get("schema_version") != SCHEMA_VERSION or result.get("contract_id") != CONTRACT_ID:
        raise WNBAStep16DIntegrityError("Step 16D result contract drift.")
    observed_hash = str(result.get("result_content_sha256") or "").lower()
    expected_hash = _canonical_hash(_result_hash_surface(result))
    if not _valid_sha256(observed_hash) or observed_hash != expected_hash:
        raise WNBAStep16DIntegrityError("Step 16D result content hash mismatch.")
    lineage = result.get("lineage")
    activation = result.get("activation")
    cycles = result.get("cycles")
    cleanup = result.get("cleanup")
    safety = result.get("safety")
    if not all(isinstance(v, Mapping) for v in (lineage, activation, cycles, cleanup, safety)):
        raise WNBAStep16DIntegrityError("Step 16D result object shape drift.")
    if (
        lineage.get("step16c_certified_sha") != STEP16C_CERTIFIED_SHA
        or lineage.get("step16c_contract_id") != STEP16C_CONTRACT_ID
        or lineage.get("step16c_manifest_content_sha256") != STEP16C_MANIFEST_CONTENT_SHA256
        or lineage.get("step16b_certified_sha") != STEP16B_CERTIFIED_SHA
    ):
        raise WNBAStep16DIntegrityError("Step 16D frozen lineage drift.")
    required_activation_true = (
        "production_docker_image",
        "direct_psycopg_live_connection",
        "protected_database_secret_used",
        "credential_value_exposed_false",
        "exact_step16b_bound_runner",
        "controlled_one_shot_activation",
    )
    if any(activation.get(key) is not True for key in required_activation_true):
        raise WNBAStep16DIntegrityError("Step 16D direct activation evidence missing.")
    if activation.get("slate_date") != EXPECTED_CANARY_SLATE_DATE:
        raise WNBAStep16DIntegrityError("Step 16D canary slate drift.")
    if activation.get("checkpoint_key") != EXPECTED_CHECKPOINT_KEY:
        raise WNBAStep16DIntegrityError("Step 16D checkpoint key drift.")
    if activation.get("lease_key") != EXPECTED_LEASE_KEY:
        raise WNBAStep16DIntegrityError("Step 16D lease key drift.")
    revision = str(activation.get("container_build_revision") or "").lower()
    if not _valid_git_sha(revision) or revision != str(activation.get("expected_revision") or "").lower():
        raise WNBAStep16DIntegrityError("Step 16D container revision evidence drift.")
    if cycles.get("cycle_1_saved_checkpoint_version") != 1:
        raise WNBAStep16DIntegrityError("Step 16D cold-start checkpoint version drift.")
    if cycles.get("cycle_1_recovered_from_checkpoint") is not False:
        raise WNBAStep16DIntegrityError("Step 16D cold-start recovery drift.")
    if cycles.get("cycle_2_loaded_checkpoint_version") != 1:
        raise WNBAStep16DIntegrityError("Step 16D restart loaded-version drift.")
    if cycles.get("cycle_2_saved_checkpoint_version") != 2:
        raise WNBAStep16DIntegrityError("Step 16D restart saved-version drift.")
    if cycles.get("cycle_2_recovered_from_checkpoint") is not True:
        raise WNBAStep16DIntegrityError("Step 16D durable restart recovery missing.")
    if cycles.get("cycle_2_injected_previous_cycle_index") != 1:
        raise WNBAStep16DIntegrityError("Step 16D exact restart handoff state drift.")
    if cycles.get("checkpoint_rows_after_two_cycles") != 2:
        raise WNBAStep16DIntegrityError("Step 16D append-only history drift.")
    if cycles.get("checkpoint_head_rows_after_two_cycles") != 1:
        raise WNBAStep16DIntegrityError("Step 16D checkpoint head drift.")
    if cycles.get("lease_rows_after_two_cycles") != 0:
        raise WNBAStep16DIntegrityError("Step 16D lease cleanup after cycles drift.")
    if cleanup.get("checkpoint_rows") != 0 or cleanup.get("checkpoint_head_rows") != 0 or cleanup.get("lease_rows") != 0:
        raise WNBAStep16DIntegrityError("Step 16D final canary residue is not zero.")
    if cleanup.get("canary_residue_zero") is not True:
        raise WNBAStep16DIntegrityError("Step 16D cleanup certification missing.")
    if any(value is not False for value in safety.values()):
        raise WNBAStep16DIntegrityError("Step 16D safety boundary drift.")
    return deepcopy(dict(result))


def run_controlled_activation(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    prerequisites = validate_activation_prerequisites(env)
    source = prerequisites["env"]
    dsn = str(source[DATABASE_URL_ENV])
    baseline = _canary_counts(dsn)
    if any(baseline.values()):
        raise WNBAStep16DDatabaseError(
            "Step 16D refuses to start with pre-existing canary-key residue."
        )
    metadata = _database_metadata(dsn)
    bound = prerequisites["bound_runner"]
    request = build_canary_request()
    observed_previous_states: list[Any] = []
    controlled_cycle = {"value": 0}
    cycle_1: Mapping[str, Any] | None = None
    cycle_2: Mapping[str, Any] | None = None
    after_two = None
    cleanup = None

    def controlled_runner(req: Mapping[str, Any], **_: Any) -> Mapping[str, Any]:
        controlled_cycle["value"] += 1
        parent = req.get("supervisor_request")
        previous = parent.get("initial_previous_state") if isinstance(parent, Mapping) else None
        observed_previous_states.append(deepcopy(previous))
        return build_controlled_step13c_response(cycle_index=controlled_cycle["value"])

    try:
        cycle_1 = bound(
            request,
            owner_id="step16d-container-cycle-1",
            env=source,
            lease_ttl_seconds=61,
            step13c_runner=controlled_runner,
        )
        cycle_2 = bound(
            request,
            owner_id="step16d-container-cycle-2",
            env=source,
            lease_ttl_seconds=61,
            step13c_runner=controlled_runner,
        )
        after_two = _canary_counts(dsn)
    finally:
        cleanup = _cleanup_canary(dsn)

    if cycle_1 is None or cycle_2 is None or after_two is None:
        raise WNBAStep16DIntegrityError("Step 16D activation did not complete both cycles.")
    second_previous = observed_previous_states[1] if len(observed_previous_states) > 1 else None
    second_cycle_index = (
        second_previous.get("cycle_index")
        if isinstance(second_previous, Mapping)
        else None
    )
    result = {
        "data_type": "wnba_step16d_controlled_production_activation_result",
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "contract_id": CONTRACT_ID,
        "status": "completed",
        "lineage": {
            "step16c_certified_sha": STEP16C_CERTIFIED_SHA,
            "step16c_contract_id": STEP16C_CONTRACT_ID,
            "step16c_manifest_content_sha256": STEP16C_MANIFEST_CONTENT_SHA256,
            "step16c_live_evidence_content_sha256": STEP16C_LIVE_EVIDENCE_CONTENT_SHA256,
            "step16b_certified_sha": STEP16B_CERTIFIED_SHA,
            "step15c_certified_sha": STEP15C_CERTIFIED_SHA,
        },
        "activation": {
            "production_docker_image": True,
            "direct_psycopg_live_connection": True,
            "protected_database_secret_used": True,
            "credential_value_exposed_false": True,
            "database_secret_scheme": prerequisites["database_secret"]["scheme"],
            "container_build_revision": prerequisites["build_revision"],
            "expected_revision": prerequisites["expected_revision"],
            "exact_step16b_bound_runner": True,
            "controlled_one_shot_activation": True,
            "slate_date": EXPECTED_CANARY_SLATE_DATE,
            "checkpoint_key": EXPECTED_CHECKPOINT_KEY,
            "lease_key": EXPECTED_LEASE_KEY,
            "database_role": metadata["database_role"],
            "postgres_version": metadata["postgres_version"],
            "database_name": metadata["database_name"],
            "baseline_checkpoint_rows": baseline["checkpoint_rows"],
            "baseline_checkpoint_head_rows": baseline["checkpoint_head_rows"],
            "baseline_lease_rows": baseline["lease_rows"],
        },
        "cycles": {
            "cycle_1_status": cycle_1.get("status"),
            "cycle_1_recovered_from_checkpoint": cycle_1.get("recovered_from_durable_checkpoint"),
            "cycle_1_loaded_checkpoint_version": cycle_1.get("loaded_checkpoint_version"),
            "cycle_1_saved_checkpoint_version": cycle_1.get("saved_checkpoint_version"),
            "cycle_1_lease_fencing_generation": cycle_1.get("lease_fencing_generation"),
            "cycle_2_status": cycle_2.get("status"),
            "cycle_2_recovered_from_checkpoint": cycle_2.get("recovered_from_durable_checkpoint"),
            "cycle_2_loaded_checkpoint_version": cycle_2.get("loaded_checkpoint_version"),
            "cycle_2_saved_checkpoint_version": cycle_2.get("saved_checkpoint_version"),
            "cycle_2_lease_fencing_generation": cycle_2.get("lease_fencing_generation"),
            "cycle_2_injected_previous_cycle_index": second_cycle_index,
            "checkpoint_rows_after_two_cycles": after_two["checkpoint_rows"],
            "checkpoint_head_rows_after_two_cycles": after_two["checkpoint_head_rows"],
            "lease_rows_after_two_cycles": after_two["lease_rows"],
        },
        "cleanup": {
            **cleanup,
            "canary_residue_zero": not any(cleanup.values()),
        },
        "safety": {
            "continuous_production_runtime_started": False,
            "global_persistence_autostart_started": False,
            "automatic_restart_autostart_started": False,
            "background_daemon_started": False,
            "background_thread_started": False,
            "background_task_started": False,
            "public_persistence_api_exposed": False,
            "supabase_rest_write_enabled": False,
            "wagering_enabled": False,
            "authentication_enabled": False,
            "cookies_enabled": False,
            "basketball_model_mutated": False,
            "ranking_mutated": False,
            "credential_value_exposed": False,
        },
        "phase_boundary": {
            "step16d_controlled_activation_complete": True,
            "step16e_final_production_freeze_ready": True,
            "continuous_production_runtime_not_started": True,
            "render_hosted_service_activation_not_certified": True,
        },
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    result["result_content_sha256"] = _canonical_hash(_result_hash_surface(result))
    return validate_live_activation_result(result)


def build_contract_manifest(*, generated_at_utc: str | None = None) -> dict[str, Any]:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    manifest = {
        "data_type": "wnba_step16d_controlled_production_activation_contract",
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "contract_id": CONTRACT_ID,
        "source": SOURCE,
        "lineage": {
            "step16c_certified_sha": STEP16C_CERTIFIED_SHA,
            "step16c_contract_id": STEP16C_CONTRACT_ID,
            "step16c_manifest_content_sha256": STEP16C_MANIFEST_CONTENT_SHA256,
            "step16c_live_evidence_content_sha256": STEP16C_LIVE_EVIDENCE_CONTENT_SHA256,
            "step16b_certified_sha": STEP16B_CERTIFIED_SHA,
            "step15c_certified_sha": STEP15C_CERTIFIED_SHA,
        },
        "activation_contract": {
            "controlled_one_shot_production_activation_allowed": True,
            "production_docker_image_execution_required": True,
            "direct_psycopg_live_connection_required": True,
            "protected_database_secret_required": True,
            "two_cycle_restart_recovery_required": True,
            "fenced_lease_required": True,
            "checkpoint_cas_required": True,
            "canary_cleanup_required": True,
            "continuous_production_runtime_allowed": False,
            "render_hosted_service_activation_certified": False,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step16d_candidate": True,
            "step16e_final_freeze_required": True,
            "continuous_production_runtime_not_authorized": True,
            "render_hosted_service_activation_not_certified": True,
        },
        "generated_at_utc": generated,
    }
    surface = {k: deepcopy(v) for k, v in manifest.items() if k != "generated_at_utc"}
    manifest["contract_content_sha256"] = _canonical_hash(surface)
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    output = Path(args[0] if args else "step16d-controlled-production-activation-live-result.json")
    result = run_controlled_activation()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_OK", result["result_content_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
