from __future__ import annotations

import cfb_game_total_clean_page_v25 as page
import streamlit_memory_lazy_router_v170 as router


def test_step2_matchup_hero_contract() -> None:
    identity = {
        "away": {"team": "Purdue", "conference": "big-ten", "logo": "https://example.com/purdue.png"},
        "home": {"team": "UCLA", "conference": "big-ten", "logo": "https://example.com/ucla.png"},
        "kickoff": "11:00 PM ET",
        "venue": "Rose Bowl",
    }
    away = {"team": "Purdue", "record": "1-1"}
    home = {"team": "UCLA", "record": "2-0"}
    game = {
        "date": "2026-09-19",
        "venue_location": "Pasadena, CA",
        "temperature": "73",
        "weather": "0% precipitation",
        "wind": "5 mph gusts",
    }

    html = page._matchup_header_html_v25(identity, away, home, game)

    assert 'data-testid="gt225-matchup-hero"' in html
    assert page.STEP2_MATCHUP_HERO_MARKER in html
    for expected in (
        "Purdue",
        "UCLA",
        "1-1",
        "2-0",
        "big-ten",
        "VS",
        "Rose Bowl",
        "Pasadena, CA",
        "73°",
        "0% precipitation",
        "5 mph gusts",
        "11:00 PM ET",
        "GAME TOTAL ANALYSIS",
    ):
        assert expected in html
    assert html.count('class="gt225-fact ') == 4
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_step2_router_activates_v25_only_for_game_total() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v25"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v169"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
