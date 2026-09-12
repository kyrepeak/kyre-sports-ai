from __future__ import annotations

import math

import nfl_passing_yards_defense_v3 as defense_v3


def _event(event_id: str, when: str, completed: bool = True) -> dict:
    return {
        "id": event_id,
        "date": when,
        "competitions": [
            {
                "status": {
                    "type": {
                        "completed": completed,
                        "state": "post" if completed else "pre",
                    }
                }
            }
        ],
    }


def test_completed_event_rows_utc_handles_zulu_dates_against_plain_cutoff():
    payload = {
        "events": [
            _event("401772700", "2025-12-28T18:00:00Z"),
            _event("401772701", "2026-09-13T17:00:00Z"),
            _event("401772702", "2025-12-21T18:00:00+00:00"),
            _event("not-an-id", "2025-12-14T18:00:00Z"),
            _event("401772703", "2025-12-14T18:00:00Z", completed=False),
        ]
    }

    rows = defense_v3._completed_event_rows_utc(payload, "2026-09-13", max_games=5)

    assert [row["event_id"] for row in rows] == ["401772700", "401772702"]
    assert all(str(row["date"].tzinfo) for row in rows)


def test_completed_event_rows_utc_respects_max_games_and_newest_first():
    payload = {
        "events": [
            _event("401772710", "2025-09-01T17:00:00Z"),
            _event("401772711", "2025-09-08T17:00:00Z"),
            _event("401772712", "2025-09-15T17:00:00Z"),
        ]
    }

    rows = defense_v3._completed_event_rows_utc(payload, "2026-09-13", max_games=2)

    assert [row["event_id"] for row in rows] == ["401772712", "401772711"]


def test_recent_defense_parser_uses_display_value_when_espn_primary_is_placeholder():
    # Mirrors the live ESPN team box-score shape seen in the 2025 NFL summaries:
    # netPassingYards has a numeric value, while completionAttempts uses value '-'
    # and stores the exact 24/35 composite in displayValue.
    summary = {
        "boxscore": {
            "teams": [
                {
                    "team": {"id": "29", "displayName": "Carolina Panthers"},
                    "statistics": [
                        {
                            "name": "netPassingYards",
                            "label": "Passing",
                            "value": 266.0,
                            "displayValue": "266",
                        },
                        {
                            "name": "completionAttempts",
                            "label": "Comp/Att",
                            "value": "-",
                            "displayValue": "24/35",
                        },
                    ],
                },
                {"team": {"id": "27", "displayName": "Tampa Bay Buccaneers"}, "statistics": []},
            ]
        }
    }

    row = defense_v3.parse_recent_defense_game(summary, "27")

    assert row["passing_yards_allowed"] == 266.0
    assert row["completions_allowed"] == 24.0
    assert row["attempts_allowed"] == 35.0
    assert math.isclose(row["completion_pct_allowed"], 100.0 * 24.0 / 35.0)
    assert math.isclose(row["yards_per_attempt_allowed"], 266.0 / 35.0)
