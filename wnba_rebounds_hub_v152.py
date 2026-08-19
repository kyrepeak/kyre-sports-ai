"""WNBA Rebounds V1.5.2 — fast-path caching across Steps 3-6.

Keeps all model/verification math unchanged. This wrapper only memoizes the
expensive historical build functions so Streamlit reruns do not rebuild the
same verified slate repeatedly. Cache keys include the full input frames + day,
so any roster, injury, projected-minute, or upstream data change invalidates the
corresponding layer automatically.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v151 as base
import wnba_rebounds_hub_v111 as step3_mod
import wnba_rebounds_hub_v13 as step4_mod
import wnba_rebounds_hub_v14 as step5_mod
import wnba_rebounds_hub_v15 as step6_mod

MODEL_VERSION = "WNBA REBOUNDS V1.5.2 • FAST PATH STEPS 3–6"

# Preserve authoritative functions before monkey-patching.
_ORIG_STEP3 = step3_mod._build_step3_minutes
_ORIG_STEP4 = step4_mod._build_step4_role
_ORIG_STEP5 = step5_mod._build_step5_form
_ORIG_STEP6 = step6_mod._build_step6


@st.cache_data(ttl=21600, show_spinner=False, max_entries=24)
def _cached_step3(slate: pd.DataFrame, day: str, merged: pd.DataFrame):
    return _ORIG_STEP3(slate, day, merged)


@st.cache_data(ttl=21600, show_spinner=False, max_entries=24)
def _cached_step4(slate: pd.DataFrame, day: str, minute_players: pd.DataFrame):
    return _ORIG_STEP4(slate, day, minute_players)


@st.cache_data(ttl=21600, show_spinner=False, max_entries=24)
def _cached_step5(step4_players: pd.DataFrame, day: str, slate: pd.DataFrame):
    return _ORIG_STEP5(step4_players, day, slate)


@st.cache_data(ttl=3600, show_spinner=False, max_entries=24)
def _cached_step6(step5_players: pd.DataFrame, day: str):
    return _ORIG_STEP6(step5_players, day)


def render_wnba_rebounds_hub(*args, **kwargs):
    # Patch only expensive builders. Rendering, gates, labels, and math remain
    # owned by the existing production modules.
    old3 = step3_mod._build_step3_minutes
    old4 = step4_mod._build_step4_role
    old5 = step5_mod._build_step5_form
    old6 = step6_mod._build_step6
    step3_mod._build_step3_minutes = _cached_step3
    step4_mod._build_step4_role = _cached_step4
    step5_mod._build_step5_form = _cached_step5
    step6_mod._build_step6 = _cached_step6
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        step3_mod._build_step3_minutes = old3
        step4_mod._build_step4_role = old4
        step5_mod._build_step5_form = old5
        step6_mod._build_step6 = old6

    st.caption(
        "⚡ V1.5.2 fast path active • verified Steps 3–5 reuse 6-hour input-keyed snapshots; "
        "Step 6 reuses a 1-hour opportunity snapshot. Any upstream input change invalidates the relevant cache automatically."
    )
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
