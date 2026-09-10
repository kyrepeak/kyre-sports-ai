"""Regression tests for CFB O/U Router V66."""
from __future__ import annotations

import streamlit_memory_lazy_router_v66 as router


def test_router_v66_is_additive_over_v65():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v65"
    assert router.OVER_UNDER_MARKET == "Over/Under"
    assert router._FROZEN_RENDER_NFL_OR_CFB is router.prior._render_nfl_or_cfb_v65


def test_router_v66_routes_only_cfb_over_under_to_v26(monkeypatch):
    calls = []

    class Page:
        def render_cfb_hub(self, market, *args):
            calls.append(("v26", market))

    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", router.CFB_SPORT_LABEL)
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: Page() if name == "cfb_over_under_clean_page_v26" else None,
    )
    router._render_nfl_or_cfb_v66("Over/Under")
    assert calls == [("v26", "Over/Under")]


def test_router_v66_delegates_non_target_routes(monkeypatch):
    calls = []
    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", router.CFB_SPORT_LABEL)
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda market: calls.append(market))
    router._render_nfl_or_cfb_v66("Moneyline")
    assert calls == ["Moneyline"]


def test_router_v66_contains_no_model_or_market_reimplementation():
    source = __import__("inspect").getsource(router)
    assert "analyze_game(" not in source
    assert "attach_market_lines(" not in source
    assert "build_market_intelligence(" not in source
    assert "build_environment_engine(" not in source


def test_render_app_patches_v65_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v65
    seen = {}
    monkeypatch.setattr(
        router.prior,
        "render_app",
        lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v65}),
    )
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v66
    assert router.prior._render_nfl_or_cfb_v65 is original
