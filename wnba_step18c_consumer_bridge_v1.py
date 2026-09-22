"""Step 18C fail-closed Daily Picks hot-reload bridge."""
from __future__ import annotations

import importlib
import sys
import types
from typing import Any

MODEL_VERSION = "WNBA STEP 18C STREAMLIT RELIABILITY BRIDGE V1"


def _safe_failure_module(error_type: str):
    module = types.ModuleType("wnba_daily_picks_hub_step18c_fail_closed")
    module.MODEL_VERSION = "WNBA DAILY PICKS STEP 18C FAIL-CLOSED"

    def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
        import streamlit as st
        st.error("WNBA Daily Picks could not load the certified API consumer safely. No legacy computation or cached picks are being shown.")
        st.caption(f"Consumer presentation state: {error_type}")
        return {
            "state": "error",
            "available": False,
            "reason": "consumer_presentation_unavailable",
            "error_type": error_type,
            "cards": [],
        }

    module.render_wnba_daily_picks_hub = render_wnba_daily_picks_hub
    return module


def install_step18c_consumer_bridge() -> dict[str, Any]:
    # Force the small presentation/read layers to reload on Streamlit hot reruns.
    for name in (
        "wnba_daily_picks_hub_v36",
        "wnba_daily_picks_hub_v35",
        "wnba_streamlit_consumer_v2",
    ):
        sys.modules.pop(name, None)
    importlib.invalidate_caches()

    error_type = None
    try:
        target = importlib.import_module("wnba_daily_picks_hub_v36")
        if not callable(getattr(target, "render_wnba_daily_picks_hub", None)):
            raise RuntimeError("Step 18C V36 renderer is unavailable.")
    except Exception as exc:
        error_type = type(exc).__name__
        target = _safe_failure_module(error_type)

    # Frozen source imports V34 and then aliases it to V4. Both names must always
    # resolve to either V36 or the safe no-compute failure module.
    sys.modules["wnba_daily_picks_hub_v34"] = target
    sys.modules["wnba_daily_picks_hub_v4"] = target
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "renderer_version": getattr(target, "MODEL_VERSION", None),
        "fail_closed": error_type is not None,
        "error_type": error_type,
        "v34_alias_safe": sys.modules.get("wnba_daily_picks_hub_v34") is target,
        "v4_alias_safe": sys.modules.get("wnba_daily_picks_hub_v4") is target,
        "legacy_daily_picks_compute_fallback": False,
        "backend_mutated": False,
    }


__all__ = ["MODEL_VERSION", "install_step18c_consumer_bridge"]
