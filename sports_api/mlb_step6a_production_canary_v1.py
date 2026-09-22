"""MLB Step 6A controlled production-canary activation policy.

Step 5 finished with a certified canary controller whose production default was
OFF/0%. Step 6A is the first intentionally active production rollout: when no
explicit control is supplied, the price gate is enabled for a deterministic
10% cohort of price-certified full-game MLB game IDs. The rollout is hard-capped
at 10% in this phase and still inherits Step 5.10's stricter 25% absolute cap.

Safety order is explicit:
1. global kill switch -> OFF
2. session rollback request -> OFF for that browser session
3. explicit Step 6A host configuration -> bounded value
4. repository production default -> ON at 10%

This module is pure policy. It does not alter model probability, Pick Strength,
ranking math, risk logic, persistence, wagering, or WNBA behavior.
"""
from __future__ import annotations

from typing import Mapping, Any

DEFAULT_ENABLED = True
DEFAULT_PERCENT = 10.0
MAX_PRODUCTION_CANARY_PERCENT = 10.0

ENABLED_ENV_KEY = "MLB_STEP6A_PRODUCTION_CANARY_ENABLED"
PERCENT_ENV_KEY = "MLB_STEP6A_PRODUCTION_CANARY_PERCENT"
KILL_SWITCH_ENV_KEY = "MLB_STEP6A_PRODUCTION_CANARY_KILL_SWITCH"
ROLLBACK_QUERY_KEY = "mlb_step6a_rollback"

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


def _parse_bool(value: object, *, default: bool) -> tuple[bool, bool]:
    if value is None:
        return default, True
    text = str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True, True
    if text in _FALSE_VALUES:
        return False, True
    return default, False


def _bounded_percent(value: object, *, default: float) -> tuple[float, bool, bool]:
    if value is None or str(value).strip() == "":
        raw = float(default)
        valid = True
    else:
        try:
            raw = float(value)
            valid = raw >= 0.0
        except Exception:
            raw = float(default)
            valid = False
    if not valid:
        raw = 0.0
    bounded = max(0.0, min(float(MAX_PRODUCTION_CANARY_PERCENT), raw))
    return bounded, valid, abs(bounded - raw) > 1e-12


def resolve_step6a_production_canary(
    env: Mapping[str, str] | None = None,
    *,
    rollback_requested: bool = False,
) -> dict[str, Any]:
    """Resolve the bounded Step 6A rollout without mutating external state."""
    env = dict(env or {})

    kill, kill_valid = _parse_bool(env.get(KILL_SWITCH_ENV_KEY), default=False)
    host_present = any(
        key in env for key in (ENABLED_ENV_KEY, PERCENT_ENV_KEY, KILL_SWITCH_ENV_KEY)
    )

    if kill:
        return {
            "enabled": False,
            "requested_percent": 0.0,
            "effective_percent": 0.0,
            "control_source": "GLOBAL_KILL_SWITCH",
            "config_valid": kill_valid,
            "percent_bounded": False,
            "host_control_present": host_present,
            "rollback_requested": bool(rollback_requested),
            "production_default_enabled": DEFAULT_ENABLED,
            "production_default_percent": DEFAULT_PERCENT,
            "max_production_canary_percent": MAX_PRODUCTION_CANARY_PERCENT,
            "exact_rollback": True,
        }

    if rollback_requested:
        return {
            "enabled": False,
            "requested_percent": 0.0,
            "effective_percent": 0.0,
            "control_source": "STREAMLIT_SESSION_ROLLBACK",
            "config_valid": True,
            "percent_bounded": False,
            "host_control_present": host_present,
            "rollback_requested": True,
            "production_default_enabled": DEFAULT_ENABLED,
            "production_default_percent": DEFAULT_PERCENT,
            "max_production_canary_percent": MAX_PRODUCTION_CANARY_PERCENT,
            "exact_rollback": True,
        }

    if host_present:
        enabled, enabled_valid = _parse_bool(env.get(ENABLED_ENV_KEY), default=DEFAULT_ENABLED)
        percent, percent_valid, bounded = _bounded_percent(
            env.get(PERCENT_ENV_KEY), default=DEFAULT_PERCENT
        )
        valid = bool(enabled_valid and percent_valid and kill_valid)
        if not valid:
            enabled = False
            percent = 0.0
        if not enabled or percent <= 0.0:
            enabled = False
            percent = 0.0
        return {
            "enabled": enabled,
            "requested_percent": percent,
            "effective_percent": percent,
            "control_source": "HOST_ENV",
            "config_valid": valid,
            "percent_bounded": bounded,
            "host_control_present": True,
            "rollback_requested": False,
            "production_default_enabled": DEFAULT_ENABLED,
            "production_default_percent": DEFAULT_PERCENT,
            "max_production_canary_percent": MAX_PRODUCTION_CANARY_PERCENT,
            "exact_rollback": True,
        }

    return {
        "enabled": DEFAULT_ENABLED,
        "requested_percent": DEFAULT_PERCENT,
        "effective_percent": DEFAULT_PERCENT,
        "control_source": "REPOSITORY_PRODUCTION_DEFAULT",
        "config_valid": True,
        "percent_bounded": False,
        "host_control_present": False,
        "rollback_requested": False,
        "production_default_enabled": DEFAULT_ENABLED,
        "production_default_percent": DEFAULT_PERCENT,
        "max_production_canary_percent": MAX_PRODUCTION_CANARY_PERCENT,
        "exact_rollback": True,
    }


__all__ = [
    "DEFAULT_ENABLED",
    "DEFAULT_PERCENT",
    "MAX_PRODUCTION_CANARY_PERCENT",
    "ENABLED_ENV_KEY",
    "PERCENT_ENV_KEY",
    "KILL_SWITCH_ENV_KEY",
    "ROLLBACK_QUERY_KEY",
    "resolve_step6a_production_canary",
]
