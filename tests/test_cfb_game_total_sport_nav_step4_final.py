from __future__ import annotations

from pathlib import Path

import cfb_game_total_clean_page_v30 as functional_page
import cfb_game_total_clean_page_v31 as responsive_page
import streamlit_memory_lazy_router_v178 as router


ROOT = Path(__file__).resolve().parents[1]


def test_step4_final_sport_nav_chain_is_active_and_frozen() -> None:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from streamlit_memory_lazy_router_v183 import record_bootstrap_import_ms, render_app" in app_text
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v31"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v177"
    assert responsive_page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v30"
    assert functional_page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v29"

    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert responsive_page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert functional_page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    assert router.MAY_MODIFY_PROJECTION is False
    assert responsive_page.MAY_MODIFY_PROJECTION is False
    assert functional_page.MAY_MODIFY_PROJECTION is False


def test_step4_final_sport_links_remain_complete() -> None:
    html = functional_page._sport_nav_html()

    for code in ("NFL", "CFB", "MLB", "WNBA"):
        assert f'data-sport="{code}"' in html
        assert f'href="?{functional_page.SPORT_JUMP_QUERY_KEY}={code}"' in html

    assert html.count('target="_self"') == 4
    assert 'data-sport="CFB" data-selected="true"' in html
    assert 'aria-current="page"' in html


def test_step4_final_responsive_contract_remains_complete() -> None:
    css = responsive_page.SPORT_NAV_STEP3_CSS

    assert "@media(max-width:760px)" in css
    assert "@media(max-width:560px)" in css
    assert "@media(max-width:360px)" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in css
    assert "grid-template-columns:1fr!important" in css
    assert "min-height:112px!important" in css
    assert "touch-action:manipulation" in css
    assert "overflow-wrap:anywhere" in css
