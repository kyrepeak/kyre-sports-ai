from nfl_passing_yards_defense_v1 import _completed_event_rows


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


def test_timezone_aware_espn_event_vs_date_only_cutoff_does_not_raise():
    payload = {
        "events": [
            _event("401", "2026-09-20T17:00:00Z"),
            _event("402", "2026-09-21T20:25:00+00:00"),
        ]
    }
    rows = _completed_event_rows(payload, "2026-09-24", max_games=5)
    assert [row["event_id"] for row in rows] == ["402", "401"]


def test_cutoff_day_and_future_events_are_excluded_after_utc_normalization():
    payload = {
        "events": [
            _event("401", "2026-09-23T23:59:59Z"),
            _event("402", "2026-09-24T00:00:00Z"),
            _event("403", "2026-09-25T01:00:00Z"),
        ]
    }
    rows = _completed_event_rows(payload, "2026-09-24", max_games=5)
    assert [row["event_id"] for row in rows] == ["401"]


def test_naive_schedule_timestamp_is_normalized_to_same_utc_clock():
    payload = {"events": [_event("401", "2026-09-23T18:00:00")]}
    rows = _completed_event_rows(payload, "2026-09-24", max_games=5)
    assert [row["event_id"] for row in rows] == ["401"]
