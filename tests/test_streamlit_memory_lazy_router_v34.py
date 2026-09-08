"""Regression checks for additive College Football Router V34."""
from __future__ import annotations

import types

import streamlit_memory_lazy_router_v34 as router


def test_v34_preserves_parent_and_cfb_page_set():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v33"
    assert router.CFB_MARKETS == ("Moneyline", "Over/Under", "Game Total")
    assert router.GAME_TOTAL_MARKET == "Game Total"


def test_game_total_advances_only_to_step10_hub(monkeypatch):
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

    router._render_nfl_or_cfb_v34("Game Total")

    assert seen["module"] == "cfb_game_total_hub_v1"
    assert seen["market"] == "Game Total"
    assert seen["args"] == ("S", "I", "L", "H")


def test_moneyline_and_over_under_delegate_to_frozen_v33(monkeypatch):
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

    router._render_nfl_or_cfb_v34("Moneyline")
    router._render_nfl_or_cfb_v34("Over/Under")

    assert seen == ["Moneyline", "Over/Under"]


def test_non_cfb_delegates_to_frozen_v33(monkeypatch):
    seen = []
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )

    router._render_nfl_or_cfb_v34("Game Total")
    assert seen == ["Game Total"]


def test_render_app_temporarily_patches_v33_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v33
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v33

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)

    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v34
    assert router.prior._render_nfl_or_cfb_v33 is original
