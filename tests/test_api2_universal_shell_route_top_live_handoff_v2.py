from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
V4_PATH = ROOT / "streamlit_memory_lazy_router_universal_nav_v4.py"


class _RerunSignal(BaseException):
    pass


def _load_v4(monkeypatch, *, returned_intent):
    events: list[object] = []

    st = types.ModuleType("streamlit")
    st.session_state = {"ks_universal_sport": "mlb", "ks_universal_market": "slate"}
    st.query_params = {"sport": "mlb", "market": "slate"}

    def rerun():
        events.append("rerun")
        raise _RerunSignal()

    st.rerun = rerun

    stable_ui = types.ModuleType("universal_sports_nav_ui_v1")

    def returned_renderer(_state):
        events.append("pill-return")
        return returned_intent

    stable_ui.render_universal_nav = returned_renderer

    v2 = types.ModuleType("streamlit_memory_lazy_router_universal_nav_v2")
    v2.nav_ui = types.SimpleNamespace(render_universal_nav=lambda _state: None)

    def prepare(intent, session, query):
        events.append(("prepare", getattr(intent, "sport_id", None), getattr(intent, "market_id", None)))
        assert session is st.session_state
        assert query is st.query_params
        return types.SimpleNamespace(sport_id="nfl", market_id="slate")

    def mask(state):
        events.append(("mask", state.sport_id, state.market_id))

    v2._prepare_pending_handoff = prepare
    v2._render_handoff_mask = mask

    v3 = types.ModuleType("streamlit_memory_lazy_router_universal_nav_v3")
    v3.record_bootstrap_import_ms = lambda value: events.append(("bootstrap", value))

    def v3_render_app():
        events.append("v3-delegate")
        return v2.nav_ui.render_universal_nav(types.SimpleNamespace(sport_id="mlb", market_id="slate"))

    v3.render_app = v3_render_app

    for name, module in {
        "streamlit": st,
        "streamlit_memory_lazy_router_universal_nav_v2": v2,
        "streamlit_memory_lazy_router_universal_nav_v3": v3,
        "universal_sports_nav_ui_v1": stable_ui,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location("_api2_router_v4_test", V4_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, v2, events


def test_entrypoint_boots_v4_and_forces_r3_runtime_refresh():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_nav_v4" in app
    assert "API2_UNIVERSAL_SHELL_ROUTE_TOP_V1_RUNTIME_REFRESH_2026_10_17_R3" in app
    assert 'sys.modules["streamlit_memory_lazy_router_universal_nav_v2"] = _router_v4' in app


def test_v4_uses_immediate_return_value_to_commit_nfl_before_legacy_delegate(monkeypatch):
    intent = types.SimpleNamespace(sport_id="nfl", market_id=None, source="tap")
    module, v2, events = _load_v4(monkeypatch, returned_intent=intent)
    original = v2.nav_ui.render_universal_nav

    with pytest.raises(_RerunSignal):
        module.render_app()

    assert events == [
        "v3-delegate",
        "pill-return",
        ("prepare", "nfl", None),
        ("mask", "nfl", "slate"),
        "rerun",
    ]
    assert v2.nav_ui.render_universal_nav is original


def test_v4_no_tap_preserves_v3_delegate_without_extra_rerun(monkeypatch):
    module, v2, events = _load_v4(monkeypatch, returned_intent=None)
    original = v2.nav_ui.render_universal_nav

    result = module.render_app()

    assert result is None
    assert events == ["v3-delegate", "pill-return"]
    assert v2.nav_ui.render_universal_nav is original
