"""WNBA Step 19E: cooldown-aware Step17B cycle preflight.

This compatibility layer prevents the always-on Step17B host from starting an
expensive frozen scheduler cycle a moment before the durable Step11E circuit
cooldown expires. It does not change controller state, projection readiness,
simulation logic, or durable persistence ownership.

Step19F is installed here before the always-on cycle runs. Step19F only adds a
strict, certified DraftKings display-team alias needed to reconcile the live
sportscontent event to the unchanged official WNBA schedule identity.

The preflight reads the certified Step14C restart checkpoint. When that
checkpoint says the controller circuit is open until a future timestamp, the
host waits interruptibly until a small safety margin after that timestamp and
then invokes the original frozen Step17B cycle exactly once.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Callable, Mapping

from sports_api import wnba_step14c_durable_restart_lease as step14c
from sports_api import wnba_step17b_always_on_runtime as step17b
from sports_api import wnba_step19f_draftkings_identity as step19f

SOURCE = "Kyre Sports API WNBA Step 19E cooldown-aware Step17B cycle preflight"
MODEL_VERSION = "wnba_step19e_cooldown_aware_step17b_preflight_v1"
COOLDOWN_SAFETY_BUFFER_SECONDS = 1.0
WAIT_POLL_SECONDS = 0.25
MAX_COOLDOWN_WAIT_SECONDS = 300.0

# Install the strict provider identity compatibility before any hosted cycle.
step19f.install_step19f_draftkings_identity()

_ORIGINAL_RUN_ONE_CYCLE = step17b.run_one_cycle
_INSTALLED = False


def _utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _cooldown_wait_seconds(
    checkpoint: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> float:
    if not isinstance(checkpoint, Mapping):
        return 0.0
    if str(checkpoint.get("circuit_state") or "").strip().casefold() != "open":
        return 0.0
    open_until = _utc(checkpoint.get("circuit_open_until_utc"))
    if open_until is None:
        return 0.0
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    remaining = (open_until - current).total_seconds()
    if remaining <= 0.0:
        return 0.0
    return min(remaining + COOLDOWN_SAFETY_BUFFER_SECONDS, MAX_COOLDOWN_WAIT_SECONDS)


def _load_controller_checkpoint(
    *,
    slate_date: str,
    env: Mapping[str, str],
) -> Mapping[str, Any] | None:
    loaded = step14c.load_step14c_restart_checkpoint(slate_date=slate_date, env=env)
    if not isinstance(loaded, Mapping) or loaded.get("found") is not True:
        return None
    state = loaded.get("controller_state_for_restart")
    return state if isinstance(state, Mapping) else None


def _wait_interruptibly(
    seconds: float,
    *,
    stop_requested: Callable[[], bool],
    sleeper: Callable[[float], None] = time.sleep,
) -> bool:
    deadline = time.monotonic() + max(0.0, seconds)
    while True:
        if stop_requested():
            return False
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return True
        sleeper(min(WAIT_POLL_SECONDS, remaining))


def run_one_cycle_step19e(
    *,
    env: Mapping[str, str],
    owner_id: str,
    slate_date: str | None = None,
    stop_requested: Callable[[], bool] | None = None,
    runner: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    stop_fn = stop_requested or (lambda: False)
    slate = slate_date or step17b._slate_date()
    runtime_env = step17b.build_runtime_env(env)

    checkpoint = _load_controller_checkpoint(slate_date=slate, env=runtime_env)
    wait_seconds = _cooldown_wait_seconds(checkpoint)
    if wait_seconds > 0.0:
        completed = _wait_interruptibly(wait_seconds, stop_requested=stop_fn)
        if not completed:
            raise step17b.WNBAStep17BIntegrityError(
                "Step 19E interrupted before the durable circuit cooldown expired."
            )

    return _ORIGINAL_RUN_ONE_CYCLE(
        env=runtime_env,
        owner_id=owner_id,
        slate_date=slate,
        stop_requested=stop_fn,
        runner=runner,
    )


def install_step19e_cooldown_aware_cycle() -> dict[str, Any]:
    global _INSTALLED
    step17b.run_one_cycle = run_one_cycle_step19e
    _INSTALLED = True
    return INSTALLATION


INSTALLATION = {
    "source": SOURCE,
    "model_version": MODEL_VERSION,
    "installed": lambda: _INSTALLED,
    "checkpoint_read_only": True,
    "controller_state_mutated_by_preflight": False,
    "circuit_force_closed": False,
    "readiness_gates_relaxed": False,
    "projection_fabrication_allowed": False,
    "provider_logic_modified": False,
    "provider_identity_compatibility": step19f.MODEL_VERSION,
    "durable_lease_ownership_modified": False,
    "cooldown_safety_buffer_seconds": COOLDOWN_SAFETY_BUFFER_SECONDS,
    "max_cooldown_wait_seconds": MAX_COOLDOWN_WAIT_SECONDS,
}


__all__ = [
    "COOLDOWN_SAFETY_BUFFER_SECONDS",
    "INSTALLATION",
    "MAX_COOLDOWN_WAIT_SECONDS",
    "MODEL_VERSION",
    "SOURCE",
    "install_step19e_cooldown_aware_cycle",
    "run_one_cycle_step19e",
]
