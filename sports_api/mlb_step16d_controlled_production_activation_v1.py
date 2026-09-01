"""MLB Step 16D — bounded controlled production activation.

Step 16D is an explicit, foreground-only activation proof over the frozen MLB
Step 16B lifecycle and Step 14C PostgreSQL persistence controls. It executes
exactly two synthetic scheduler/recovery checkpoint cycles against one isolated
canary slate key, proves restart recovery + fenced lease/CAS behavior, and then
removes every canary row in ``finally``.

This module does *not* start the MLB model runtime, scheduler loop, providers,
sportsbooks, background workers, public persistence APIs, actionable output, or
wagering. Continuous production remains out of scope and Step 16E remains the
final production freeze boundary.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
import re
from typing import Any
from uuid import uuid4

from sports_api import mlb_step12_final_runtime_freeze_v1 as step12
from sports_api import mlb_step13a_bounded_scheduler_v1 as step13a
from sports_api import mlb_step13b_runtime_supervisor_v1 as step13b
from sports_api import mlb_step13c_reliability_recovery_v1 as step13c
from sports_api import mlb_step14a_persistence_contract_v1 as step14a
from sports_api import mlb_step14b_database_checkpoint_adapter_v1 as step14b
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c
from sports_api import mlb_step16b_production_lifecycle_v1 as lifecycle
from sports_api import mlb_step16c_live_postgresql_canary_v1 as step16c
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step16d_controlled_production_activation_v1"
SCHEMA_VERSION = 1
INTEGRATION_VERSION = "mlb_step16d_controlled_production_activation_2026_v1"
CONTRACT_ID = "mlb_step16d_controlled_production_activation_2026_regular_v1"
RUNTIME_MODE = "SHADOW_ONLY"
BRANCH = "mlb-step16d-controlled-production-activation"
STEP16C_PARENT_SHA = "35c7fa29cddb9dc76ee8535d8c92cb0762233dae"
STEP16C_FINAL_MARKER = "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_GREEN"
FINAL_CERTIFICATION_MARKER = "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_GREEN"

STEP16D_ENABLED_ENV = "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED"
STEP16D_CANARY_SLATE_DATE_ENV = "MLB_STEP16D_CANARY_SLATE_DATE"
STEP16D_OWNER_PREFIX_ENV = "MLB_STEP16D_OWNER_PREFIX"
STEP16D_EXPECTED_REVISION_ENV = "MLB_STEP16D_EXPECTED_REVISION"
RELEASE_BUILD_REVISION_ENV = "MLB_RELEASE_BUILD_REVISION"
DEPLOYMENT_MODE_ENV = "MLB_DEPLOYMENT_MODE"
DEFAULT_CANARY_SLATE_DATE = "2026-01-15"
DEFAULT_OWNER_PREFIX = "mlb-step16d"
DEFAULT_LEASE_TTL_SECONDS = 120

DEFAULT_ENABLED = False
CONTROLLED_ONE_SHOT_ACTIVATION_ALLOWED = True
DIRECT_PSYCOG_CONNECTION_ALLOWED = True
TWO_CYCLE_RESTART_PROOF_REQUIRED = True
FENCED_LEASE_REQUIRED = True
CHECKPOINT_CAS_REQUIRED = True
FINALLY_CLEANUP_REQUIRED = True
ZERO_BASELINE_REQUIRED = True
ZERO_RESIDUE_REQUIRED = True

CONTINUOUS_PRODUCTION_ALLOWED = False
PRODUCTION_RUNTIME_ALLOWED = False
PRODUCTION_SCHEDULER_ALLOWED = False
BACKGROUND_WORKER_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
BACKGROUND_TASK_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
PROVIDER_CALLS_ALLOWED = False
SPORTSBOOK_CALLS_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False
WAGERING_ALLOWED = False
AUTH_MUTATION_ALLOWED = False
COOKIE_MUTATION_ALLOWED = False
MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False
SECRETS_OUTPUT_ALLOWED = False

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
)
_REQUIRED_TRUE_ENV_KEYS = (
    lifecycle.STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV,
    step14c.STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV,
    step14b.STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV,
    step14b.STEP14B_DATABASE_READ_ENABLED_ENV,
    step14b.STEP14B_DATABASE_WRITE_ENABLED_ENV,
)
_REQUIRED_BINDING_KEYS = {
    "scheduler_tick",
    "runtime_supervision",
    "recovery_decision",
    "load_restart_context",
    "restart_inputs",
    "persist_checkpoint",
    "renew_lease",
    "release_lease",
}


class MLBStep16DActivationDisabledError(RuntimeError):
    """Raised unless Step 16D is explicitly and safely enabled."""


class MLBStep16DActivationIntegrityError(RuntimeError):
    """Raised when a frozen contract, lifecycle, or cleanup boundary drifts."""


class MLBStep16DActivationDatabaseError(RuntimeError):
    """Raised when the controlled PostgreSQL activation proof fails."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled",
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


def _result_hash_surface(value: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(value))
    result.pop("observed_at_utc", None)
    result.pop("result_content_sha256", None)
    return result


def step16d_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP16D_ENABLED_ENV))


def _validated_revision(source: Mapping[str, str]) -> str:
    expected = str(source.get(STEP16D_EXPECTED_REVISION_ENV) or "").strip().lower()
    release = str(source.get(RELEASE_BUILD_REVISION_ENV) or "").strip().lower()
    if _GIT_SHA_RE.fullmatch(expected) is None:
        raise MLBStep16DActivationDisabledError(
            f"Step 16D requires {STEP16D_EXPECTED_REVISION_ENV}=<full 40-char Git SHA>"
        )
    if _GIT_SHA_RE.fullmatch(release) is None:
        raise MLBStep16DActivationDisabledError(
            f"Step 16D requires {RELEASE_BUILD_REVISION_ENV}=<full 40-char Git SHA>"
        )
    if expected != release:
        raise MLBStep16DActivationIntegrityError(
            "Step 16D expected revision does not match packaged release revision"
        )
    render_sha = str(source.get("RENDER_GIT_COMMIT") or "").strip().lower()
    if render_sha and render_sha != expected:
        raise MLBStep16DActivationIntegrityError(
            "Step 16D Render revision does not match the expected immutable revision"
        )
    return expected


def validate_step16d_enablement(
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = dict(os.environ if env is None else env)
    if not step16d_enabled(source):
        raise MLBStep16DActivationDisabledError(
            f"Step 16D requires {STEP16D_ENABLED_ENV}=true"
        )
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise MLBStep16DActivationDisabledError(
            "Step 16D refuses continuous/actionable production switches: "
            + ", ".join(bad)
        )
    missing = [key for key in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(key))]
    if missing:
        raise MLBStep16DActivationDisabledError(
            "Step 16D requires frozen lifecycle/persistence gates: "
            + ", ".join(missing)
        )
    if str(source.get(DEPLOYMENT_MODE_ENV) or "").strip().casefold() != "container":
        raise MLBStep16DActivationDisabledError(
            f"Step 16D requires {DEPLOYMENT_MODE_ENV}=container"
        )
    if not str(source.get(lifecycle.DATABASE_URL_ENV) or "").strip():
        raise MLBStep16DActivationDisabledError(
            f"Step 16D requires {lifecycle.DATABASE_URL_ENV} from the secret manager"
        )
    _validated_revision(source)

    if step16c.FINAL_CERTIFICATION_MARKER != STEP16C_FINAL_MARKER:
        raise MLBStep16DActivationIntegrityError("Step 16C certification marker drift")
    if lifecycle.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise MLBStep16DActivationIntegrityError("Step 16B activation boundary drift")
    if step14c.FENCING_GENERATION_REQUIRED is not True:
        raise MLBStep16DActivationIntegrityError("Step 14C fencing requirement drift")
    if step14c.CHECKPOINT_CAS_REQUIRED is not True:
        raise MLBStep16DActivationIntegrityError("Step 14C checkpoint CAS drift")
    if any(value is not False for value in PROTECTED_INVARIANTS.values()):
        raise MLBStep16DActivationIntegrityError("protected MLB invariant drift")

    lifecycle.validate_step16b_enablement(source)
    return source


def _validate_runtime_binding(binding: Mapping[str, Callable[..., Any]] | None) -> dict[str, Callable[..., Any]]:
    if not isinstance(binding, Mapping):
        raise MLBStep16DActivationIntegrityError("Step 16B runtime binding is unavailable")
    if set(binding) != _REQUIRED_BINDING_KEYS:
        raise MLBStep16DActivationIntegrityError("Step 16B runtime binding key drift")
    exact = {
        "scheduler_tick": step13a.build_bounded_scheduler_tick,
        "runtime_supervision": step13b.build_runtime_supervision,
        "recovery_decision": step13c.build_recovery_decision,
        "load_restart_context": step14c.load_step14c_restart_context,
        "restart_inputs": step14c.restart_inputs_from_context,
        "persist_checkpoint": step14c.persist_step14c_checkpoint_under_lease,
        "renew_lease": step14c.renew_step14c_lease,
        "release_lease": step14c.release_step14c_lease,
    }
    for key, expected in exact.items():
        if binding[key] is not expected:
            raise MLBStep16DActivationIntegrityError(
                f"Step 16B runtime binding identity drift: {key}"
            )
    return dict(binding)


def _slate_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise MLBStep16DActivationDisabledError(
            f"{STEP16D_CANARY_SLATE_DATE_ENV} must use YYYY-MM-DD"
        ) from exc
    if parsed.year != 2026:
        raise MLBStep16DActivationDisabledError(
            "Step 16D canary slate must remain inside the frozen 2026 season"
        )
    return parsed


def _cycle_time(slate: date, cycle_number: int) -> str:
    base = datetime(slate.year, slate.month, slate.day, tzinfo=timezone.utc)
    return (base + timedelta(minutes=cycle_number)).isoformat().replace("+00:00", "Z")


def _build_checkpoint_envelope(
    *,
    slate_date: str,
    cycle_number: int,
    prior_recovery_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    parsed = _slate_date(slate_date)
    evaluated = _cycle_time(parsed, cycle_number)
    anchor = datetime(
        parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc
    ).isoformat().replace("+00:00", "Z")
    scheduler_state = {
        "last_granted_slot_utc": None,
        "active_cycle_id": None,
        "active_cycle_slot_utc": None,
    }
    tick = step13a.build_bounded_scheduler_tick(
        evaluated_at_utc=evaluated,
        scheduler_anchor_utc=anchor,
        scheduler_state=scheduler_state,
        step12_final_manifest=step12.final_runtime_freeze_manifest(),
        scheduler_enabled=False,
    )
    supervision = step13b.build_runtime_supervision(
        tick,
        observed_at_utc=evaluated,
        cycle_observation=None,
        step13a_manifest=step13a.bounded_scheduler_manifest(),
    )
    decision = step13c.build_recovery_decision(
        supervision,
        evaluated_at_utc=evaluated,
        recovery_state=prior_recovery_state,
    )
    envelope = step14a.build_step14a_checkpoint_envelope(
        recovery_decision=decision,
        scheduler_state=tick["scheduler_state"],
        slate_date=slate_date,
        created_at_utc=evaluated,
    )
    validation = step14a.validate_step14a_checkpoint_envelope(
        envelope, expected_slate_date=slate_date,
    )
    if validation.get("envelope_valid") is not True:
        raise MLBStep16DActivationIntegrityError(
            "Step 16D synthetic checkpoint failed frozen Step 14A validation"
        )
    return envelope


def _open_connection(env: Mapping[str, str]) -> Any:
    try:
        import psycopg
        return psycopg.connect(
            str(env[lifecycle.DATABASE_URL_ENV]),
            connect_timeout=10,
            application_name="kyre-sports-ai-mlb-step16d",
        )
    except Exception as exc:
        raise MLBStep16DActivationDatabaseError(
            "Step 16D could not open the direct PostgreSQL connection"
        ) from exc


def _direct_database_probe(
    *,
    env: Mapping[str, str],
    checkpoint_key: str,
    lease_key: str,
) -> dict[str, Any]:
    connection = _open_connection(env)
    cursor = None
    try:
        cursor = connection.cursor()
        schema = step14a.DATABASE_SCHEMA_NAME
        checkpoint_table = step14a.CHECKPOINT_TABLE_NAME
        head_table = step14a.CHECKPOINT_HEAD_TABLE_NAME
        lease_table = step14c.LEASE_TABLE_NAME
        cursor.execute(
            "SELECT to_regclass(%s) IS NOT NULL, to_regclass(%s) IS NOT NULL, "
            "to_regclass(%s) IS NOT NULL",
            (
                f"{schema}.{checkpoint_table}",
                f"{schema}.{head_table}",
                f"{schema}.{lease_table}",
            ),
        )
        present = cursor.fetchone()
        if not isinstance(present, (tuple, list)) or len(present) != 3:
            raise MLBStep16DActivationDatabaseError("Step 16D schema probe shape drift")
        counts: dict[str, int] = {}
        for label, table, key_field, key_value in (
            ("checkpoint_rows", checkpoint_table, "checkpoint_key", checkpoint_key),
            ("head_rows", head_table, "checkpoint_key", checkpoint_key),
            ("lease_rows", lease_table, "lease_key", lease_key),
        ):
            cursor.execute(
                f'SELECT count(*) FROM "{schema}"."{table}" WHERE "{key_field}" = %s',
                (key_value,),
            )
            row = cursor.fetchone()
            if not isinstance(row, (tuple, list)) or len(row) != 1:
                raise MLBStep16DActivationDatabaseError(
                    f"Step 16D {label} probe shape drift"
                )
            counts[label] = int(row[0])
        connection.rollback()
        return {
            "checkpoint_table_present": present[0] is True,
            "checkpoint_head_table_present": present[1] is True,
            "lease_table_present": present[2] is True,
            **counts,
        }
    except MLBStep16DActivationDatabaseError:
        try:
            connection.rollback()
        except Exception:
            pass
        raise
    except Exception as exc:
        try:
            connection.rollback()
        except Exception:
            pass
        raise MLBStep16DActivationDatabaseError("Step 16D database probe failed") from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()


def _cleanup_canary_rows(
    *,
    env: Mapping[str, str],
    checkpoint_key: str,
    lease_key: str,
) -> None:
    connection = _open_connection(env)
    cursor = None
    try:
        cursor = connection.cursor()
        schema = step14a.DATABASE_SCHEMA_NAME
        for table, key_field, key_value in (
            (step14c.LEASE_TABLE_NAME, "lease_key", lease_key),
            (step14a.CHECKPOINT_HEAD_TABLE_NAME, "checkpoint_key", checkpoint_key),
            (step14a.CHECKPOINT_TABLE_NAME, "checkpoint_key", checkpoint_key),
        ):
            cursor.execute(
                f'DELETE FROM "{schema}"."{table}" WHERE "{key_field}" = %s',
                (key_value,),
            )
        connection.commit()
    except Exception as exc:
        try:
            connection.rollback()
        except Exception:
            pass
        raise MLBStep16DActivationDatabaseError("Step 16D canary cleanup failed") from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()


def _release_best_effort(
    binding: Mapping[str, Callable[..., Any]],
    handle: Mapping[str, Any] | None,
    source: Mapping[str, str],
) -> bool:
    if not isinstance(handle, Mapping):
        return False
    try:
        return binding["release_lease"](handle=handle, env=source) is True
    except Exception:
        return False


def _assert_probe_counts(probe: Mapping[str, Any], *, checkpoints: int, heads: int, leases: int) -> None:
    if not all(
        probe.get(key) is True
        for key in (
            "checkpoint_table_present",
            "checkpoint_head_table_present",
            "lease_table_present",
        )
    ):
        raise MLBStep16DActivationIntegrityError("Step 16D required PostgreSQL schema is missing")
    observed = (
        int(probe.get("checkpoint_rows", -1)),
        int(probe.get("head_rows", -1)),
        int(probe.get("lease_rows", -1)),
    )
    if observed != (checkpoints, heads, leases):
        raise MLBStep16DActivationIntegrityError(
            "Step 16D scoped row-count mismatch: "
            f"observed={observed} expected={(checkpoints, heads, leases)}"
        )


def run_step16d_controlled_production_activation(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute exactly two durable canary checkpoint cycles, then clean up."""
    source = validate_step16d_enablement(env)
    binding = _validate_runtime_binding(lifecycle.get_step16b_runtime_binding(source))
    slate_date = str(source.get(STEP16D_CANARY_SLATE_DATE_ENV) or DEFAULT_CANARY_SLATE_DATE).strip()
    _slate_date(slate_date)
    owner_prefix = str(source.get(STEP16D_OWNER_PREFIX_ENV) or DEFAULT_OWNER_PREFIX).strip()
    if not owner_prefix or len(owner_prefix) > 180:
        raise MLBStep16DActivationDisabledError("Step 16D owner prefix is invalid")

    checkpoint_key = step14a.checkpoint_key_for_slate(slate_date)
    lease_key = step14c.lease_key_for_slate(slate_date)
    baseline = _direct_database_probe(
        env=source, checkpoint_key=checkpoint_key, lease_key=lease_key,
    )
    _assert_probe_counts(baseline, checkpoints=0, heads=0, leases=0)

    cleanup_authorized = True
    handle1: Mapping[str, Any] | None = None
    handle2: Mapping[str, Any] | None = None
    persist1: dict[str, Any] | None = None
    persist2: dict[str, Any] | None = None
    after_writes: dict[str, Any] | None = None
    cleanup_error: Exception | None = None

    try:
        context1 = binding["load_restart_context"](
            slate_date=slate_date,
            owner_id=f"{owner_prefix}-cycle-1-{uuid4()}",
            lease_ttl_seconds=DEFAULT_LEASE_TTL_SECONDS,
            env=source,
        )
        handle1 = deepcopy(context1.get("lease"))
        if context1.get("found") is not False or context1.get("expected_head_version") != 0:
            raise MLBStep16DActivationIntegrityError(
                "Step 16D cycle 1 did not start from an empty scoped checkpoint"
            )
        envelope1 = _build_checkpoint_envelope(
            slate_date=slate_date,
            cycle_number=1,
            prior_recovery_state=None,
        )
        persist1 = binding["persist_checkpoint"](
            restart_context=context1,
            checkpoint_envelope=envelope1,
            lease_ttl_seconds=DEFAULT_LEASE_TTL_SECONDS,
            env=source,
        )
        handle1 = deepcopy(persist1.get("lease"))
        if persist1.get("saved_checkpoint_version") != 1:
            raise MLBStep16DActivationIntegrityError("Step 16D cycle 1 version drift")
        if binding["release_lease"](handle=handle1, env=source) is not True:
            raise MLBStep16DActivationIntegrityError("Step 16D cycle 1 lease release failed")
        handle1 = None

        context2 = binding["load_restart_context"](
            slate_date=slate_date,
            owner_id=f"{owner_prefix}-cycle-2-{uuid4()}",
            lease_ttl_seconds=DEFAULT_LEASE_TTL_SECONDS,
            env=source,
        )
        handle2 = deepcopy(context2.get("lease"))
        if context2.get("found") is not True or context2.get("loaded_checkpoint_version") != 1:
            raise MLBStep16DActivationIntegrityError(
                "Step 16D cycle 2 failed to recover cycle 1 checkpoint"
            )
        if context2.get("checkpoint_id") != persist1.get("saved_checkpoint_id"):
            raise MLBStep16DActivationIntegrityError(
                "Step 16D cycle 2 recovered the wrong checkpoint lineage"
            )
        envelope2 = _build_checkpoint_envelope(
            slate_date=slate_date,
            cycle_number=2,
            prior_recovery_state=context2.get("recovery_state_for_restart"),
        )
        persist2 = binding["persist_checkpoint"](
            restart_context=context2,
            checkpoint_envelope=envelope2,
            lease_ttl_seconds=DEFAULT_LEASE_TTL_SECONDS,
            env=source,
        )
        handle2 = deepcopy(persist2.get("lease"))
        if persist2.get("previous_checkpoint_version") != 1 or persist2.get("saved_checkpoint_version") != 2:
            raise MLBStep16DActivationIntegrityError("Step 16D cycle 2 CAS lineage drift")
        if binding["release_lease"](handle=handle2, env=source) is not True:
            raise MLBStep16DActivationIntegrityError("Step 16D cycle 2 lease release failed")
        handle2 = None

        after_writes = _direct_database_probe(
            env=source, checkpoint_key=checkpoint_key, lease_key=lease_key,
        )
        _assert_probe_counts(after_writes, checkpoints=2, heads=1, leases=0)
    finally:
        _release_best_effort(binding, handle2, source)
        _release_best_effort(binding, handle1, source)
        if cleanup_authorized:
            try:
                _cleanup_canary_rows(
                    env=source, checkpoint_key=checkpoint_key, lease_key=lease_key,
                )
            except Exception as exc:
                cleanup_error = exc

    if cleanup_error is not None:
        raise MLBStep16DActivationDatabaseError(
            "Step 16D cleanup failed; manual investigation is required"
        ) from cleanup_error
    if persist1 is None or persist2 is None or after_writes is None:
        raise MLBStep16DActivationIntegrityError("Step 16D activation proof did not complete")

    residue = _direct_database_probe(
        env=source, checkpoint_key=checkpoint_key, lease_key=lease_key,
    )
    _assert_probe_counts(residue, checkpoints=0, heads=0, leases=0)

    observed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "contract_id": CONTRACT_ID,
        "runtime_mode": RUNTIME_MODE,
        "branch": BRANCH,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "release_revision": _validated_revision(source),
        "slate_date": slate_date,
        "checkpoint_key": checkpoint_key,
        "lease_key": lease_key,
        "cycle_count": 2,
        "cycle_1_saved_version": persist1["saved_checkpoint_version"],
        "cycle_2_recovered_version": persist2["previous_checkpoint_version"],
        "cycle_2_saved_version": persist2["saved_checkpoint_version"],
        "checkpoint_history_rows_before_cleanup": after_writes["checkpoint_rows"],
        "checkpoint_head_rows_before_cleanup": after_writes["head_rows"],
        "lease_rows_before_cleanup": after_writes["lease_rows"],
        "checkpoint_rows_after_cleanup": residue["checkpoint_rows"],
        "checkpoint_head_rows_after_cleanup": residue["head_rows"],
        "lease_rows_after_cleanup": residue["lease_rows"],
        "controlled_one_shot_activation_executed": True,
        "restart_recovery_proved": True,
        "fenced_lease_proved": True,
        "checkpoint_cas_proved": True,
        "finally_cleanup_proved": True,
        "continuous_production_started": False,
        "production_runtime_started": False,
        "production_scheduler_started": False,
        "background_worker_started": False,
        "background_thread_started": False,
        "background_task_started": False,
        "public_persistence_api_exposed": False,
        "supabase_rest_write_used": False,
        "provider_calls": 0,
        "sportsbook_calls": 0,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
        "auth_mutated": False,
        "cookies_mutated": False,
        "model_mutated": False,
        "ranking_mutated": False,
        "secret_value_exposed": False,
        "step16e_final_production_freeze_ready": True,
        "hosted_continuous_service_certified": False,
        "observed_at_utc": observed,
    }
    result["result_content_sha256"] = _hash(_result_hash_surface(result))
    validation = validate_step16d_result(result)
    if validation.get("result_valid") is not True:
        raise MLBStep16DActivationIntegrityError(
            "Step 16D result failed self-validation: " + repr(validation.get("failures"))
        )
    return result


def validate_step16d_result(result: Mapping[str, Any] | None) -> dict[str, Any]:
    failures: list[str] = []
    if not isinstance(result, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "result_valid": False,
            "failures": ["STEP16D_RESULT_NOT_MAPPING"],
        }
    value = dict(result)
    try:
        exact = {
            "data_type": value.get("data_type") == DATA_TYPE,
            "schema_version": value.get("schema_version") == SCHEMA_VERSION,
            "integration_version": value.get("integration_version") == INTEGRATION_VERSION,
            "contract_id": value.get("contract_id") == CONTRACT_ID,
            "runtime_mode": value.get("runtime_mode") == RUNTIME_MODE,
            "branch": value.get("branch") == BRANCH,
            "marker": value.get("final_certification_marker") == FINAL_CERTIFICATION_MARKER,
            "cycles": value.get("cycle_count") == 2,
            "v1": value.get("cycle_1_saved_version") == 1,
            "recovered_v1": value.get("cycle_2_recovered_version") == 1,
            "v2": value.get("cycle_2_saved_version") == 2,
            "history_two": value.get("checkpoint_history_rows_before_cleanup") == 2,
            "head_one": value.get("checkpoint_head_rows_before_cleanup") == 1,
            "lease_zero_before_cleanup": value.get("lease_rows_before_cleanup") == 0,
            "checkpoint_cleanup": value.get("checkpoint_rows_after_cleanup") == 0,
            "head_cleanup": value.get("checkpoint_head_rows_after_cleanup") == 0,
            "lease_cleanup": value.get("lease_rows_after_cleanup") == 0,
            "activation": value.get("controlled_one_shot_activation_executed") is True,
            "restart": value.get("restart_recovery_proved") is True,
            "fencing": value.get("fenced_lease_proved") is True,
            "cas": value.get("checkpoint_cas_proved") is True,
            "cleanup": value.get("finally_cleanup_proved") is True,
            "step16e": value.get("step16e_final_production_freeze_ready") is True,
        }
        failed = [name for name, ok in exact.items() if not ok]
        if failed:
            raise MLBStep16DActivationIntegrityError(
                "Step 16D result contract drift: " + ", ".join(failed)
            )
        forbidden = (
            "continuous_production_started",
            "production_runtime_started",
            "production_scheduler_started",
            "background_worker_started",
            "background_thread_started",
            "background_task_started",
            "public_persistence_api_exposed",
            "supabase_rest_write_used",
            "actionable_output_enabled",
            "wagering_enabled",
            "auth_mutated",
            "cookies_mutated",
            "model_mutated",
            "ranking_mutated",
            "secret_value_exposed",
            "hosted_continuous_service_certified",
        )
        if any(value.get(key) is not False for key in forbidden):
            raise MLBStep16DActivationIntegrityError("Step 16D forbidden capability drift")
        if value.get("provider_calls") != 0 or value.get("sportsbook_calls") != 0:
            raise MLBStep16DActivationIntegrityError("Step 16D network-call boundary drift")
        revision = value.get("release_revision")
        if not isinstance(revision, str) or _GIT_SHA_RE.fullmatch(revision) is None:
            raise MLBStep16DActivationIntegrityError("Step 16D release revision invalid")
        digest = value.get("result_content_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise MLBStep16DActivationIntegrityError("Step 16D result hash invalid")
        if digest != _hash(_result_hash_surface(value)):
            raise MLBStep16DActivationIntegrityError("Step 16D result content hash mismatch")
    except Exception as exc:
        failures.append(f"STEP16D_RESULT_INVALID:{type(exc).__name__}:{exc}")
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "result_valid": not failures,
        "failures": failures,
    }


def controlled_production_activation_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "contract_id": CONTRACT_ID,
        "runtime_mode": RUNTIME_MODE,
        "branch": BRANCH,
        "step16c_parent_sha": STEP16C_PARENT_SHA,
        "step16c_final_marker_required": STEP16C_FINAL_MARKER,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "default_enabled": False,
        "explicit_gate_required": True,
        "immutable_release_revision_required": True,
        "container_deployment_required": True,
        "direct_psycopg_connection_allowed": True,
        "controlled_one_shot_activation_allowed": True,
        "exact_two_cycle_restart_proof_required": True,
        "fenced_lease_required": True,
        "checkpoint_cas_required": True,
        "zero_baseline_required": True,
        "finally_cleanup_required": True,
        "zero_residue_required": True,
        "continuous_production_allowed": False,
        "production_runtime_allowed": False,
        "production_scheduler_allowed": False,
        "background_worker_allowed": False,
        "background_thread_allowed": False,
        "background_task_allowed": False,
        "public_persistence_api_allowed": False,
        "supabase_rest_write_allowed": False,
        "provider_calls_allowed": False,
        "sportsbook_calls_allowed": False,
        "actionable_output_allowed": False,
        "wagering_allowed": False,
        "auth_mutation_allowed": False,
        "cookie_mutation_allowed": False,
        "model_mutation_allowed": False,
        "ranking_mutation_allowed": False,
        "secrets_output_allowed": False,
        "future_step16e_final_production_freeze_required": True,
        **PROTECTED_INVARIANTS,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "INTEGRATION_VERSION",
    "CONTRACT_ID",
    "RUNTIME_MODE",
    "BRANCH",
    "STEP16C_PARENT_SHA",
    "STEP16C_FINAL_MARKER",
    "FINAL_CERTIFICATION_MARKER",
    "STEP16D_ENABLED_ENV",
    "STEP16D_CANARY_SLATE_DATE_ENV",
    "STEP16D_OWNER_PREFIX_ENV",
    "STEP16D_EXPECTED_REVISION_ENV",
    "RELEASE_BUILD_REVISION_ENV",
    "DEPLOYMENT_MODE_ENV",
    "DEFAULT_CANARY_SLATE_DATE",
    "DEFAULT_LEASE_TTL_SECONDS",
    "DEFAULT_ENABLED",
    "CONTROLLED_ONE_SHOT_ACTIVATION_ALLOWED",
    "CONTINUOUS_PRODUCTION_ALLOWED",
    "MLBStep16DActivationDisabledError",
    "MLBStep16DActivationIntegrityError",
    "MLBStep16DActivationDatabaseError",
    "step16d_enabled",
    "validate_step16d_enablement",
    "run_step16d_controlled_production_activation",
    "validate_step16d_result",
    "controlled_production_activation_manifest",
]
