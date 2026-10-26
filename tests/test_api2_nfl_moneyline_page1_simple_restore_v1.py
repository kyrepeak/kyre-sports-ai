from __future__ import annotations

import inspect

import nfl_moneyline_hub_v20 as page


FORBIDDEN_PAGE1_MARKERS = (
    "TEAM SNAPSHOT",
    "EVIDENCE & GUARDRAILS",
    "QUICK FACTS",
    "KEY MATCHUP FACTORS",
    "ANALYSIS / EVIDENCE",
    "MARKET INTELLIGENCE",
)


def _game() -> dict:
    return {
        "game_id": "DAL@PHI",
        "away_team": "Dallas Cowboys",
        "away_abbr": "DAL",
        "home_team": "Philadelphia Eagles",
        "home_abbr": "PHI",
        "tip_et": "8:20 PM ET",
        "venue": "Lincoln Financial Field",
        "broadcast": "NBC",
    }


def _final() -> dict:
    return {
        "state": "QUALIFIED",
        "leader_side": "home",
        "away_grade": {"grade": "NO PLAY"},
        "home_grade": {"grade": "QUALIFIED"},
    }


def _edges() -> dict:
    return {
        "away": {
            "model_p": 0.438,
            "best_price": 155,
            "best_book": "FanDuel",
            "edge": -0.014,
        },
        "home": {
            "model_p": 0.562,
            "best_price": -142,
            "best_book": "FanDuel",
            "edge": 0.037,
        },
    }


def test_page1_simple_card_contains_only_quick_decision_contract():
    html = page._simple_matchup_html(_game(), _final(), _edges(), {}, {}, {}, {})
    for marker in (
        "GAME TIME / VENUE",
        "MODEL PICK / PROBABILITY",
        "BEST ML",
        "EDGE / CONFIDENCE",
        "PLAY",
        "VIEW FULL ANALYSIS",
    ):
        assert marker in html
    assert "Philadelphia Eagles" in html
    assert "56.2%" in html
    assert "-142" in html
    assert "FanDuel" in html
    for marker in FORBIDDEN_PAGE1_MARKERS:
        assert marker not in html.upper()


def test_page1_maps_frozen_final_state_to_display_action_only():
    assert page._display_action("QUALIFIED") == "PLAY"
    assert page._display_action("LEAN / WATCH") == "LEAN"
    assert page._display_action("HIGH UNCERTAINTY") == "PASS"
    assert page._display_action("NO PLAY") == "PASS"
    assert page._display_action("GATED") == "PASS"


def test_page1_owns_a_dedicated_renderer_and_suppresses_v19_diagnostics():
    source = inspect.getsource(page._page1)
    assert "_simple_matchup_html" in source
    assert "prior._diagnostics" in source
    assert "original(game" not in source


def test_page2_route_remains_separate_from_page1_renderer():
    source = inspect.getsource(page._page2)
    assert "_simple_matchup_html" not in source
    assert "page2_api.build_page2_context" in source
    assert "war_room.render_context(context)" in source


def test_model_and_sportsbook_firewalls_remain_frozen():
    assert page.PRESENTATION_ONLY is True
    assert page.DISPLAY_ONLY is True
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.MAY_MODIFY_MARKET_MATH is False
    assert page.SPORTSBOOK_MODEL_INFLUENCE == 0.0
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.STAKE_SIZING_ENABLED is False
