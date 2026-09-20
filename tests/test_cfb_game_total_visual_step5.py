from __future__ import annotations

import cfb_game_total_clean_page_v28 as page
import streamlit_memory_lazy_router_v173 as router


def test_step5_polish_is_css_only_and_covers_green_surfaces() -> None:
    css = page.STEP5_SYSTEM_POLISH_CSS
    for selector in (
        ".gt225-hero",
        ".gt226-wrap",
        ".gt227-section",
        ".gt226-card",
        ".gt227-card",
        ".gt160-masthead",
    ):
        assert selector in css
    assert "transition:" in css
    assert ":focus-within" in css
    assert "@media(max-width:760px)" in css
    assert "@media(max-width:560px)" in css
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v27"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_step5_router_activates_v28_only_for_game_total() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v28"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v172"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
