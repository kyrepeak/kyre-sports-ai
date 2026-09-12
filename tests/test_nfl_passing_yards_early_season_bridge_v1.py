from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_defense_v2 as defense_v2
import nfl_passing_yards_early_season_v1 as early
import nfl_passing_yards_environment_v2 as environment_v2
import nfl_passing_yards_profile_v1 as profile
import nfl_passing_yards_pressure_v2 as pressure_v2


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _season_payload(games=16, attempts=500, yards=4000):
    return {
        "splits": {"categories": [{"name": "passing", "stats": [
            {"name": "gamesPlayed", "value": games},
            {"name": "completions", "value": 330},
            {"name": "passingAttempts", "value": attempts},
            {"name": "passingYards", "value": yards},
            {"name": "passingTouchdowns", "value": 28},
            {"name": "interceptions", "value": 10},
        ]}]}
    }


def _gamelog_payload(year: int):
    return {
        "categories": [{
            "name": "passing",
            "labels": ["CMP", "ATT", "YDS", "TD", "INT"],
            "events": [
                {"eventId": f"{year}01", "stats": ["22", "34", "280", "2", "0"]},
                {"eventId": f"{year}02", "stats": ["20", "32", "250", "1", "1"]},
                {"eventId": f"{year}03", "stats": ["24", "36", "310", "3", "0"]},
            ],
        }],
        "events": {
            f"{year}01": {"date": f"{year}-12-28", "atVs": "vs", "opponent": {"abbreviation": "A"}},
            f"{year}02": {"date": f"{year}-12-21", "atVs": "@", "opponent": {"abbreviation": "B"}},
            f"{year}03": {"date": f"{year}-12-14", "atVs": "vs", "opponent": {"abbreviation": "C"}},
        },
    }


def test_merge_recent_rows_keeps_current_then_prior_and_dedupes() -> None:
    current = [{"event_id": "2"}, {"event_id": "1"}]
    prior = [{"event_id": "1"}, {"event_id": "0"}]
    out = early.merge_recent_rows(current, prior, limit=3)
    assert [x["event_id"] for x in out] == ["2", "1", "0"]


def test_step2_uses_prior_regular_season_when_current_has_no_sample(monkeypatch) -> None:
    def season_loader(year, season_type, athlete_id):
        if year == 2026:
            return {"splits": {"categories": [{"name": "passing", "stats": []}]}}, {"ok": True, "http": 200}
        return _season_payload(), {"ok": True, "http": 200}

    def gamelog_loader(year, athlete_id):
        if year == 2026:
            return {"categories": []}, {"ok": True, "http": 200}
        return _gamelog_payload(year), {"ok": True, "http": 200}

    monkeypatch.setattr(profile, "_season_stats_payload", season_loader)
    monkeypatch.setattr(profile, "_gamelog_payload", gamelog_loader)
    out = profile.build_qb_profile("3915511", "Verified QB", 2026, 2)
    assert out["ready"] is True
    assert out["early_season_fallback"] is True
    assert out["baseline_source_year"] == 2025
    assert out["season"]["yards_per_game"] == 250.0
    assert len(out["recent_games"]) == 3
    assert out["recent3_yards"] == 280.0


def test_step2_current_sample_always_beats_prior(monkeypatch) -> None:
    def season_loader(year, season_type, athlete_id):
        return _season_payload(games=1 if year == 2026 else 16, attempts=35 if year == 2026 else 500, yards=300 if year == 2026 else 4000), {"ok": True, "http": 200}

    monkeypatch.setattr(profile, "_season_stats_payload", season_loader)
    monkeypatch.setattr(profile, "_gamelog_payload", lambda year, athlete_id: (_gamelog_payload(year), {"ok": True, "http": 200}))
    out = profile.build_qb_profile("3915511", "Verified QB", 2026, 2)
    assert out["ready"] is True
    assert out["early_season_fallback"] is False
    assert out["baseline_source_year"] == 2026
    assert out["season"]["passing_yards"] == 300.0


def test_defense_v2_bridges_prior_baseline_and_recent(monkeypatch) -> None:
    def fake_build(team_id, team_name, year, season_type, cutoff):
        if year == 2026:
            return {"ready": False, "team_id": team_id, "team_name": team_name, "season": {}, "recent_games": []}
        return {
            "ready": True,
            "team_id": team_id,
            "team_name": team_name,
            "season": {"passing_yards_allowed_per_game": 220.0, "passing_attempts_allowed_per_game": 33.0, "yards_per_attempt_allowed": 6.67},
            "recent_games": [
                {"event_id": "p1", "passing_yards_allowed": 210.0, "completion_pct_allowed": 60.0, "yards_per_attempt_allowed": 6.0},
                {"event_id": "p2", "passing_yards_allowed": 230.0, "completion_pct_allowed": 62.0, "yards_per_attempt_allowed": 7.0},
                {"event_id": "p3", "passing_yards_allowed": 220.0, "completion_pct_allowed": 61.0, "yards_per_attempt_allowed": 6.5},
            ],
            "matchup_grade": "BALANCED",
            "grade_basis": "ESPN rank #16",
        }
    monkeypatch.setattr(defense_v2.base, "build_pass_defense_profile", fake_build)
    out = defense_v2.build_pass_defense_profile("4", "Bengals", 2026, 2, "2026-09-13")
    assert out["ready"] is True
    assert out["early_season_fallback"] is True
    assert out["baseline_source_year"] == 2025
    assert out["recent_verified_games"] == 3
    assert out["recent3_yards_allowed"] == 220.0


def test_pressure_v2_uses_prior_only_when_current_not_ready(monkeypatch) -> None:
    def fake_build(*args):
        year = int(args[4])
        if year == 2026:
            return {"ready": False, "recent_offense": [], "recent_defense": [], "projection_adjustment": 0.0}
        return {
            "ready": True,
            "offense": {"sack_rate_allowed": 5.0},
            "defense": {"sack_rate_generated": 7.0},
            "pressure_label": "MODERATE",
            "pressure_basis": "verified prior season",
            "recent_offense": [{"event_id": "o1", "sacks_taken": 2.0, "sack_rate": 5.0}],
            "recent_defense": [{"event_id": "d1", "sacks_made": 3.0, "sack_rate_generated": 7.0}],
            "projection_adjustment": 0.0,
        }
    monkeypatch.setattr(pressure_v2.base, "build_pressure_matchup", fake_build)
    out = pressure_v2.build_pressure_matchup("27", "Bucs", "4", "Bengals", 2026, 2, "2026-09-13")
    assert out["ready"] is True
    assert out["early_season_fallback"] is True
    assert out["baseline_source_year"] == 2025
    assert out["projection_adjustment"] == 0.0
    assert out["sportsbook_influence"] == 0.0


def test_environment_v2_keeps_current_event_but_bridges_prior_pace(monkeypatch) -> None:
    monkeypatch.setattr(environment_v2.base, "build_game_environment", lambda *a, **k: {
        "ready": False,
        "summary_http": 200,
        "away_team_id": "27",
        "home_team_id": "4",
        "event": {"weather_available": True, "weather_condition": "Clear", "indoor": False},
        "away_pace": {"ready": False},
        "home_pace": {"ready": False},
        "away_rest": {"ready": False},
        "home_rest": {"ready": False},
    })
    payload = {"splits": {"categories": [{"stats": [
        {"name": "gamesPlayed", "value": 17},
        {"name": "totalOffensivePlays", "value": 1105},
        {"name": "passingAttempts", "value": 600},
        {"name": "rushingAttempts", "value": 505},
    ]}]}}
    monkeypatch.setattr(environment_v2.defense, "_team_stats_payload", lambda year, st, team_id: (payload, {"ok": True, "http": 200}))
    out = environment_v2.build_game_environment({"game_id": "1"}, {"team_id": "27"}, {"team_id": "4"}, 2026, 2, "2026-09-13")
    assert out["ready"] is True
    assert out["early_season_fallback"] is True
    assert out["baseline_source_year"] == 2025
    assert out["event"]["weather_condition"] == "Clear"
    assert out["away_pace"]["pass_attempts_per_game"] > 35
    assert out["sportsbook_influence"] == 0.0


def test_router_v97_preserves_v96_precedence_fix_and_advances_only_passing_yards() -> None:
    hub = _read("nfl_hub_v35.py")
    router = _read("streamlit_memory_lazy_router_v97.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v17.py")

    assert "import nfl_hub_v34 as base" in hub
    assert "nfl_passing_yards_hub_v17" in hub
    assert "import streamlit_memory_lazy_router_v96 as prior" in router
    assert 'PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v96._render_nfl_v96"' in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v35"' in router
    assert "prior._render_nfl_v96 = _render_nfl_v97" in router
    assert "streamlit_memory_lazy_router_v97" in app
    assert "STREAMLIT_MAIN_V96_NFL_PASSING_YARDS_ROUTE_PRECEDENCE_HOTFIX_V2_2026-09-11" in app
    assert "STREAMLIT_MAIN_V97_NFL_PASSING_YARDS_EARLY_SEASON_BRIDGE_2026-09-11" in app
    assert "current-season data will replace this automatically" in page
    assert "Sportsbook" not in _read("nfl_passing_yards_early_season_v1.py") or "No sportsbook" in _read("nfl_passing_yards_early_season_v1.py")
