from __future__ import annotations

from pathlib import Path

import nfl_game_totals_page1_s_tier_v1 as page


ROOT = Path(__file__).resolve().parents[1]


def _row() -> dict:
    return {
        "game_id": "game-1",
        "state": "pre",
        "away_team": "Dallas Cowboys",
        "away_record": "2-4",
        "away_logo": "https://example.com/dal.png",
        "home_team": "Philadelphia Eagles",
        "home_record": "2-4",
        "home_logo": "https://example.com/phi.png",
        "venue": "Lincoln Financial Field",
        "tip_et": "8:15 PM ET",
    }


def _snapshot() -> dict:
    return {
        "ready": True,
        "market_available": True,
        "markets": [{
            "active": True,
            "sportsbook": "FanDuel",
            "total": 44.5,
            "over_price": -102,
            "under_price": -120,
        }],
    }


def _projection() -> dict:
    return {
        "ready": True,
        "projected_total": 46.3,
        "baseline_total": 47.8,
        "range_low": 39.8,
        "range_high": 52.8,
        "adjustments": {
            "pace": -1.2,
            "explosive": -0.4,
            "sustainability": 0.1,
            "environment": 0.0,
        },
        "sportsbook_projection_weight": 0.0,
    }


def _read() -> dict:
    return {
        "ready": True,
        "final_read": "PASS",
        "model_total": 46.3,
        "market_total": 44.5,
        "edge_points": 1.8,
        "range_low": 39.8,
        "range_high": 52.8,
        "range_clearance": 0.0,
        "over_price": -102,
        "under_price": -120,
        "sportsbook_projection_weight": 0.0,
        "stake_sizing_enabled": False,
        "wager_actions_enabled": False,
    }


def _scoring() -> dict:
    return {
        "ready": True,
        "away": {"team_name": "Dallas Cowboys", "offense_ppg": 26.4, "opponent_defense_papg": 21.0},
        "home": {"team_name": "Philadelphia Eagles", "offense_ppg": 20.0, "opponent_defense_papg": 28.3},
    }


def _pace() -> dict:
    return {"ready": True, "matchup": {"average_plays_per_game": 60.7, "grade": "LOW"}}


def _explosive() -> dict:
    return {"ready": True, "matchup": {"average_explosive_plays_per_game": 2.4, "grade": "BALANCED"}}


def _red_zone() -> dict:
    return {"ready": True, "matchup": {"average_red_zone_td_pct": 71.3, "average_third_down_conv_pct": 42.3, "average_first_downs_per_game": 16.9, "grade": "BALANCED"}}


def _environment() -> dict:
    return {
        "ready": True,
        "indoor": False,
        "temperature_f": 61,
        "precip_probability_pct": 0,
        "wind_gust_mph": 6,
        "weather_pressure": "LOW",
    }


def _html() -> str:
    return page.build_decision_card_html(
        _row(), _snapshot(), _scoring(), _pace(), _explosive(), _red_zone(), _environment(), _projection(), _read()
    )


def test_mobile_density_promotes_three_numbers_then_one_decision_banner() -> None:
    html = _html()
    assert 'class="kgt-s1-primary"' in html
    assert html.count('class="kgt-s1-primary-stat') == 3
    assert "MARKET TOTAL" in html
    assert "KYRE TOTAL" in html
    assert "EDGE" in html
    assert 'class="kgt-s1-decision pass"' in html
    assert "PASS — EDGE NOT STRONG ENOUGH" in html
    assert "Kyre 46.3 · Market 44.5 · Difference +1.8" in html


def test_mobile_density_moves_range_and_confidence_to_secondary_row() -> None:
    html = _html()
    assert 'class="kgt-s1-secondary"' in html
    assert "MODEL RANGE" in html
    assert "39.8–52.8" in html
    assert "CONFIDENCE" in html
    assert "PASS" in html
    assert 'class="kgt-s1-stat lean' not in html


def test_mobile_density_combines_sportsbook_and_weather_context() -> None:
    html = _html()
    assert html.count('class="kgt-s1-context"') == 1
    assert "FanDuel" in html
    assert "O <b class=\"kgt-s1-over\">-102</b>" in html
    assert "U <b class=\"kgt-s1-under\">-120</b>" in html
    assert "61°F · 0% precip · 6 mph" in html
    assert "LOW impact" in html
    assert "kgt-s1-weather" not in html


def test_pass_explanation_is_decision_specific_and_keeps_weather_out_of_reason_list() -> None:
    html = _html()
    assert "💡 WHY PASS?" in html
    assert "Only 1.8 pts above market" in html
    assert "Pace suppresses total 1.2 pts" in html
    assert "Market remains inside 39.8–52.8 model range" in html
    assert "Weather impact LOW" not in html


def test_mobile_css_is_compact_and_full_analysis_is_secondary() -> None:
    source = (ROOT / "nfl_game_totals_page1_s_tier_v1.py").read_text(encoding="utf-8")
    assert ".kgt-s1-primary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))" in source
    assert ".kgt-s1-secondary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in source
    assert "@media(max-width:760px)" in source
    assert ".kgt-s1-team img{width:36px;height:36px" in source
    assert "VIEW FULL ANALYSIS →" in _html()


def test_cleanup_is_presentation_only_and_preserves_frozen_model_contract() -> None:
    source = (ROOT / "nfl_game_totals_page1_s_tier_v1.py").read_text(encoding="utf-8")
    assert "import nfl_game_totals_hub_v10 as v10" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = v10.SPORTSBOOK_PROJECTION_INFLUENCE" in source
    assert "STAKE_SIZING_ENABLED = v10.STAKE_SIZING_ENABLED" in source
    assert "WAGER_ACTIONS_ENABLED = v10.WAGER_ACTIONS_ENABLED" in source
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
