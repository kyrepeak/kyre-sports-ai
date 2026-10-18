from __future__ import annotations

from datetime import date
import importlib
import sys
import types
from zoneinfo import ZoneInfo

import pandas as pd


def test_spread_manual_mode_never_calls_legacy_resolver():
    import nfl_spread_autodate_repair_v1 as spread
    selected = date(2026, 9, 20)
    session = {
        "nfl_active_slate_mode": "MANUAL",
        "nfl_manual_slate_date": selected,
        "nfl_v1_date": selected,
        "nfl_spread_v4_date_input": selected,
    }
    calls = []
    out = spread.apply_spread_autodate(
        session,
        date(2026, 10, 18),
        lambda value: calls.append(value) or {"state": "FOUND", "resolved_date": date(2026, 10, 19), "advanced": True},
    )
    assert calls == []
    assert session["nfl_spread_v4_date_input"] == selected
    assert session["nfl_v1_date"] == selected
    assert out["resolved_date"] == selected


def _load_passing(monkeypatch, selected):
    st = types.ModuleType("streamlit")
    st.session_state = {
        "nfl_active_slate_mode": "MANUAL",
        "nfl_manual_slate_date": selected,
        "nfl_passing_yards_v8_date_input": selected,
    }
    monkeypatch.setitem(sys.modules, "streamlit", st)

    auto = types.ModuleType("nfl_passing_yards_hub_v12")
    auto.nfl = types.SimpleNamespace(ET=ZoneInfo("America/New_York"))
    auto.AUTO_RESOLVED_KEY = "auto_resolved"
    auto.find_next_verified_slate = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("finder called"))
    monkeypatch.setitem(sys.modules, "nfl_passing_yards_hub_v12", auto)
    prior = types.ModuleType("nfl_passing_yards_hub_v36")
    prior.render_nfl_passing_yards_hub = lambda: None
    monkeypatch.setitem(sys.modules, "nfl_passing_yards_hub_v36", prior)
    ctl = types.ModuleType("nfl_passing_yards_slate_controller_v1")
    ctl.is_empty_slate_notice = lambda *_: False
    ctl.resolve_next_verified_slate_date = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("resolver called"))
    monkeypatch.setitem(sys.modules, "nfl_passing_yards_slate_controller_v1", ctl)
    sys.modules.pop("nfl_passing_yards_hub_v37", None)
    return importlib.import_module("nfl_passing_yards_hub_v37"), st


def test_passing_manual_mode_never_calls_smart_slate_resolver(monkeypatch):
    selected = date(2026, 9, 20)
    module, st = _load_passing(monkeypatch, selected)
    out = module._prime_smart_slate()
    assert out["state"] == "MANUAL"
    assert out["resolved_date"] == selected
    assert st.session_state[module.V8_DATE_INPUT_KEY] == selected


def _load_receiving(monkeypatch, selected):
    st = types.ModuleType("streamlit")
    st.session_state = {
        "nfl_active_slate_mode": "MANUAL",
        "nfl_manual_slate_date": selected,
        "nfl_receiving_yards_v1_date_input": selected,
    }
    monkeypatch.setitem(sys.modules, "streamlit", st)
    prior = types.ModuleType("nfl_receiving_yards_hub_v10")
    prior.render_nfl_receiving_yards_hub = lambda: None
    monkeypatch.setitem(sys.modules, "nfl_receiving_yards_hub_v10", prior)
    base = types.ModuleType("nfl_hub_v1")
    base.ET = ZoneInfo("America/New_York")
    monkeypatch.setitem(sys.modules, "nfl_hub_v1", base)
    auto = types.ModuleType("nfl_passing_yards_hub_v12")
    auto.find_next_verified_slate = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("finder called"))
    monkeypatch.setitem(sys.modules, "nfl_passing_yards_hub_v12", auto)
    ctl = types.ModuleType("nfl_receiving_yards_slate_controller_v1")
    ctl.is_empty_slate_notice = lambda *_: False
    ctl.resolve_next_verified_slate_date = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("resolver called"))
    monkeypatch.setitem(sys.modules, "nfl_receiving_yards_slate_controller_v1", ctl)
    sys.modules.pop("nfl_receiving_yards_hub_v11", None)
    return importlib.import_module("nfl_receiving_yards_hub_v11"), st


def test_receiving_manual_mode_never_calls_smart_slate_resolver(monkeypatch):
    selected = date(2026, 9, 20)
    module, st = _load_receiving(monkeypatch, selected)
    out = module._prime_smart_slate()
    assert out["state"] == "MANUAL"
    assert out["resolved_date"] == selected
    assert st.session_state[module.DATE_INPUT_KEY] == selected


def _load_game_totals(monkeypatch, selected):
    st = types.ModuleType("streamlit")
    st.session_state = {
        "nfl_active_slate_mode": "MANUAL",
        "nfl_manual_slate_date": selected,
        "nfl_v1_date": selected,
    }
    monkeypatch.setitem(sys.modules, "streamlit", st)

    def forbidden_loader(_day):
        raise AssertionError("game totals loader called")

    foundation = types.SimpleNamespace(load_nfl_slate=forbidden_loader)
    v2 = types.SimpleNamespace(foundation=foundation)
    v3 = types.SimpleNamespace(v2=v2)
    v4 = types.SimpleNamespace(v3=v3)
    v5 = types.SimpleNamespace(v4=v4)
    v6 = types.SimpleNamespace(v5=v5)
    v7 = types.SimpleNamespace(v6=v6)
    v8_obj = types.SimpleNamespace(v7=v7)
    v8_mod = types.ModuleType("nfl_game_totals_hub_v8")
    v8_mod.v7 = v7
    monkeypatch.setitem(sys.modules, "nfl_game_totals_hub_v8", v8_mod)

    router = types.ModuleType("sports_api.nfl_data_router_v1")
    router.clear_router_caches = lambda: None
    monkeypatch.setitem(sys.modules, "sports_api.nfl_data_router_v1", router)
    nav = types.ModuleType("sports_api.nfl_game_totals_mobile_navigation_v1")
    nav.find_next_game_day = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("next-day finder called"))
    monkeypatch.setitem(sys.modules, "sports_api.nfl_game_totals_mobile_navigation_v1", nav)
    sys.modules.pop("nfl_game_totals_hub_v8_1", None)
    return importlib.import_module("nfl_game_totals_hub_v8_1"), st


def test_game_totals_manual_mode_skips_empty_today_auto_advance(monkeypatch):
    selected = date(2026, 10, 18)
    module, st = _load_game_totals(monkeypatch, selected)
    out = module._auto_surface_next_slate(selected, selected)
    assert out == selected
    assert st.session_state["nfl_v1_date"] == selected
    assert module._WIDGET_DATE_KEY not in st.session_state
