from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import nfl_moneyline_hub_v12 as v12
import streamlit_memory_lazy_router_v131 as r131


def test_v12_permanent_safety_constants():
    assert v12.PERFORMANCE_ONLY is True
    assert v12.FROZEN_PRIOR == "nfl_moneyline_hub_v11"
    assert v12.FROZEN_ENGINE == "nfl_moneyline_hub_v8"
    assert v12.MONTE_CARLO_SIMULATIONS == 5_000_000
    assert v12.SPORTSBOOK_MODEL_INFLUENCE == 0.0
    assert v12.STAKE_SIZING_ENABLED is False


def test_request_memo_reuses_same_key_exact_value():
    calls = []
    stats = {}
    sentinel = object()

    def original(value):
        calls.append(value)
        return sentinel

    wrapped = v12._timed_request_memo(original, lambda value: (value,), stats, "probe")
    assert wrapped("same") is sentinel
    assert wrapped("same") is sentinel
    assert calls == ["same"]
    assert stats["probe"]["calls"] == 2
    assert stats["probe"]["misses"] == 1
    assert stats["probe"]["hits"] == 1


def test_request_memo_keeps_different_keys_separate():
    calls = []
    stats = {}

    def original(value):
        calls.append(value)
        return value.upper()

    wrapped = v12._timed_request_memo(original, lambda value: (value,), stats, "probe")
    assert wrapped("a") == "A"
    assert wrapped("b") == "B"
    assert calls == ["a", "b"]
    assert stats["probe"]["misses"] == 2
    assert stats["probe"]["hits"] == 0


def test_schedule_key_is_date_only():
    assert v12._schedule_key("2026-09-14") == ("2026-09-14",)
    assert v12._schedule_key(" 2026-09-14 ") == ("2026-09-14",)


def test_calibration_key_is_frozen_constant():
    assert v12._calibration_key() == ("frozen-calibration",)
    assert v12._calibration_key(1, two=2) == ("frozen-calibration",)


def test_sink_columns_returns_requested_count():
    stats = {}
    cols = v12._columns_sink(stats, 3)
    assert len(cols) == 3
    assert all(isinstance(x, v12._Sink) for x in cols)
    assert stats["suppressed"]["columns"] == 1


def test_sink_hidden_presentation_restores_functions(monkeypatch):
    original_markdown = v12.st.markdown
    original_columns = v12.st.columns
    stats = {}
    with v12._sink_hidden_presentation(stats):
        assert v12.st.markdown is not original_markdown
        assert v12.st.columns is not original_columns
        assert v12.st.markdown("hidden") is None
        assert len(v12.st.columns(2)) == 2
    assert v12.st.markdown is original_markdown
    assert v12.st.columns is original_columns
    assert stats["suppressed"]["markdown"] == 1
    assert stats["suppressed"]["columns"] == 1


def test_sink_hidden_presentation_restores_after_exception():
    original_markdown = v12.st.markdown
    stats = {}
    with pytest.raises(RuntimeError, match="boom"):
        with v12._sink_hidden_presentation(stats):
            raise RuntimeError("boom")
    assert v12.st.markdown is original_markdown


def test_fast_hidden_runner_keeps_v11_hide_then_runs_frozen_once(monkeypatch):
    events = []
    stats = {}

    class Ctx:
        def __enter__(self):
            events.append("enter")
            return self
        def __exit__(self, exc_type, exc, tb):
            events.append("exit")
            return False
        def container(self):
            events.append("legacy-container")
            return self
        def empty(self):
            events.append("legacy-empty")

    monkeypatch.setattr(v12.st, "markdown", lambda body, **kwargs: events.append("css"))
    monkeypatch.setattr(v12.st, "container", lambda **kwargs: (events.append("hidden-container") or Ctx()))
    monkeypatch.setattr(v12.st, "empty", lambda: Ctx())
    monkeypatch.setattr(v12.v11.frozen_v9.frozen, "render_nfl_moneyline_hub", lambda: events.append("frozen-engine"))
    monkeypatch.setattr(v12, "_sink_hidden_presentation", lambda stats: Ctx())

    v12._fast_hidden_run_frozen_engine(stats)
    assert events[0] == "css"
    assert "hidden-container" in events
    assert events.count("frozen-engine") == 1


def test_render_rejects_non_moneyline():
    with pytest.raises(RuntimeError, match="Moneyline V12 direct handler"):
        v12.render_nfl_hub("Passing Yards")


def test_v12_render_restores_all_patches_on_success(monkeypatch):
    original_schedule = v12.foundation.load_nfl_slate
    original_calibration = v12.calibration_page._fit_calibration_model
    original_hidden = v12.v11._hidden_run_frozen_engine
    seen = {}

    def fake_render(market):
        seen["schedule_patched"] = v12.foundation.load_nfl_slate is not original_schedule
        seen["calibration_patched"] = v12.calibration_page._fit_calibration_model is not original_calibration
        seen["hidden_patched"] = v12.v11._hidden_run_frozen_engine is not original_hidden
        return "ok"

    monkeypatch.setattr(v12.v11, "render_nfl_hub", fake_render)
    monkeypatch.setattr(v12, "_store_speed_stats", lambda stats, total_ms: seen.update(stored=True))

    assert v12.render_nfl_hub("Moneyline") == "ok"
    assert all(seen[k] for k in ("schedule_patched", "calibration_patched", "hidden_patched", "stored"))
    assert v12.foundation.load_nfl_slate is original_schedule
    assert v12.calibration_page._fit_calibration_model is original_calibration
    assert v12.v11._hidden_run_frozen_engine is original_hidden


def test_v12_render_restores_all_patches_on_error(monkeypatch):
    original_schedule = v12.foundation.load_nfl_slate
    original_calibration = v12.calibration_page._fit_calibration_model
    original_hidden = v12.v11._hidden_run_frozen_engine
    monkeypatch.setattr(v12.v11, "render_nfl_hub", lambda market: (_ for _ in ()).throw(ValueError("boom")))
    monkeypatch.setattr(v12, "_store_speed_stats", lambda stats, total_ms: None)

    with pytest.raises(ValueError, match="boom"):
        v12.render_nfl_hub("Moneyline")
    assert v12.foundation.load_nfl_slate is original_schedule
    assert v12.calibration_page._fit_calibration_model is original_calibration
    assert v12.v11._hidden_run_frozen_engine is original_hidden


def test_v131_permanent_safety_constants():
    assert r131.FROZEN_ROUTER == "streamlit_memory_lazy_router_v130"
    assert r131.ACTIVE_MONEYLINE_HUB == "nfl_moneyline_hub_v12"
    assert r131.MONEYLINE_MARKET == "Moneyline"
    assert r131.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert r131.STAKE_SIZING_ENABLED is False


def test_fast_route_active_requires_exact_nfl_moneyline(monkeypatch):
    state = {"ks_sport_touch": "NFL", "ks_nfl_market_touch": "Moneyline"}
    monkeypatch.setattr(r131.st, "session_state", state)
    assert r131._fast_route_active() is True
    state["ks_nfl_market_touch"] = "Slate"
    assert r131._fast_route_active() is False


def test_restore_fast_route_from_query_only_when_route_empty(monkeypatch):
    state = {}
    query = {r131.ROUTE_QUERY_SPORT: "NFL", r131.ROUTE_QUERY_MARKET: "Moneyline"}
    monkeypatch.setattr(r131.st, "session_state", state)
    monkeypatch.setattr(r131.st, "query_params", query)
    assert r131._restore_fast_route_from_query() is True
    assert state["ks_sport_touch"] == "NFL"
    assert state["ks_nfl_market_touch"] == "Moneyline"
    assert r131._restore_fast_route_from_query() is False


def test_persist_and_clear_fast_route_query(monkeypatch):
    query = {}
    monkeypatch.setattr(r131.st, "query_params", query)
    r131._persist_fast_route_query()
    assert query[r131.ROUTE_QUERY_SPORT] == "NFL"
    assert query[r131.ROUTE_QUERY_MARKET] == "Moneyline"
    r131._clear_fast_route_query()
    assert r131.ROUTE_QUERY_SPORT not in query
    assert r131.ROUTE_QUERY_MARKET not in query


def test_render_nfl_v131_rejects_non_moneyline():
    with pytest.raises(RuntimeError, match="Moneyline only"):
        r131._render_nfl_v131("Slate")


def test_v131_fast_render_imports_v12_not_prior(monkeypatch):
    calls = []
    state = {}
    monkeypatch.setattr(r131.st, "session_state", state)
    monkeypatch.setattr(r131, "_persist_fast_route_query", lambda: None)
    monkeypatch.setattr(r131, "_query_value", lambda name: "Moneyline" if name == r131.ROUTE_QUERY_MARKET else "NFL")
    monkeypatch.setattr(r131.root, "_import", lambda name: (calls.append(name) or SimpleNamespace(render_nfl_hub=lambda market: "ok")))
    monkeypatch.setattr(r131, "_load_prior", lambda: (_ for _ in ()).throw(AssertionError("prior router must not load")))

    assert r131._render_nfl_v131("Moneyline") == "ok"
    assert calls == ["nfl_moneyline_hub_v12"]
    assert state["nfl_moneyline_cold_start_v131_last"]["sportsbook_projection_influence"] == 0.0


def test_v131_fallback_loads_frozen_prior(monkeypatch):
    monkeypatch.setattr(r131, "_fast_route_active", lambda: False)
    monkeypatch.setattr(r131, "_restore_fast_route_from_query", lambda: False)
    prior = SimpleNamespace(render_app=lambda: "prior")
    monkeypatch.setattr(r131, "_load_prior", lambda: prior)
    assert r131.render_app() == "prior"


def test_v131_nonmoneyline_session_clears_stale_fast_query_before_fallback(monkeypatch):
    state = {"ks_sport_touch": "NFL", "ks_nfl_market_touch": "Slate"}
    query = {r131.ROUTE_QUERY_SPORT: "NFL", r131.ROUTE_QUERY_MARKET: "Moneyline"}
    monkeypatch.setattr(r131.st, "session_state", state)
    monkeypatch.setattr(r131.st, "query_params", query)
    prior = SimpleNamespace(render_app=lambda: "prior")
    monkeypatch.setattr(r131, "_load_prior", lambda: prior)

    assert r131.render_app() == "prior"
    assert r131.ROUTE_QUERY_SPORT not in query
    assert r131.ROUTE_QUERY_MARKET not in query


def test_v131_fast_path_does_not_load_prior(monkeypatch):
    monkeypatch.setattr(r131, "_fast_route_active", lambda: True)
    monkeypatch.setattr(r131, "_render_direct_moneyline", lambda: "fast")
    monkeypatch.setattr(r131, "_load_prior", lambda: (_ for _ in ()).throw(AssertionError("prior loaded")))
    assert r131.render_app() == "fast"


def test_direct_route_restores_root_patches_on_success(monkeypatch):
    original_selectbox = r131.root.st.selectbox
    original_render_nfl = r131.root._render_nfl
    original_prefixes = r131.root._ROUTE_MODULE_PREFIXES
    monkeypatch.setattr(r131.root, "render_app", lambda: "ok")
    assert r131._render_direct_moneyline() == "ok"
    assert r131.root.st.selectbox is original_selectbox
    assert r131.root._render_nfl is original_render_nfl
    assert r131.root._ROUTE_MODULE_PREFIXES == original_prefixes


def test_direct_route_restores_root_patches_on_error(monkeypatch):
    original_selectbox = r131.root.st.selectbox
    original_render_nfl = r131.root._render_nfl
    original_prefixes = r131.root._ROUTE_MODULE_PREFIXES
    monkeypatch.setattr(r131.root, "render_app", lambda: (_ for _ in ()).throw(ValueError("boom")))
    with pytest.raises(ValueError, match="boom"):
        r131._render_direct_moneyline()
    assert r131.root.st.selectbox is original_selectbox
    assert r131.root._render_nfl is original_render_nfl
    assert r131.root._ROUTE_MODULE_PREFIXES == original_prefixes


def test_v131_source_has_no_eager_v130_import():
    import inspect
    source = inspect.getsource(r131)
    assert "import streamlit_memory_lazy_router_v130" not in source
    assert "importlib.import_module(FROZEN_ROUTER)" in source
