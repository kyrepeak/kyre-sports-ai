from __future__ import annotations

from datetime import date
from pathlib import Path

import nfl_passing_yards_hub_v41 as hub


ROOT = Path(__file__).resolve().parents[1]


def test_dead_day_advances_to_next_verified_game_date() -> None:
    def primary(start_day: date, max_forward_days: int):
        assert start_day == date(2026, 9, 19)
        assert max_forward_days == 7
        return date(2026, 9, 20), 1, "verified"

    result = hub.resolve_next_play_date(
        date(2026, 9, 19),
        primary_finder=primary,
        fallback_finder=lambda *_: None,
    )

    assert result["state"] == "FOUND"
    assert result["resolved_date"] == date(2026, 9, 20)
    assert result["advanced"] is True
    assert result["source"] == hub.PRIMARY_SCHEDULE_SOURCE


def test_game_day_stays_on_selected_date() -> None:
    def primary(start_day: date, max_forward_days: int):
        return start_day, 0, "verified"

    result = hub.resolve_next_play_date(
        date(2026, 9, 20),
        primary_finder=primary,
        fallback_finder=lambda *_: None,
    )

    assert result["state"] == "FOUND"
    assert result["resolved_date"] == date(2026, 9, 20)
    assert result["advanced"] is False


def test_primary_provider_failure_uses_nflverse_date_fallback() -> None:
    def primary(start_day: date, max_forward_days: int):
        return start_day, None, "verification_failed"

    def fallback(start_day: date, max_forward_days: int):
        return date(2026, 9, 20)

    result = hub.resolve_next_play_date(
        date(2026, 9, 19),
        primary_finder=primary,
        fallback_finder=fallback,
    )

    assert result["state"] == "FOUND"
    assert result["resolved_date"] == date(2026, 9, 20)
    assert result["source"] == hub.FALLBACK_SCHEDULE_SOURCE
    assert result["primary_status"] == "verification_failed"


def test_no_source_can_prove_game_date_fails_closed() -> None:
    result = hub.resolve_next_play_date(
        date(2026, 9, 19),
        primary_finder=lambda day, window: (day, None, "verification_failed"),
        fallback_finder=lambda day, window: None,
    )

    assert result["state"] == "PROVIDER_ERROR"
    assert result["resolved_date"] == date(2026, 9, 19)
    assert result["advanced"] is False


def test_v41_is_additive_and_model_safe() -> None:
    source = (ROOT / "nfl_passing_yards_hub_v41.py").read_text(encoding="utf-8")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v40"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source
    assert "nfl_passing_yards_v8_date_input" in source
    assert "nfl_passing_yards_v8_date" in source
    assert "nfl_passing_yards_v8_matchup" in source


def test_router_v186_keeps_v185_frozen_and_routes_only_passing_yards_to_v41() -> None:
    source = (ROOT / "streamlit_memory_lazy_router_v186.py").read_text(encoding="utf-8")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v185"' in source
    assert 'ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v41"' in source
    assert 'PASSING_YARDS_MARKET = "Passing Yards"' in source
    assert "prior._consume_any_nfl_category_without_rerun()" in source
    assert "return _render_direct_passing()" in source
    assert "return root.render_app()" in source
    assert "return prior.render_app()" in source
    assert ".rerun(" not in source


def test_app_boots_router_v186() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v186 import record_bootstrap_import_ms, render_app" in source



def test_v41_uses_date_versioned_widget_key_to_block_stale_browser_state() -> None:
    resolved = date(2026, 9, 20)
    seen = {}

    def original(label, *args, **kwargs):
        seen["label"] = label
        seen["key"] = kwargs.get("key")
        seen["value"] = kwargs.get("value")
        return kwargs.get("value")

    proxy = hub._date_input_proxy(resolved, original)
    returned = proxy(
        "NFL Passing Yards slate date",
        value=date(2026, 9, 19),
        key=hub.V8_DATE_INPUT_KEY,
        label_visibility="collapsed",
    )

    assert returned == resolved
    assert seen["value"] == resolved
    assert seen["key"] == "nfl_passing_yards_v41_date_input_2026-09-20"
    assert seen["key"] != hub.V8_DATE_INPUT_KEY


def test_v41_proxy_does_not_touch_unrelated_date_widgets() -> None:
    resolved = date(2026, 9, 20)
    seen = {}

    def original(label, *args, **kwargs):
        seen["key"] = kwargs.get("key")
        seen["value"] = kwargs.get("value")
        return kwargs.get("value")

    proxy = hub._date_input_proxy(resolved, original)
    original_day = date(2026, 9, 19)
    returned = proxy("Another date", value=original_day, key="other_date")

    assert returned == original_day
    assert seen["key"] == "other_date"
    assert seen["value"] == original_day
