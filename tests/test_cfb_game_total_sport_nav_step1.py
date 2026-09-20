from __future__ import annotations

import cfb_game_total_clean_page_v29 as page
import streamlit_memory_lazy_router_v176 as router


def test_sport_nav_step1_shell_contract() -> None:
    html = page._sport_nav_shell_html()

    assert 'data-testid="gt229-sport-nav-shell"' in html
    assert page.SPORT_NAV_STEP1_MARKER in html
    assert "Jump to a" in html
    assert "Sport Page" in html

    for sport in ("NFL", "CFB", "MLB", "WNBA"):
        assert f'data-sport="{sport}"' in html

    assert 'data-sport="CFB" data-selected="true"' in html
    assert "Pro Football" in html
    assert "College Football" in html
    assert "Baseball" in html
    assert "Women's Basketball" in html

    # Step 1 is shell-only. Real actions are intentionally deferred to Step 2.
    assert "<button" not in html
    assert "href=" not in html

    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v28"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_sport_nav_step1_router_activates_v29_and_preserves_escape_owner() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v29"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v175"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
