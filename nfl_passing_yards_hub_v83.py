"""NFL Passing Yards V83 — same-session full-analysis transition.

Speed Phase Step 7 removes the legacy V79 full-analysis anchor transition from
the active lazy shell. Streamlit sanitizes that anchor as target="_blank", so
the current document does not receive ks_py_full=1. V83 preserves the frozen
V82 full-analysis pipeline and replaces only the activation transport with a
native Streamlit button that sets the existing query flag and reruns the same
session.

No football value, data provider, projection, context, probability, market,
sportsbook, widget-selection key, or stake behavior changes.
"""
from __future__ import annotations

import re
from typing import Any, Callable

import streamlit as st

import nfl_passing_yards_hub_v79 as lazy_v79
import nfl_passing_yards_hub_v82 as prior

MODEL_VERSION = "NFL PASSING YARDS V83 • SPEED STEP 7 SAME-SESSION FULL ANALYSIS"
FROZEN_PRIOR = "nfl_passing_yards_hub_v82"
SPEED_PHASE_STEP = 7
TRANSITION_VERSION = "v83"
FULL_PARAM = "ks_py_full"
BUTTON_KEY = "ks_py83_load_full_analysis"
SAME_SESSION_TRANSPORT = True
PRESENTATION_ONLY = False
TRANSPORT_NAVIGATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_SPORTSBOOK_BEHAVIOR = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_LEGACY_LOAD_RE = re.compile(
    r'<a class="ks-py79-load" data-passing-yards-load-full="v79" '
    r'href="[^"]*">Load Full Analysis →</a>'
)


def _strip_legacy_load_link(html: str) -> str:
    cleaned, count = _LEGACY_LOAD_RE.subn("", str(html or ""), count=1)
    if count != 1:
        raise RuntimeError("SPEED_STEP7_LEGACY_LOAD_LINK_CONTRACT_CHANGED")
    return cleaned


def _activate_full_analysis(
    query_params: Any | None = None,
    rerun: Callable[[], None] | None = None,
) -> None:
    params = st.query_params if query_params is None else query_params
    params[FULL_PARAM] = "1"
    if rerun is None:
        st.rerun()
    else:
        rerun()


def _lazy_slot() -> int | None:
    lazy_v79.selection._restore_context_from_query()
    raw_slot = lazy_v79.selection._param("ks_qb_slot")
    return int(raw_slot) if raw_slot in {"1", "2"} else None


def _render_same_session_lazy(slot: int) -> None:
    hints = lazy_v79.prior._query_hints(slot)
    shell = _strip_legacy_load_link(lazy_v79.build_lazy_detail_shell(slot, hints))
    st.markdown(
        '<span data-passing-yards-same-session-owner="v83" '
        'data-passing-yards-speed-step="7" '
        'data-step7-transport="native-streamlit-rerun" '
        'style="display:none" aria-hidden="true"></span>'
        '<style data-passing-yards-same-session-css="v83">'
        'div[data-testid="stButton"] button[kind="primary"]{width:100%;'
        'border-radius:999px;font-weight:900;letter-spacing:.02em}'
        '</style>',
        unsafe_allow_html=True,
    )
    if st.button(
        "Load Full Analysis →",
        key=BUTTON_KEY,
        type="primary",
        use_container_width=True,
    ):
        _activate_full_analysis()
    st.markdown(shell, unsafe_allow_html=True)


def render_nfl_passing_yards_hub() -> None:
    slot = _lazy_slot()
    if slot is not None and not lazy_v79._full_requested():
        return _render_same_session_lazy(slot)

    st.markdown(
        '<span data-passing-yards-same-session-owner="v83" '
        'data-passing-yards-speed-step="7" '
        'data-step7-transport="native-streamlit-rerun" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    return prior.render_nfl_passing_yards_hub()


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V83 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "BUTTON_KEY","FROZEN_PRIOR","FULL_PARAM","MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR","MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY","MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SPORTSBOOK_BEHAVIOR","MAY_MODIFY_WIDGET_KEYS","MODEL_VERSION",
    "PRESENTATION_ONLY","SAME_SESSION_TRANSPORT","SPEED_PHASE_STEP",
    "SPORTSBOOK_PROJECTION_INFLUENCE","STAKE_SIZING_ENABLED",
    "TRANSITION_VERSION","TRANSPORT_NAVIGATION_ONLY",
    "_activate_full_analysis","_lazy_slot","_strip_legacy_load_link",
    "render_nfl_hub","render_nfl_passing_yards_hub",
]
