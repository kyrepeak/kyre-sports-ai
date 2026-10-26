from __future__ import annotations

from pathlib import Path

import nfl_game_totals_page1_s_tier_v1 as page


ROOT = Path(__file__).resolve().parents[1]


def _row() -> dict:
    return {
        "game_id": "game-1",
        "state": "pre",
        "away_team": "Dallas Cowboys",
        "away_abbr": "DAL",
        "away_record": "2-4",
        "away_logo": "https://example.com/dal.png",
        "home_team": "Philadelphia Eagles",
        "home_abbr": "PHI",
        "home_record": "2-4",
        "home_logo": "https://example.com/phi.png",
        "venue": "Lincoln Financial Field",
        "broadcast": "Verified broadcast",
        "tip_et": "8:15 PM ET",
        "season_type": "Regular Season",
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
        "adjustments": {"pace": -1.2, "explosive": -0.4, "sustainability": 0.1, "environment": 0.0},
        "sportsbook_projection_weight": 0.0,
    }


def _read(final_read: str = "PASS") -> dict:
    return {
        "ready": True,
        "final_read": final_read,
        "model_total": 46.3,
        "market_total": 44.5,
        "edge_points": 1.8,
        "range_low": 39.8,
        "range_high": 52.8,
        "range_clearance": 0.0,
        "over_price": -102,
        "under_price": -120,
        "rationale": "Market total sits inside the certified model range.",
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
    return {"ready": True, "indoor": False, "temperature_f": 61, "precip_probability_pct": 0, "wind_gust_mph": 6, "weather_pressure": "LOW", "venue": "Lincoln Financial Field"}


def test_card_model_preserves_market_blind_projection_and_truthful_pass_state() -> None:
    model = page.build_decision_card_model(
        _row(), _snapshot(), _scoring(), _pace(), _explosive(), _red_zone(), _environment(), _projection(), _read()
    )
    assert model["market_total"] == 44.5
    assert model["kyre_total"] == 46.3
    assert model["edge"] == 1.8
    assert model["lean"] == "PASS"
    assert model["model_range"] == "39.8–52.8"
    assert model["sportsbook_projection_weight"] == 0.0
    assert model["weather"] == "61°F · 0% precip · 6 mph"
    assert len(model["reasons"]) == 3


def test_card_html_is_super_simple_s_tier_decision_board() -> None:
    html = page.build_decision_card_html(
        _row(), _snapshot(), _scoring(), _pace(), _explosive(), _red_zone(), _environment(), _projection(), _read()
    )
    for token in (
        "MARKET TOTAL", "KYRE TOTAL", "EDGE", "LEAN", "MODEL RANGE", "CONFIDENCE",
        "WHY KYRE", "TOTAL ENVIRONMENT", "FULL ANALYSIS", "FanDuel", "44.5", "46.3", "+1.8",
    ):
        assert token in html
    assert "STEP 3" not in html
    assert "STEP 4" not in html
    assert "STEP 5" not in html
    assert "STEP 6" not in html
    assert "STEP 7" not in html
    assert "STEP 8" not in html
    assert "STEP 9" not in html
    assert "ESPN" not in html
    assert "captured_at" not in html
    assert "market_id" not in html
    assert "sportsbook projection influence" not in html.lower()


def test_full_analysis_is_collapsed_by_default_but_keeps_certified_deep_sections() -> None:
    html = page.build_decision_card_html(
        _row(), _snapshot(), _scoring(), _pace(), _explosive(), _red_zone(), _environment(), _projection(), _read()
    )
    assert "<details" in html
    assert "FULL ANALYSIS" in html
    assert "Offense vs Defense" in html
    assert "Pace + Possession" in html
    assert "Explosive Scoring" in html
    assert "Red Zone + Drive Sustainability" in html
    assert "Game Environment" in html


def test_router_activates_s_tier_page_only_for_game_totals() -> None:
    hub = (ROOT / "nfl_hub_v36.py").read_text(encoding="utf-8")
    assert 'if market == "Game Total":' in hub
    assert "from nfl_game_totals_page1_s_tier_v1 import render_nfl_game_totals_hub" in hub
    assert "return base.render_nfl_hub(market)" in hub


def test_s_tier_page_preserves_frozen_v10_and_existing_compact_wrapper() -> None:
    source = (ROOT / "nfl_game_totals_page1_s_tier_v1.py").read_text(encoding="utf-8")
    assert "import nfl_game_totals_compact_layout_v1 as compact" in source
    assert "import nfl_game_totals_hub_v10 as v10" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = v10.SPORTSBOOK_PROJECTION_INFLUENCE" in source
    assert "STAKE_SIZING_ENABLED = v10.STAKE_SIZING_ENABLED" in source
    assert "WAGER_ACTIONS_ENABLED = v10.WAGER_ACTIONS_ENABLED" in source
