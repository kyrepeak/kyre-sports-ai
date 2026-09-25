from __future__ import annotations

import inspect

import nfl_passing_yards_hub_v85 as hub
import streamlit_memory_lazy_router_v236 as router


def test_v85_same_tab_contract():
    assert hub.FROZEN_PRIOR == "nfl_passing_yards_hub_v84"
    assert hub.SPEED_PHASE_STEP == 7
    assert hub.SAME_TAB_DIRECT_TRANSPORT is True
    assert hub.TRANSPORT_NAVIGATION_ONLY is True
    assert hub.MAY_MODIFY_PROJECTION is False
    assert hub.MAY_MODIFY_CONTEXT_MATH is False
    assert hub.MAY_MODIFY_PROBABILITY is False
    assert hub.MAY_MODIFY_MARKET_MATH is False
    assert hub.MAY_MODIFY_SPORTSBOOK_BEHAVIOR is False
    assert hub.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert hub.MAY_MODIFY_WIDGET_KEYS is False
    assert hub.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert hub.STAKE_SIZING_ENABLED is False


def test_v85_control_forces_same_tab_direct_navigation():
    html = hub._same_tab_control_html("?ks_qb_slot=2&ks_py_full=1")
    assert 'target="_self"' in html
    assert "window.location.assign" in html
    assert "ks_py_full=1" in html
    assert 'data-passing-yards-same-tab-owner="v85"' in html


def test_v85_lazy_renderer_has_no_streamlit_widget_rerun():
    source = inspect.getsource(hub._render_same_tab_lazy)
    assert "st.button" not in source
    assert "st.rerun" not in source
    assert "unsafe_allow_javascript=True" in source


def test_v236_router_advances_only_passing_yards_owner():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v235"
    assert router.PASSING_HUB == "nfl_passing_yards_hub_v85"
    assert router.FALLBACK_HUB == "nfl_passing_yards_hub_v84"
