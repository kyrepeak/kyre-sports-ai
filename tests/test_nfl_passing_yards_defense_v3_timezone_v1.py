from __future__ import annotations

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
