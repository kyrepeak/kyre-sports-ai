from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_identity_v1 as identity
import nfl_passing_yards_profile_v1 as profile


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_passing_yards_gets_a_dedicated_compact_route_only() -> None:
    hub = _read("nfl_hub_v19.py")
    page = _read("nfl_passing_yards_hub_v1.py")

    assert 'if market == "Passing Yards":' in hub
    assert 'from nfl_passing_yards_hub_v1 import render_nfl_passing_yards_hub' in hub
    assert 'return base.render_nfl_hub(market)' in hub
    assert 'NFL PASSING YARDS V1 • COMPACT FOUNDATION • VERIFIED SLATE' in page
    assert 'base.load_nfl_slate(day_str)' in page


def test_compact_page_does_not_enable_uncertified_betting_logic() -> None:
    page = _read("nfl_passing_yards_hub_v1.py")

    assert 'MODEL OFF' in page
    assert 'no projection or sportsbook influence enabled.' in page
    assert 'QB starter identity, passing data, matchup engines, projections, probabilities, and rankings are not active yet.' in page
    assert 'st.metric(' not in page
    assert 'np.random' not in page
    assert 'numpy' not in page


def test_compact_layout_reduces_above_fold_vertical_weight() -> None:
    page = _read("nfl_passing_yards_hub_v1.py")

    assert '.ks-shell{padding:10px 14px!important' in page
    assert '.ks-title{font-size:1.55rem!important' in page
    assert '.kpy-head' in page
    assert '.kpy-strip' in page
    assert '.kpy-grid' in page


def test_router_v80_preserves_cfb_v79_and_advances_only_nfl_hub() -> None:
    router = _read("streamlit_memory_lazy_router_v80.py")
    app = _read("app.py")

    assert 'import streamlit_memory_lazy_router_v79 as prior' in router
    assert 'nfl_hub_v19' in router
    assert 'streamlit_memory_lazy_router_v80' in app
    assert 'STREAMLIT_MAIN_V80_NFL_PASSING_YARDS_COMPACT_FOUNDATION_2026-09-11' in app


def test_step1_verified_depth_qb1_is_resolved(monkeypatch) -> None:
    payload = {
        "depthCharts": [{
            "positions": {
                "qb": {
                    "position": {"abbreviation": "QB", "name": "Quarterback"},
                    "athletes": [
                        {"rank": 1, "athlete": {"id": "100", "displayName": "Verified QB One"}},
                        {"rank": 2, "athlete": {"id": "101", "displayName": "Verified QB Two"}},
                    ],
                }
            }
        }]
    }
    monkeypatch.setattr(identity.depth_base, "_depth_payload", lambda team_id: (payload, {"ok": True, "http": 200}))
    ctx = identity.resolve_team_qb_identity("IND", "Indianapolis Colts", 2026, {"IND": []}, True)
    assert ctx["depth_state"] == "VERIFIED"
    assert ctx["identity_verified"] is True
    assert ctx["qb1"]["athlete_id"] == "100"
    assert ctx["qb1"]["name"] == "Verified QB One"


def test_step1_roster_fallback_never_becomes_verified_qb1(monkeypatch) -> None:
    monkeypatch.setattr(identity.depth_base, "_depth_payload", lambda team_id: ({}, {"ok": False, "http": 404}))
    monkeypatch.setattr(identity.depth_repair, "_core_depth_payload", lambda year, team_id: ({}, {"ok": False, "http": 404}))
    roster = {
        "athletes": [{
            "position": "Quarterback",
            "items": [{
                "id": "200",
                "displayName": "Roster Only QB",
                "position": {"abbreviation": "QB", "name": "Quarterback"},
            }],
        }]
    }
    monkeypatch.setattr(identity.depth_base, "_roster_payload", lambda team_id: (roster, {"ok": True, "http": 200}))
    ctx = identity.resolve_team_qb_identity("IND", "Indianapolis Colts", 2026, {"IND": []}, True)
    assert ctx["depth_state"] == "ROSTER FALLBACK"
    assert ctx["identity_verified"] is False
    assert ctx["qb1"] == {}


def test_step1_invalid_game_id_fails_closed() -> None:
    out = identity.resolve_matchup_identity({"game_id": "synthetic-game"}, 2026)
    assert out["ready"] is False
    assert "official ESPN game ID" in out["reason"]


def test_router_v81_advances_only_passing_yards_step1() -> None:
    hub = _read("nfl_hub_v20.py")
    router = _read("streamlit_memory_lazy_router_v81.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v2.py")
    resolver = _read("nfl_passing_yards_identity_v1.py")

    assert "import nfl_hub_v19 as base" in hub
    assert "nfl_passing_yards_hub_v2" in hub
    assert "import streamlit_memory_lazy_router_v80 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v20"' in router
    assert "streamlit_memory_lazy_router_v81" in app
    assert "STREAMLIT_MAIN_V81_NFL_PASSING_YARDS_STEP1_IDENTITY_2026-09-11" in app
    assert "STEP 1 IDENTITY GREEN" in page
    assert "sportsbook influence 0.0%" in page
    assert "projection/Monte Carlo/ranking/recommendation OFF" in page
    assert "never promoted to verified QB1" in resolver


def test_step2_parses_espn_passing_totals_and_derives_baseline() -> None:
    payload = {
        "splits": {
            "categories": [{
                "name": "passing",
                "stats": [
                    {"name": "gamesPlayed", "value": 2},
                    {"name": "completions", "value": 44},
                    {"name": "passingAttempts", "value": 70},
                    {"name": "passingYards", "value": 560},
                    {"name": "passingTouchdowns", "value": 4},
                    {"name": "interceptions", "value": 1},
                ],
            }]
        }
    }
    out = profile.parse_season_passing(payload)
    assert out["ready"] is True
    assert out["yards_per_game"] == 280.0
    assert out["attempts_per_game"] == 35.0
    assert round(out["completion_pct"], 1) == 62.9
    assert out["yards_per_attempt"] == 8.0


def test_step2_recent_game_log_is_descriptive_and_keeps_site_split() -> None:
    payload = {
        "categories": [{
            "name": "passing",
            "labels": ["CMP", "ATT", "YDS", "TD", "INT"],
            "events": [
                {"eventId": "1", "stats": ["22", "33", "275", "2", "0"]},
                {"eventId": "2", "stats": ["18", "29", "225", "1", "1"]},
            ],
        }],
        "events": {
            "1": {"date": "2026-09-10", "atVs": "vs", "opponent": {"abbreviation": "HOU"}},
            "2": {"date": "2026-09-03", "atVs": "@", "opponent": {"abbreviation": "TEN"}},
        },
    }
    rows = profile.parse_recent_passing(payload)
    assert len(rows) == 2
    assert rows[0]["passing_yards"] == 275.0
    assert rows[0]["home_away"] == "home"
    assert rows[1]["home_away"] == "away"


def test_step2_profile_uses_verified_athlete_id_and_no_projection(monkeypatch) -> None:
    season_payload = {
        "splits": {"categories": [{"name": "passing", "stats": [
            {"name": "gamesPlayed", "value": 2},
            {"name": "completions", "value": 40},
            {"name": "passingAttempts", "value": 60},
            {"name": "passingYards", "value": 500},
        ]}]}
    }
    game_payload = {
        "categories": [{"name": "passing", "labels": ["CMP", "ATT", "YDS"], "events": [
            {"eventId": "1", "stats": ["20", "30", "260"]},
            {"eventId": "2", "stats": ["20", "30", "240"]},
        ]}],
        "events": {
            "1": {"date": "2026-09-10", "atVs": "vs", "opponent": {"abbreviation": "HOU"}},
            "2": {"date": "2026-09-03", "atVs": "@", "opponent": {"abbreviation": "TEN"}},
        },
    }
    monkeypatch.setattr(profile, "_season_stats_payload", lambda year, season_type, athlete_id: (season_payload, {"ok": True, "http": 200}))
    monkeypatch.setattr(profile, "_gamelog_payload", lambda year, athlete_id: (game_payload, {"ok": True, "http": 200}))
    out = profile.build_qb_profile("999", "Verified QB", 2026, 2)
    assert out["ready"] is True
    assert out["athlete_id"] == "999"
    assert out["recent3_yards"] == 250.0
    assert out["home_yards"] == 260.0
    assert out["away_yards"] == 240.0
    assert "projection" not in out


def test_router_v82_advances_only_passing_yards_step2() -> None:
    hub = _read("nfl_hub_v21.py")
    router = _read("streamlit_memory_lazy_router_v82.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v3.py")
    engine = _read("nfl_passing_yards_profile_v1.py")

    assert "import nfl_hub_v20 as base" in hub
    assert "nfl_passing_yards_hub_v3" in hub
    assert "import streamlit_memory_lazy_router_v81 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v21"' in router
    assert "streamlit_memory_lazy_router_v82" in app
    assert "STREAMLIT_MAIN_V81_NFL_PASSING_YARDS_STEP1_IDENTITY_2026-09-11" in app
    assert "STREAMLIT_MAIN_V82_NFL_PASSING_YARDS_STEP2_QB_PROFILE_2026-09-11" in app
    assert "STEP 2 PROFILE GREEN" in page
    assert "sportsbook influence 0.0%" in page
    assert "descriptive stats only" in page
    assert "projection/Monte Carlo/probability/ranking/recommendation OFF" in page
    assert "passing-yards projection" in engine
