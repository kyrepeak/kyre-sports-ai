"""MLB Step 17B — controlled always-on durable control runtime.

Step 17B is additive to the frozen Step 16E release and certified Step 17A host
contract. It activates one explicitly gated, PostgreSQL-leader-controlled
background *control* loop on the existing host. Each leader iteration writes one
validated Step 13/14 control checkpoint under the frozen Step 14C lease/CAS
boundary and releases the slate lease immediately.

This step deliberately does not activate provider/sportsbook networking, model
workload execution, actionable output, wagering, the legacy production runtime
switch, or the legacy production scheduler switch. Those frozen switches remain
OFF. The always-on behavior certified here is process supervision + durable
restart heartbeat only, with one global advisory leader and exact checkpoint
recovery across redeploys.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import os
import re
import threading
from typing import Any, AsyncIterator, Callable, Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from sports_api import mlb_step12_final_runtime_freeze_v1 as step12
from sports_api import mlb_step13a_bounded_scheduler_v1 as step13a
from sports_api import mlb_step13b_runtime_supervisor_v1 as step13b
from sports_api import mlb_step13c_reliability_recovery_v1 as step13c
from sports_api import mlb_step14a_persistence_contract_v1 as step14a
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c
from sports_api import mlb_step16b_production_lifecycle_v1 as step16b
from sports_api import mlb_step17a_production_host_contract_v1 as step17a
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step17b_controlled_always_on_runtime_v1"
STATUS_DATA_TYPE = "mlb_step17b_runtime_status_v1"
SCHEMA_VERSION = 1
RUNTIME_VERSION = "mlb_step17b_render_single_leader_durable_control_loop_2026_v1"
CONTRACT_ID = "mlb_step17b_controlled_always_on_2026_v1"
RUNTIME_MODE = "SHADOW_ONLY"
BRANCH = "mlb-step17b-controlled-always-on"
STEP17A_MAIN_SHA = "99336141ff416af13bd03dae245fbbb42de23680"
STEP17A_FINAL_MARKER = "MLB_STEP17A_PRODUCTION_HOST_CONTRACT_GREEN"
FINAL_CERTIFICATION_MARKER = "MLB_STEP17B_CONTROLLED_ALWAYS_ON_GREEN"
SEASON = 2026
SLATE_TIMEZONE = "America/New_York"

STEP17B_ENABLED_ENV = "MLB_STEP17B_ALWAYS_ON_ENABLED"
STEP17B_LOOP_SECONDS_ENV = "MLB_STEP17B_LOOP_SECONDS"
STEP17B_EXPECTED_REVISION_ENV = "MLB_STEP17B_EXPECTED_REVISION"
DEPLOYMENT_MODE_ENV = "MLB_DEPLOYMENT_MODE"
DATABASE_URL_ENV = step14c.DATABASE_URL_ENV

DEFAULT_ENABLED = False
DEFAULT_LOOP_SECONDS = 60
MIN_LOOP_SECONDS = 30
MAX_LOOP_SECONDS = 3600
LEADERSHIP_RETRY_SECONDS = 15
SHUTDOWN_GRACE_SECONDS = 90
CONTROL_LEASE_TTL_SECONDS = 120

HOSTED_ALWAYS_ON_CONTROL_ALLOWED = True
BACKGROUND_TASK_ALLOWED = True
DIRECT_POSTGRESQL_ALLOWED = True
DURABLE_RESTART_ALLOWED = True
CHECKPOINT_CAS_REQUIRED = True
GLOBAL_ADVISORY_LEADER_REQUIRED = True
PROVIDER_WORKLOAD_ALLOWED = False
SPORTSBOOK_WORKLOAD_ALLOWED = False
LEGACY_PRODUCTION_RUNTIME_ALLOWED = False
LEGACY_PRODUCTION_SCHEDULER_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False
WAGERING_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False
SECRETS_OUTPUT_ALLOWED = False

LEADERSHIP_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"kyre-sports-api:mlb:step17b:always-on-control-leader:v1").digest()[:8],
    "big",
) & ((1 << 63) - 1)

_REQUIRED_TRUE_GATES = (
    step16b.STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV,
    step14c.STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV,
    "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
    "MLB_STEP14B_DATABASE_READ_ENABLED",
    "MLB_STEP14B_DATABASE_WRITE_ENABLED",
)

_FROZEN_FALSE_GATES = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
    "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED",
    "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED",
    "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED",
)

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_STATUS_LOCK = threading.RLock()
_STATUS: dict[str, Any] = {}


class MLBStep17BDisabledError(RuntimeError):
    """Raised unless Step 17B is explicitly enabled."""


class MLBStep17BIntegrityError(RuntimeError):
    """Raised when a frozen parent, host, or safety boundary drifts."""


class MLBStep17BLeadershipError(RuntimeError):
    """Raised when the PostgreSQL advisory leadership session fails."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled",
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def step17b_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP17B_ENABLED_ENV))


def _strict_loop_seconds(value: object) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise MLBStep17BIntegrityError("Step 17B loop seconds must be an integer") from exc
    if not MIN_LOOP_SECONDS <= parsed <= MAX_LOOP_SECONDS:
        raise MLBStep17BIntegrityError(
            f"Step 17B loop seconds must be {MIN_LOOP_SECONDS}..{MAX_LOOP_SECONDS}"
        )
    return parsed


def _validate_database_url(value: object) -> None:
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if (
        not raw
        or parsed.scheme.casefold() not in {"postgres", "postgresql"}
        or not parsed.hostname
        or parsed.path in {"", "/"}
    ):
        raise MLBStep17BIntegrityError(
            "Step 17B requires protected PostgreSQL KYRE_DATABASE_URL"
        )


def _assert_parent_identity() -> None:
    checks = {
        "step17a_marker": step17a.FINAL_CERTIFICATION_MARKER == STEP17A_FINAL_MARKER,
        "step17a_host": step17a.EXPECTED_RENDER_SERVICE_ID == "srv-da84q6ifngtc73bdbm6g",
        "step17a_autodeploy": step17a.AUTO_DEPLOY_MUST_REMAIN_DISABLED is True,
        "step16b_marker": step16b.INTEGRATION_VERSION
        == "mlb_step16b_production_packaging_lifecycle_2026_v1",
        "step14c_marker": step14c.FINAL_CERTIFICATION_MARKER
        == "MLB_STEP14C_DURABLE_RESTART_LEASE_GREEN",
        "step13a_marker": step13a.FINAL_CERTIFICATION_MARKER
        == "MLB_STEP13A_BOUNDED_SCHEDULER_GREEN",
        "step13b_marker": step13b.FINAL_CERTIFICATION_MARKER
        == "MLB_STEP13B_RUNTIME_SUPERVISOR_GREEN",
        "step13c_marker": step13c.FINAL_CERTIFICATION_MARKER
        == "MLB_STEP13C_RELIABILITY_RECOVERY_GREEN",
        "runtime_mode": all(
            item == RUNTIME_MODE
            for item in (
                step13a.RUNTIME_MODE,
                step13b.RUNTIME_MODE,
                step13c.RUNTIME_MODE,
                step14c.RUNTIME_MODE,
                step16b.RUNTIME_MODE,
            )
        ),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise MLBStep17BIntegrityError(
            "Step 17B frozen parent identity drift: " + ", ".join(failed)
        )
    if any(value is not False for value in PROTECTED_INVARIANTS.values()):
        raise MLBStep17BIntegrityError("Step 17B protected MLB invariant drift")


def build_runtime_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = {
        str(key): str(value)
        for key, value in dict(os.environ if env is None else env).items()
    }
    source[STEP17B_ENABLED_ENV] = "true"
    for key in _REQUIRED_TRUE_GATES:
        source[key] = "true"
    for key in _FROZEN_FALSE_GATES:
        source[key] = "false"
    return source


def validate_step17b_startup(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step17b_enabled(source):
        raise MLBStep17BDisabledError(f"{STEP17B_ENABLED_ENV}=true is required")
    if str(source.get(DEPLOYMENT_MODE_ENV) or "").strip().casefold() != "container":
        raise MLBStep17BIntegrityError("Step 17B requires MLB_DEPLOYMENT_MODE=container")
    if str(source.get("WEB_CONCURRENCY") or "").strip() != "1":
        raise MLBStep17BIntegrityError("Step 17B requires WEB_CONCURRENCY=1")
    bad = [key for key in _FROZEN_FALSE_GATES if _truthy(source.get(key))]
    if bad:
        raise MLBStep17BIntegrityError(
            "Step 17B refuses frozen production/actionable switches: " + ", ".join(bad)
        )
    missing = [key for key in _REQUIRED_TRUE_GATES if not _truthy(source.get(key))]
    if missing:
        raise MLBStep17BIntegrityError(
            "Step 17B requires frozen durable gates: " + ", ".join(missing)
        )
    _validate_database_url(source.get(DATABASE_URL_ENV))
    loop_seconds = _strict_loop_seconds(
        source.get(STEP17B_LOOP_SECONDS_ENV, DEFAULT_LOOP_SECONDS)
    )
    expected_revision = str(source.get(STEP17B_EXPECTED_REVISION_ENV) or "").strip().lower()
    if _GIT_SHA_RE.fullmatch(expected_revision) is None:
        raise MLBStep17BIntegrityError(
            "Step 17B expected revision must be a full 40-character Git SHA"
        )
    render_revision = str(source.get("RENDER_GIT_COMMIT") or "").strip().lower()
    if render_revision and render_revision != expected_revision:
        raise MLBStep17BIntegrityError(
            "Step 17B Render revision does not match expected immutable revision"
        )
    _assert_parent_identity()
    step16b.validate_step16b_enablement(build_runtime_env(source))
    return {
        "loop_seconds": loop_seconds,
        "database_secret_configured": True,
        "database_secret_exposed": False,
        "web_concurrency": 1,
        "expected_revision": expected_revision,
        "leadership_lock_key": LEADERSHIP_LOCK_KEY,
        "provider_workload_enabled": False,
        "sportsbook_workload_enabled": False,
        "legacy_production_runtime_enabled": False,
        "legacy_production_scheduler_enabled": False,
    }


def _slate_date(now: datetime | None = None) -> str:
    current = now or _utc_now()
    return current.astimezone(ZoneInfo(SLATE_TIMEZONE)).date().isoformat()


def _control_checkpoint(
    *,
    slate_date: str,
    evaluated_at_utc: str,
    scheduler_state: Mapping[str, Any] | None,
    recovery_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    parsed = datetime.fromisoformat(slate_date + "T00:00:00+00:00")
    anchor = parsed.isoformat().replace("+00:00", "Z")
    state = deepcopy(dict(scheduler_state or {}))
    if not state:
        state = {
            "last_granted_slot_utc": None,
            "active_cycle_id": None,
            "active_cycle_slot_utc": None,
        }
    tick = step13a.build_bounded_scheduler_tick(
        evaluated_at_utc=evaluated_at_utc,
        scheduler_anchor_utc=anchor,
        scheduler_state=state,
        step12_final_manifest=step12.final_runtime_freeze_manifest(),
        scheduler_enabled=False,
    )
    supervision = step13b.build_runtime_supervision(
        tick,
        observed_at_utc=evaluated_at_utc,
        cycle_observation=None,
        step13a_manifest=step13a.bounded_scheduler_manifest(),
    )
    decision = step13c.build_recovery_decision(
        supervision,
        evaluated_at_utc=evaluated_at_utc,
        recovery_state=recovery_state,
    )
    envelope = step14a.build_step14a_checkpoint_envelope(
        recovery_decision=decision,
        scheduler_state=tick["scheduler_state"],
        slate_date=slate_date,
        created_at_utc=evaluated_at_utc,
    )
    validation = step14a.validate_step14a_checkpoint_envelope(
        envelope,
        expected_slate_date=slate_date,
    )
    if validation.get("envelope_valid") is not True:
        raise MLBStep17BIntegrityError(
            "Step 17B control checkpoint failed frozen Step 14A validation"
        )
    return envelope


def run_one_control_cycle(
    *,
    env: Mapping[str, str],
    owner_id: str,
    slate_date: str | None = None,
    now: datetime | None = None,
    load_restart_context: Callable[..., Mapping[str, Any]] | None = None,
    persist_checkpoint: Callable[..., Mapping[str, Any]] | None = None,
    release_lease: Callable[..., bool] | None = None,
) -> dict[str, Any]:
    """Persist one no-provider control heartbeat through the frozen lease/CAS path."""
    runtime_env = build_runtime_env(env)
    slate = slate_date or _slate_date(now)
    evaluated = (now or _utc_now()).astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    loader = load_restart_context or step14c.load_step14c_restart_context
    persister = persist_checkpoint or step14c.persist_step14c_checkpoint_under_lease
    releaser = release_lease or step14c.release_step14c_lease

    context: Mapping[str, Any] | None = None
    release_handle: Mapping[str, Any] | None = None
    try:
        context = loader(
            slate_date=slate,
            owner_id=owner_id,
            lease_ttl_seconds=CONTROL_LEASE_TTL_SECONDS,
            env=runtime_env,
        )
        if not isinstance(context, Mapping):
            raise MLBStep17BIntegrityError("Step 17B restart context shape drift")
        release_handle = deepcopy(context.get("lease"))
        envelope = _control_checkpoint(
            slate_date=slate,
            evaluated_at_utc=evaluated,
            scheduler_state=context.get("scheduler_state_for_restart"),
            recovery_state=context.get("recovery_state_for_restart"),
        )
        persisted = persister(
            restart_context=context,
            checkpoint_envelope=envelope,
            lease_ttl_seconds=CONTROL_LEASE_TTL_SECONDS,
            env=runtime_env,
        )
        if not isinstance(persisted, Mapping):
            raise MLBStep17BIntegrityError("Step 17B persist result shape drift")
        release_handle = deepcopy(persisted.get("lease"))
        previous = persisted.get("previous_checkpoint_version")
        saved = persisted.get("saved_checkpoint_version")
        if (
            isinstance(previous, bool)
            or not isinstance(previous, int)
            or isinstance(saved, bool)
            or not isinstance(saved, int)
            or saved != previous + 1
        ):
            raise MLBStep17BIntegrityError("Step 17B checkpoint CAS/version drift")
        if releaser(handle=release_handle, env=runtime_env) is not True:
            raise MLBStep17BIntegrityError("Step 17B slate lease release failed")
        release_handle = None
        return {
            "status": "completed",
            "slate_date": slate,
            "previous_checkpoint_version": previous,
            "saved_checkpoint_version": saved,
            "recovered_from_durable_checkpoint": context.get("found") is True,
            "control_checkpoint_persisted": True,
            "slate_lease_released": True,
            "scheduler_permit_granted": False,
            "provider_workload_executed": False,
            "sportsbook_workload_executed": False,
            "provider_calls": 0,
            "sportsbook_calls": 0,
            "actionable_output_enabled": False,
            "wagering_enabled": False,
            "database_secret_exposed": False,
        }
    except Exception:
        if release_handle is not None:
            try:
                releaser(handle=release_handle, env=runtime_env)
            except Exception:
                pass
        raise


class AdvisoryLeadership:
    """Own one PostgreSQL session advisory lock for the process lifetime."""

    def __init__(self, connection: Any):
        self.connection = connection
        self.acquired = False

    @classmethod
    def attempt(cls, env: Mapping[str, str]) -> "AdvisoryLeadership | None":
        dsn = str(env.get(DATABASE_URL_ENV) or "").strip()
        try:
            import psycopg  # type: ignore

            connection = psycopg.connect(
                dsn,
                connect_timeout=10,
                application_name="kyre-sports-ai-mlb-step17b-leader",
                autocommit=True,
            )
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", (LEADERSHIP_LOCK_KEY,))
                row = cursor.fetchone()
            finally:
                cursor.close()
            if not isinstance(row, (tuple, list)) or len(row) != 1:
                connection.close()
                raise MLBStep17BLeadershipError(
                    "Step 17B leadership query returned invalid shape"
                )
            if row[0] is not True:
                connection.close()
                return None
            leadership = cls(connection)
            leadership.acquired = True
            return leadership
        except MLBStep17BLeadershipError:
            raise
        except Exception as exc:
            raise MLBStep17BLeadershipError(
                "Step 17B could not acquire PostgreSQL leadership"
            ) from exc

    def check(self) -> bool:
        if not self.acquired:
            return False
        try:
            cursor = self.connection.cursor()
            try:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
            finally:
                cursor.close()
            return isinstance(row, (tuple, list)) and tuple(row) == (1,)
        except Exception:
            return False

    def close(self) -> None:
        try:
            if self.acquired:
                cursor = self.connection.cursor()
                try:
                    cursor.execute(
                        "SELECT pg_advisory_unlock(%s)",
                        (LEADERSHIP_LOCK_KEY,),
                    )
                finally:
                    cursor.close()
        except Exception:
            pass
        finally:
            self.acquired = False
            try:
                self.connection.close()
            except Exception:
                pass


def _base_status(enabled: bool) -> dict[str, Any]:
    return {
        "data_type": STATUS_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "contract_id": CONTRACT_ID,
        "runtime_mode": RUNTIME_MODE,
        "enabled": enabled,
        "running": False,
        "role": "disabled" if not enabled else "starting",
        "leadership_acquired": False,
        "leadership_lock_key": LEADERSHIP_LOCK_KEY,
        "owner_id": None,
        "started_at_utc": None,
        "heartbeat_at_utc": None,
        "next_cycle_due_at_utc": None,
        "control_cycle_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "leadership_miss_count": 0,
        "duplicate_lease_skip_count": 0,
        "last_cycle_started_at_utc": None,
        "last_cycle_finished_at_utc": None,
        "last_slate_date": None,
        "last_status": "disabled" if not enabled else "starting",
        "last_error_class": None,
        "last_checkpoint_version": None,
        "recovered_from_checkpoint": None,
        "provider_workload_cycle_count": 0,
        "sportsbook_workload_cycle_count": 0,
        "production_scheduler_started": False,
        "legacy_production_runtime_started": False,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
        "provider_calls": 0,
        "sportsbook_calls": 0,
        "database_secret_exposed": False,
        "new_render_service_created": False,
    }


def _replace_status(value: Mapping[str, Any]) -> None:
    with _STATUS_LOCK:
        _STATUS.clear()
        _STATUS.update(deepcopy(dict(value)))


def _patch_status(**changes: Any) -> None:
    with _STATUS_LOCK:
        _STATUS.update(deepcopy(changes))


def get_step17b_status() -> dict[str, Any]:
    with _STATUS_LOCK:
        if not _STATUS:
            return _base_status(step17b_enabled())
        return deepcopy(_STATUS)


async def _sleep_interruptibly(stop_event: threading.Event, seconds: float) -> None:
    deadline = asyncio.get_running_loop().time() + max(0.0, seconds)
    while not stop_event.is_set():
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return
        await asyncio.sleep(min(1.0, remaining))


async def run_always_on_loop(
    stop_event: threading.Event,
    *,
    env: Mapping[str, str] | None = None,
    leadership_acquirer: Callable[[Mapping[str, str]], Any | None] | None = None,
    cycle_runner: Callable[..., Mapping[str, Any]] | None = None,
    max_iterations_for_test: int | None = None,
) -> None:
    source = dict(os.environ if env is None else env)
    config = validate_step17b_startup(source)
    runtime_env = build_runtime_env(source)
    owner_id = f"render-mlb-step17b:{os.getpid()}"
    acquirer = leadership_acquirer or AdvisoryLeadership.attempt
    leadership: Any | None = None
    iterations = 0
    status = _base_status(True)
    status.update(
        {
            "running": True,
            "role": "candidate",
            "owner_id": owner_id,
            "started_at_utc": _iso_now(),
            "heartbeat_at_utc": _iso_now(),
            "last_status": "candidate",
        }
    )
    _replace_status(status)

    try:
        while not stop_event.is_set():
            if max_iterations_for_test is not None and iterations >= max_iterations_for_test:
                break
            iterations += 1
            _patch_status(heartbeat_at_utc=_iso_now())

            if leadership is None:
                try:
                    leadership = await asyncio.to_thread(acquirer, runtime_env)
                except Exception as exc:
                    current = get_step17b_status()
                    _patch_status(
                        role="degraded",
                        leadership_acquired=False,
                        failure_count=int(current["failure_count"]) + 1,
                        last_status="leadership_error",
                        last_error_class=type(exc).__name__,
                    )
                    await _sleep_interruptibly(stop_event, LEADERSHIP_RETRY_SECONDS)
                    continue
                if leadership is None:
                    current = get_step17b_status()
                    _patch_status(
                        role="standby",
                        leadership_acquired=False,
                        leadership_miss_count=int(current["leadership_miss_count"]) + 1,
                        last_status="standby_other_process_is_leader",
                        last_error_class=None,
                    )
                    await _sleep_interruptibly(stop_event, LEADERSHIP_RETRY_SECONDS)
                    continue
                _patch_status(
                    role="leader",
                    leadership_acquired=True,
                    last_status="leadership_acquired",
                    last_error_class=None,
                )

            try:
                alive = await asyncio.to_thread(leadership.check)
                if not alive:
                    raise MLBStep17BLeadershipError(
                        "Step 17B leadership connection was lost"
                    )
                slate = _slate_date()
                started = _iso_now()
                current = get_step17b_status()
                _patch_status(
                    last_cycle_started_at_utc=started,
                    last_slate_date=slate,
                    control_cycle_count=int(current["control_cycle_count"]) + 1,
                    last_status="control_cycle_running",
                    heartbeat_at_utc=started,
                )
                runner = cycle_runner or run_one_control_cycle
                result = await asyncio.to_thread(
                    runner,
                    env=runtime_env,
                    owner_id=owner_id,
                    slate_date=slate,
                )
                if not isinstance(result, Mapping) or result.get("status") != "completed":
                    raise MLBStep17BIntegrityError(
                        "Step 17B control cycle did not complete"
                    )
                if result.get("provider_calls") != 0 or result.get("sportsbook_calls") != 0:
                    raise MLBStep17BIntegrityError(
                        "Step 17B control cycle crossed network-call boundary"
                    )
                finished = _iso_now()
                current = get_step17b_status()
                _patch_status(
                    last_cycle_finished_at_utc=finished,
                    heartbeat_at_utc=finished,
                    success_count=int(current["success_count"]) + 1,
                    last_status="control_cycle_completed",
                    last_error_class=None,
                    last_checkpoint_version=result.get("saved_checkpoint_version"),
                    recovered_from_checkpoint=result.get(
                        "recovered_from_durable_checkpoint"
                    ),
                )
            except step14c.MLBStep14CLeaseUnavailableError:
                finished = _iso_now()
                current = get_step17b_status()
                _patch_status(
                    heartbeat_at_utc=finished,
                    last_cycle_finished_at_utc=finished,
                    duplicate_lease_skip_count=int(
                        current["duplicate_lease_skip_count"]
                    ) + 1,
                    last_status="control_cycle_skipped_duplicate_lease",
                    last_error_class=None,
                )
            except Exception as exc:
                finished = _iso_now()
                current = get_step17b_status()
                _patch_status(
                    role="degraded",
                    leadership_acquired=False,
                    heartbeat_at_utc=finished,
                    last_cycle_finished_at_utc=finished,
                    failure_count=int(current["failure_count"]) + 1,
                    last_status="control_cycle_failed",
                    last_error_class=type(exc).__name__,
                )
                try:
                    await asyncio.to_thread(leadership.close)
                finally:
                    leadership = None

            if stop_event.is_set():
                break
            due = _utc_now().timestamp() + int(config["loop_seconds"])
            _patch_status(
                next_cycle_due_at_utc=datetime.fromtimestamp(
                    due,
                    tz=timezone.utc,
                ).isoformat().replace("+00:00", "Z")
            )
            await _sleep_interruptibly(stop_event, int(config["loop_seconds"]))
    finally:
        if leadership is not None:
            try:
                await asyncio.to_thread(leadership.close)
            except Exception:
                pass
        _patch_status(
            running=False,
            role="stopped",
            leadership_acquired=False,
            heartbeat_at_utc=_iso_now(),
            next_cycle_due_at_utc=None,
            last_status="stopped",
        )


@asynccontextmanager
async def step17b_lifespan(app: Any) -> AsyncIterator[None]:
    """Compose Step 16B binding with one explicitly gated background control loop."""
    env = dict(os.environ)
    enabled = step17b_enabled(env)
    stop_event = threading.Event()
    task: asyncio.Task[None] | None = None

    async with step16b.step16b_lifespan(app):
        if enabled:
            validate_step17b_startup(env)
            _replace_status(_base_status(True))
            task = asyncio.create_task(
                run_always_on_loop(stop_event, env=env),
                name="mlb-step17b-always-on-control-runtime",
            )
        else:
            _replace_status(_base_status(False))
        setattr(app.state, "mlb_step17b_runtime_task", task)
        setattr(app.state, "mlb_step17b_stop_event", stop_event)
        try:
            yield
        finally:
            stop_event.set()
            if task is not None:
                try:
                    await asyncio.wait_for(
                        asyncio.shield(task),
                        timeout=SHUTDOWN_GRACE_SECONDS,
                    )
                except asyncio.TimeoutError:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            setattr(app.state, "mlb_step17b_runtime_task", None)


def controlled_always_on_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "contract_id": CONTRACT_ID,
        "runtime_mode": RUNTIME_MODE,
        "branch": BRANCH,
        "step17a_main_sha": STEP17A_MAIN_SHA,
        "step17a_final_marker": STEP17A_FINAL_MARKER,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "default_enabled": False,
        "explicit_gate_required": True,
        "single_worker_required": True,
        "global_postgresql_advisory_leader_required": True,
        "durable_control_checkpoint_required": True,
        "durable_restart_recovery_required": True,
        "checkpoint_cas_required": True,
        "slate_lease_release_after_each_control_cycle": True,
        "background_control_task_allowed": True,
        "legacy_production_runtime_allowed": False,
        "legacy_production_scheduler_allowed": False,
        "provider_workload_allowed": False,
        "sportsbook_workload_allowed": False,
        "provider_calls_allowed": False,
        "sportsbook_calls_allowed": False,
        "actionable_output_allowed": False,
        "wagering_allowed": False,
        "supabase_rest_write_allowed": False,
        "public_persistence_api_allowed": False,
        "model_mutation_allowed": False,
        "ranking_mutation_allowed": False,
        "secrets_output_allowed": False,
        **PROTECTED_INVARIANTS,
    }


__all__ = [
    "DATA_TYPE",
    "STATUS_DATA_TYPE",
    "SCHEMA_VERSION",
    "RUNTIME_VERSION",
    "CONTRACT_ID",
    "RUNTIME_MODE",
    "BRANCH",
    "STEP17A_MAIN_SHA",
    "FINAL_CERTIFICATION_MARKER",
    "STEP17B_ENABLED_ENV",
    "STEP17B_LOOP_SECONDS_ENV",
    "STEP17B_EXPECTED_REVISION_ENV",
    "DEPLOYMENT_MODE_ENV",
    "DATABASE_URL_ENV",
    "DEFAULT_LOOP_SECONDS",
    "LEADERSHIP_LOCK_KEY",
    "MLBStep17BDisabledError",
    "MLBStep17BIntegrityError",
    "MLBStep17BLeadershipError",
    "step17b_enabled",
    "build_runtime_env",
    "validate_step17b_startup",
    "run_one_control_cycle",
    "AdvisoryLeadership",
    "get_step17b_status",
    "run_always_on_loop",
    "step17b_lifespan",
    "controlled_always_on_manifest",
]
