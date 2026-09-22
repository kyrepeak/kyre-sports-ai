"""WNBA Step 17B: controlled always-on scheduler activation.

Step 17B is additive to the frozen Step-16E release and certified Step-17A host
attachment. It owns only process supervision: one Render process wins a
PostgreSQL advisory leadership lock, repeatedly invokes the frozen Step-14C
durable runner, and exposes sanitized runtime status. The frozen Step-14C lease
and checkpoint CAS remain authoritative for each slate cycle.

Legacy production/scheduler/write switches deliberately remain OFF so frozen
Step 11-16 safety contracts are not weakened. Step 17B has its own explicit
activation gate.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import os
import threading
from typing import Any, AsyncIterator, Callable, Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14c_durable_restart_lease as step14c
from sports_api import wnba_step16b_production_lifecycle as step16b
from sports_api import wnba_step17a_production_host_contract as step17a
from sports_api import wnba_step18a_streamlit_consumer as step18a

SOURCE = "Kyre Sports API WNBA Step 17B controlled always-on runtime"
SCHEMA_VERSION = "wnba_step_17b_controlled_always_on_v1"
RUNTIME_VERSION = "wnba_step17b_render_single_leader_durable_loop_v1"
BRANCH = "wnba-step17b-controlled-always-on-20260828"
STEP17A_FROZEN_SHA = "da6e9d8e660c1ead7c497cbaeb6205c845978cfd"
SEASON = 2026
SLATE_TIMEZONE = "America/New_York"

STEP17B_ENABLED_ENV = "WNBA_STEP17B_ALWAYS_ON_ENABLED"
STEP17B_LOOP_SECONDS_ENV = "WNBA_STEP17B_LOOP_SECONDS"
STEP17B_EXPECTED_REVISION_ENV = "WNBA_STEP17B_EXPECTED_REVISION"
DATABASE_URL_ENV = step14c.DATABASE_URL_ENV

DEFAULT_ENABLED = False
DEFAULT_LOOP_SECONDS = 60
MIN_LOOP_SECONDS = 30
MAX_LOOP_SECONDS = 3600
LEADERSHIP_RETRY_SECONDS = 15
SHUTDOWN_GRACE_SECONDS = 90

# Stable signed-63-bit advisory lock key; no schema row is required. PostgreSQL
# automatically releases this session lock if the owning connection/process dies.
LEADERSHIP_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"kyre-sports-api:wnba:step17b:always-on-leader:v1").digest()[:8],
    "big",
) & ((1 << 63) - 1)

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

_FROZEN_FALSE_GATES = (
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

_STATUS_LOCK = threading.RLock()
_STATUS: dict[str, Any] = {}


class WNBAStep17BDisabledError(RuntimeError):
    pass


class WNBAStep17BIntegrityError(RuntimeError):
    pass


class WNBAStep17BLeadershipError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step17b_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP17B_ENABLED_ENV))


def _strict_loop_seconds(value: object) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise WNBAStep17BIntegrityError("Step 17B loop seconds must be an integer.") from exc
    if not MIN_LOOP_SECONDS <= parsed <= MAX_LOOP_SECONDS:
        raise WNBAStep17BIntegrityError(
            f"Step 17B loop seconds must be {MIN_LOOP_SECONDS}..{MAX_LOOP_SECONDS}."
        )
    return parsed


def build_runtime_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = {str(k): str(v) for k, v in dict(os.environ if env is None else env).items()}
    source[STEP17B_ENABLED_ENV] = "true"
    for key in _REQUIRED_TRUE_GATES:
        source[key] = "true"
    for key in _FROZEN_FALSE_GATES:
        source[key] = "false"
    return source


def validate_step17b_startup(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step17b_enabled(source):
        raise WNBAStep17BDisabledError(f"{STEP17B_ENABLED_ENV}=true is required.")
    if str(source.get("WEB_CONCURRENCY") or "").strip() != "1":
        raise WNBAStep17BIntegrityError("Step 17B requires WEB_CONCURRENCY=1 on the Render host.")
    bad = [key for key in _FROZEN_FALSE_GATES if _truthy(source.get(key))]
    if bad:
        raise WNBAStep17BIntegrityError(
            "Step 17B refuses frozen legacy production/write switches: " + ", ".join(bad)
        )
    if not _truthy(source.get("WNBA_STEP16B_DURABLE_LIFECYCLE_ENABLED")):
        raise WNBAStep17BIntegrityError("Step 17B requires the certified Step-16B lifecycle binding.")
    raw = str(source.get(DATABASE_URL_ENV) or "").strip()
    parsed = urlsplit(raw)
    if (
        not raw
        or parsed.scheme.casefold() not in {"postgres", "postgresql"}
        or not parsed.hostname
        or parsed.path in {"", "/"}
    ):
        raise WNBAStep17BIntegrityError("Step 17B requires protected PostgreSQL KYRE_DATABASE_URL.")
    loop_seconds = _strict_loop_seconds(source.get(STEP17B_LOOP_SECONDS_ENV, DEFAULT_LOOP_SECONDS))
    expected_revision = str(source.get(STEP17B_EXPECTED_REVISION_ENV) or "").strip().lower()
    if expected_revision and (
        len(expected_revision) != 40
        or any(ch not in "0123456789abcdef" for ch in expected_revision)
    ):
        raise WNBAStep17BIntegrityError("Step 17B expected revision must be a full Git SHA.")
    return {
        "loop_seconds": loop_seconds,
        "database_secret_configured": True,
        "database_secret_exposed": False,
        "web_concurrency": 1,
        "expected_revision": expected_revision or None,
        "leadership_lock_key": LEADERSHIP_LOCK_KEY,
    }


def _slate_date(now: datetime | None = None) -> str:
    current = now or _utc_now()
    return current.astimezone(ZoneInfo(SLATE_TIMEZONE)).date().isoformat()


def build_step17b_request(slate_date: str) -> dict[str, Any]:
    parent = step13b.build_step13b_request(
        season=SEASON,
        initial_slate_date=slate_date,
        slate_timezone=SLATE_TIMEZONE,
        rollover_policy="stop",
        max_supervisor_sessions=1,
        max_supervisor_runtime_seconds=300,
        max_total_intersession_sleep_seconds=0,
        scheduler_cycles_per_session=1,
        scheduler_sleep_budget_seconds_per_session=0,
        initial_previous_state=None,
    )
    return step13c.build_step13c_request(
        supervisor_request=parent,
        max_recovery_attempts=2,
        base_recovery_backoff_seconds=5,
        max_total_recovery_sleep_seconds=10,
    )


def run_one_cycle(
    *,
    env: Mapping[str, str],
    owner_id: str,
    slate_date: str | None = None,
    stop_requested: Callable[[], bool] | None = None,
    runner: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    runtime_env = build_runtime_env(env)
    request = build_step17b_request(slate_date or _slate_date())
    durable_runner = runner or step14c.run_step14c_durable_restart_lease
    kwargs: dict[str, Any] = {}
    if runner is None:
        if step18a.step18a_streamlit_consumer_enabled(runtime_env):
            kwargs["step13c_runner"] = step18a.run_step13c_and_capture
        kwargs["runner_kwargs"] = {"stop_requested": stop_requested or (lambda: False)}
    result = durable_runner(
        request,
        owner_id=owner_id,
        env=runtime_env,
        **kwargs,
    )
    if not isinstance(result, Mapping) or result.get("status") != "completed":
        raise WNBAStep17BIntegrityError("Step 17B durable cycle did not complete.")
    return deepcopy(dict(result))


class AdvisoryLeadership:
    """Own one PostgreSQL session advisory lock for the lifetime of a process."""

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
                application_name="kyre-sports-ai-step17b-leader",
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
                raise WNBAStep17BLeadershipError("Step 17B leadership query returned invalid shape.")
            if row[0] is not True:
                connection.close()
                return None
            leadership = cls(connection)
            leadership.acquired = True
            return leadership
        except WNBAStep17BLeadershipError:
            raise
        except Exception as exc:
            raise WNBAStep17BLeadershipError("Step 17B could not acquire PostgreSQL leadership.") from exc

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
            return isinstance(row, (tuple, list)) and row == (1,)
        except Exception:
            return False

    def close(self) -> None:
        try:
            if self.acquired:
                cursor = self.connection.cursor()
                try:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", (LEADERSHIP_LOCK_KEY,))
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
        "data_type": "wnba_step17b_runtime_status",
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "enabled": enabled,
        "running": False,
        "role": "disabled" if not enabled else "starting",
        "leadership_acquired": False,
        "leadership_lock_key": LEADERSHIP_LOCK_KEY,
        "owner_id": None,
        "started_at_utc": None,
        "heartbeat_at_utc": None,
        "next_cycle_due_at_utc": None,
        "cycle_count": 0,
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
        "database_secret_exposed": False,
        "legacy_production_switches_enabled": False,
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
    owner_id = f"render-step17b:{os.getpid()}"
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
                    raise WNBAStep17BLeadershipError("Step 17B leadership connection was lost.")
                slate = _slate_date()
                started = _iso_now()
                current = get_step17b_status()
                _patch_status(
                    last_cycle_started_at_utc=started,
                    last_slate_date=slate,
                    cycle_count=int(current["cycle_count"]) + 1,
                    last_status="cycle_running",
                    heartbeat_at_utc=started,
                )
                runner = cycle_runner or run_one_cycle
                if cycle_runner is None:
                    result = await asyncio.to_thread(
                        runner,
                        env=runtime_env,
                        owner_id=owner_id,
                        slate_date=slate,
                        stop_requested=stop_event.is_set,
                    )
                else:
                    result = await asyncio.to_thread(
                        runner,
                        env=runtime_env,
                        owner_id=owner_id,
                        slate_date=slate,
                    )
                finished = _iso_now()
                current = get_step17b_status()
                _patch_status(
                    last_cycle_finished_at_utc=finished,
                    heartbeat_at_utc=finished,
                    success_count=int(current["success_count"]) + 1,
                    last_status="cycle_completed",
                    last_error_class=None,
                    last_checkpoint_version=result.get("saved_checkpoint_version"),
                    recovered_from_checkpoint=result.get("recovered_from_durable_checkpoint"),
                )
            except step14c.WNBAStep14CLeaseUnavailableError:
                finished = _iso_now()
                current = get_step17b_status()
                _patch_status(
                    heartbeat_at_utc=finished,
                    last_cycle_finished_at_utc=finished,
                    duplicate_lease_skip_count=int(current["duplicate_lease_skip_count"]) + 1,
                    last_status="cycle_skipped_duplicate_lease",
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
                    last_status="cycle_failed",
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
                next_cycle_due_at_utc=datetime.fromtimestamp(due, tz=timezone.utc).isoformat()
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
    """Compose frozen Step-16B lifespan with one Step-17B background supervisor."""
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
                name="wnba-step17b-always-on-runtime",
            )
        else:
            _replace_status(_base_status(False))
        setattr(app.state, "wnba_step17b_runtime_task", task)
        setattr(app.state, "wnba_step17b_stop_event", stop_event)
        try:
            yield
        finally:
            stop_event.set()
            if task is not None:
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=SHUTDOWN_GRACE_SECONDS)
                except asyncio.TimeoutError:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            setattr(app.state, "wnba_step17b_runtime_task", None)


__all__ = [
    "BRANCH",
    "DEFAULT_LOOP_SECONDS",
    "LEADERSHIP_LOCK_KEY",
    "RUNTIME_VERSION",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP17A_FROZEN_SHA",
    "STEP17B_ENABLED_ENV",
    "STEP17B_EXPECTED_REVISION_ENV",
    "STEP17B_LOOP_SECONDS_ENV",
    "AdvisoryLeadership",
    "WNBAStep17BDisabledError",
    "WNBAStep17BIntegrityError",
    "WNBAStep17BLeadershipError",
    "build_runtime_env",
    "build_step17b_request",
    "get_step17b_status",
    "run_always_on_loop",
    "run_one_cycle",
    "step17b_enabled",
    "step17b_lifespan",
    "validate_step17b_startup",
]
