from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit_memory_lazy_router_v184 as router


ROOT = Path(__file__).resolve().parents[1]


def test_v184_primes_exact_existing_route_state_without_rerun() -> None:
    state = {
        router.V8_DATE_KEY: date(2026, 9, 19),
        router.V8_DATE_INPUT_KEY: date(2026, 9, 19),
        router.V12_AUTO_RESOLVED_KEY: True,
        "unrelated": "keep",
    }

    today = date(2026, 9, 20)
    router._prime_fresh_passing_yards_state(state, today_et=today)

    assert state[router.SPORT_KEY] == "NFL"
    assert state[router.NFL_MARKET_KEY] == "Passing Yards"
    assert state[router.V8_DATE_KEY] == today
    assert state[router.V8_DATE_INPUT_KEY] == today
    assert router.V12_AUTO_RESOLVED_KEY not in state
    assert state["unrelated"] == "keep"


def test_v184_one_shot_migration_only_targets_stale_active_passing_yards(monkeypatch) -> None:
    state = {
        router.SPORT_KEY: "NFL",
        router.NFL_MARKET_KEY: "Passing Yards",
        router.V8_DATE_KEY: date(2026, 9, 19),
        router.V8_DATE_INPUT_KEY: date(2026, 9, 19),
    }
    monkeypatch.setattr(router.st, "session_state", state)

    assert router._migrate_already_stuck_session_once(today_et=date(2026, 9, 20)) is True
    assert state[router.V8_DATE_KEY] == date(2026, 9, 20)
    assert state[router.V8_DATE_INPUT_KEY] == date(2026, 9, 20)
    assert state[router.MIGRATION_KEY] is True

    # Versioned migration does not keep overwriting later user choices.
    state[router.V8_DATE_INPUT_KEY] = date(2026, 9, 21)
    assert router._migrate_already_stuck_session_once(today_et=date(2026, 9, 20)) is False
    assert state[router.V8_DATE_INPUT_KEY] == date(2026, 9, 21)


def test_v184_does_not_migrate_other_nfl_markets(monkeypatch) -> None:
    state = {
        router.SPORT_KEY: "NFL",
        router.NFL_MARKET_KEY: "Rushing Yards",
        router.V8_DATE_KEY: date(2026, 9, 19),
    }
    monkeypatch.setattr(router.st, "session_state", state)

    assert router._migrate_already_stuck_session_once(today_et=date(2026, 9, 20)) is False
    assert router.V8_DATE_INPUT_KEY not in state


def test_v184_replaces_two_run_handoff_but_preserves_v183() -> None:
    source = (ROOT / "streamlit_memory_lazy_router_v184.py").read_text(encoding="utf-8")

    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v183"
    assert "return prior.render_app()" in source
    assert "st.rerun()" not in source
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False


def test_app_boots_v184() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v184 import record_bootstrap_import_ms, render_app" in app
