from __future__ import annotations
import nfl_passing_yards_hub_v80 as v80
import streamlit_memory_lazy_router_v231 as v231

def test_speed_step4_contract_is_cache_only():
    assert v80.FROZEN_PRIOR=="nfl_passing_yards_hub_v79"
    assert v80.SPEED_PHASE_STEP==4
    assert v80.CACHE_ONLY is True
    assert v80.CACHE_TTL_SECONDS==300
    assert v80.MAY_MODIFY_PROJECTION is False
    assert v80.MAY_MODIFY_CONTEXT_MATH is False
    assert v80.MAY_MODIFY_PROBABILITY is False
    assert v80.MAY_MODIFY_MARKET_MATH is False
    assert v80.MAY_MODIFY_SPORTSBOOK_BEHAVIOR is False
    assert v80.MAY_MODIFY_WIDGET_KEYS is False
    assert v80.MAY_MODIFY_NAVIGATION_STATE is False
    assert v80.SPORTSBOOK_PROJECTION_INFLUENCE==0.0
    assert v80.STAKE_SIZING_ENABLED is False

def test_speed_step4_profile_cache_reuses_identical_result(monkeypatch):
    calls={"n":0}
    def fake(athlete_id,qb_name,year,season_type=2):
        calls["n"]+=1
        return {"athlete_id":athlete_id,"qb_name":qb_name,"year":year,"season_type":season_type,"ready":True}
    monkeypatch.setattr(v80,"_ORIGINAL_PROFILE",fake)
    v80._cached_profile.clear()
    a=v80._cached_profile("999","Jordan Love",2026,2)
    b=v80._cached_profile("999","Jordan Love",2026,2)
    assert a==b
    assert calls["n"]==1

def test_speed_step4_pressure_cache_reuses_identical_result(monkeypatch):
    calls={"n":0}
    def fake(*args):
        calls["n"]+=1
        return {"ready":True,"args":list(args),"sportsbook_influence":0.0}
    monkeypatch.setattr(v80,"_ORIGINAL_PRESSURE",fake)
    v80._cached_pressure.clear()
    args=("9","GB","1","ATL",2026,2,"2026-09-24")
    a=v80._cached_pressure(*args)
    b=v80._cached_pressure(*args)
    assert a==b
    assert calls["n"]==1

def test_speed_step4_router_advances_only_passing_yards():
    assert v231.FROZEN_ROUTER=="streamlit_memory_lazy_router_v230"
    assert v231.PASSING_HUB=="nfl_passing_yards_hub_v80"
    assert v231.FALLBACK_HUB=="nfl_passing_yards_hub_v79"
    assert v231.SPORTSBOOK_PROJECTION_INFLUENCE==0.0
