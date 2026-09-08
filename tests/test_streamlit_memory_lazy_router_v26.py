"""Regression checks for additive College Football Router V26."""
from __future__ import annotations

import types

import streamlit_memory_lazy_router_v26 as router


def test_v26_preserves_cfb_page_set_and_parent():
    assert router.CFB_MARKETS == ("Moneyline", "Over/Under", "Game Total")
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v25"
    assert router.MONEYLINE_MARKET == "Moneyline"


def test_moneyline_advances_only_to_step4_hub(monkeypatch):
    seen = {}
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "College Football"})

    def render_cfb_hub(market, section_header, status_info, team_logo, h):
        seen["market"] = market
        seen["args"] = (section_header, status_info, team_logo, h)

    module = types.SimpleNamespace(render_cfb_hub=render_cfb_hub)

    def fake_import(name):
        seen["module"] = name
        return module

    monkeypatch.setattr(router.root, "_import", fake_import)
    monkeypatch.setattr(router.root, "section_header", "SECTION")
    monkeypatch.setattr(router.root, "status_info", "STATUS")
    monkeypatch.setattr(router.root, "team_logo", "LOGO")
    monkeypatch.setattr(router.root, "h", "ESCAPE")

    router._render_nfl_or_cfb_v26("Moneyline")

    assert seen["module"] == "cfb_moneyline_hub_v1"
    assert seen["market"] == "Moneyline"
    assert seen["args"] == ("SECTION", "STATUS", "LOGO", "ESCAPE")


def test_over_under_and_game_total_remain_on_frozen_v25(monkeypatch):
    seen = []
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "College Football"})
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )

    router._render_nfl_or_cfb_v26("Over/Under")
    router._render_nfl_or_cfb_v26("Game Total")

    assert seen == ["Over/Under", "Game Total"]


def test_non_cfb_routes_delegate_to_frozen_v25(monkeypatch):
    seen = []
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )

    router._render_nfl_or_cfb_v26("Moneyline")

    assert seen == ["Moneyline"]


def test_render_app_temporarily_patches_v25_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v25
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v25

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)

    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v26
    assert router.prior._render_nfl_or_cfb_v25 is original
