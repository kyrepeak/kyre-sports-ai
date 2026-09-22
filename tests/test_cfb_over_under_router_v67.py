"""Regression tests for CFB O/U Router V67."""
from __future__ import annotations

import streamlit_memory_lazy_router_v67 as router


def test_router_v67_is_additive_over_v66():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v66"
    assert router.OVER_UNDER_MARKET == "Over/Under"
    assert router._FROZEN_RENDER_NFL_OR_CFB is router.prior._render_nfl_or_cfb_v66


def test_router_v67_routes_only_cfb_over_under_to_v27(monkeypatch):
    calls = []

    class Page:
        def render_cfb_hub(self, market, *args):
            calls.append(("v27", market))

    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", router.CFB_SPORT_LABEL)
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: Page() if name == "cfb_over_under_clean_page_v27" else None,
    )
    router._render_nfl_or_cfb_v67("Over/Under")
    assert calls == [("v27", "Over/Under")]


def test_router_v67_delegates_non_target_routes(monkeypatch):
    calls = []
    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", router.CFB_SPORT_LABEL)
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda market: calls.append(market))
    router._render_nfl_or_cfb_v67("Moneyline")
    assert calls == ["Moneyline"]


def test_router_v67_contains_no_model_or_market_reimplementation():
    source = __import__("inspect").getsource(router)
    assert "analyze_game(" not in source
    assert "attach_market_lines(" not in source
    assert "build_market_intelligence(" not in source
    assert "build_history_engine(" not in source


def test_render_app_patches_v66_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v66
    seen = {}
    monkeypatch.setattr(
        router.prior,
        "render_app",
        lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v66}),
    )
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v67
    assert router.prior._render_nfl_or_cfb_v66 is original
