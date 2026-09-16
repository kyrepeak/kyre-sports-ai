from __future__ import annotations

from cfb_moneyline_phoenix_time_v1 import PHOENIX_TZ_NAME, phoenix_kickoff


def test_summer_eastern_kickoff_converts_to_phoenix_without_dst_shift() -> None:
    result = phoenix_kickoff("2026-09-17", "7:30 PM ET")

    assert result == {
        "clock": "4:30 PM MST",
        "clock_with_location": "4:30 PM MST • Phoenix",
        "date": "2026-09-17",
        "timezone": "America/Phoenix",
    }


def test_winter_eastern_kickoff_converts_to_phoenix() -> None:
    result = phoenix_kickoff("2026-12-05", "7:30 PM ET")

    assert result is not None
    assert result["clock"] == "5:30 PM MST"
    assert result["date"] == "2026-12-05"
    assert result["timezone"] == PHOENIX_TZ_NAME


def test_date_rollover_is_preserved_in_phoenix_display() -> None:
    result = phoenix_kickoff("2026-09-18", "1:00 AM ET")

    assert result is not None
    assert result["clock"] == "10:00 PM MST"
    assert result["date"] == "2026-09-17"


def test_tbd_and_bad_inputs_fail_closed() -> None:
    assert phoenix_kickoff("2026-09-17", "TBD") is None
    assert phoenix_kickoff("", "7:30 PM ET") is None
    assert phoenix_kickoff("2026-09-17", "not-a-time") is None
