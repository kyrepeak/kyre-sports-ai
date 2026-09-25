from pathlib import Path

import streamlit_memory_lazy_router_v188 as passing_base
import streamlit_memory_lazy_router_v225 as route_guard
import streamlit_memory_lazy_router_v237 as prior
import streamlit_memory_lazy_router_v238 as v238


def test_non_passing_route_delegates_unchanged(monkeypatch):
    calls=[]
    monkeypatch.setattr(v238,"_cold_passing_yards_query_requested",lambda:False)
    monkeypatch.setattr(v238,"_active_passing_yards_route",lambda:False)
    monkeypatch.setattr(prior,"render_app",lambda:calls.append("prior"))
    v238.render_app()
    assert calls==["prior"]


def test_passing_route_uses_v188_direct_handoff_with_v85(monkeypatch):
    calls=[]
    original=passing_base.PASSING_HUB

    monkeypatch.setattr(v238,"_cold_passing_yards_query_requested",lambda:False)
    monkeypatch.setattr(v238,"_active_passing_yards_route",lambda:True)
    monkeypatch.setattr(v238,"_passing_hub_importable",lambda:True)
    monkeypatch.setattr(
        route_guard,
        "_prime_passing_route_token_for_session",
        lambda:calls.append("prime"),
    )
    monkeypatch.setattr(
        v238.st,
        "markdown",
        lambda *args,**kwargs:calls.append("marker"),
    )

    def fake_render():
        calls.append(("render",passing_base.PASSING_HUB))

    monkeypatch.setattr(passing_base,"_render_passing_v188",fake_render)

    v238.render_app()

    assert calls[0]=="prime"
    assert "marker" in calls
    assert ("render","nfl_passing_yards_hub_v85") in calls
    assert passing_base.PASSING_HUB==original


def test_passing_route_fail_closed_delegates_if_v85_unavailable(monkeypatch):
    calls=[]
    monkeypatch.setattr(v238,"_cold_passing_yards_query_requested",lambda:False)
    monkeypatch.setattr(v238,"_active_passing_yards_route",lambda:True)
    monkeypatch.setattr(v238,"_passing_hub_importable",lambda:False)
    monkeypatch.setattr(prior,"render_app",lambda:calls.append("prior"))
    monkeypatch.setattr(
        v238,
        "_render_passing_yards_direct",
        lambda:calls.append("direct"),
    )
    v238.render_app()
    assert calls==["prior"]


def test_cold_route_primes_frozen_v185_state_before_direct_handoff(monkeypatch):
    calls=[]
    monkeypatch.setattr(v238,"_cold_passing_yards_query_requested",lambda:True)
    monkeypatch.setattr(v238,"_active_passing_yards_route",lambda:False)
    monkeypatch.setattr(v238,"_prime_cold_passing_state",lambda:calls.append("cold"))
    monkeypatch.setattr(v238,"_passing_hub_importable",lambda:True)
    monkeypatch.setattr(v238,"_render_passing_yards_direct",lambda:calls.append("direct"))
    v238.render_app()
    assert calls==["cold","direct"]


def test_v238_contract_is_route_only():
    assert v238.PRESENTATION_ONLY is True
    assert v238.ROUTE_HANDOFF_ONLY is True
    assert v238.MAY_MODIFY_PROJECTION is False
    assert v238.MAY_MODIFY_CONTEXT_MATH is False
    assert v238.MAY_MODIFY_PROBABILITY is False
    assert v238.MAY_MODIFY_MARKET_MATH is False
    assert v238.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert v238.MAY_MODIFY_WIDGET_KEYS is False
    assert v238.SPORTSBOOK_PROJECTION_INFLUENCE==0.0
    assert v238.STAKE_SIZING_ENABLED is False
    assert v238.FROZEN_ROUTER=="streamlit_memory_lazy_router_v237"
    assert v238.FROZEN_MONSTER_ROUTER=="streamlit_memory_lazy_router_v236"
    assert v238.FROZEN_DIRECT_PROP_ROUTER=="streamlit_memory_lazy_router_v188"


def test_app_activates_v238_only():
    app=Path("app.py").read_text()
    assert "from streamlit_memory_lazy_router_v238 import record_bootstrap_import_ms, render_app" in app
    assert "from streamlit_memory_lazy_router_v237 import record_bootstrap_import_ms, render_app" not in app
