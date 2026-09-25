from __future__ import annotations

import inspect

import nfl_passing_yards_hub_v84 as hub
import streamlit_memory_lazy_router_v235 as router


def test_v84_single_rerun_contract():
    assert hub.FROZEN_PRIOR == "nfl_passing_yards_hub_v83"
    assert hub.SPEED_PHASE_STEP == 7
    assert hub.SAME_SESSION_TRANSPORT is True
    assert hub.SINGLE_RERUN_TRANSPORT is True
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


def test_v84_callback_sets_only_full_flag_without_explicit_rerun():
    params = {"ks_py_date": "2026-09-24", "ks_qb_slot": "2"}
    hub._activate_full_analysis_once(params)
    assert params == {
        "ks_py_date": "2026-09-24",
        "ks_qb_slot": "2",
        "ks_py_full": "1",
    }
    source = inspect.getsource(hub._activate_full_analysis_once)
    assert "st.rerun" not in source


def test_v84_lazy_renderer_uses_button_callback():
    source = inspect.getsource(hub._render_single_rerun_lazy)
    assert "on_click=_activate_full_analysis_once" in source
    assert "st.rerun" not in source
    assert 'data-passing-yards-single-rerun-owner="v84"' in source


def test_v235_router_advances_only_passing_yards_owner():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v234"
    assert router.PASSING_HUB == "nfl_passing_yards_hub_v84"
    assert router.FALLBACK_HUB == "nfl_passing_yards_hub_v83"
