from __future__ import annotations

import cfb_game_total_clean_page_v31 as page
import streamlit_memory_lazy_router_v178 as router


def test_step3_responsive_polish_contract() -> None:
    css = page.SPORT_NAV_STEP3_CSS

    assert "@media(max-width:760px)" in css
    assert "@media(max-width:560px)" in css
    assert "@media(max-width:360px)" in css

    # Tablet/mobile becomes roomy 2x2.
    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in css
    # Very narrow phones get a safe one-column fallback.
    assert "grid-template-columns:1fr!important" in css
    # Comfortable tappable card heights are explicitly protected.
    assert "min-height:112px!important" in css
    assert "touch-action:manipulation" in css
    assert "overflow-wrap:anywhere" in css

    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v30"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_step3_router_preserves_functional_navigation_owner() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v31"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v177"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
