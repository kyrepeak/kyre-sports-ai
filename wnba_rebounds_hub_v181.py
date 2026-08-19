"""WNBA Rebounds V1.8.1 — safe Step 9 wrapper.

Emergency compatibility wrapper over V1.8.

Fix:
- Bypass V1.7.1 disk/session hydration entirely for this route so stale widget
  values such as the legacy Rebounds recheck button can never be restored.
- Remove any already-present transient Rebounds widget keys before rendering.
- Preserve all verified V1.8 Step-9 model logic unchanged.

This is a safety/performance wrapper only. It does not change rebound math,
position buckets, sportsbook logic, pace, or Monte Carlo behavior.
"""
from __future__ import annotations

import streamlit as st

import wnba_rebounds_hub_v18 as _impl

MODEL_VERSION = "WNBA REBOUNDS V1.8.1 • SAFE STEP 9 • FAST-START HYDRATION BYPASSED"

_TRANSIENT_TOKENS = (
    "recheck", "button", "clicked", "refresh", "force_", "select", "toggle", "slider"
)


def _purge_transient_rebounds_widget_state():
    for key in list(st.session_state.keys()):
        skey = str(key)
        if not skey.startswith("wnba_rebounds_"):
            continue
        low = skey.lower()
        if any(token in low for token in _TRANSIENT_TOKENS):
            try:
                del st.session_state[key]
            except Exception:
                pass


def render_wnba_rebounds_hub(*args, **kwargs):
    # Prevent V1.7.1 from reading any disk snapshot on this route. The current
    # live session/cached data layers continue to work normally; only persistent
    # widget-state hydration is bypassed until the safe persistence layer is
    # rebuilt cleanly.
    _purge_transient_rebounds_widget_state()
    st.session_state["wnba_rebounds_fast_start_hydrated"] = True
    st.session_state["wnba_rebounds_fast_start_status"] = "BYPASSED_SAFE_V181"

    out = _impl.render_wnba_rebounds_hub(*args, **kwargs)

    st.caption(
        "⚡ V1.8.1 SAFE MODE • Step 9 logic unchanged • persistent disk hydration temporarily bypassed • "
        "transient widget/button state purged • no sportsbook/Monte Carlo/final rebound projection."
    )
    return out


def __getattr__(name):
    return getattr(_impl, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
