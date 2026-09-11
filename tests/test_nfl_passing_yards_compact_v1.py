from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_identity_v1 as identity
import nfl_passing_yards_profile_v1 as profile
import nfl_passing_yards_defense_v1 as defense
import nfl_passing_yards_pressure_v1 as pressure
import nfl_passing_yards_personnel_v1 as personnel


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


def test_step3_parses_opponent_pass_defense_and_derives_efficiency() -> None:
    payload = {
        "splits": {"categories": [{"name": "defensive", "stats": [
            {"name": "gamesPlayed", "value": 2},
            {"name": "opponentPassingYards", "value": 500, "rank": 28},
            {"name": "opponentPassingAttempts", "value": 70},
            {"name": "opponentPassingCompletions", "value": 44},
            {"name": "opponentPassingTouchdowns", "value": 4},
            {"name": "interceptions", "value": 2},
            {"name": "sacks", "value": 5},
        ]}]}
    }
    out = defense.parse_season_pass_defense(payload)
    assert out["ready"] is True
    assert out["passing_yards_allowed_per_game"] == 250.0
    assert out["passing_attempts_allowed_per_game"] == 35.0
    assert round(out["completion_pct_allowed"], 1) == 62.9
    assert round(out["yards_per_attempt_allowed"], 2) == 7.14
    assert out["passing_yards_allowed_rank"] == 28
    assert defense.matchup_grade(out)[0] == "FAVORABLE"


def test_step3_recent_defense_uses_opponent_boxscore_row() -> None:
    summary = {
        "boxscore": {"teams": [
            {"team": {"id": "11", "abbreviation": "IND"}, "statistics": [
                {"name": "passingYards", "displayValue": "210"},
            ]},
            {"team": {"id": "34", "abbreviation": "HOU"}, "statistics": [
                {"name": "passingYards", "displayValue": "280"},
                {"name": "completionAttempts", "displayValue": "25/36"},
            ]},
        ]}
    }
    out = defense.parse_recent_defense_game(summary, "11")
    assert out["passing_yards_allowed"] == 280.0
    assert out["completions_allowed"] == 25.0
    assert out["attempts_allowed"] == 36.0
    assert round(out["completion_pct_allowed"], 1) == 69.4
    assert round(out["yards_per_attempt_allowed"], 2) == 7.78


def test_step3_missing_verified_team_id_fails_closed() -> None:
    out = defense.build_pass_defense_profile("synthetic-team", "Fake Team", 2026, 2, "2026-09-12")
    assert out["ready"] is False
    assert "verified opponent ESPN team ID" in out["reason"]


def test_step3_matchup_grade_requires_espn_rank() -> None:
    grade, reason = defense.matchup_grade({"passing_yards_allowed_rank": None})
    assert grade == "CHECK"
    assert "rank unavailable" in reason


def test_router_v83_advances_only_passing_yards_step3() -> None:
    hub = _read("nfl_hub_v22.py")
    router = _read("streamlit_memory_lazy_router_v83.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v4.py")
    engine = _read("nfl_passing_yards_defense_v1.py")

    assert "import nfl_hub_v21 as base" in hub
    assert "nfl_passing_yards_hub_v4" in hub
    assert "import streamlit_memory_lazy_router_v82 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v22"' in router
    assert "streamlit_memory_lazy_router_v83" in app
    assert "STREAMLIT_MAIN_V82_NFL_PASSING_YARDS_STEP2_QB_PROFILE_2026-09-11" in app
    assert "STREAMLIT_MAIN_V83_NFL_PASSING_YARDS_STEP3_PASS_DEFENSE_2026-09-11" in app
    assert "STEP 3 PASS DEFENSE GREEN" in page
    assert "sportsbook influence 0.0%" in page
    assert "descriptive matchup evidence only" in page
    assert "projection/Monte Carlo/probability/fair-line/EV/ranking/recommendation OFF" in page
    assert "passing-yards projection" in engine
    assert "no fuzzy team matching" in engine.lower()


def test_step4_offense_protection_uses_passing_sacks_not_defensive_sacks() -> None:
    payload = {
        "splits": {"categories": [
            {"name": "general", "stats": [{"name": "gamesPlayed", "value": 2}]},
            {"name": "passing", "stats": [
                {"name": "passingAttempts", "value": 70},
                {"name": "sacks", "value": 4, "rank": 7},
                {"name": "sackYardsLost", "value": 29},
            ]},
            {"name": "defensive", "stats": [{"name": "sacks", "value": 11}]},
        ]}
    }
    out = pressure.parse_offense_protection(payload)
    assert out["ready"] is True
    assert out["sacks_allowed"] == 4.0
    assert out["passing_attempts"] == 70.0
    assert out["sack_yards_lost"] == 29.0
    assert round(out["sack_rate_allowed"], 2) == 5.41
    assert out["sacks_allowed_rank"] == 7


def test_step4_defensive_pressure_derives_sack_rate_proxy() -> None:
    payload = {
        "splits": {"categories": [{"name": "defensive", "stats": [
            {"name": "gamesPlayed", "value": 2},
            {"name": "opponentPassingYards", "value": 480},
            {"name": "opponentPassingAttempts", "value": 70},
            {"name": "sacks", "value": 7},
        ]}]}
    }
    out = pressure.parse_defensive_pressure(payload)
    assert out["ready"] is True
    assert out["sacks_made"] == 7.0
    assert out["sacks_per_game"] == 3.5
    assert round(out["sack_rate_generated"], 2) == 9.09
    assert out["blitz_state"].startswith("UNAVAILABLE")


def test_step4_recent_boxscore_sacks_taken_are_parsed_from_offense_row() -> None:
    summary = {
        "boxscore": {"teams": [
            {"team": {"id": "11"}, "statistics": [
                {"name": "completionAttempts", "displayValue": "24-38"},
                {"name": "sacksYardsLost", "displayValue": "3-21"},
            ]},
            {"team": {"id": "34"}, "statistics": [
                {"name": "completionAttempts", "displayValue": "18-29"},
                {"name": "sacksYardsLost", "displayValue": "2-12"},
            ]},
        ]}
    }
    taken = pressure.parse_recent_sacks_taken(summary, "11")
    made = pressure.parse_recent_sacks_made(summary, "34")
    assert taken["sacks_taken"] == 3.0
    assert taken["pass_attempts"] == 38.0
    assert round(taken["sack_rate"], 2) == 7.32
    assert made["sacks_made"] == 3.0


def test_step4_invalid_verified_ids_fail_closed() -> None:
    out = pressure.build_pressure_matchup("fake", "Fake O", "34", "Houston", 2026, 2, "2026-09-12")
    assert out["ready"] is False
    assert "verified ESPN offense and defense team IDs" in out["reason"]


def test_router_v84_advances_only_passing_yards_step4() -> None:
    hub = _read("nfl_hub_v23.py")
    router = _read("streamlit_memory_lazy_router_v84.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v5.py")
    engine = _read("nfl_passing_yards_pressure_v1.py")

    assert "import nfl_hub_v22 as base" in hub
    assert "nfl_passing_yards_hub_v5" in hub
    assert "import streamlit_memory_lazy_router_v83 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v23"' in router
    assert "streamlit_memory_lazy_router_v84" in app
    assert "STREAMLIT_MAIN_V83_NFL_PASSING_YARDS_STEP3_PASS_DEFENSE_2026-09-11" in app
    assert "STREAMLIT_MAIN_V84_NFL_PASSING_YARDS_STEP4_PRESSURE_2026-09-11" in app
    assert "STEP 4 PRESSURE GREEN" in page
    assert "Step 4 projection influence 0.0%" in page
    assert "projection/Monte Carlo/probability/fair-line/EV/ranking/recommendation OFF" in page
    assert '"projection_adjustment": 0.0' in engine
    assert "blitz" in engine.lower()
    assert "not synthesized" in engine.lower()


def test_step5_parses_depth_positions_with_exact_athlete_ids() -> None:
    payload = {"depthCharts": [{"positions": {
        "wr": {"position": {"abbreviation": "WR"}, "athletes": [
            {"rank": 1, "athlete": {"id": "501", "displayName": "WR One"}},
            {"rank": 2, "athlete": {"id": "502", "displayName": "WR Two"}},
        ]},
        "lt": {"position": {"abbreviation": "LT"}, "athletes": [
            {"rank": 1, "athlete": {"id": "601", "displayName": "Left Tackle"}},
        ]},
    }}]}
    rows = personnel.parse_depth_positions(payload)
    assert rows[0]["athlete_id"] == "601" or rows[0]["athlete_id"] == "501"
    assert {row["athlete_id"] for row in rows} == {"501", "502", "601"}
    assert any(row["position"] == "WR" and row["rank"] == 1 for row in rows)


def test_step5_receiving_targets_fail_closed_without_explicit_targets() -> None:
    with_targets = {"splits": {"categories": [{"name": "receiving", "stats": [
        {"name": "receivingTargets", "value": 20},
        {"name": "receptions", "value": 14},
        {"name": "receivingYards", "value": 180},
    ]}]}}
    without_targets = {"splits": {"categories": [{"name": "receiving", "stats": [
        {"name": "receptions", "value": 14},
        {"name": "receivingYards", "value": 180},
    ]}]}}
    good = personnel.parse_receiving_usage(with_targets)
    missing = personnel.parse_receiving_usage(without_targets)
    assert good["ready"] is True and good["targets"] == 20.0
    assert missing["ready"] is False


def test_step5_personnel_label_separates_offense_hurt_from_secondary_help() -> None:
    skill = [{"tier": "HARD", "depth_rank": 1, "target_share": 22.0}]
    ol = [{"tier": "HARD", "depth_rank": 1}, {"tier": "HARD", "depth_rank": 1}]
    secondary = [{"tier": "HARD", "depth_rank": 1}, {"tier": "HARD", "depth_rank": 1}]
    hurt, _ = personnel.personnel_label("No listed injury", skill, ol, [], 22.0, True)
    help_label, _ = personnel.personnel_label("No listed injury", [], [], secondary, float("nan"), True)
    mixed, _ = personnel.personnel_label("No listed injury", skill, ol, secondary, 22.0, True)
    assert hurt == "HURT"
    assert help_label == "HELP"
    assert mixed == "MIXED"


def test_step5_invalid_team_identity_fails_closed() -> None:
    out = personnel.build_personnel_matchup({"team_id": "fake"}, {"team_id": "34"}, 2026, 2, 70)
    assert out["ready"] is False
    assert "verified ESPN offense and defense team IDs" in out["reason"]
    assert out["projection_adjustment"] == 0.0


def test_router_v85_advances_only_passing_yards_step5() -> None:
    hub = _read("nfl_hub_v24.py")
    router = _read("streamlit_memory_lazy_router_v85.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v6.py")
    engine = _read("nfl_passing_yards_personnel_v1.py")

    assert "import nfl_hub_v23 as base" in hub
    assert "nfl_passing_yards_hub_v6" in hub
    assert "import streamlit_memory_lazy_router_v84 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v24"' in router
    assert "streamlit_memory_lazy_router_v85" in app
    assert "STREAMLIT_MAIN_V84_NFL_PASSING_YARDS_STEP4_PRESSURE_2026-09-11" in app
    assert "STREAMLIT_MAIN_V85_NFL_PASSING_YARDS_STEP5_PERSONNEL_2026-09-11" in app
    assert "STEP 5 PERSONNEL GREEN" in page
    assert "Step 5 projection influence 0.0%" in page
    assert "exact ESPN athlete IDs" in page
    assert "No fuzzy player matching" in engine
    assert '"projection_adjustment": 0.0' in engine
    assert "explicit target" in engine.lower()
