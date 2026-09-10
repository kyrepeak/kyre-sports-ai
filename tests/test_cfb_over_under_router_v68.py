"""Regression tests for CFB O/U Router V68."""
from __future__ import annotations

import inspect

import streamlit_memory_lazy_router_v68 as router


def test_router_v68_is_additive_over_v67():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v67"
    assert router.OVER_UNDER_MARKET == "Over/Under"
    assert router._FROZEN_RENDER_NFL_OR_CFB is router.prior._render_nfl_or_cfb_v67


def test_router_v68_routes_only_cfb_over_under_to_v28(monkeypatch):
    calls = []

    class Page:
        def render_cfb_hub(self, market, *args):
            calls.append(("v28", market))

    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", router.CFB_SPORT_LABEL)
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: Page() if name == "cfb_over_under_clean_page_v28" else None,
    )
    router._render_nfl_or_cfb_v68("Over/Under")
    assert calls == [("v28", "Over/Under")]


def test_router_v68_delegates_non_target_routes(monkeypatch):
    calls = []
    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", router.CFB_SPORT_LABEL)
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda market: calls.append(market))
    router._render_nfl_or_cfb_v68("Moneyline")
    assert calls == ["Moneyline"]


def test_router_v68_delegates_non_cfb_over_under_routes(monkeypatch):
    calls = []
    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", "NFL")
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda market: calls.append(market))
    router._render_nfl_or_cfb_v68("Over/Under")
    assert calls == ["Over/Under"]


def test_router_v68_contains_no_model_or_market_reimplementation():
    source = inspect.getsource(router)
    for token in (
        "analyze_game(",
        "attach_market_lines(",
        "build_market_intelligence(",
        "build_history_engine(",
        "build_form_strength_engine(",
    ):
        assert token not in source


def test_render_app_patches_v67_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v67
    seen = {}
    monkeypatch.setattr(
        router.prior,
        "render_app",
        lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v67}),
    )
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v68
    assert router.prior._render_nfl_or_cfb_v67 is original
