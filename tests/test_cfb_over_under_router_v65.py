"""Regression tests for CFB O/U Router V65."""
from __future__ import annotations

import inspect

import streamlit_memory_lazy_router_v65 as router


def test_router_v65_is_additive_over_v64():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v64"
    assert router.OVER_UNDER_MARKET == "Over/Under"
    assert router._FROZEN_RENDER_NFL_OR_CFB is router.prior._render_nfl_or_cfb_v64


def test_router_v65_routes_only_cfb_over_under_to_v25(monkeypatch):
    calls = []

    class Page:
        def render_cfb_hub(self, market, *args):
            calls.append(("v25", market))

    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", router.CFB_SPORT_LABEL)
    monkeypatch.setattr(router.root, "_import", lambda name: Page() if name == "cfb_over_under_clean_page_v25" else None)
    router._render_nfl_or_cfb_v65("Over/Under")
    assert calls == [("v25", "Over/Under")]


def test_router_v65_delegates_non_target_routes(monkeypatch):
    calls = []
    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", router.CFB_SPORT_LABEL)
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda market: calls.append(market))
    router._render_nfl_or_cfb_v65("Moneyline")
    assert calls == ["Moneyline"]


def test_router_v65_contains_no_model_or_market_reimplementation():
    source = inspect.getsource(router)
    assert "analyze_game(" not in source
    assert "attach_market_lines(" not in source
    assert "build_market_intelligence(" not in source
    assert "project_matchup(" not in source
