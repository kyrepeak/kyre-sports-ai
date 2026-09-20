from __future__ import annotations

import cfb_game_total_clean_page_v30 as page
import streamlit_memory_lazy_router_v177 as router


def test_step2_cards_are_real_same_app_links() -> None:
    html = page._sport_nav_html()

    for code in ("NFL", "CFB", "MLB", "WNBA"):
        assert f'data-sport="{code}"' in html
        assert f'href="?{page.SPORT_JUMP_QUERY_KEY}={code}"' in html

    assert html.count('target="_self"') == 4
    assert 'data-sport="CFB" data-selected="true"' in html
    assert 'aria-current="page"' in html
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v29"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_step2_sport_jump_uses_existing_session_contract(monkeypatch) -> None:
    state: dict[str, str] = {}
    monkeypatch.setattr(router.st, "session_state", state)

    assert router._apply_sport_jump("NFL") is True
    assert state["ks_sport_touch"] == "NFL"

    assert router._apply_sport_jump("MLB") is True
    assert state["ks_sport_touch"] == "MLB"

    assert router._apply_sport_jump("WNBA") is True
    assert state["ks_sport_touch"] == "WNBA"

    assert router._apply_sport_jump("CFB") is True
    assert state["ks_sport_touch"] == router.CFB_SPORT_LABEL
    assert state["ks_cfb_market_touch"] == router.GAME_TOTAL_MARKET

    assert router._apply_sport_jump("NOPE") is False


def test_step2_router_activates_v30_and_preserves_v176() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v30"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v176"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
