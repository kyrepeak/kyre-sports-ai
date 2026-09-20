from __future__ import annotations

import json

import cfb_game_total_game_evidence_v1 as game_evidence
import cfb_game_total_model_input_v1 as model_input
import cfb_game_total_step3_form_v1 as step3


def _local_snapshot():
    return json.loads(
        step3.STEP3_RUNTIME_SNAPSHOT_PATH.read_text(encoding="utf-8")
    )


def test_step6_selector_finds_exact_purdue_ucla_without_upstream_espn_ids():
    payload = _local_snapshot()
    selected = step3._runtime_v2_selected_row(
        payload,
        {
            "away_team": "Purdue",
            "home_team": "UCLA",
            "game_date": "2026-09-19",
        },
        "2026-09-19",
    )
    assert selected["event_id"] == "401858458"
    assert selected["away"]["team_id"] == "2509"
    assert selected["home"]["team_id"] == "26"


def test_step6_local_snapshot_repairs_model_profiles_without_remote_identity(monkeypatch):
    payload = _local_snapshot()
    monkeypatch.setattr(
        model_input.runtime_owner.runtime_snapshot_v2,
        "_load_v2_snapshot",
        lambda: payload,
    )
    profiles, diag = model_input.enrich_matchup_model_profiles(
        {
            "away_team": "Purdue",
            "home_team": "UCLA",
            "game_date": "2026-09-19",
        },
        "2026-09-19",
        {"away": {}, "home": {}},
    )
    assert diag["selected_event_found"] is True
    assert diag["event_id"] == "401858458"
    assert set(diag["repaired_sides"]) == {"away", "home"}
    assert profiles["away"]["record"]["games"] == 2
    assert profiles["home"]["record"]["games"] == 2
    assert profiles["away"]["ppg"] == 40.0
    assert profiles["away"]["points_allowed_pg"] == 28.5
    assert profiles["home"]["ppg"] == 36.5
    assert profiles["home"]["points_allowed_pg"] == 17.0


def test_step6_checked_in_environment_cache_works_with_network_disabled(monkeypatch):
    def network_forbidden(*args, **kwargs):
        raise AssertionError("network fallback must not run for verified cached event")

    monkeypatch.setattr(
        game_evidence.environment_owner,
        "_fetch_scoreboard",
        network_forbidden,
    )
    monkeypatch.setattr(
        game_evidence.environment_owner,
        "_fetch_summary",
        network_forbidden,
    )
    enriched, diag = game_evidence.enrich_game_evidence(
        {
            "away_team": "Purdue",
            "home_team": "UCLA",
            "game_date": "2026-09-19",
        }
    )
    assert diag["data_green"] is True
    assert diag["verified_cache_used"] is True
    assert enriched["venue"] == "Rose Bowl"
    assert enriched["venue_location"] == "Pasadena, CA"
    assert enriched["temperature"] == 73.0
    assert enriched["weather"] == "0% precipitation"
    assert enriched["wind"] == "5 mph gusts"
    assert enriched["kickoff_iso"] == "2026-09-19T23:00:00-04:00"
    assert enriched["status"] == "Scheduled"
