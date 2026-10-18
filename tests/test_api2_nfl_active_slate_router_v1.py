from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import importlib
from pathlib import Path
import sys
import types
from zoneinfo import ZoneInfo


def _load_router(monkeypatch, *, sport="nfl", market="spread", manual=False):
    events = []
    st = types.ModuleType("streamlit")
    st.session_state = {
        "ks_universal_sport": sport,
        "ks_universal_market": market,
    }
    if manual:
        st.session_state.update({
            "nfl_active_slate_mode": "MANUAL",
            "nfl_manual_slate_date": date(2026, 9, 20),
            "nfl_v1_date": date(2026, 9, 20),
        })
    st.query_params = {"sport": sport, "market": market}
    monkeypatch.setitem(sys.modules, "streamlit", st)

    prior = types.ModuleType("streamlit_memory_lazy_router_monster_cfb_market_completeness_r1")
    prior.record_bootstrap_import_ms = lambda value: events.append(("bootstrap", value))
    prior.render_app = lambda: events.append(("render", st.session_state.get("nfl_v1_date"))) or "prior-render"
    monkeypatch.setitem(sys.modules, "streamlit_memory_lazy_router_monster_cfb_market_completeness_r1", prior)

    nfl = types.ModuleType("nfl_hub_v1")
    nfl.ET = ZoneInfo("America/New_York")
    nfl.load_nfl_slate = lambda day: ([], {"request_ok": True})
    monkeypatch.setitem(sys.modules, "nfl_hub_v1", nfl)

    next_slate = types.ModuleType("nfl_passing_yards_next_slate_v1")
    next_slate.nflverse_schedule_dates = lambda start, end: []
    monkeypatch.setitem(sys.modules, "nfl_passing_yards_next_slate_v1", next_slate)

    runtime = types.ModuleType("nfl_active_slate_runtime_v1")
    def prepare(session, **kwargs):
        events.append(("prepare", session.get("ks_universal_sport")))
        if session.get("nfl_active_slate_mode") == "MANUAL":
            return {"state": "MANUAL", "resolved_date": session["nfl_v1_date"]}
        session["nfl_active_slate_mode"] = "AUTO"
        session["nfl_v1_date"] = date(2026, 10, 18)
        return {"state": "FOUND", "resolved_date": session["nfl_v1_date"]}
    @contextmanager
    def bridge(session):
        events.append(("bridge-enter", session.get("nfl_v1_date")))
        try:
            yield
        finally:
            events.append(("bridge-exit", session.get("nfl_v1_date")))
    runtime.prepare_nfl_active_slate = prepare
    runtime.install_nfl_date_input_bridge = bridge
    monkeypatch.setitem(sys.modules, "nfl_active_slate_runtime_v1", runtime)

    sys.modules.pop("streamlit_memory_lazy_router_api2_nfl_active_slate_v1", None)
    module = importlib.import_module("streamlit_memory_lazy_router_api2_nfl_active_slate_v1")
    return module, st, events


def test_nfl_route_prepares_slate_before_prior_render_and_bridges(monkeypatch):
    module, st, events = _load_router(monkeypatch, sport="nfl", market="passing-yards")
    assert module.render_app() == "prior-render"
    assert events[0] == ("prepare", "nfl")
    assert events[1] == ("bridge-enter", date(2026, 10, 18))
    assert events[2] == ("render", date(2026, 10, 18))
    assert events[3] == ("bridge-exit", date(2026, 10, 18))


def test_nfl_market_switch_keeps_manual_state(monkeypatch):
    module, st, events = _load_router(monkeypatch, sport="nfl", market="game-total", manual=True)
    module.render_app()
    assert st.session_state["nfl_active_slate_mode"] == "MANUAL"
    assert st.session_state["nfl_v1_date"] == date(2026, 9, 20)
    assert events[2] == ("render", date(2026, 9, 20))


def test_non_nfl_route_delegates_without_prepare_or_bridge(monkeypatch):
    module, _st, events = _load_router(monkeypatch, sport="cfb", market="game-total")
    assert module.render_app() == "prior-render"
    assert events == [("render", None)]


def test_app_activates_exact_api2_terminal_successor():
    source = Path("app.py").read_text(encoding="utf-8")
    active = source.split("_LEGACY_ROUTER_IMPORT_V4 =", 1)[1].split("_legacy_router_import_count", 1)[0]
    assert "streamlit_memory_lazy_router_api2_nfl_active_slate_v1" in active
    assert "streamlit_memory_lazy_router_monster_cfb_market_completeness_r1" not in active
    assert source.count("_legacy_router_import_count") >= 1


def test_router_declares_current_monster_parent_and_model_firewalls():
    source = Path("streamlit_memory_lazy_router_api2_nfl_active_slate_v1.py").read_text(encoding="utf-8")
    assert 'FROZEN_PARENT = "streamlit_memory_lazy_router_monster_cfb_market_completeness_r1"' in source
    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
