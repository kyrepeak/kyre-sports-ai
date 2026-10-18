from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from nfl_active_slate_controller_v1 import classify_loaded_slate, resolve_active_slate


def _frame(*states: str) -> pd.DataFrame:
    return pd.DataFrame([{"game_id": str(i + 1), "state": state} for i, state in enumerate(states)])


def _loader(mapping):
    calls = []

    def load(day_iso: str):
        calls.append(day_iso)
        value = mapping.get(day_iso)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return pd.DataFrame(), {"request_ok": True, "games": 0}
        if isinstance(value, tuple):
            return value
        return value, {"request_ok": True, "games": len(value)}

    return load, calls


def test_today_with_pre_game_stays_today():
    today = date(2026, 10, 18)
    load, calls = _loader({today.isoformat(): _frame("pre")})
    out = resolve_active_slate(today, load, lambda *_: [])
    assert out["state"] == "FOUND"
    assert out["resolved_date"] == today
    assert out["advanced"] is False
    assert calls == [today.isoformat()]


def test_today_with_live_game_stays_today():
    today = date(2026, 10, 18)
    load, _ = _loader({today.isoformat(): _frame("in")})
    out = resolve_active_slate(today, load, lambda *_: [])
    assert out["resolved_date"] == today
    assert out["reason"] == "current_slate_active"


def test_mixed_post_and_pre_stays_today():
    today = date(2026, 10, 18)
    load, _ = _loader({today.isoformat(): _frame("post", "pre")})
    out = resolve_active_slate(today, load, lambda *_: [])
    assert out["state"] == "FOUND"
    assert out["resolved_date"] == today


def test_all_post_rolls_to_next_verified_date():
    today = date(2026, 10, 18)
    nxt = date(2026, 10, 19)
    load, calls = _loader({today.isoformat(): _frame("post", "post"), nxt.isoformat(): _frame("pre")})
    out = resolve_active_slate(today, load, lambda *_: [nxt])
    assert out["resolved_date"] == nxt
    assert out["source"] == "calendar_verified"
    assert out["advanced"] is True
    assert calls == [today.isoformat(), nxt.isoformat()]


def test_empty_today_rolls_to_next_verified_date():
    today = date(2026, 10, 20)
    nxt = date(2026, 10, 22)
    load, _ = _loader({nxt.isoformat(): _frame("scheduled")})
    out = resolve_active_slate(today, load, lambda *_: [nxt])
    assert out["resolved_date"] == nxt


def test_calendar_candidate_must_verify_before_selection():
    today = date(2026, 10, 20)
    stale = date(2026, 10, 21)
    real = date(2026, 10, 22)
    load, calls = _loader({stale.isoformat(): _frame("post"), real.isoformat(): _frame("pre")})
    out = resolve_active_slate(today, load, lambda *_: [stale, real])
    assert out["resolved_date"] == real
    assert stale.isoformat() in calls and real.isoformat() in calls


def test_unknown_state_fails_closed_without_rollover():
    today = date(2026, 10, 18)
    nxt = date(2026, 10, 19)
    load, calls = _loader({today.isoformat(): _frame("mystery"), nxt.isoformat(): _frame("pre")})
    out = resolve_active_slate(today, load, lambda *_: [nxt])
    assert out["state"] == "UNAVAILABLE"
    assert out["resolved_date"] is None
    assert calls == [today.isoformat()]


def test_calendar_failure_uses_bounded_primary_fallback():
    today = date(2026, 10, 20)
    target = today + timedelta(days=3)
    load, calls = _loader({target.isoformat(): _frame("pre")})

    def broken_calendar(*_):
        raise RuntimeError("calendar unavailable")

    out = resolve_active_slate(today, load, broken_calendar, network_fallback_days=5)
    assert out["resolved_date"] == target
    assert out["source"] == "primary_fallback"
    assert len(calls) == 4  # today + 3 bounded forward probes


def test_provider_and_calendar_failure_is_retryable_unavailable():
    today = date(2026, 10, 20)

    def load(_day):
        return pd.DataFrame(), {"request_ok": False, "error": "timeout"}

    out = resolve_active_slate(today, load, lambda *_: (_ for _ in ()).throw(RuntimeError("calendar down")))
    assert out["state"] == "UNAVAILABLE"
    assert out["resolved_date"] is None
    assert out["reason"] == "current_slate_unavailable"


def test_irregular_schedule_date_requires_no_weekday_logic():
    today = date(2026, 12, 23)  # Wednesday
    target = date(2026, 12, 25)  # Friday irregular slate
    load, _ = _loader({target.isoformat(): _frame("pre")})
    out = resolve_active_slate(today, load, lambda *_: [target])
    assert out["resolved_date"] == target


def test_classify_loaded_slate_supports_canonical_status_aliases():
    assert classify_loaded_slate(_frame("scheduled"), {"request_ok": True}) == "ACTIVE"
    assert classify_loaded_slate(_frame("live"), {"request_ok": True}) == "ACTIVE"
    assert classify_loaded_slate(_frame("completed"), {"request_ok": True}) == "EXHAUSTED"
