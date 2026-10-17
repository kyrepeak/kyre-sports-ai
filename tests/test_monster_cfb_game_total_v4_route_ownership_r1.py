from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

MODULE = "streamlit_memory_lazy_router_monster_cfb_v4_route_ownership_r1"


def _load(monkeypatch, *, session=None, query=None):
    calls: list[str] = []
    fake_st = types.SimpleNamespace(
        session_state=dict(session or {}),
        query_params=dict(query or {}),
    )
    fake_v4 = types.ModuleType("streamlit_memory_lazy_router_universal_nav_v4")
    fake_v4.record_bootstrap_import_ms = lambda value: calls.append(f"bootstrap:{value}")
    fake_v4.render_app = lambda: calls.append("v4") or "v4"
    fake_cfb = types.ModuleType("streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1")
    fake_cfb.render_app = lambda: calls.append("cfb") or "cfb"

    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    monkeypatch.setitem(sys.modules, "streamlit_memory_lazy_router_universal_nav_v4", fake_v4)
    monkeypatch.setitem(sys.modules, "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1", fake_cfb)
    sys.modules.pop(MODULE, None)
    module = importlib.import_module(MODULE)
    return module, calls


def test_canonical_cfb_game_total_bypasses_v4(monkeypatch):
    module, calls = _load(
        monkeypatch,
        session={"ks_universal_sport": "cfb", "ks_universal_market": "game-total"},
    )
    assert module.render_app() == "cfb"
    assert calls == ["cfb"]


def test_cold_deep_link_cfb_game_total_bypasses_v4(monkeypatch):
    module, calls = _load(
        monkeypatch,
        query={"sport": "cfb", "market": "game-total", "ks_sport": "College Football", "ks_cfb_market": "Game Total"},
    )
    assert module.render_app() == "cfb"
    assert calls == ["cfb"]


def test_non_cfb_route_stays_on_v4(monkeypatch):
    module, calls = _load(
        monkeypatch,
        session={"ks_universal_sport": "nfl", "ks_universal_market": "spread"},
    )
    assert module.render_app() == "v4"
    assert calls == ["v4"]


def test_app_activates_monster_gate_without_replacing_v4_module():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_monster_cfb_v4_route_ownership_r1" in source
    assert "import streamlit_memory_lazy_router_universal_nav_v4 as _router_v4" in source
