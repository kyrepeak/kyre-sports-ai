from __future__ import annotations

from pathlib import Path

import streamlit_memory_lazy_router_v182 as router


ROOT = Path(__file__).resolve().parents[1]


def test_v182_clears_only_passing_yards_entry_state() -> None:
    state = {
        "nfl_passing_yards_v8_date": "2026-09-19",
        "nfl_passing_yards_v8_date_input": "2026-09-19",
        "nfl_passing_yards_v8_matchup": "stale-matchup",
        "nfl_passing_yards_v12_auto_slate_resolved": True,
        "ks_sport_touch": "NFL",
        "ks_nfl_market_touch": "Passing Yards",
        "unrelated": "keep-me",
    }

    router._clear_passing_yards_entry_state(state)

    for key in router.PASSING_YARDS_ENTRY_STATE_KEYS:
        assert key not in state

    assert state["ks_sport_touch"] == "NFL"
    assert state["ks_nfl_market_touch"] == "Passing Yards"
    assert state["unrelated"] == "keep-me"


def test_v182_resets_only_exact_nfl_passing_yards_jump() -> None:
    assert router._passing_yards_jump_requested("NFL", "Passing Yards") is True
    assert router._passing_yards_jump_requested("nfl", "Passing Yards") is True

    assert router._passing_yards_jump_requested("NFL", "Rushing Yards") is False
    assert router._passing_yards_jump_requested("CFB", "Passing Yards") is False
    assert router._passing_yards_jump_requested("MLB", "Passing Yards") is False


def test_v182_preserves_v181_and_projection_guardrails() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v181"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
    assert "from streamlit_memory_lazy_router_v182 import record_bootstrap_import_ms, render_app" in app
