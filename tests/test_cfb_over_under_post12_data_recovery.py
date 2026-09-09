"""Regression checks for post-12 multi-source CFB O/U data recovery."""
from __future__ import annotations

import copy

import cfb_over_under_data_recovery_v1 as recovery


def _game():
    return {
        "game_date": "2026-09-10",
        "kickoff_iso": "2026-09-10T20:00:00-04:00",
        "away_team": "Florida A&M",
        "home_team": "Miami (FL)",
    }


def _event(event_id="401858213", date="2026-09-11T00:00:00Z"):
    return {
        "id": event_id,
        "date": date,
        "competitions": [{
            "id": event_id,
            "date": date,
            "competitors": [
                {"homeAway": "away", "team": {"id": "50", "displayName": "Florida A&M Rattlers"}},
                {"homeAway": "home", "team": {"id": "2390", "displayName": "Miami Hurricanes"}},
            ],
        }],
    }


def test_slug_guesses_cover_famu_and_miami():
    assert recovery._slug_guess("Florida A&M") == "florida-am"
    assert recovery._slug_guess("Miami (FL)") == "miami-fl"
    assert recovery._slug_guess("Texas A&M") == "texas-am"


def test_team_id_overrides_cover_ambiguous_live_matchup(monkeypatch):
    monkeypatch.setattr(recovery, "_fetch_espn_teams", lambda: {})
    assert recovery._resolve_team_id_from_directory("Florida A&M") == "50"
    assert recovery._resolve_team_id_from_directory("Miami (FL)") == "2390"


def test_find_event_requires_exact_team_pair_and_near_date(monkeypatch):
    payload = {"events": [
        _event(),
        {
            "id": "wrong",
            "date": "2026-09-11T00:00:00Z",
            "competitions": [{
                "id": "wrong",
                "competitors": [
                    {"homeAway": "away", "team": {"id": "50"}},
                    {"homeAway": "home", "team": {"id": "999"}},
                ],
            }],
        },
    ]}
    monkeypatch.setattr(
        recovery.frozen_history,
        "_fetch_team_schedule",
        lambda team_id, season: (payload, []),
    )
    found = recovery._find_event_from_team_schedules(_game(), "50", "2390")
    assert found["id"] == "401858213"


def test_winsipedia_parser_reads_game_rows(monkeypatch):
    html = """
    <table>
      <tr><th>Date</th><th>Location</th><th>Florida A&M</th><th>Miami (FL)</th></tr>
      <tr><td>2024-09-07</td><td>Miami Gardens, FL</td><td>9</td><td>56</td></tr>
      <tr><td>2016-09-03</td><td>Miami Gardens, FL</td><td>3</td><td>70</td></tr>
    </table>
    """
    class Resp:
        status_code = 200
        text = html
    monkeypatch.setattr(recovery.requests, "get", lambda *a, **k: Resp())
    out = recovery._fetch_winsipedia_games.__wrapped__(
        "Florida A&M", "Miami (FL)"
    )
    assert out["ready"] is True
    assert out["meetings"] == 2
    assert out["away_wins"] == 0
    assert out["home_wins"] == 2
    assert out["latest"]["combined_total"] == 65
    assert out["source"] == "Winsipedia"
    assert out["projection_weight"] == 0.0
    assert out["selection_weight"] == 0.0


def test_environment_recovery_uses_team_schedule_after_primary_gate(monkeypatch):
    monkeypatch.setattr(
        recovery,
        "_FROZEN_ENV_BUILD",
        lambda *a, **k: {
            "ready": True,
            "model_ready": False,
            "reason": "exact same-date ESPN event identity is unavailable",
            "diagnostics": {},
        },
    )
    monkeypatch.setattr(
        recovery,
        "resolve_espn_team_ids",
        lambda *a, **k: {
            "ready": True,
            "away_team_id": "50",
            "home_team_id": "2390",
            "source": "ESPN team directory",
        },
    )
    monkeypatch.setattr(
        recovery,
        "_find_event_from_team_schedules",
        lambda *a, **k: _event(),
    )
    monkeypatch.setattr(
        recovery,
        "_rebuild_environment_from_event",
        lambda base,event,away_id,home_id,source: {
            **base,
            "model_ready": True,
            "event_id": event["id"],
            "away_espn_team_id": away_id,
            "home_espn_team_id": home_id,
            "recovery_used": True,
            "recovery_source": source,
        },
    )
    out = recovery.build_environment_engine(_game(), {}, {})
    assert out["model_ready"] is True
    assert out["event_id"] == "401858213"
    assert out["away_espn_team_id"] == "50"
    assert out["home_espn_team_id"] == "2390"
    assert out["recovery_used"] is True


def test_history_recovery_attaches_external_all_time_context(monkeypatch):
    monkeypatch.setattr(
        recovery,
        "_FROZEN_HISTORY_BUILD",
        lambda *a, **k: {
            "model_ready": False,
            "reason": "history unavailable",
            "away_recent": {},
            "home_recent": {},
            "head_to_head": {},
        },
    )
    monkeypatch.setattr(
        recovery,
        "_fetch_winsipedia_games",
        lambda *a, **k: {
            "ready": True,
            "source": "Winsipedia",
            "meetings": 12,
            "away_wins": 1,
            "home_wins": 11,
            "avg_combined_total": 55.3,
            "latest": {
                "date": "2024-09-07",
                "away_points": 9,
                "home_points": 56,
                "combined_total": 65,
            },
        },
    )
    env = {
        "away_espn_team_id": "50",
        "home_espn_team_id": "2390",
    }
    out = recovery.build_history_engine(
        _game(), {}, {}, step9_environment=env
    )
    assert out["all_time_head_to_head"]["meetings"] == 12
    assert out["external_history_source_used"] is True
    assert out["context_ready"] is True
    assert out["external_history_projection_weight"] == 0.0
    assert out["external_history_selection_weight"] == 0.0
