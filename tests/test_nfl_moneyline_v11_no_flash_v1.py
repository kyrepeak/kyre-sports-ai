from __future__ import annotations

from datetime import date
import inspect
from pathlib import Path
import pickle

import pytest

import nfl_moneyline_hub_v11 as v11
import streamlit_memory_lazy_router_v130 as router


def test_v11_contract_is_presentation_execution_only():
    assert v11.FROZEN_TRANSPORT == "nfl_moneyline_hub_v10"
    assert v11.FROZEN_PRESENTATION == "nfl_moneyline_hub_v9"
    assert v11.FROZEN_ENGINE == "nfl_moneyline_hub_v8"
    assert v11.PRESENTATION_EXECUTION_ONLY is True
    assert v11.LEGACY_UI_EMISSION_ENABLED is False
    assert v11.SPORTSBOOK_MODEL_INFLUENCE == 0.0
    assert v11.STAKE_SIZING_ENABLED is False


def test_silent_context_suppresses_legacy_output_and_restores_streamlit(monkeypatch):
    emitted = []

    def witness(body=None, *args, **kwargs):
        emitted.append(body)

    monkeypatch.setattr(v11.st, "markdown", witness)
    original = v11.st.markdown

    with v11._silent_streamlit_execution():
        assert v11.st.markdown is not original
        v11.st.markdown("NFL Moneyline Command Center")
        v11.st.warning("STEP 1A PASSED")
        columns = v11.st.columns(2)
        assert len(columns) == 2
        columns[0].metric("Legacy metric", "1")
        with v11.st.expander("Legacy expander"):
            v11.st.caption("legacy caption")

    assert emitted == []
    assert v11.st.markdown is original


def test_silent_fallbacks_are_pickle_safe_for_streamlit_cache():
    block = v11._SilentBlock()
    assert pickle.loads(pickle.dumps(block)).__class__ is v11._SilentBlock
    fallback = block.any_unknown_streamlit_method
    restored = pickle.loads(pickle.dumps(fallback))
    assert restored is v11._noop
    assert pickle.loads(pickle.dumps(v11._false)) is v11._false
    assert pickle.loads(pickle.dumps(v11._none)) is v11._none


def test_silent_widgets_return_existing_values_without_rendering():
    chosen = date(2026, 9, 14)
    assert v11._silent_date_input("date", chosen) == chosen
    assert v11._silent_text_input("text", "abc") == "abc"
    assert v11._silent_number_input("number", value=17) == 17
    assert v11._silent_bool_widget("toggle", True) is True
    assert v11._silent_selectbox("select", ["A", "B"], index=1) == "B"
    assert v11._silent_multiselect("multi", ["A", "B"], default=["B"]) == ["B"]


def test_silent_engine_executes_frozen_v8_without_emitting_legacy_markdown(monkeypatch):
    emitted = []
    ran = {"value": False}

    def witness(body=None, *args, **kwargs):
        emitted.append(body)

    def fake_engine():
        ran["value"] = True
        v11.st.markdown("NFL Moneyline Command Center")
        v11.st.success("STEP 1A PASSED")

    monkeypatch.setattr(v11.st, "markdown", witness)
    monkeypatch.setattr(v11.frozen_v9.frozen, "render_nfl_moneyline_hub", fake_engine)
    v11._silent_run_frozen_engine()

    assert ran["value"] is True
    assert emitted == []


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
    assert seen["runner"] is v11._silent_run_frozen_engine
    assert v11.frozen_v9._run_frozen_engine is original


def test_v11_restores_v9_runner_even_when_v10_raises(monkeypatch):
    original = v11.frozen_v9._run_frozen_engine

    def boom(market):
        assert v11.frozen_v9._run_frozen_engine is v11._silent_run_frozen_engine
        raise RuntimeError("synthetic V11 witness")

    monkeypatch.setattr(v11.v10, "render_nfl_hub", boom)
    with pytest.raises(RuntimeError, match="synthetic V11 witness"):
        v11.render_nfl_hub("Moneyline")
    assert v11.frozen_v9._run_frozen_engine is original


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

    assert "frozen_v9._run_frozen_engine = _silent_run_frozen_engine" in source
    assert "return v10.render_nfl_hub(market)" in source
    assert "legacy.empty()" not in source
