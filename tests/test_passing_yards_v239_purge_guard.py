from pathlib import Path

import streamlit_memory_lazy_router_v188 as passing_base
import streamlit_memory_lazy_router_v238 as prior
import streamlit_memory_lazy_router_v239 as v239


def test_non_passing_route_delegates_unchanged(monkeypatch):
    calls = []
    monkeypatch.setattr(v239, "_cold_passing_yards_query_requested", lambda: False)
    monkeypatch.setattr(v239, "_active_passing_yards_route", lambda: False)
    monkeypatch.setattr(prior, "render_app", lambda: calls.append("prior"))
    v239.render_app()
    assert calls == ["prior"]


def test_active_passing_route_primes_guard_before_import_and_render(monkeypatch):
    calls = []
    original = passing_base.PASSING_HUB

    monkeypatch.setattr(v239, "_cold_passing_yards_query_requested", lambda: False)
    monkeypatch.setattr(v239, "_active_passing_yards_route", lambda: True)
    monkeypatch.setattr(v239, "_prime_passing_route_token", lambda: calls.append("prime") or "NFL:Passing Yards")
    monkeypatch.setattr(v239, "_passing_hub_importable", lambda: calls.append("import") or True)
    monkeypatch.setattr(v239.st, "markdown", lambda *args, **kwargs: calls.append("marker"))
    monkeypatch.setattr(
        passing_base,
        "_render_passing_v188",
        lambda: calls.append(("render", passing_base.PASSING_HUB)),
    )

    v239.render_app()

    assert calls[0:2] == ["prime", "import"]
    assert "marker" in calls
    assert ("render", "nfl_passing_yards_hub_v85") in calls
    assert passing_base.PASSING_HUB == original


def test_cold_route_primes_state_then_route_guard(monkeypatch):
    calls = []
    monkeypatch.setattr(v239, "_cold_passing_yards_query_requested", lambda: True)
    monkeypatch.setattr(v239, "_active_passing_yards_route", lambda: False)
    monkeypatch.setattr(v239, "_prime_cold_passing_state", lambda: calls.append("cold"))
    monkeypatch.setattr(v239, "_prime_passing_route_token", lambda: calls.append("guard") or "NFL:Passing Yards")
    monkeypatch.setattr(v239, "_passing_hub_importable", lambda: True)
    monkeypatch.setattr(v239, "_render_passing_yards_direct", lambda: calls.append("render"))

    v239.render_app()

    assert calls == ["cold", "guard", "render"]


def test_import_failure_fails_closed_after_guard(monkeypatch):
    calls = []
    monkeypatch.setattr(v239, "_cold_passing_yards_query_requested", lambda: False)
    monkeypatch.setattr(v239, "_active_passing_yards_route", lambda: True)
    monkeypatch.setattr(v239, "_prime_passing_route_token", lambda: calls.append("guard") or "NFL:Passing Yards")
    monkeypatch.setattr(v239, "_passing_hub_importable", lambda: False)
    monkeypatch.setattr(prior, "render_app", lambda: calls.append("prior"))

    v239.render_app()

    assert calls == ["guard", "prior"]


def test_v239_contract_is_route_only():
    assert v239.PRESENTATION_ONLY is True
    assert v239.ROUTE_HANDOFF_ONLY is True
    assert v239.MAY_MODIFY_PROJECTION is False
    assert v239.MAY_MODIFY_CONTEXT_MATH is False
    assert v239.MAY_MODIFY_PROBABILITY is False
    assert v239.MAY_MODIFY_MARKET_MATH is False
    assert v239.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert v239.MAY_MODIFY_WIDGET_KEYS is False
    assert v239.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v239.STAKE_SIZING_ENABLED is False
    assert v239.FROZEN_ROUTER == "streamlit_memory_lazy_router_v238"
    assert v239.FROZEN_ROUTE_GUARD == "streamlit_memory_lazy_router_v225"
    assert v239.FROZEN_DIRECT_PROP_ROUTER == "streamlit_memory_lazy_router_v188"


def test_app_activates_v239_only():
    app = Path("app.py").read_text()
    assert "from streamlit_memory_lazy_router_v239 import record_bootstrap_import_ms, render_app" in app
    assert "from streamlit_memory_lazy_router_v238 import record_bootstrap_import_ms, render_app" not in app
