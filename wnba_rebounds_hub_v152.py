"""WNBA Rebounds V1.5.3 — fast-path caching across Steps 3-6.

Keeps all model/verification math unchanged. This wrapper memoizes expensive
historical build functions so Streamlit reruns do not rebuild the same verified
slate repeatedly. V1.5.3 also invalidates the prior Step-6 empty-feed cache so
the hardened dual official tracking-host fetch is attempted immediately.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v151 as base
import wnba_rebounds_hub_v111 as step3_mod
import wnba_rebounds_hub_v13 as step4_mod
import wnba_rebounds_hub_v14 as step5_mod
import wnba_rebounds_hub_v15 as step6_mod

MODEL_VERSION = "WNBA REBOUNDS V1.5.3 • FAST PATH + DUAL OFFICIAL TRACKING HOST"

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


# New function identity intentionally invalidates V1.5.2's cached empty result.
@st.cache_data(ttl=1800, show_spinner=False, max_entries=24)
def _cached_step6_v153(step5_players: pd.DataFrame, day: str):
    return _ORIG_STEP6(step5_players, day)


def render_wnba_rebounds_hub(*args, **kwargs):
    old3 = step3_mod._build_step3_minutes
    old4 = step4_mod._build_step4_role
    old5 = step5_mod._build_step5_form
    old6 = step6_mod._build_step6
    step3_mod._build_step3_minutes = _cached_step3
    step4_mod._build_step4_role = _cached_step4
    step5_mod._build_step5_form = _cached_step5
    step6_mod._build_step6 = _cached_step6_v153
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        step3_mod._build_step3_minutes = old3
        step4_mod._build_step4_role = old4
        step5_mod._build_step5_form = old5
        step6_mod._build_step6 = old6

    st.caption(
        "⚡ V1.5.3 fast path active • Steps 3–5 reuse 6-hour input-keyed snapshots; "
        "Step 6 uses a fresh 30-minute snapshot and tries NBA Stats first, then the legacy WNBA Stats host. "
        "No proxy rebound-chance data is substituted."
    )
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]