from __future__ import annotations

from datetime import datetime, timezone

import cfb_top_picks_offense_research_v1 as offense


def _row():
    return {
        "event_id": "401234567",
        "away": "Virginia",
        "home": "Florida State",
        "away_team_id": "258",
        "home_team_id": "52",
    }


def _game():
    return {
        "espn_event_id": "401234567",
        "game_id": "401234567",
        "game_date": "2026-10-03",
        "kickoff_iso": "2026-10-03T20:00:00Z",
        "away_team": "Virginia",
        "home_team": "Florida State",
        "away_espn_team_id": "258",
        "home_espn_team_id": "52",
        "away_team_slug": "virginia",
        "home_team_slug": "florida-state",
    }


def _live(team_id, season):
    base = 30.0 if team_id == "258" else 35.0
    return {
        "games": 4,
        "points_pg": base,
        "pass_yards_pg": 250.0,
        "rush_yards_pg": 165.0,
        "pass_td_pg": 2.0,
        "rush_td_pg": 1.5,
        "yards_per_play": 6.25,
    }, {
        "ready": True,
        "provider": "ESPN Core current-season team statistics",
        "attempts": [{"http": 200, "bytes": 1000, "error": ""}],
    }


def _rows(team_id, season, cutoff, excluded):
    return [
        {
            "event_id": f"{team_id}1",
            "date": "2026-09-01T00:00:00Z",
            "date_dt": datetime(2026, 9, 1, tzinfo=timezone.utc),
            "opponent_name": "A",
            "points_for": 28.0,
            "points_against": 20.0,
        },
        {
            "event_id": f"{team_id}2",
            "date": "2026-09-08T00:00:00Z",
            "date_dt": datetime(2026, 9, 8, tzinfo=timezone.utc),
            "opponent_name": "B",
            "points_for": 35.0,
            "points_against": 24.0,
        },
        {
            "event_id": f"{team_id}3",
            "date": "2026-09-15T00:00:00Z",
            "date_dt": datetime(2026, 9, 15, tzinfo=timezone.utc),
            "opponent_name": "C",
            "points_for": 42.0,
            "points_against": 31.0,
        },
    ], [{"http": 200, "bytes": 1000, "error": ""}]


def test_offense_research_routes_exact_id_live_and_recent_fields(monkeypatch):
    monkeypatch.setattr(offense.readable, "_live_offense", _live)
    monkeypatch.setattr(offense.readable, "_completed_rows", _rows)
    monkeypatch.setattr(offense.readable, "_snapshot_team", lambda team_id: {})
    monkeypatch.setattr(offense, "_resolve_division", lambda profile: ("FBS", {}))
    monkeypatch.setattr(
        offense,
        "_red_zone_offense",
        lambda profile, division, observed: (
            offense._metric(0.72, source="NCAA FBS Red Zone Offense", observed_at=observed),
            {"ready": True},
        ),
    )
    monkeypatch.setattr(
        offense,
        "_explosive_offense",
        lambda profile, division, observed: (
            {
                **offense._metric(0.25, source="NCAA FBS efficiency", observed_at=observed),
                "label": "HIGH",
            },
            {"ready": True},
        ),
    )

    out = offense.build_offense_research(_row(), _game(), "2026-10-03")
    assert out["status"] == "READY"
    assert out["away"]["team_id"] == "258"
    assert out["home"]["team_id"] == "52"
    assert out["away"]["metrics"]["points_per_game"]["value"] == 30.0
    assert out["home"]["metrics"]["points_per_game"]["value"] == 35.0
    assert out["away"]["metrics"]["recent_scoring_avg"]["value"] == 35.0
    assert out["away"]["metrics"]["red_zone_td_rate"]["value"] == 0.72
    assert out["away"]["metrics"]["explosive_efficiency_proxy"]["label"] == "HIGH"
    assert out["combined_points_per_game"] == 65.0
    assert len(out["reasoning"]) >= 3


def test_field_level_snapshot_fallback_is_explicit(monkeypatch):
    monkeypatch.setattr(
        offense.readable,
        "_live_offense",
        lambda team_id, season: ({}, {"ready": False, "attempts": []}),
    )
    monkeypatch.setattr(
        offense.readable,
        "_snapshot_team",
        lambda team_id: {
            "offense": {
                "points_pg": 31.5,
                "yards_per_play": 5.9,
                "pass_yards_pg": 220.0,
                "rush_yards_pg": 170.0,
                "pass_td_pg": 1.8,
                "rush_td_pg": 1.4,
            }
        },
    )
    monkeypatch.setattr(offense.readable, "_completed_rows", _rows)
    monkeypatch.setattr(offense, "_resolve_division", lambda profile: ("", {}))
    monkeypatch.setattr(
        offense,
        "_red_zone_offense",
        lambda profile, division, observed: (
            offense._metric(None, source="", observed_at=observed),
            {"ready": False},
        ),
    )
    monkeypatch.setattr(
        offense,
        "_explosive_offense",
        lambda profile, division, observed: (
            offense._metric(None, source="", observed_at=observed),
            {"ready": False},
        ),
    )

    out = offense.build_offense_research(_row(), _game(), "2026-10-03")
    ppg = out["away"]["metrics"]["points_per_game"]
    assert ppg["value"] == 31.5
    assert ppg["status"] == "VERIFIED_FALLBACK"
    assert "snapshot" in ppg["source"].lower()


def test_material_metrics_carry_source_and_observed_at(monkeypatch):
    monkeypatch.setattr(offense.readable, "_live_offense", _live)
    monkeypatch.setattr(offense.readable, "_completed_rows", _rows)
    monkeypatch.setattr(offense.readable, "_snapshot_team", lambda team_id: {})
    monkeypatch.setattr(offense, "_resolve_division", lambda profile: ("FBS", {}))
    monkeypatch.setattr(
        offense,
        "_red_zone_offense",
        lambda profile, division, observed: (
            offense._metric(0.70, source="NCAA", observed_at=observed),
            {"ready": True},
        ),
    )
    monkeypatch.setattr(
        offense,
        "_explosive_offense",
        lambda profile, division, observed: (
            {
                **offense._metric(0.1, source="NCAA", observed_at=observed),
                "label": "ABOVE AVERAGE",
            },
            {"ready": True},
        ),
    )
    out = offense.build_offense_research(_row(), _game())
    for side in ("away", "home"):
        for metric in out[side]["metrics"].values():
            if metric["value"] is not None:
                assert metric["source"]
                assert metric["observed_at"]


def test_research_is_descriptive_only_and_api2_is_separate():
    assert offense.OFFENSE_RESEARCH_PROJECTION_WEIGHT == 0.0
    assert offense.SPORTSBOOK_PROJECTION_WEIGHT == 0.0
    assert offense.MAY_MODIFY_PROBABILITY is False
    assert offense.MAY_MODIFY_RANKING is False
    assert offense.MAY_MODIFY_SELECTION is False
    assert offense.API2_USED is False


def test_south_florida_uses_deterministic_ncaa_alias():
    profile = offense._identity_profile("South Florida", "south-florida", "FBS")
    assert profile["team"] == "South Florida"
    assert profile["team_slug"] == "south-fla"
    assert profile["division_context"] == "FBS"
