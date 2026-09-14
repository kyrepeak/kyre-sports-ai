from __future__ import annotations

import inspect

import nfl_spread_hub_v2 as page
import streamlit_memory_lazy_router_v133 as router


def _game() -> dict:
    return {
        "game_id": "401872931",
        "state": "pre",
        "season_type": "Regular Season",
        "tip_et": "8:15 PM ET",
        "venue": "Arrowhead Stadium",
        "broadcast": "ESPN / ABC",
        "away_team": "Denver Broncos",
        "away_abbr": "DEN",
        "away_record": "0-0",
        "away_logo": "https://example.com/den.png",
        "home_team": "Kansas City Chiefs",
        "home_abbr": "KC",
        "home_record": "0-0",
        "home_logo": "https://example.com/kc.png",
    }


def _market() -> dict:
    return {
        "ready": True,
        "market_available": True,
        "official_event_id": "401872931",
        "projection_weight": 0.0,
        "books": [
            {
                "sportsbook": "FanDuel",
                "away_spread": 2.5,
                "away_price": -115,
                "home_spread": -2.5,
                "home_price": -105,
                "age_seconds": 4,
            }
        ],
    }


def test_v2_is_presentation_only_over_frozen_v1_transport() -> None:
    assert page.FROZEN_TRANSPORT == "nfl_spread_hub_v1"
    assert page.PRESENTATION_ONLY is True
    assert page.MATCHUP_BOARD_FIRST is True
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.PROJECTION_MODEL_ENABLED is False
    assert page.MONTE_CARLO_ENABLED is False
    assert page.RANKINGS_ENABLED is False
    assert page.STAKE_SIZING_ENABLED is False
    assert page.WAGER_ACTIONS_ENABLED is False

    source = inspect.getsource(page.render_nfl_hub)
    assert "frozen._fetch_markets(games)" in source
    assert "fetch_event_market" not in source


def test_matchup_card_renders_certified_spread_market_cleanly() -> None:
    html = page._matchup_card(_game(), _market())
    assert "Denver Broncos" in html
    assert "Kansas City Chiefs" in html
    assert "+2.5" in html
    assert "-2.5" in html
    assert "-115" in html
    assert "-105" in html
    assert "FanDuel" in html
    assert "UNDERDOG" in html
    assert "MARKET FAVORITE" in html
    assert "MARKET READY" in html
    assert "EXACT ID" in html
    assert "MODEL OFF" in html
    assert "MC OFF" in html
    assert "ESPN event 401872931" in html
    assert "sportsbook projection influence 0.0%" in html


def test_market_role_is_market_semantics_only() -> None:
    assert page._market_role(-3.5) == "MARKET FAVORITE"
    assert page._market_role(3.5) == "UNDERDOG"
    assert page._market_role(0.0) == "PICK'EM"
    assert page._market_role(None) == "LINE UNAVAILABLE"


def test_summary_keeps_model_and_mc_visibly_off() -> None:
    html = page._summary_html(games=1, upcoming=1, available=1)
    assert "MARKET" in html
    assert "READY" in html
    assert html.count("OFF") == 2
    assert "Step 7" in html


def test_router_v133_is_additive_over_v132() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v132"
    assert router.ACTIVE_SPREAD_HUB == "nfl_spread_hub_v2"
    assert router.SPREAD_MARKET == "Spread"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.PROJECTION_MODEL_ENABLED is False
    assert router.MONTE_CARLO_ENABLED is False
    assert router.STAKE_SIZING_ENABLED is False
    assert router.WAGER_ACTIONS_ENABLED is False

    source = inspect.getsource(router.render_app)
    assert "prior.ACTIVE_SPREAD_HUB = ACTIVE_SPREAD_HUB" in source
    assert "return prior.render_app()" in source
    assert "prior.ACTIVE_SPREAD_HUB = original_active_hub" in source
