from __future__ import annotations

import cfb_game_total_clean_page_v28 as page
import streamlit_memory_lazy_router_v160 as visible_heartbeat_owner
import streamlit_memory_lazy_router_v174 as step1_router
import streamlit_memory_lazy_router_v175 as router


def _set_state(monkeypatch, *, sport: str = "", market: str = "") -> None:
    monkeypatch.setattr(
        router.st,
        "session_state",
        {
            "ks_sport_touch": sport,
            "ks_cfb_market_touch": market,
        },
    )


def test_cleanup_step3_combines_wall_suppression_and_navigation_escape(monkeypatch) -> None:
    visible_calls: list[str] = []

    def visible_heartbeat() -> None:
        visible_calls.append("visible")

    monkeypatch.setattr(
        visible_heartbeat_owner,
        "_render_production_heartbeat",
        visible_heartbeat,
    )

    assert (
        step1_router._hide_legacy_visible_heartbeat(
            visible_heartbeat_owner._render_production_heartbeat
        )
        is None
    )
    assert visible_calls == []

    _set_state(monkeypatch, sport="NFL", market=router.GAME_TOTAL_MARKET)
    nav_calls: list[str] = []
    monkeypatch.setattr(
        router,
        "_clear_game_total_route_query",
        lambda: nav_calls.append("clear"),
    )
    monkeypatch.setattr(
        router.prior,
        "render_app",
        lambda: nav_calls.append("delegate"),
    )

    router.render_app()

    assert nav_calls == ["clear", "delegate"]


def test_cleanup_step3_intentional_game_total_still_opens(monkeypatch) -> None:
    _set_state(
        monkeypatch,
        sport=router.CFB_SPORT_LABEL,
        market=router.GAME_TOTAL_MARKET,
    )

    calls: list[str] = []
    monkeypatch.setattr(router, "_step6_cert_requested", lambda: False)
    monkeypatch.setattr(
        router,
        "_render_exact_game_total_surface",
        lambda: calls.append("game-total"),
    )

    router.render_app()

    assert calls == ["game-total"]


def test_cleanup_step3_final_route_and_responsive_contract() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v174"
    assert step1_router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v173"
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v28"

    assert "DEBUG_WALL_HIDDEN" in step1_router.PAGE_CLEANUP_STEP1_MARKER
    assert "NAVIGATION_ESCAPE_ACTIVE" in router.PAGE_CLEANUP_STEP2_MARKER

    css = page.STEP5_SYSTEM_POLISH_CSS
    assert "@media(max-width:760px)" in css
    assert "@media(max-width:560px)" in css

    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
