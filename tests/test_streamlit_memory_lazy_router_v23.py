"""Regression checks for additive College Football Router V23."""

import types

import streamlit_memory_lazy_router_v23 as r


def test_sport_selector_adds_college_football(monkeypatch):
    seen = {}

    def fake_selectbox(label, options, *args, **kwargs):
        seen["label"] = label
        seen["options"] = list(options)
        return "College Football"

    monkeypatch.setattr(r, "_ORIGINAL_SELECTBOX", fake_selectbox)
    out = r._selectbox_v23("🏟️ Sport", ["MLB", "WNBA", "NFL"], key="ks_sport_touch")

    assert out == "College Football"
    assert seen["options"] == ["MLB", "WNBA", "NFL", "College Football"]


def test_cfb_market_selector_has_exact_three_pages(monkeypatch):
    seen = {}
    monkeypatch.setattr(r.st, "session_state", {"ks_sport_touch": "College Football"})

    def fake_selectbox(label, options, *args, **kwargs):
        seen["label"] = label
        seen["options"] = list(options)
        seen["key"] = kwargs.get("key")
        return "Moneyline"

    monkeypatch.setattr(r, "_ORIGINAL_SELECTBOX", fake_selectbox)
    out = r._selectbox_v23("🎯 NFL Market", ["Slate", "Moneyline"], key="ks_nfl_market_touch")

    assert out == "Moneyline"
    assert seen["label"] == "🎯 CFB Market"
    assert seen["options"] == ["Moneyline", "Over/Under", "Game Total"]
    assert seen["key"] == "ks_cfb_market_touch"


def test_cfb_dispatch_loads_only_cfb_hub(monkeypatch):
    seen = {}
    monkeypatch.setattr(r.st, "session_state", {"ks_sport_touch": "College Football"})

    def render_cfb_hub(market, section_header, status_info, team_logo, h):
        seen["market"] = market
        seen["args"] = (section_header, status_info, team_logo, h)

    module = types.SimpleNamespace(render_cfb_hub=render_cfb_hub)
    monkeypatch.setattr(
        r.root,
        "_import",
        lambda name: (seen.setdefault("module", name), module)[1],
    )

    r._render_nfl_or_cfb_v23("Over/Under")

    assert seen["module"] == "cfb_hub_v1"
    assert seen["market"] == "Over/Under"


def test_real_nfl_still_delegates_to_frozen_nfl_route(monkeypatch):
    seen = []
    monkeypatch.setattr(r.st, "session_state", {"ks_sport_touch": "NFL"})
    monkeypatch.setattr(r, "_ORIGINAL_RENDER_NFL", lambda market: seen.append(market))

    r._render_nfl_or_cfb_v23("Moneyline")

    assert seen == ["Moneyline"]


def test_render_app_temporarily_extends_root_and_restores(monkeypatch):
    original_selectbox = r.root.st.selectbox
    original_nfl = r.root._render_nfl
    original_prefixes = r.root._ROUTE_MODULE_PREFIXES
    seen = {}

    def delegated_render():
        seen["selectbox"] = r.root.st.selectbox
        seen["nfl"] = r.root._render_nfl
        seen["prefixes"] = r.root._ROUTE_MODULE_PREFIXES

    monkeypatch.setattr(r.prior, "render_app", delegated_render)
    r.render_app()

    assert seen["selectbox"] is r._selectbox_v23
    assert seen["nfl"] is r._render_nfl_or_cfb_v23
    assert "cfb_" in seen["prefixes"]
    assert r.root.st.selectbox is original_selectbox
    assert r.root._render_nfl is original_nfl
    assert r.root._ROUTE_MODULE_PREFIXES == original_prefixes


def test_existing_frozen_router_remains_v22():
    assert r.FROZEN_ROUTER == "streamlit_memory_lazy_router_v22"
