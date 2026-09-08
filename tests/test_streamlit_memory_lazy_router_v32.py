"""Regression checks for additive College Football Router V32."""
from __future__ import annotations

import types

import streamlit_memory_lazy_router_v32 as router


def test_v32_preserves_parent_and_cfb_page_set():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v31"
    assert router.CFB_MARKETS == ("Moneyline", "Over/Under", "Game Total")
    assert router.OVER_UNDER_MARKET == "Over/Under"


def test_over_under_advances_only_to_step8_hub(monkeypatch):
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

    router._render_nfl_or_cfb_v32("Over/Under")

    assert seen["module"] == "cfb_over_under_hub_v2"
    assert seen["market"] == "Over/Under"
    assert seen["args"] == ("S", "I", "L", "H")


def test_moneyline_and_game_total_delegate_to_frozen_v31(monkeypatch):
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

    router._render_nfl_or_cfb_v32("Moneyline")
    router._render_nfl_or_cfb_v32("Game Total")

    assert seen == ["Moneyline", "Game Total"]


def test_non_cfb_delegates_to_frozen_v31(monkeypatch):
    seen = []
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )

    router._render_nfl_or_cfb_v32("Over/Under")
    assert seen == ["Over/Under"]


def test_render_app_temporarily_patches_v31_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v31
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v31

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)

    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v32
    assert router.prior._render_nfl_or_cfb_v31 is original
