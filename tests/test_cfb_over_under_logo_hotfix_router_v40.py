"""Regression checks for CFB O/U logo-hotfix wrapper and Router V40."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v3_logo_hotfix_v1 as ui
import streamlit_memory_lazy_router_v40 as router


def test_logo_wrapper_temporarily_patches_only_step1_visual_resolver(monkeypatch):
    original = ui._STEP1_UI._visuals_for_game
    seen = {}

    monkeypatch.setattr(ui.st, "caption", lambda *a, **k: None)

    def fake_render(*args, **kwargs):
        seen["during"] = ui._STEP1_UI._visuals_for_game
        return "ok"

    monkeypatch.setattr(ui.frozen_v3, "render_over_under_hub", fake_render)
    result = ui.render_over_under_hub()

    assert result == "ok"
    assert seen["during"] is ui.logo_resolver.resolve_visuals
    assert ui._STEP1_UI._visuals_for_game is original


def test_v40_preserves_v39_and_market_set():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v39"
    assert router.CFB_MARKETS == ("Moneyline", "Over/Under", "Game Total")
    assert router.OVER_UNDER_MARKET == "Over/Under"


def test_only_cfb_over_under_routes_to_logo_hotfix(monkeypatch):
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
    router._render_nfl_or_cfb_v40("Over/Under")

    assert seen["module"] == "cfb_over_under_matchup_ui_v3_logo_hotfix_v1"
    assert seen["market"] == "Over/Under"


def test_other_cfb_markets_delegate_to_frozen_v39(monkeypatch):
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

    router._render_nfl_or_cfb_v40("Moneyline")
    router._render_nfl_or_cfb_v40("Game Total")
    assert seen == ["Moneyline", "Game Total"]


def test_non_cfb_delegates_to_frozen_v39(monkeypatch):
    seen = []
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )
    router._render_nfl_or_cfb_v40("Over/Under")
    assert seen == ["Over/Under"]


def test_render_app_temporarily_patches_v39_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v39
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v39

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)
    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v40
    assert router.prior._render_nfl_or_cfb_v39 is original
