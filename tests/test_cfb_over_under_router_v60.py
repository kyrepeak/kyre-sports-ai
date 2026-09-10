"""Router V60 Step 6 regression tests."""
from __future__ import annotations

import types

import streamlit_memory_lazy_router_v60 as router


def test_router_v60_routes_only_cfb_ou_to_market_intelligence_page(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )
    module = types.SimpleNamespace(
        render_cfb_hub=lambda market, *args: seen.update({"market": market})
    )
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: (seen.update({"module": name}) or module),
    )

    router._render_nfl_or_cfb_v60("Over/Under")

    assert seen["module"] == "cfb_over_under_clean_page_v20"
    assert seen["market"] == "Over/Under"


def test_router_v60_delegates_every_other_route(monkeypatch):
    seen = []
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )

    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )
    router._render_nfl_or_cfb_v60("Moneyline")

    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "NFL"},
    )
    router._render_nfl_or_cfb_v60("Over/Under")

    assert seen == ["Moneyline", "Over/Under"]


def test_router_v60_is_additive_over_certified_v59():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v59"
    assert router._FROZEN_RENDER_NFL_OR_CFB is router.prior._render_nfl_or_cfb_v59


def test_router_v60_render_app_restores_prior_hook(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v59
    seen = []

    def fake_render_app():
        seen.append(router.prior._render_nfl_or_cfb_v59)

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)
    router.render_app()

    assert seen == [router._render_nfl_or_cfb_v60]
    assert router.prior._render_nfl_or_cfb_v59 is original
