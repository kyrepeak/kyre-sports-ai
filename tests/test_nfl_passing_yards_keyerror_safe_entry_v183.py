from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit_memory_lazy_router_v183 as router


ROOT = Path(__file__).resolve().parents[1]


def test_v183_primes_widget_state_without_deleting_widget_keys() -> None:
    state = {
        router.V8_DATE_KEY: date(2026, 9, 19),
        router.V8_DATE_INPUT_KEY: date(2026, 9, 19),
        "nfl_passing_yards_v8_matchup": "stale-matchup",
        router.V12_AUTO_RESOLVED_KEY: True,
        "unrelated": "keep",
    }

    today = date(2026, 9, 20)
    result = router._prime_passing_yards_entry_state(state, today_et=today)

    assert result == today
    assert state[router.V8_DATE_KEY] == today
    assert state[router.V8_DATE_INPUT_KEY] == today

    # Widget-owned matchup state is intentionally not deleted by V183.
    assert state["nfl_passing_yards_v8_matchup"] == "stale-matchup"

    # Only the non-widget one-shot controller flag is cleared.
    assert router.V12_AUTO_RESOLVED_KEY not in state
    assert state["unrelated"] == "keep"


def test_v183_bypasses_broken_v182_and_preserves_v181() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v181"
    assert router.REPLACED_BROKEN_ROUTER == "streamlit_memory_lazy_router_v182"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False


def test_v183_only_primes_exact_nfl_passing_yards_jump() -> None:
    assert router._passing_yards_jump_requested("NFL", "Passing Yards") is True
    assert router._passing_yards_jump_requested("NFL", "Rushing Yards") is False
    assert router._passing_yards_jump_requested("CFB", "Passing Yards") is False


def test_app_boots_v183() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v183 import record_bootstrap_import_ms, render_app" in app
