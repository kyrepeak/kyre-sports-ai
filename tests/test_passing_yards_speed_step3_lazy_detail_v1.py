from __future__ import annotations
from urllib.parse import parse_qs, urlsplit
import nfl_passing_yards_hub_v79 as v79
import streamlit_memory_lazy_router_v230 as v230

HINTS={"name":"Jordan Love","meta":"GB • QB","projection":"276.4","attempts":"34.8","ypa":"7.94","line":"274.5","lean":"LEAN OVER"}

def test_speed_step3_is_lazy_presentation_only():
    assert v79.FROZEN_PRIOR == "nfl_passing_yards_hub_v78"
    assert v79.SPEED_PHASE_STEP == 3
    assert v79.PRESENTATION_ONLY is True
    assert v79.MAY_MODIFY_PROJECTION is False
    assert v79.MAY_MODIFY_CONTEXT_MATH is False
    assert v79.MAY_MODIFY_PROBABILITY is False
    assert v79.MAY_MODIFY_MARKET_MATH is False
    assert v79.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert v79.MAY_MODIFY_WIDGET_KEYS is False
    assert v79.MAY_MODIFY_NAVIGATION_STATE is False
    assert v79.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v79.STAKE_SIZING_ENABLED is False

def test_speed_step3_full_link_preserves_hints_and_adds_opt_in():
    url=v79._with_full("/?ks_jump_sport=NFL&ks_qb_slot=2&ks_py_hint_name=Jordan+Love",True)
    query=parse_qs(urlsplit(url).query)
    assert query["ks_qb_slot"]==["2"]
    assert query["ks_py_hint_name"]==["Jordan Love"]
    assert query["ks_py_full"]==["1"]

def test_speed_step3_lazy_shell_is_small_and_contains_deferred_sections(monkeypatch):
    monkeypatch.setattr(v79.selection,"_current_nav_url",lambda slot=None:"/?ks_jump_sport=NFL&ks_jump_market=Passing+Yards"+(f"&ks_qb_slot={slot}" if slot else ""))
    html=v79.build_lazy_detail_shell(2,HINTS)
    assert 'data-passing-yards-lazy-detail="v79"' in html
    assert 'data-passing-yards-load-full="v79"' in html
    for token in ("Jordan Love","Why","Matchup","Market","Game Day","Reliability"):
        assert token in html
    assert "ks_py_full=1" in html.replace("&amp;","&")
    assert len(html.encode("utf-8")) < 50000

def test_speed_step3_router_advances_only_passing_yards():
    assert v230.FROZEN_ROUTER=="streamlit_memory_lazy_router_v229"
    assert v230.PASSING_HUB=="nfl_passing_yards_hub_v79"
    assert v230.FALLBACK_HUB=="nfl_passing_yards_hub_v78"
    assert v230.SPORTSBOOK_PROJECTION_INFLUENCE==0.0
