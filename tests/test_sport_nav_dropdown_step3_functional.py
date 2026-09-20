from __future__ import annotations

from urllib.parse import quote_plus

import cfb_hub_v1 as cfb
import cfb_game_total_clean_page_v33 as page
import streamlit_memory_lazy_router_v1 as base
import streamlit_memory_lazy_router_v180 as router


EXPECTED = {
    "NFL": list(base.NFL_MARKETS),
    "CFB": list(cfb.CFB_MARKETS),
    "MLB": list(base.MLB_MARKETS),
    "WNBA": list(base.WNBA_MARKETS),
}


def test_step3_every_dropdown_category_is_a_real_same_app_link() -> None:
    html = page._sport_dropdown_nav_html()

    for sport, markets in EXPECTED.items():
        for market in markets:
            href = (
                f'?{page.SPORT_JUMP_QUERY_KEY}={quote_plus(sport)}'
                f'&{page.MARKET_JUMP_QUERY_KEY}={quote_plus(market)}'
            )
            assert f'href="{href}"' in html
            assert f'data-category="{market.replace("&", "&amp;")}"' in html

    assert html.count('target="_self"') == 4 + sum(len(v) for v in EXPECTED.values())


def test_step3_category_handoff_uses_existing_session_keys(monkeypatch) -> None:
    state: dict[str, str] = {}
    monkeypatch.setattr(router.st, "session_state", state)

    cases = {
        "NFL": ("Game Total", "NFL", "ks_nfl_market_touch"),
        "CFB": ("Over/Under", router.CFB_SPORT_LABEL, "ks_cfb_market_touch"),
        "MLB": ("Pitcher Strikeouts", "MLB", "ks_mlb_market_touch"),
        "WNBA": ("Rebounds + Assists", "WNBA", "ks_wnba_market_touch"),
    }

    for code, (market, sport_value, market_key) in cases.items():
        state.clear()
        assert router._apply_category_jump(code, market) is True
        assert state["ks_sport_touch"] == sport_value
        assert state[market_key] == market


def test_step3_rejects_nonexistent_market_values(monkeypatch) -> None:
    state: dict[str, str] = {}
    monkeypatch.setattr(router.st, "session_state", state)

    assert router._apply_category_jump("NFL", "Fake Market") is False
    assert router._apply_category_jump("CFB", "Spread") is False
    assert router._apply_category_jump("NOPE", "Game Total") is False
    assert state == {}


def test_step3_router_advances_without_touching_projection_math() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v33"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v179"
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v32"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
    assert page.MAY_MODIFY_PROJECTION is False
