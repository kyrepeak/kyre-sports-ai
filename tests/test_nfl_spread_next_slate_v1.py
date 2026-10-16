from datetime import date

import pandas as pd

import nfl_spread_next_slate_v1 as next_slate


def _frame(has_games: bool):
    return pd.DataFrame([{"game_id": "1"}]) if has_games else pd.DataFrame()


def test_keeps_selected_day_when_it_has_games(monkeypatch):
    calls = []

    def primary(day):
        calls.append(day)
        return _frame(True), {"request_ok": True}

    monkeypatch.setattr(next_slate, "nflverse_schedule_dates", lambda start, end: [])
    result = next_slate.resolve_spread_slate_date(date(2026, 10, 18), primary)
    assert result["resolved_date"] == date(2026, 10, 18)
    assert result["advanced"] is False
    assert calls == ["2026-10-18"]


def test_empty_friday_jumps_directly_to_sunday_calendar_date(monkeypatch):
    calls = []

    def primary(day):
        calls.append(day)
        return _frame(False), {"request_ok": True}

    monkeypatch.setattr(
        next_slate,
        "nflverse_schedule_dates",
        lambda start, end: [date(2026, 10, 18), date(2026, 10, 19)],
    )
    result = next_slate.resolve_spread_slate_date(date(2026, 10, 16), primary)
    assert result["resolved_date"] == date(2026, 10, 18)
    assert result["advanced"] is True
    assert result["source"] == "schedule"
    assert calls == ["2026-10-16"]


def test_calendar_can_find_far_future_date_without_network_day_scan(monkeypatch):
    calls = []

    def primary(day):
        calls.append(day)
        return _frame(False), {"request_ok": True}

    monkeypatch.setattr(
        next_slate,
        "nflverse_schedule_dates",
        lambda start, end: [date(2027, 1, 10)],
    )
    result = next_slate.resolve_spread_slate_date(date(2026, 10, 16), primary)
    assert result["resolved_date"] == date(2027, 1, 10)
    assert result["source"] == "schedule"
    assert calls == ["2026-10-16"]


def test_schedule_failure_uses_bounded_network_fallback(monkeypatch):
    calls = []

    def primary(day):
        calls.append(day)
        return _frame(day == "2026-10-19"), {"request_ok": True}

    def broken_schedule(start, end):
        raise RuntimeError("calendar unavailable")

    monkeypatch.setattr(next_slate, "nflverse_schedule_dates", broken_schedule)
    result = next_slate.resolve_spread_slate_date(
        date(2026, 10, 16), primary, network_fallback_days=4
    )
    assert result["resolved_date"] == date(2026, 10, 19)
    assert result["source"] == "primary_scan"
    assert calls == ["2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19"]


def test_no_game_result_never_fabricates_a_date(monkeypatch):
    calls = []

    def primary(day):
        calls.append(day)
        return _frame(False), {"request_ok": True}

    monkeypatch.setattr(next_slate, "nflverse_schedule_dates", lambda start, end: [])
    result = next_slate.resolve_spread_slate_date(
        date(2026, 10, 16), primary, network_fallback_days=2
    )
    assert result["state"] == "NO_GAMES"
    assert result["resolved_date"] == date(2026, 10, 16)
    assert calls == ["2026-10-16", "2026-10-17", "2026-10-18"]
