from __future__ import annotations

from pathlib import Path

import pandas as pd

import mlb_schedule_v32 as schedule


SLATE_SOURCE = Path("mlb_slate_hub_v32.py")


def _frame(day: str, away_id: int = 111, home_id: int = 147):
    return pd.DataFrame(
        [
            {
                "game_pk": 900001,
                "game_date": day,
                "verified": True,
                "venue_name": "Postseason Park",
                "away_team_id": away_id,
                "away_team": "Boston Red Sox",
                "home_team_id": home_id,
                "home_team": "New York Yankees",
                "away_pitcher_id": None,
                "away_pitcher": "TBD",
                "home_pitcher_id": None,
                "home_pitcher": "TBD",
                "first_pitch_et": "8:00 PM",
                "status": "Scheduled",
                "schedule_source": "MLB Stats API V3.2",
                "external_game_id": "",
            }
        ],
        columns=schedule.COLUMNS,
    )


def test_next_games_after_skips_off_day_and_returns_first_verified_slate(monkeypatch):
    calls = []

    def fake_load(day):
        calls.append(str(day))
        if str(day) == "2026-09-29":
            frame = _frame("2026-09-29")
            return frame, {
                "version": "V3.2",
                "date": "2026-09-29",
                "source": "MLB Stats API requests",
                "games": 1,
                "attempts": [],
            }
        return schedule._empty(), {
            "version": "V3.2",
            "date": str(day),
            "source": "none",
            "games": 0,
            "attempts": [],
        }

    monkeypatch.setattr(schedule, "load_with_diagnostics", fake_load)

    frame, diag = schedule.next_games_after("2026-09-28", max_days=7)

    assert calls == ["2026-09-29"]
    assert len(frame) == 1
    assert frame.iloc[0]["game_date"] == "2026-09-29"
    assert diag["requested_date"] == "2026-09-28"
    assert diag["date"] == "2026-09-29"
    assert diag["auto_advanced"] is True
    assert diag["scan_days"] == 1


def test_next_games_after_never_fabricates_when_window_is_empty(monkeypatch):
    calls = []

    def fake_load(day):
        calls.append(str(day))
        return schedule._empty(), {
            "version": "V3.2",
            "date": str(day),
            "source": "none",
            "games": 0,
            "attempts": [],
        }

    monkeypatch.setattr(schedule, "load_with_diagnostics", fake_load)

    frame, diag = schedule.next_games_after("2026-09-28", max_days=3)

    assert frame.empty
    assert calls == ["2026-09-29", "2026-09-30", "2026-10-01"]
    assert diag["auto_advanced"] is False
    assert diag["games"] == 0
    assert diag["scan_days"] == 3


def test_official_postseason_payload_is_accepted_without_regular_season_filter():
    payload = {
        "dates": [
            {
                "date": "2026-09-29",
                "games": [
                    {
                        "gamePk": 900029,
                        "officialDate": "2026-09-29",
                        "gameType": "F",
                        "gameDate": "2026-09-30T00:00:00Z",
                        "venue": {"name": "Yankee Stadium"},
                        "status": {"detailedState": "Scheduled"},
                        "teams": {
                            "away": {
                                "team": {"id": 111, "name": "Boston Red Sox"},
                                "probablePitcher": {},
                            },
                            "home": {
                                "team": {"id": 147, "name": "New York Yankees"},
                                "probablePitcher": {},
                            },
                        },
                    }
                ],
            }
        ]
    }

    frame = schedule._parse_mlb(payload, "2026-09-29")

    assert len(frame) == 1
    assert int(frame.iloc[0]["game_pk"]) == 900029
    assert frame.iloc[0]["away_team"] == "Boston Red Sox"
    assert frame.iloc[0]["home_team"] == "New York Yankees"
    assert frame.iloc[0]["verified"] == True


def test_slate_wrapper_promotes_next_slate_before_provider_diagnostics():
    text = SLATE_SOURCE.read_text(encoding="utf-8")
    render_body = text.split("def render_slate_hub", 1)[1]

    assert "schedule.next_games_after(day, max_days=7)" in render_body
    assert "MLB Postseason" in render_body
    assert "NEXT SLATE" in render_body
    diagnostic_marker = '<span class="mlb32-bad">provider diagnostics</span>'
    assert render_body.index("schedule.next_games_after(day, max_days=7)") < render_body.index(diagnostic_marker)
