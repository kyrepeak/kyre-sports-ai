from __future__ import annotations

import importlib
import importlib.util

import pandas as pd


def _load(name: str):
    assert importlib.util.find_spec(name) is not None, f"{name} must exist"
    return importlib.import_module(name)


def _sample_item() -> dict:
    return {
        "row": {
            "game_id": "401873009",
            "away_team": "Dallas Cowboys",
            "home_team": "Philadelphia Eagles",
            "away_abbr": "DAL",
            "home_abbr": "PHI",
            "away_record": "2-4",
            "home_record": "2-4",
            "venue": "Lincoln Financial Field",
            "tip_et": "5:15 PM MST",
        },
        "snapshot": {
            "ready": True,
            "market_available": True,
            "markets": [{"sportsbook": "FanDuel", "total": 43.5, "over_price": -120, "under_price": -102}],
        },
        "scoring": {"ready": True},
        "pace": {"ready": True, "matchup": {"pace_signal": "LOW", "average_plays_per_game": 60.7}},
        "explosive": {"ready": True, "matchup": {"signal": "BALANCED", "average_explosive_plays_per_game": 2.4}},
        "red_zone": {
            "ready": True,
            "away": {"red_zone_td_pct": 73.9},
            "home": {"red_zone_td_pct": 68.8},
            "matchup": {"signal": "HIGH", "average_red_zone_td_pct": 71.3},
        },
        "environment": {
            "ready": True,
            "indoor": False,
            "venue_name": "Lincoln Financial Field",
            "temperature": 59,
            "precipitation": 0,
            "gust": 8,
            "weather_pressure": "LOW",
        },
        "projection": {
            "ready": True,
            "projected_total": 46.3,
            "baseline_total": 47.8,
            "range_low": 39.8,
            "range_high": 52.8,
            "adjustments": {"pace": -1.2, "explosive": -0.4, "sustainability": 0.1, "environment": 0.0},
            "sportsbook_projection_weight": 0.0,
        },
        "read": {
            "ready": True,
            "final_read": "PASS",
            "model_total": 46.3,
            "market_total": 43.5,
            "edge_points": 2.8,
            "over_price": -120,
            "under_price": -102,
            "range_low": 39.8,
            "range_high": 52.8,
            "rationale": "Market total sits inside the certified model range.",
        },
        "model": {"market_total": 43.5, "kyre_total": 46.3, "edge": 2.8, "lean": "PASS"},
    }


def test_context_history_filters_exact_matchup_and_computes_ou_only_from_verified_line():
    ctx = _load("nfl_game_totals_page2_context_v2")
    frame = pd.DataFrame(
        [
            {"gameday": "2025-12-14", "away_team": "DAL", "home_team": "PHI", "away_score": 24, "home_score": 27, "total_line": 46.5},
            {"gameday": "2025-10-05", "away_team": "PHI", "home_team": "DAL", "away_score": 20, "home_score": 17, "total_line": 45.0},
            {"gameday": "2024-12-22", "away_team": "DAL", "home_team": "PHI", "away_score": 28, "home_score": 25, "total_line": 53.0},
            {"gameday": "2024-10-01", "away_team": "DAL", "home_team": "PHI", "away_score": 20, "home_score": 20, "total_line": None},
            {"gameday": "2025-11-01", "away_team": "DAL", "home_team": "NYG", "away_score": 35, "home_score": 10, "total_line": 44.0},
        ]
    )
    out = ctx.normalize_matchup_history(frame, "DAL", "PHI", limit=3)
    assert out["ready"] is True
    assert out["source"] == "nflverse"
    assert out["display_only"] is True and out["model_influence"] == 0.0
    assert [row["date"] for row in out["meetings"]] == ["2025-12-14", "2025-10-05", "2024-12-22"]
    assert [row["combined_score"] for row in out["meetings"]] == [51.0, 37.0, 53.0]
    assert [row["closing_total"] for row in out["meetings"]] == [46.5, 45.0, 53.0]
    assert [row["ou_result"] for row in out["meetings"]] == ["OVER", "UNDER", "PUSH"]
    assert out["overs"] == 1 and out["unders"] == 1 and out["pushes"] == 1


def test_history_missing_line_is_semantic_not_fabricated():
    ctx = _load("nfl_game_totals_page2_context_v2")
    frame = pd.DataFrame([
        {"gameday": "2024-10-01", "away_team": "DAL", "home_team": "PHI", "away_score": 20, "home_score": 20, "total_line": None},
    ])
    out = ctx.normalize_matchup_history(frame, "DAL", "PHI", limit=3)
    row = out["meetings"][0]
    assert row["closing_total"] is None
    assert row["ou_result"] == "—"
    assert out["line_verified_games"] == 0


def test_availability_prioritizes_official_key_offensive_designations_and_fails_closed():
    ctx = _load("nfl_game_totals_page2_context_v2")
    report = {
        "DAL": {"verified": True, "rows": [
            {"player_name": "QB One", "position": "QB", "injury": "Shoulder", "game_status": "QUESTIONABLE", "practice_status": "Limited"},
            {"player_name": "WR One", "position": "WR", "injury": "Knee", "game_status": "OUT", "practice_status": "DNP"},
            {"player_name": "CB One", "position": "CB", "injury": "Ankle", "game_status": "QUESTIONABLE", "practice_status": "Limited"},
        ]},
        "PHI": {"verified": True, "rows": [
            {"player_name": "TE One", "position": "TE", "injury": "Hamstring", "game_status": "PROBABLE", "practice_status": "Full"},
        ]},
    }
    out = ctx.normalize_availability(report, "DAL", "PHI", limit_per_team=2)
    assert out["ready"] is True
    assert out["source"] == "NFL.com Official Injury Report"
    assert out["display_only"] is True and out["model_influence"] == 0.0
    assert [row["player_name"] for row in out["away"]] == ["WR One", "QB One"]
    assert out["impact"] == "HIGH"

    unavailable = ctx.normalize_availability({}, "DAL", "PHI")
    assert unavailable["ready"] is False
    assert unavailable["impact"] == "UNAVAILABLE"


def test_v12_page2_html_matches_approved_s_tier_hierarchy_and_hides_debug_language():
    page = _load("nfl_game_totals_hub_v12")
    item = _sample_item()
    history = {
        "ready": True, "games": 3, "overs": 2, "unders": 1, "pushes": 0,
        "average_combined_score": 47.0, "line_verified_games": 3,
        "meetings": [
            {"date": "2025-12-14", "score": "DAL 24 – PHI 27", "combined_score": 51.0, "closing_total": 46.5, "ou_result": "OVER"},
            {"date": "2025-10-05", "score": "PHI 20 – DAL 17", "combined_score": 37.0, "closing_total": 45.0, "ou_result": "UNDER"},
            {"date": "2024-12-22", "score": "DAL 28 – PHI 25", "combined_score": 53.0, "closing_total": 47.5, "ou_result": "OVER"},
        ],
        "source": "nflverse", "display_only": True, "model_influence": 0.0,
    }
    availability = {
        "ready": True, "impact": "LOW IMPACT", "source": "NFL.com Official Injury Report",
        "away": [{"player_name": "C. Lamb", "position": "WR", "game_status": "QUESTIONABLE", "injury": "Knee"}],
        "home": [{"player_name": "A.J. Brown", "position": "WR", "game_status": "PROBABLE", "injury": "Hamstring"}],
        "display_only": True, "model_influence": 0.0,
    }
    html = page.build_page2_html(item, history, availability, "2026-10-26")
    markers = [
        "NFL GAME TOTALS • FULL ANALYSIS", "WHY THIS READ", "MARKET CONTEXT", "MATCHUP HISTORY",
        "KEY AVAILABILITY", "GAME PROFILE", "PROJECTION RANGE", "BOTTOM LINE", "Data & Sources",
        "Dallas Cowboys @ Philadelphia Eagles", "43.5", "46.3", "+2.8", "PASS",
    ]
    for marker in markers:
        assert marker in html
    positions = [html.index(marker) for marker in ["WHY THIS READ", "MARKET CONTEXT", "MATCHUP HISTORY", "KEY AVAILABILITY", "GAME PROFILE", "PROJECTION RANGE", "BOTTOM LINE"]]
    assert positions == sorted(positions)
    assert "STEP 3" not in html and "STEP 4" not in html and "STEP 10" not in html
    assert "401873009" not in html
    assert "SELECTED-GAME ANALYSIS CERTIFIED" not in html
    assert "ESPN" not in html
    assert "sportsbook influence 0.0%" in html
    assert "matchup history is context only" in html.lower()


def test_canonical_game_total_adapter_promotes_v12_while_retaining_frozen_page1_anchor():
    loader = _load("universal_runtime_v5_loader")
    route = loader.RuntimeRoute("nfl", "game-total", {})
    adapter = loader.resolve_destination(route)
    assert adapter.source_version == "nfl_game_totals_hub_v12"
    assert adapter.loader.__name__ == "loader"
    source = importlib.util.find_spec("nfl_game_totals_page1_s_tier_v1")
    assert source is not None
