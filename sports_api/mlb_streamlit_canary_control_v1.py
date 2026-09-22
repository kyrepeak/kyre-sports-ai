"""Pure Step 5.10B configuration resolver for session-scoped Streamlit canary control.

This module contains no Streamlit dependency and does not alter the certified
Step 5.10 cohort. It only resolves precedence between explicit host environment
control and explicit browser-session query control.
"""
from __future__ import annotations

from typing import Any, Mapping

DATA_TYPE = "mlb_streamlit_canary_control_config_v1"
SCHEMA_VERSION = 1
QUERY_ENABLED_KEY = "mlb_step5_10b_canary"
QUERY_PERCENT_KEY = "mlb_step5_10b_percent"
TRUE_VALUES = frozenset({"1", "true", "yes", "on", "enabled"})


class MLBStreamlitCanaryControlError(ValueError):
    pass


def resolve_streamlit_canary_config(
    base_config: Mapping[str, Any],
    *,
    host_env_present: bool,
    query_enabled_value: Any = None,
    query_percent_value: Any = None,
) -> dict[str, Any]:
    if not isinstance(base_config, Mapping):
        raise MLBStreamlitCanaryControlError("base_config must be a mapping")
    if not isinstance(host_env_present, bool):
        raise MLBStreamlitCanaryControlError("host_env_present must be boolean")

    base = dict(base_config)
    common = {
        "step5_10b_data_type": DATA_TYPE,
        "step5_10b_schema_version": SCHEMA_VERSION,
        "query_enabled_key": QUERY_ENABLED_KEY,
        "query_percent_key": QUERY_PERCENT_KEY,
        "exact_query_rollback": True,
        "session_only": True,
        "host_env_precedence": True,
        "step5_10_core_impact": False,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
    }

    if host_env_present:
        return {
            **base,
            **common,
            "control_source": "HOST_ENV",
            "streamlit_session_control": False,
            "query_param_activation_requested": False,
        }

    enabled_raw = None if query_enabled_value is None else str(query_enabled_value).strip().lower()
    percent_raw = None if query_percent_value is None else str(query_percent_value).strip()
    query_present = enabled_raw is not None or percent_raw is not None
    if not query_present:
        return {
            **base,
            **common,
            "control_source": "DEFAULT_OFF",
            "streamlit_session_control": False,
            "query_param_activation_requested": False,
        }

    enabled = enabled_raw in TRUE_VALUES if enabled_raw is not None else False
    try:
        requested_percent = float(percent_raw) if percent_raw not in (None, "") else 0.0
        config_valid = True
    except Exception:
        requested_percent = 0.0
        config_valid = False
        enabled = False

    return {
        **base,
        **common,
        "enabled": bool(enabled and config_valid),
        "requested_percent": requested_percent,
        "config_valid": config_valid,
        "control_source": "STREAMLIT_QUERY_SESSION",
        "streamlit_session_control": True,
        "query_param_activation_requested": bool(enabled and config_valid),
    }


__all__ = [
    "DATA_TYPE",
    "MLBStreamlitCanaryControlError",
    "QUERY_ENABLED_KEY",
    "QUERY_PERCENT_KEY",
    "SCHEMA_VERSION",
    "TRUE_VALUES",
    "resolve_streamlit_canary_config",
]
