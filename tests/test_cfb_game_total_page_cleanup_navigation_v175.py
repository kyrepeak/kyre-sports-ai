from __future__ import annotations

import streamlit_memory_lazy_router_v175 as router


def _set_state(monkeypatch, *, sport: str = "", market: str = "") -> None:
    state = {
        "ks_sport_touch": sport,
        "ks_cfb_market_touch": market,
    }
    monkeypatch.setattr(router.st, "session_state", state)


def test_cleanup_step2_detects_explicit_nfl_escape(monkeypatch) -> None:
    _set_state(monkeypatch, sport="NFL", market=router.GAME_TOTAL_MARKET)
    assert router._explicit_non_game_total_route_selected() is True


def test_cleanup_step2_detects_other_cfb_market_escape(monkeypatch) -> None:
    _set_state(monkeypatch, sport=router.CFB_SPORT_LABEL, market="Moneyline")
    assert router._explicit_non_game_total_route_selected() is True


def test_cleanup_step2_does_not_block_intentional_game_total(monkeypatch) -> None:
    _set_state(
        monkeypatch,
        sport=router.CFB_SPORT_LABEL,
        market=router.GAME_TOTAL_MARKET,
    )
    assert router._explicit_non_game_total_route_selected() is False


def test_cleanup_step2_clears_stale_query_before_delegating(monkeypatch) -> None:
    _set_state(monkeypatch, sport="NFL", market=router.GAME_TOTAL_MARKET)
    calls: list[str] = []

    monkeypatch.setattr(router, "_clear_game_total_route_query", lambda: calls.append("clear"))
    monkeypatch.setattr(router.prior, "render_app", lambda: calls.append("delegate"))

    router.render_app()

    assert calls == ["clear", "delegate"]


def test_cleanup_step2_preserves_certified_route_and_guards() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v28"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v174"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
