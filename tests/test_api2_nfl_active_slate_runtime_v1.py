from __future__ import annotations

from datetime import date
import sys
import types

import pandas as pd
import pytest

import nfl_active_slate_runtime_v1 as runtime


def _frame(*states: str) -> pd.DataFrame:
    return pd.DataFrame([{"state": state} for state in states])


def test_fresh_session_starts_auto_and_writes_compatibility_date():
    today = date(2026, 10, 18)
    session = {}
    calls = []

    def loader(day_iso):
        calls.append(day_iso)
        return _frame("pre"), {"request_ok": True}

    out = runtime.prepare_nfl_active_slate(
        session,
        today_et=today,
        primary_loader=loader,
        calendar_dates=lambda *_: [],
        now_monotonic=10.0,
    )
    assert out["state"] == "FOUND"
    assert session[runtime.MODE_KEY] == "AUTO"
    assert session[runtime.ACTIVE_DATE_KEY] == today
    assert session["nfl_v1_date"] == today
    assert session[runtime.STATE_KEY] == "FOUND"
    assert session[runtime.SOURCE_KEY] == "current_verified"
    assert session[runtime.CHECKED_AT_KEY] == 10.0
    assert calls == [today.isoformat()]


def test_current_day_auto_is_rechecked_on_meaningful_rerender():
    today = date(2026, 10, 18)
    session = {}
    calls = []

    def loader(day_iso):
        calls.append(day_iso)
        return _frame("pre"), {"request_ok": True}

    for tick in (10.0, 11.0):
        runtime.prepare_nfl_active_slate(
            session,
            today_et=today,
            primary_loader=loader,
            calendar_dates=lambda *_: [],
            now_monotonic=tick,
        )
    assert calls == [today.isoformat(), today.isoformat()]


def test_verified_future_date_is_reused_without_second_scan():
    today = date(2026, 10, 20)
    future = date(2026, 10, 22)
    session = {}
    calls = []

    def loader(day_iso):
        calls.append(day_iso)
        if day_iso == future.isoformat():
            return _frame("pre"), {"request_ok": True}
        return pd.DataFrame(), {"request_ok": True}

    first = runtime.prepare_nfl_active_slate(
        session,
        today_et=today,
        primary_loader=loader,
        calendar_dates=lambda *_: [future],
        now_monotonic=10.0,
    )
    call_count = len(calls)
    second = runtime.prepare_nfl_active_slate(
        session,
        today_et=today,
        primary_loader=loader,
        calendar_dates=lambda *_: (_ for _ in ()).throw(AssertionError("must reuse")),
        now_monotonic=11.0,
    )
    assert first["resolved_date"] == future
    assert second["resolved_date"] == future
    assert second["source"] == "session_future_reuse"
    assert len(calls) == call_count


def test_unavailable_is_not_cached_and_recovers_next_call():
    today = date(2026, 10, 18)
    session = {}
    attempts = {"count": 0}

    def loader(_day_iso):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return pd.DataFrame(), {"request_ok": False, "error": "timeout"}
        return _frame("pre"), {"request_ok": True}

    first = runtime.prepare_nfl_active_slate(session, today_et=today, primary_loader=loader, calendar_dates=lambda *_: [])
    second = runtime.prepare_nfl_active_slate(session, today_et=today, primary_loader=loader, calendar_dates=lambda *_: [])
    assert first["state"] == "UNAVAILABLE"
    assert second["state"] == "FOUND"
    assert attempts["count"] == 2


class _FakeStreamlit(types.ModuleType):
    def __init__(self, session):
        super().__init__("streamlit")
        self.session_state = session
        self.calls = []

    def date_input(self, label, *args, **kwargs):
        self.calls.append((label, args, dict(kwargs)))
        key = kwargs.get("key")
        if key and key in self.session_state:
            return self.session_state[key]
        if "value" in kwargs:
            return kwargs["value"]
        return args[0] if args else None


def _install_fake_streamlit(monkeypatch, session):
    fake = _FakeStreamlit(session)
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    return fake


def test_new_nfl_date_widget_is_seeded_from_universal_date(monkeypatch):
    active = date(2026, 10, 18)
    stale_default = date(2026, 10, 17)
    session = {runtime.MODE_KEY: "AUTO", runtime.ACTIVE_DATE_KEY: active, "nfl_v1_date": active}
    fake = _install_fake_streamlit(monkeypatch, session)

    with runtime.install_nfl_date_input_bridge(session):
        out = fake.date_input("NFL Passing Yards slate date", value=stale_default, key="nfl_passing_yards_v8_date_input")

    assert out == active
    assert session["nfl_passing_yards_v8_date_input"] == active


def test_user_widget_change_enters_manual_mode(monkeypatch):
    active = date(2026, 10, 18)
    chosen = date(2026, 10, 25)
    key = "nfl_spread_v4_date_input"
    seed_key = runtime.bridge_seed_key(key)
    session = {
        runtime.MODE_KEY: "AUTO",
        runtime.ACTIVE_DATE_KEY: active,
        "nfl_v1_date": active,
        key: chosen,
        seed_key: active,
    }
    fake = _install_fake_streamlit(monkeypatch, session)

    with runtime.install_nfl_date_input_bridge(session):
        out = fake.date_input("NFL Spread slate date", value=active, key=key)

    assert out == chosen
    assert session[runtime.MODE_KEY] == "MANUAL"
    assert session[runtime.MANUAL_DATE_KEY] == chosen
    assert session["nfl_v1_date"] == chosen


def test_manual_mode_seeds_a_different_nfl_market_widget(monkeypatch):
    manual = date(2026, 9, 20)
    session = {
        runtime.MODE_KEY: "MANUAL",
        runtime.MANUAL_DATE_KEY: manual,
        "nfl_v1_date": manual,
    }
    fake = _install_fake_streamlit(monkeypatch, session)

    with runtime.install_nfl_date_input_bridge(session):
        out = fake.date_input("NFL Game Totals slate date", value=date(2026, 10, 18), key="nfl_game_totals_v8_date_input")

    assert out == manual
    assert session["nfl_game_totals_v8_date_input"] == manual


def test_non_nfl_date_widget_delegates_unchanged(monkeypatch):
    original = date(2026, 10, 18)
    session = {runtime.MODE_KEY: "AUTO", runtime.ACTIVE_DATE_KEY: date(2026, 10, 19)}
    fake = _install_fake_streamlit(monkeypatch, session)

    with runtime.install_nfl_date_input_bridge(session):
        out = fake.date_input("CFB slate date", value=original, key="cfb_game_total_date")

    assert out == original
    assert "cfb_game_total_date" not in session
    assert fake.calls[-1][2]["value"] == original


def test_bridge_always_restores_native_date_input(monkeypatch):
    session = {runtime.MODE_KEY: "AUTO", runtime.ACTIVE_DATE_KEY: date(2026, 10, 18)}
    fake = _install_fake_streamlit(monkeypatch, session)
    original = fake.date_input
    with pytest.raises(RuntimeError):
        with runtime.install_nfl_date_input_bridge(session):
            assert fake.date_input != original
            raise RuntimeError("boom")
    assert fake.date_input == original


def test_cleared_nfl_state_starts_auto_again():
    today = date(2026, 10, 18)
    session = {
        runtime.MODE_KEY: "MANUAL",
        runtime.MANUAL_DATE_KEY: date(2026, 9, 1),
        "nfl_v1_date": date(2026, 9, 1),
    }
    for key in list(session):
        if key.startswith("nfl_"):
            session.pop(key)

    runtime.prepare_nfl_active_slate(
        session,
        today_et=today,
        primary_loader=lambda _day: (_frame("pre"), {"request_ok": True}),
        calendar_dates=lambda *_: [],
    )
    assert session[runtime.MODE_KEY] == "AUTO"
    assert session["nfl_v1_date"] == today
