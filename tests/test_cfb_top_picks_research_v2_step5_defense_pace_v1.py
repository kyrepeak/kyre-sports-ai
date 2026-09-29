from __future__ import annotations

from datetime import datetime, timezone

import cfb_top_picks_defense_pace_research_v1 as research


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


def _live_defense(team_id, season, cutoff_iso, excluded_event_id):
    base = 18.0 if team_id == "258" else 22.0
    return {
        "games": 4,
        "points_allowed_pg": base,
        "pass_yards_allowed_pg": 205.0,
        "rush_yards_allowed_pg": 120.0,
        "pass_td_allowed_pg": 1.0,
        "rush_td_allowed_pg": 0.75,
        "yards_per_play_allowed": 4.85,
    }, {
        "ready": True,
        "provider": "ESPN exact-event completed-game summaries",
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
            "points_against": 14.0,
        },
        {
            "event_id": f"{team_id}2",
            "date": "2026-09-08T00:00:00Z",
            "date_dt": datetime(2026, 9, 8, tzinfo=timezone.utc),
            "opponent_name": "B",
            "points_for": 35.0,
            "points_against": 21.0,
        },
        {
            "event_id": f"{team_id}3",
            "date": "2026-09-15T00:00:00Z",
            "date_dt": datetime(2026, 9, 15, tzinfo=timezone.utc),
            "opponent_name": "C",
            "points_for": 42.0,
            "points_against": 17.0,
        },
    ], [{"http": 200, "bytes": 1000, "error": ""}]


def _pace(profile, division, team_id, season, observed):
    return {
        "plays_per_game": research._metric(
            72.0, source="NCAA FBS Total Offense", observed_at=observed
        ),
        "seconds_per_play": research._metric(
            25.5, source="NCAA FBS Time of Possession", observed_at=observed
        ),
        "pace_index": {
            **research._metric(
                1.08, source="NCAA FBS baseline", observed_at=observed
            ),
            "label": "FAST",
        },
    }, {"ready": True}


def test_defense_pace_routes_exact_id_live_recent_and_pace(monkeypatch):
    monkeypatch.setattr(research.readable, "_live_defense", _live_defense)
    monkeypatch.setattr(research.readable, "_completed_rows", _rows)
    monkeypatch.setattr(research.readable, "_snapshot_team", lambda team_id: {})
    monkeypatch.setattr(
        research.offense_research,
        "_resolve_division",
        lambda profile: ("FBS", {}),
    )
    monkeypatch.setattr(
        research,
        "_red_zone_defense",
        lambda profile, division, observed: (
            research._metric(
                0.55,
                source="NCAA FBS Red Zone Defense",
                observed_at=observed,
            ),
            {"ready": True},
        ),
    )
    monkeypatch.setattr(
        research,
        "_explosive_defense",
        lambda profile, division, observed: (
            {
                **research._metric(
                    -0.15,
                    source="NCAA FBS defense efficiency",
                    observed_at=observed,
                ),
                "label": "ABOVE-AVG SUPPRESSION",
            },
            {"ready": True},
        ),
    )
    monkeypatch.setattr(research, "_pace_profile", _pace)

    out = research.build_defense_pace_research(_row(), _game(), "2026-10-03")
    assert out["status"] == "READY"
    assert out["away"]["metrics"]["points_allowed_per_game"]["value"] == 18.0
    assert out["home"]["metrics"]["points_allowed_per_game"]["value"] == 22.0
    assert round(out["away"]["metrics"]["recent_points_allowed_avg"]["value"], 6) == round(52 / 3, 6)
    assert out["away"]["metrics"]["yards_per_play_allowed"]["value"] == 4.85
    assert out["away"]["metrics"]["plays_per_game"]["value"] == 72.0
    assert out["away"]["metrics"]["pace_index"]["label"] == "FAST"
    assert len(out["reasoning"]) >= 4


def test_defense_field_snapshot_fallback_is_explicit(monkeypatch):
    monkeypatch.setattr(
        research.readable,
        "_live_defense",
        lambda *args, **kwargs: ({}, {"ready": False, "attempts": []}),
    )
    monkeypatch.setattr(
        research.readable,
        "_snapshot_team",
        lambda team_id: {
            "defense": {
                "points_allowed_pg": 19.5,
                "yards_per_play_allowed": 5.1,
                "pass_yards_allowed_pg": 210.0,
                "rush_yards_allowed_pg": 130.0,
                "pass_td_allowed_pg": 1.2,
                "rush_td_allowed_pg": 0.9,
            }
        },
    )
    monkeypatch.setattr(research.readable, "_completed_rows", _rows)
    monkeypatch.setattr(
        research.offense_research,
        "_resolve_division",
        lambda profile: ("", {}),
    )
    monkeypatch.setattr(
        research,
        "_red_zone_defense",
        lambda profile, division, observed: (
            research._metric(None, source="", observed_at=observed),
            {"ready": False},
        ),
    )
    monkeypatch.setattr(
        research,
        "_explosive_defense",
        lambda profile, division, observed: (
            {
                **research._metric(None, source="", observed_at=observed),
                "label": "UNAVAILABLE",
            },
            {"ready": False},
        ),
    )
    monkeypatch.setattr(research, "_pace_profile", _pace)

    out = research.build_defense_pace_research(_row(), _game(), "2026-10-03")
    metric = out["away"]["metrics"]["points_allowed_per_game"]
    assert metric["value"] == 19.5
    assert metric["status"] == "VERIFIED_FALLBACK"
    assert "snapshot" in metric["source"].lower()
    assert out["status"] == "READY"


def test_material_defense_pace_metrics_carry_provenance(monkeypatch):
    monkeypatch.setattr(research.readable, "_live_defense", _live_defense)
    monkeypatch.setattr(research.readable, "_completed_rows", _rows)
    monkeypatch.setattr(research.readable, "_snapshot_team", lambda team_id: {})
    monkeypatch.setattr(
        research.offense_research,
        "_resolve_division",
        lambda profile: ("FBS", {}),
    )
    monkeypatch.setattr(
        research,
        "_red_zone_defense",
        lambda profile, division, observed: (
            research._metric(0.5, source="NCAA", observed_at=observed),
            {"ready": True},
        ),
    )
    monkeypatch.setattr(
        research,
        "_explosive_defense",
        lambda profile, division, observed: (
            {
                **research._metric(0.1, source="NCAA", observed_at=observed),
                "label": "ABOVE-AVG VULNERABILITY",
            },
            {"ready": True},
        ),
    )
    monkeypatch.setattr(research, "_pace_profile", _pace)
    out = research.build_defense_pace_research(_row(), _game())
    for side in ("away", "home"):
        for metric in out[side]["metrics"].values():
            if metric["value"] is not None:
                assert metric["source"]
                assert metric["observed_at"]


def test_step5_research_is_descriptive_only_and_api2_is_separate():
    assert research.DEFENSE_PACE_RESEARCH_PROJECTION_WEIGHT == 0.0
    assert research.SPORTSBOOK_PROJECTION_WEIGHT == 0.0
    assert research.MAY_MODIFY_PROBABILITY is False
    assert research.MAY_MODIFY_RANKING is False
    assert research.MAY_MODIFY_SELECTION is False
    assert research.API2_USED is False
