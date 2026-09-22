from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import nfl_moneyline_hub_v11 as v11
import streamlit_memory_lazy_router_v130 as router


def test_v11_contract_is_presentation_execution_only():
    assert v11.FROZEN_TRANSPORT == "nfl_moneyline_hub_v10"
    assert v11.FROZEN_PRESENTATION == "nfl_moneyline_hub_v9"
    assert v11.FROZEN_ENGINE == "nfl_moneyline_hub_v8"
    assert v11.PRESENTATION_EXECUTION_ONLY is True
    assert v11.LEGACY_UI_VISIBLE is False
    assert v11.SPORTSBOOK_MODEL_INFLUENCE == 0.0
    assert v11.STAKE_SIZING_ENABLED is False
    assert v11.LEGACY_CONTAINER_KEY == "nfl_moneyline_v11_legacy_hidden"
    assert v11.LEGACY_CONTAINER_CLASS == "st-key-nfl_moneyline_v11_legacy_hidden"


def test_hidden_css_contract_is_fail_closed_before_legacy_render():
    css = v11._HIDDEN_LEGACY_CSS
    assert f".{v11.LEGACY_CONTAINER_CLASS}" in css
    assert "display: none !important" in css
    assert "visibility: hidden !important" in css
    assert "opacity: 0 !important" in css
    assert "pointer-events: none !important" in css
    assert "height: 0 !important" in css
    assert "overflow: hidden !important" in css


def test_hidden_engine_orders_css_container_engine_and_cleanup(monkeypatch):
    events = []

    class Context:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            events.append(("enter", self.name))
            return self

        def __exit__(self, exc_type, exc, tb):
            events.append(("exit", self.name))
            return False

    class EmptySlot:
        def container(self):
            events.append(("legacy-container",))
            return Context("legacy")

        def empty(self):
            events.append(("legacy-empty",))

    def markdown(body=None, *args, **kwargs):
        events.append(("markdown", body, kwargs.get("unsafe_allow_html")))

    def container(*args, **kwargs):
        events.append(("hidden-container", kwargs.get("key")))
        return Context("hidden")

    def empty():
        events.append(("empty-slot",))
        return EmptySlot()

    def fake_engine():
        # V8 must see the normal Streamlit renderer; V11 does not monkeypatch it.
        events.append(("engine", v11.st.markdown is markdown))
        v11.st.markdown("NFL Moneyline Command Center")

    monkeypatch.setattr(v11.st, "markdown", markdown)
    monkeypatch.setattr(v11.st, "container", container)
    monkeypatch.setattr(v11.st, "empty", empty)
    monkeypatch.setattr(v11.frozen_v9.frozen, "render_nfl_moneyline_hub", fake_engine)

    v11._hidden_run_frozen_engine()

    assert events[0][0] == "markdown"
    assert events[0][1] == v11._HIDDEN_LEGACY_CSS
    assert events[0][2] is True
    assert ("hidden-container", v11.LEGACY_CONTAINER_KEY) in events
    assert ("enter", "hidden") in events
    assert ("enter", "legacy") in events
    assert ("engine", True) in events
    assert ("markdown", "NFL Moneyline Command Center", None) in events
    assert ("legacy-empty",) in events

    css_i = events.index(events[0])
    hidden_i = events.index(("hidden-container", v11.LEGACY_CONTAINER_KEY))
    engine_i = events.index(("engine", True))
    cleanup_i = events.index(("legacy-empty",))
    assert css_i < hidden_i < engine_i < cleanup_i


def test_v11_temporarily_patches_v9_runner_and_restores(monkeypatch):
    original = v11.frozen_v9._run_frozen_engine
    seen = {}

    def render(market):
        seen["market"] = market
        seen["runner"] = v11.frozen_v9._run_frozen_engine
        return "ok"

    monkeypatch.setattr(v11.v10, "render_nfl_hub", render)
    assert v11.render_nfl_hub("Moneyline") == "ok"
    assert seen["market"] == "Moneyline"
    assert seen["runner"] is v11._hidden_run_frozen_engine
    assert v11.frozen_v9._run_frozen_engine is original


def test_v11_restores_v9_runner_even_when_v10_raises(monkeypatch):
    original = v11.frozen_v9._run_frozen_engine

    def boom(market):
        assert v11.frozen_v9._run_frozen_engine is v11._hidden_run_frozen_engine
        raise RuntimeError("synthetic V11 witness")

    monkeypatch.setattr(v11.v10, "render_nfl_hub", boom)
    with pytest.raises(RuntimeError, match="synthetic V11 witness"):
        v11.render_nfl_hub("Moneyline")
    assert v11.frozen_v9._run_frozen_engine is original


def test_v11_rejects_non_moneyline_direct_calls():
    with pytest.raises(RuntimeError, match="Moneyline only"):
        v11.render_nfl_hub("Passing Yards")


def test_v130_advances_only_exact_nfl_moneyline():
    source = inspect.getsource(router)
    direct = inspect.getsource(router._render_nfl_v130)
    render = inspect.getsource(router.render_app)
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v129"
    assert router.ACTIVE_MONEYLINE_HUB == "nfl_moneyline_hub_v11"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.STAKE_SIZING_ENABLED is False
    assert 'MONEYLINE_MARKET = "Moneyline"' in source
    assert "module.render_nfl_hub(market)" in direct
    assert "return prior.render_app()" in render
    assert "Passing Yards" not in direct


def test_app_activates_v130_and_preserves_v129_descendant_anchor():
    source = Path("app.py").read_text()
    assert 'from streamlit_memory_lazy_router_v130 import record_bootstrap_import_ms, render_app' in source
    assert 'from streamlit_memory_lazy_router_v129 import render_app as _frozen_v129_render_app' in source
    assert 'from streamlit_memory_lazy_router_v129 import record_bootstrap_import_ms, render_app' in source
    assert 'FROZEN_V129_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V129_NFL_MONEYLINE_KYRE_API_TRANSPORT_2026-09-14"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V130_NFL_MONEYLINE_NO_FLASH_2026-09-14"' in source


def test_v11_owns_no_moneyline_analytics_or_market_math():
    source = inspect.getsource(v11)
    forbidden = (
        "np.random",
        "default_rng",
        "monte_carlo",
        "_expected_return(",
        "_fair_american(",
        "QUALIFIED_EDGE =",
        "QUALIFIED_EV =",
        "LEAN_EDGE =",
        "MAX_COMFORTABLE_INTERVAL =",
        "away_no_vig",
        "consensus_away_no_vig",
        "implied_probability(",
    )
    for token in forbidden:
        assert token not in source, token

    assert "frozen_v9._run_frozen_engine = _hidden_run_frozen_engine" in source
    assert "return v10.render_nfl_hub(market)" in source
    assert "frozen_v9.frozen.render_nfl_moneyline_hub()" in source
    assert "legacy.empty()" in source
    assert "st.markdown(_HIDDEN_LEGACY_CSS, unsafe_allow_html=True)" in source
