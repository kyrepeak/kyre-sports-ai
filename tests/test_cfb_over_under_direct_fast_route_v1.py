"""Regression tests for CFB O/U direct fast-route Step 2."""
from __future__ import annotations

from pathlib import Path
import types

import streamlit_memory_lazy_router_v73 as router


def test_fast_route_activates_only_for_cfb_over_under(monkeypatch):
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football", "ks_cfb_market_touch": "Over/Under"},
    )
    assert router._fast_route_active() is True

    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football", "ks_cfb_market_touch": "Moneyline"},
    )
    assert router._fast_route_active() is False

    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "NFL", "ks_cfb_market_touch": "Over/Under"},
    )
    assert router._fast_route_active() is False


def test_render_app_bypasses_v72_only_on_active_fast_route(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(router, "_fast_route_active", lambda: True)
    monkeypatch.setattr(router, "_render_direct_cfb_ou", lambda: seen.append("direct"))
    monkeypatch.setattr(router.prior, "render_app", lambda: seen.append("prior"))

    router.render_app()
    assert seen == ["direct"]

    seen.clear()
    monkeypatch.setattr(router, "_fast_route_active", lambda: False)
    router.render_app()
    assert seen == ["prior"]


def test_direct_renderer_uses_root_shell_and_restores_all_hooks(monkeypatch):
    original_selectbox = router.root.st.selectbox
    original_render_nfl = router.root._render_nfl
    original_prefixes = router.root._ROUTE_MODULE_PREFIXES
    seen = {}

    def fake_root_render():
        seen["selectbox"] = router.root.st.selectbox
        seen["render_nfl"] = router.root._render_nfl
        seen["prefixes"] = router.root._ROUTE_MODULE_PREFIXES

    monkeypatch.setattr(router.root, "render_app", fake_root_render)

    router._render_direct_cfb_ou()

    assert seen["selectbox"] is router._selectbox_v73
    assert seen["render_nfl"] is router._render_cfb_ou_direct
    assert "cfb_" in seen["prefixes"]
    assert router.root.st.selectbox is original_selectbox
    assert router.root._render_nfl is original_render_nfl
    assert router.root._ROUTE_MODULE_PREFIXES == original_prefixes


def test_selector_adapter_preserves_current_cfb_market_list(monkeypatch):
    calls = []

    def fake_selectbox(label, options, *args, **kwargs):
        calls.append((label, list(options), dict(kwargs)))
        if label == "🏟️ Sport":
            return "College Football"
        if label == "🎯 CFB Market":
            return "Over/Under"
        return options[0]

    monkeypatch.setattr(router, "_ORIGINAL_SELECTBOX", fake_selectbox)
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football", "ks_cfb_market_touch": "Over/Under"},
    )

    sport = router._selectbox_v73("🏟️ Sport", ["MLB", "WNBA", "NFL"], key="ks_sport_touch")
    market = router._selectbox_v73(
        "🎯 NFL Market",
        ["Moneyline", "Spread"],
        key="ks_nfl_market_touch",
    )

    assert sport == "College Football"
    assert market == "Over/Under"
    assert calls[0][1] == ["MLB", "WNBA", "NFL", "College Football"]
    assert calls[1][0] == "🎯 CFB Market"
    assert calls[1][1] == list(router.CFB_MARKETS)
    assert calls[1][2]["key"] == "ks_cfb_market_touch"


def test_direct_dispatch_targets_certified_v32_page(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football", "ks_cfb_market_touch": "Over/Under"},
    )
    module = types.SimpleNamespace(
        render_cfb_hub=lambda market, *args: seen.update({"market": market})
    )
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: (seen.update({"module": name}) or module),
    )

    router._render_cfb_ou_direct("Over/Under")

    assert seen["module"] == "cfb_over_under_clean_page_v32"
    assert seen["market"] == "Over/Under"


def test_app_entrypoint_advances_to_v73_and_retains_v72_guard():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v72 import render_app as _frozen_v72_render_app" in text
    assert "from streamlit_memory_lazy_router_v73 import render_app" in text
    assert (
        'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V73_CFB_OU_DIRECT_FAST_ROUTE_2026-09-11"'
        in text
    )
    assert "No schedule, market, team-data" in text
    assert "0.0%" in text
