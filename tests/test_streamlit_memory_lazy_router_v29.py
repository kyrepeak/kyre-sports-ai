"""Regression checks for additive CFB full-slate Router V29."""
from __future__ import annotations

import types

import streamlit_memory_lazy_router_v29 as router


def test_v29_preserves_parent_and_page_set():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v28"
    assert router.CFB_MARKETS == ("Moneyline", "Over/Under", "Game Total")


def test_cfb_moneyline_routes_to_full_slate_hub(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )

    def render_cfb_hub(market, section_header, status_info, team_logo, h):
        seen["market"] = market
        seen["args"] = (section_header, status_info, team_logo, h)

    module = types.SimpleNamespace(render_cfb_hub=render_cfb_hub)

    def fake_import(name):
        seen["module"] = name
        return module

    monkeypatch.setattr(router.root, "_import", fake_import)
    monkeypatch.setattr(router.root, "section_header", "S")
    monkeypatch.setattr(router.root, "status_info", "I")
    monkeypatch.setattr(router.root, "team_logo", "L")
    monkeypatch.setattr(router.root, "h", "H")

    router._render_nfl_or_cfb_v29("Moneyline")

    assert seen["module"] == "cfb_moneyline_hub_v4"
    assert seen["market"] == "Moneyline"
    assert seen["args"] == ("S", "I", "L", "H")


def test_other_cfb_markets_remain_frozen(monkeypatch):
    seen = []
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )

    router._render_nfl_or_cfb_v29("Over/Under")
    router._render_nfl_or_cfb_v29("Game Total")

    assert seen == ["Over/Under", "Game Total"]


def test_non_cfb_delegates_to_frozen_router(monkeypatch):
    seen = []
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )

    router._render_nfl_or_cfb_v29("Moneyline")

    assert seen == ["Moneyline"]


def test_render_app_temporarily_patches_v28_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v28
    seen = {}

    def fake_render():
        seen["during"] = router.prior._render_nfl_or_cfb_v28

    monkeypatch.setattr(router.prior, "render_app", fake_render)

    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v29
    assert router.prior._render_nfl_or_cfb_v28 is original
