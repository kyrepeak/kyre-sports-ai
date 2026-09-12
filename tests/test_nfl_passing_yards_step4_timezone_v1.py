from __future__ import annotations

import nfl_passing_yards_hub_v17 as hub_v17
import nfl_passing_yards_hub_v18 as hub_v18
import nfl_passing_yards_hub_v19 as hub_v19
import nfl_passing_yards_pressure_v1 as pressure_v1
import nfl_passing_yards_pressure_v2 as pressure_v2
import nfl_passing_yards_pressure_v3 as pressure_v3


def _aware_schedule():
    return {
        "events": [
            {
                "id": "401772510",
                "date": "2025-12-28T18:00:00Z",
                "competitions": [
                    {"status": {"type": {"completed": True, "state": "post"}}}
                ],
            }
        ]
    }


def test_pressure_v3_accepts_timezone_aware_espn_events_with_plain_cutoff(monkeypatch):
    original_defense_module = pressure_v1.defense

    monkeypatch.setattr(
        original_defense_module,
        "_team_stats_payload",
        lambda year, season_type, team_id: ({}, {"ok": True, "http": 200}),
    )
    monkeypatch.setattr(
        original_defense_module,
        "_team_schedule_payload",
        lambda year, season_type, team_id: (_aware_schedule(), {"ok": True, "http": 200}),
    )
    monkeypatch.setattr(
        original_defense_module,
        "_summary_payload",
        lambda event_id: ({}, {"ok": False, "http": 200}),
    )

    row = pressure_v3.build_pressure_matchup(
        "27",
        "Tampa Bay Buccaneers",
        "4",
        "Cincinnati Bengals",
        2026,
        2,
        "2026-09-13",
    )

    assert isinstance(row, dict)
    assert row["timezone_normalization"] == "UTC"
    assert row["projection_adjustment"] == 0.0
    assert row["sportsbook_influence"] == 0.0
    assert pressure_v1.defense is original_defense_module


def test_v19_routes_v17_pressure_bridge_to_v3_without_mutating_real_v2(monkeypatch):
    original_v17_pressure_module = hub_v17.pressure_v2
    real_v2_builder = pressure_v2.build_pressure_matchup
    observed = {}

    def fake_render():
        observed["v17_builder"] = hub_v17.pressure_v2.build_pressure_matchup
        observed["real_v2_builder"] = pressure_v2.build_pressure_matchup

    monkeypatch.setattr(hub_v18, "render_nfl_passing_yards_hub", fake_render)

    hub_v19.render_nfl_passing_yards_hub()

    assert observed["v17_builder"] is pressure_v3.build_pressure_matchup
    assert observed["real_v2_builder"] is real_v2_builder
    assert hub_v17.pressure_v2 is original_v17_pressure_module
