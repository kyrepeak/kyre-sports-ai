"""Regression checks for additive College Football Router V25."""
from __future__ import annotations

import types

import streamlit_memory_lazy_router_v25 as router


def test_v25_preserves_exact_cfb_page_set_and_parent():
    assert router.CFB_MARKETS == ("Moneyline", "Over/Under", "Game Total")
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v24"


def test_cfb_dispatch_advances_only_to_hub_v3(monkeypatch):
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

    router._render_nfl_or_cfb_v25("Over/Under")

    assert seen["module"] == "cfb_hub_v3"
    assert seen["market"] == "Over/Under"
    assert seen["args"] == ("SECTION", "STATUS", "LOGO", "ESCAPE")


def test_non_cfb_still_delegates_to_frozen_v24_dispatch(monkeypatch):
    seen = []
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda market: seen.append(market))

    router._render_nfl_or_cfb_v25("Moneyline")

    assert seen == ["Moneyline"]


def test_render_app_temporarily_patches_v24_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v24
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v24

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)

    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v25
    assert router.prior._render_nfl_or_cfb_v24 is original
