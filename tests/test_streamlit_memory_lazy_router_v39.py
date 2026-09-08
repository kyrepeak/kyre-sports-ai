"""Regression checks for additive College Football Router V39."""
from __future__ import annotations

import types

import streamlit_memory_lazy_router_v39 as router


def test_v39_preserves_v38_and_cfb_market_set():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v38"
    assert router.CFB_MARKETS == ("Moneyline", "Over/Under", "Game Total")
    assert router.OVER_UNDER_MARKET == "Over/Under"


def test_only_cfb_over_under_advances_to_upgrade_step3(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )

    def render_cfb_hub(market, section_header, status_info, team_logo, h):
        seen["market"] = market

    module = types.SimpleNamespace(render_cfb_hub=render_cfb_hub)

    def fake_import(name):
        seen["module"] = name
        return module

    monkeypatch.setattr(router.root, "_import", fake_import)
    router._render_nfl_or_cfb_v39("Over/Under")

    assert seen["module"] == "cfb_over_under_matchup_ui_v3"
    assert seen["market"] == "Over/Under"


def test_moneyline_and_game_total_delegate_to_frozen_v38(monkeypatch):
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

    router._render_nfl_or_cfb_v39("Moneyline")
    router._render_nfl_or_cfb_v39("Game Total")
    assert seen == ["Moneyline", "Game Total"]


def test_non_cfb_delegates_to_frozen_v38(monkeypatch):
    seen = []
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )
    router._render_nfl_or_cfb_v39("Over/Under")
    assert seen == ["Over/Under"]


def test_render_app_temporarily_patches_v38_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v38
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v38

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)
    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v39
    assert router.prior._render_nfl_or_cfb_v38 is original
