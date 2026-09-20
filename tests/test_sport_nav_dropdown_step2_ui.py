from __future__ import annotations

import cfb_hub_v1 as cfb
import cfb_game_total_clean_page_v32 as page
import streamlit_memory_lazy_router_v1 as base
import streamlit_memory_lazy_router_v179 as router


def test_step2_dropdown_ui_uses_only_existing_streamlit_categories() -> None:
    assert list(page.SPORT_CATEGORIES["NFL"]) == list(base.NFL_MARKETS)
    assert list(page.SPORT_CATEGORIES["CFB"]) == list(cfb.CFB_MARKETS)
    assert list(page.SPORT_CATEGORIES["MLB"]) == list(base.MLB_MARKETS)
    assert list(page.SPORT_CATEGORIES["WNBA"]) == list(base.WNBA_MARKETS)


def test_step2_dropdown_structure_and_default_state() -> None:
    html = page._sport_dropdown_nav_html()

    for code in ("NFL", "CFB", "MLB", "WNBA"):
        assert f'data-dropdown-sport="{code}"' in html
        assert f'data-dropdown="{code}"' in html
        assert f'href="?{page.SPORT_JUMP_QUERY_KEY}={code}"' in html

    assert '<details class="gt232-dropdown" data-dropdown="CFB" open>' in html
    assert '<details class="gt232-dropdown" data-dropdown="NFL">' in html
    assert '<details class="gt232-dropdown" data-dropdown="MLB">' in html
    assert '<details class="gt232-dropdown" data-dropdown="WNBA">' in html

    # Category rows are presentation-only in Step 2.
    assert "ks_jump_market" not in html
    assert "route wiring comes in Step 3" in html


def test_step2_dropdown_router_advances_without_changing_navigation_owner() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v32"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v178"
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v31"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
    assert page.MAY_MODIFY_PROJECTION is False
