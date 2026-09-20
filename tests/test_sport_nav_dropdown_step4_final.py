from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

import cfb_hub_v1 as cfb
import cfb_game_total_clean_page_v32 as dropdown_ui
import cfb_game_total_clean_page_v33 as functional
import streamlit_memory_lazy_router_v1 as base
import streamlit_memory_lazy_router_v180 as router


ROOT = Path(__file__).resolve().parents[1]


def _expected() -> dict[str, list[str]]:
    return {
        "NFL": list(base.NFL_MARKETS),
        "CFB": list(cfb.CFB_MARKETS),
        "MLB": list(base.MLB_MARKETS),
        "WNBA": list(base.WNBA_MARKETS),
    }


def test_step4_final_dropdown_chain_is_active_and_frozen() -> None:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from streamlit_memory_lazy_router_v182 import record_bootstrap_import_ms, render_app" in app_text
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v33"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v179"
    assert functional.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v32"

    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert functional.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert dropdown_ui.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    assert router.MAY_MODIFY_PROJECTION is False
    assert functional.MAY_MODIFY_PROJECTION is False
    assert dropdown_ui.MAY_MODIFY_PROJECTION is False


def test_step4_final_dropdown_categories_and_links_are_complete() -> None:
    expected = _expected()
    html = functional._sport_dropdown_nav_html()

    for sport, markets in expected.items():
        assert list(functional.SPORT_CATEGORIES[sport]) == markets
        assert f'data-dropdown-sport="{sport}"' in html
        assert f'data-dropdown="{sport}"' in html

        for market in markets:
            href = (
                f'?{functional.SPORT_JUMP_QUERY_KEY}={quote_plus(sport)}'
                f'&{functional.MARKET_JUMP_QUERY_KEY}={quote_plus(market)}'
            )
            assert f'href="{href}"' in html

    assert '<details class="gt232-dropdown" data-dropdown="CFB" open>' in html
    assert '<details class="gt232-dropdown" data-dropdown="NFL">' in html
    assert '<details class="gt232-dropdown" data-dropdown="MLB">' in html
    assert '<details class="gt232-dropdown" data-dropdown="WNBA">' in html


def test_step4_final_responsive_dropdown_contract_remains_complete() -> None:
    css = dropdown_ui.SPORT_DROPDOWN_STEP2_CSS + functional.SPORT_DROPDOWN_STEP3_CSS

    assert "@media(max-width:760px)" in css
    assert "@media(max-width:560px)" in css
    assert "@media(max-width:360px)" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "grid-template-columns:1fr" in css
    assert "min-height:44px" in css
    assert "min-height:42px" in css


def test_step4_final_router_uses_only_existing_market_state_keys() -> None:
    assert router.SPORT_MARKET_KEYS == {
        "NFL": "ks_nfl_market_touch",
        "CFB": "ks_cfb_market_touch",
        "MLB": "ks_mlb_market_touch",
        "WNBA": "ks_wnba_market_touch",
    }

    expected = _expected()
    for sport, markets in expected.items():
        assert list(router.SPORT_MARKETS[sport]) == markets
