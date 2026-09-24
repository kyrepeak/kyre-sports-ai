from __future__ import annotations

import nfl_passing_yards_hub_v83 as hub
import streamlit_memory_lazy_router_v234 as router


def test_step7_contract_is_navigation_only():
    assert hub.FROZEN_PRIOR == "nfl_passing_yards_hub_v82"
    assert hub.SPEED_PHASE_STEP == 7
    assert hub.SAME_SESSION_TRANSPORT is True
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


def test_step7_removes_legacy_blank_target_activation_link():
    sample = (
        '<section><a class="ks-py79-load" '
        'data-passing-yards-load-full="v79" '
        'href="?ks_qb_slot=2&amp;ks_py_full=1">'
        'Load Full Analysis →</a><b>keep</b></section>'
    )
    cleaned = hub._strip_legacy_load_link(sample)
    assert 'data-passing-yards-load-full="v79"' not in cleaned
    assert "<b>keep</b>" in cleaned


def test_step7_activation_sets_only_full_flag_then_reruns():
    params = {"ks_py_date": "2026-09-24", "ks_qb_slot": "2"}
    calls = []
    hub._activate_full_analysis(params, lambda: calls.append("rerun"))
    assert params == {
        "ks_py_date": "2026-09-24",
        "ks_qb_slot": "2",
        "ks_py_full": "1",
    }
    assert calls == ["rerun"]


def test_step7_router_advances_only_passing_yards_owner():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v233"
    assert router.PASSING_HUB == "nfl_passing_yards_hub_v83"
    assert router.FALLBACK_HUB == "nfl_passing_yards_hub_v82"
