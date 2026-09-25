"""NFL Passing Yards V84 — single-rerun full-analysis activation.

Speed Phase Step 7 transport repair. V83 proved same-document activation but
used an explicit st.rerun() after a Streamlit button event. Button events
already cause a Streamlit rerun, so production paid for a second avoidable
roundtrip. V84 moves ks_py_full=1 into the button on_click callback and lets
the button's normal rerun render the unchanged V83/V82 full-analysis path.

No football value, data provider, projection, context, probability, market,
sportsbook, widget-selection key, or stake behavior changes.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v79 as lazy_v79
import nfl_passing_yards_hub_v83 as prior

MODEL_VERSION = "NFL PASSING YARDS V84 • SPEED STEP 7 SINGLE RERUN"
FROZEN_PRIOR = "nfl_passing_yards_hub_v83"
SPEED_PHASE_STEP = 7
TRANSITION_VERSION = "v84"
FULL_PARAM = "ks_py_full"
BUTTON_KEY = "ks_py84_load_full_analysis"
SAME_SESSION_TRANSPORT = True
SINGLE_RERUN_TRANSPORT = True
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


def _activate_full_analysis_once(query_params: Any | None = None) -> None:
    params = st.query_params if query_params is None else query_params
    params[FULL_PARAM] = "1"


def _lazy_slot() -> int | None:
    lazy_v79.selection._restore_context_from_query()
    raw_slot = lazy_v79.selection._param("ks_qb_slot")
    return int(raw_slot) if raw_slot in {"1", "2"} else None


def _render_single_rerun_lazy(slot: int) -> None:
    hints = lazy_v79.prior._query_hints(slot)
    shell = prior._strip_legacy_load_link(lazy_v79.build_lazy_detail_shell(slot, hints))
    st.markdown(
        '<span data-passing-yards-single-rerun-owner="v84" '
        'data-passing-yards-speed-step="7" '
        'data-step7-transport="native-streamlit-callback-one-rerun" '
        'style="display:none" aria-hidden="true"></span>'
        '<style data-passing-yards-single-rerun-css="v84">'
        'div[data-testid="stButton"] button[kind="primary"]{width:100%;'
        'border-radius:999px;font-weight:900;letter-spacing:.02em}'
        '</style>',
        unsafe_allow_html=True,
    )
    st.button(
        "Load Full Analysis →",
        key=BUTTON_KEY,
        type="primary",
        use_container_width=True,
        on_click=_activate_full_analysis_once,
    )
    st.markdown(shell, unsafe_allow_html=True)


def render_nfl_passing_yards_hub() -> None:
    slot = _lazy_slot()
    if slot is not None and not lazy_v79._full_requested():
        return _render_single_rerun_lazy(slot)

    st.markdown(
        '<span data-passing-yards-single-rerun-owner="v84" '
        'data-passing-yards-speed-step="7" '
        'data-step7-transport="native-streamlit-callback-one-rerun" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    return prior.render_nfl_passing_yards_hub()


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V84 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "BUTTON_KEY","FROZEN_PRIOR","FULL_PARAM","MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR","MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY","MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SPORTSBOOK_BEHAVIOR","MAY_MODIFY_WIDGET_KEYS","MODEL_VERSION",
    "PRESENTATION_ONLY","SAME_SESSION_TRANSPORT","SINGLE_RERUN_TRANSPORT",
    "SPEED_PHASE_STEP","SPORTSBOOK_PROJECTION_INFLUENCE","STAKE_SIZING_ENABLED",
    "TRANSITION_VERSION","TRANSPORT_NAVIGATION_ONLY",
    "_activate_full_analysis_once","_lazy_slot","_render_single_rerun_lazy",
    "render_nfl_hub","render_nfl_passing_yards_hub",
]
