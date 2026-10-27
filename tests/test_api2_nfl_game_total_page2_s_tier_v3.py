from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path


def _load(name: str):
    assert importlib.util.find_spec(name) is not None, f"{name} must exist"
    return importlib.import_module(name)


def _item(*, market: bool = True, team_split: bool = False) -> dict:
    projection = {
        "ready": True,
        "projected_total": 45.6,
        "range_low": 39.1,
        "range_high": 52.1,
        "adjustments": {"pace": -0.8, "explosive": 1.4, "sustainability": 0.0, "environment": -0.2},
        "sportsbook_projection_weight": 0.0,
    }
    if team_split:
        projection.update({"projected_away_points": 20.4, "projected_home_points": 25.2})
    snapshot = {"ready": False, "market_available": False, "markets": []}
    model = {
        "market_total": None,
        "kyre_total": 45.6,
        "edge": None,
        "lean": "WAIT",
        "confidence": "PASS",
    }
    read = {"ready": False, "final_read": "PASS"}
    if market:
        snapshot = {
            "ready": True,
            "market_available": True,
            "markets": [{
                "sportsbook": "FanDuel",
                "total": 46.5,
                "opening_total": 45.0,
                "over_price": -110,
                "under_price": -110,
            }],
        }
        model.update({"market_total": 46.5, "edge": -0.9, "lean": "PASS", "confidence": "MEDIUM"})
        read = {"ready": True, "final_read": "PASS", "market_total": 46.5, "edge_points": -0.9}
    return {
        "row": {
            "game_id": "g1",
            "away_team": "Carolina Panthers",
            "home_team": "Green Bay Packers",
            "away_abbr": "CAR",
            "home_abbr": "GB",
            "away_record": "3-3",
            "home_record": "4-3",
            "venue": "Lambeau Field",
            "tip_et": "5:15 PM MST",
        },
        "snapshot": snapshot,
        "model": model,
        "read": read,
        "scoring": {
            "ready": True,
            "away": {"team": "Carolina Panthers", "offense_ppg": 19.8, "opponent_defense_papg": 21.4, "signal": "MEDIUM", "quality": "HIGH"},
            "home": {"team": "Green Bay Packers", "offense_ppg": 26.2, "opponent_defense_papg": 24.9, "signal": "FAVORABLE", "quality": "HIGH"},
            "sportsbook_projection_weight": 0.0,
        },
        "pace": {"ready": True, "matchup": {"pace_signal": "BALANCED", "average_plays_per_game": 63.9}},
        "explosive": {"ready": True, "matchup": {"signal": "HIGH", "average_explosive_plays_per_game": 4.5}},
        "red_zone": {"ready": True, "matchup": {"signal": "BALANCED", "average_red_zone_td_pct": 58.1}},
        "environment": {
            "ready": True,
            "venue_name": "Lambeau Field",
            "temperature": 55,
            "gust": 12,
            "precipitation": 8,
            "weather_pressure": "LOW",
            "indoor": False,
        },
        "projection": projection,
    }


def test_v13_is_additive_page2_successor_with_frozen_invariants():
    page = _load("nfl_game_totals_hub_v13")
    v12 = _load("nfl_game_totals_hub_v12")
    assert page.page1 is v12.page1
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MATCHUP_HISTORY_MODEL_INFLUENCE == 0.0
    assert page.AVAILABILITY_MODEL_INFLUENCE == 0.0
    assert page.STAKE_SIZING_ENABLED is False
    assert page.WAGER_ACTIONS_ENABLED is False
    source = Path(page.__file__).read_text(encoding="utf-8").lower()
    for banned in ("import requests", "from sports_api", "espn bet", "sgo"):
        assert banned not in source


def test_v13_verified_page_is_decision_grade_and_uses_certified_fields_only():
    page = _load("nfl_game_totals_hub_v13")
    history = {
        "ready": True,
        "games": 2,
        "overs": 1,
        "unders": 1,
        "pushes": 0,
        "line_verified_games": 2,
        "average_combined_score": 44.5,
        "meetings": [
            {"date": "2025-11-02", "score": "GB 27–CAR 20", "combined_score": 47, "closing_total": 44.5, "ou_result": "OVER"},
            {"date": "2024-10-06", "score": "CAR 17–GB 25", "combined_score": 42, "closing_total": 45.0, "ou_result": "UNDER"},
        ],
    }
    availability = {
        "ready": True,
        "impact": "WATCH",
        "source": "NFL.com Official Injury Report",
        "away": [{"player_name": "WR One", "position": "WR", "game_status": "QUESTIONABLE", "injury": "Knee"}],
        "home": [],
    }
    html = page.build_page2_html(_item(market=True, team_split=True), history, availability, "2026-10-29")
    for marker in (
        "GAME INTELLIGENCE", "GAME SCRIPT", "WHY THIS READ", "MARKET CONTEXT", "PROJECTION RANGE",
        "MATCHUP EDGES", "TOTAL DRIVERS", "MATCHUP HISTORY", "KEY AVAILABILITY", "GAME ENVIRONMENT",
        "BOTTOM LINE", "Data &amp; Sources",
    ):
        assert marker in html
    assert "20.4" in html and "25.2" in html
    assert "19.8 PF/G" in html and "24.9 PA/G" in html
    assert "FAVORABLE" in html
    assert "Explosive +1.4" in html
    assert "Pace −0.8" in html or "Pace -0.8" in html
    assert "55°F" in html and "12 mph" in html and "8%" in html
    assert "kgt13-model-callout" in html and "kgt13-market-callout" in html
    assert "kgt12-labels" not in html


def test_v13_missing_context_uses_compact_semantic_states_and_never_synthesizes():
    page = _load("nfl_game_totals_hub_v13")
    html = page.build_page2_html(
        _item(market=False, team_split=False),
        {"ready": False},
        {"ready": False, "impact": "UNAVAILABLE"},
        "2026-10-29",
    )
    assert "MARKET NOT VERIFIED YET" in html
    assert "NO RELEVANT RECENT HISTORY" in html
    assert "AVAILABILITY VERIFICATION PENDING" in html
    assert "TEAM SPLIT NOT CERTIFIED" in html
    assert "45.6" in html
    assert "20.4" not in html and "25.2" not in html
    assert "OPEN → CURRENT" not in html
    assert "kgt13-market-grid" not in html
    assert "Verified matchup history is unavailable" not in html
    assert "Official key-availability verification is temporarily unavailable" not in html


def test_v13_mobile_contract_is_compact_and_range_callouts_have_separate_lanes():
    page = _load("nfl_game_totals_hub_v13")
    css = page._CSS
    assert "@media(max-width:760px)" in css
    assert ".kgt13-card{padding:8px" in css.replace(" ", "")
    assert "kgt13-model-callout" in css
    assert "kgt13-market-callout" in css
    assert "grid-template-columns:1fr1fr" in css.replace(" ", "")


def test_universal_game_total_adapter_routes_to_v13_and_keeps_v12_anchor():
    source = Path("universal_runtime_v5_loader.py").read_text(encoding="utf-8")
    start = source.index("def _nfl_game_total_adapter")
    end = source.index("def _nfl_passing_yards_adapter", start)
    block = source[start:end]
    assert '_import("nfl_game_totals_hub_v12")' in block
    assert 'return _import("nfl_game_totals_hub_v13")' in block
    loader = importlib.import_module("universal_runtime_v5_loader")
    adapter = loader.resolve_destination(loader.RuntimeRoute("nfl", "game-total", {}))
    assert adapter.source_version == "nfl_game_totals_hub_v12"
    assert adapter.loader().__name__ == "nfl_game_totals_hub_v13"
