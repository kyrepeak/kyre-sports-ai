from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "nba_spread_schedule_v1.py"
PAGE = ROOT / "nba_spread_page_v1.py"
EXECUTION_PLAN = ROOT / "devsystem" / "execution_plans" / "nba-spread-step3-schedule-phoenix-v1.json"
RUNLESS_PLAN = ROOT / "devsystem" / "runless_proof_plans" / "nba-spread-step3-schedule-phoenix-v1.json"


def _load_schedule():
    assert MODULE.exists(), "NBA Spread Step-3 schedule module must exist"
    spec = importlib.util.spec_from_file_location("nba_spread_schedule_v1", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _official_payload(*, away: str = "LAL", home: str = "PHX", status: int = 1, status_text: str = "7:00 pm ET"):
    return {
        "leagueSchedule": {
            "gameDates": [
                {
                    "gameDate": "10/12/2026 00:00:00",
                    "games": [
                        {
                            "gameId": "0012600001",
                            "gameDateTimeUTC": "2026-10-13T02:00:00Z",
                            "gameStatus": status,
                            "gameStatusText": status_text,
                            "arenaName": "Footprint Center",
                            "awayTeam": {
                                "teamTricode": away,
                                "teamCity": "Los Angeles" if away == "LAL" else "Golden State",
                                "teamName": "Lakers" if away == "LAL" else "Warriors",
                            },
                            "homeTeam": {
                                "teamTricode": home,
                                "teamCity": "Phoenix",
                                "teamName": "Suns",
                            },
                        }
                    ],
                }
            ]
        }
    }


def _espn_payload(*, away: str = "LAL", home: str = "PHX", state: str = "pre", detail: str = "10/12 - 10:00 PM EDT"):
    return {
        "events": [
            {
                "id": "401810001",
                "date": "2026-10-13T02:00:00Z",
                "status": {"type": {"state": state, "description": detail}},
                "competitions": [
                    {
                        "date": "2026-10-13T02:00:00Z",
                        "venue": {"fullName": "Footprint Center"},
                        "competitors": [
                            {
                                "homeAway": "away",
                                "team": {
                                    "abbreviation": away,
                                    "displayName": "Los Angeles Lakers" if away == "LAL" else "Golden State Warriors",
                                },
                            },
                            {
                                "homeAway": "home",
                                "team": {"abbreviation": home, "displayName": "Phoenix Suns"},
                            },
                        ],
                    }
                ],
            }
        ]
    }


def test_step3_rolling_window_uses_phoenix_calendar_not_utc_calendar():
    schedule = _load_schedule()
    now_utc = datetime(2026, 10, 12, 6, 30, tzinfo=timezone.utc)
    assert schedule.rolling_phoenix_dates(now_utc=now_utc, days=7) == (
        "2026-10-11",
        "2026-10-12",
        "2026-10-13",
        "2026-10-14",
        "2026-10-15",
        "2026-10-16",
        "2026-10-17",
    )


def test_step3_two_sources_reconcile_to_one_canonical_phoenix_game():
    schedule = _load_schedule()
    window = ("2026-10-12",)
    official = schedule.parse_nba_official(_official_payload(), window)
    espn = schedule.parse_espn(_espn_payload(), window)
    result = schedule.reconcile_verified_schedule(official, espn, window)

    assert result["verification"] == "VERIFIED"
    assert result["source_agreement"] == 2
    assert len(result["games"]) == 1
    game = result["games"][0]
    assert game["game_key"] == "LAL@PHX:2026-10-12"
    assert game["game_date_phoenix"] == "2026-10-12"
    assert game["tip_iso_phoenix"].endswith("-07:00")
    assert game["tip_phoenix"] == "7:00 PM MST"
    assert game["status"] == "UPCOMING"
    assert game["confirming_sources"] == ["NBA Official", "ESPN NBA"]


def test_step3_provider_conflict_fails_closed_instead_of_inventing_a_slate():
    schedule = _load_schedule()
    window = ("2026-10-12",)
    official = schedule.parse_nba_official(_official_payload(away="LAL"), window)
    espn = schedule.parse_espn(_espn_payload(away="GSW"), window)
    result = schedule.reconcile_verified_schedule(official, espn, window)

    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "PROVIDER_CONFLICT"
    assert result["games"] == []


def test_step3_unknown_team_identity_is_rejected_not_guessed():
    schedule = _load_schedule()
    window = ("2026-10-12",)
    official = schedule.parse_nba_official(_official_payload(away="ZZZ"), window)
    assert official == []


def test_step3_game_state_normalizes_upcoming_live_and_final():
    schedule = _load_schedule()
    assert schedule.normalize_game_status("Scheduled", "pre", 1) == "UPCOMING"
    assert schedule.normalize_game_status("In Progress", "in", 2) == "LIVE"
    assert schedule.normalize_game_status("Final", "post", 3) == "FINAL"


def test_step3_page_consumes_verified_schedule_without_betting_or_model_scope():
    source = PAGE.read_text(encoding="utf-8")
    lowered = source.lower()
    assert "load_verified_nba_schedule" in source
    assert 'data-testid="nba-spread-step3-schedule-active"' in source
    assert "Phoenix, Arizona" in source
    assert "Live / Final" in source
    assert "fair spread" not in lowered
    assert "cover probability" not in lowered
    assert "public bet" not in lowered
    assert "sportsbook_projection_influence = 0.0" in lowered


def test_step3_control_plane_contract_is_runless_and_scope_locked():
    assert EXECUTION_PLAN.exists(), "Step-3 execution plan must exist"
    assert RUNLESS_PLAN.exists(), "Step-3 Runless proof plan must exist"
    execution = json.loads(EXECUTION_PLAN.read_text(encoding="utf-8"))
    runless = json.loads(RUNLESS_PLAN.read_text(encoding="utf-8"))

    assert execution["workstream"] == "nba-spread-two-page-v1"
    assert execution["source_main_sha"] == "30e803ea943091d07e760d9d4e003e110cbc29ed"
    assert execution["sportsbook_projection_influence"] == 0.0
    assert execution["step2a"]["one_authoritative_proof_chain"] is True
    assert execution["step2a"]["other_sports_may_be_modified"] is False
    assert execution["step2a"]["existing_nba_workstreams_may_be_modified"] is False
    assert runless["mode"] == "runless"
    assert runless["required_check"] == "runless-final-gate"
    assert runless["github_actions_fallback"] == 0
