from __future__ import annotations

from datetime import date
from pathlib import Path


def _controller():
    import nfl_receiving_yards_slate_controller_v1 as controller

    return controller


def test_empty_selected_day_advances_to_next_verified_slate() -> None:
    controller = _controller()

    def finder(selected: date, *, max_forward_days: int):
        assert selected == date(2026, 9, 16)
        assert max_forward_days == 7
        return date(2026, 9, 17), 1, "verified"

    result = controller.resolve_next_verified_slate_date(
        date(2026, 9, 16),
        finder,
        max_lookahead_days=7,
    )
    assert result["state"] == "FOUND"
    assert result["resolved_date"] == date(2026, 9, 17)
    assert result["advanced"] is True


def test_selected_day_with_games_stays_put() -> None:
    controller = _controller()

    def finder(selected: date, *, max_forward_days: int):
        return selected, 0, "verified"

    result = controller.resolve_next_verified_slate_date(date(2026, 9, 17), finder)
    assert result["state"] == "FOUND"
    assert result["resolved_date"] == date(2026, 9, 17)
    assert result["advanced"] is False


def test_provider_failure_fails_closed_and_does_not_advance() -> None:
    controller = _controller()

    def finder(selected: date, *, max_forward_days: int):
        return selected, None, "verification_failed"

    result = controller.resolve_next_verified_slate_date(date(2026, 9, 16), finder)
    assert result == {
        "state": "PROVIDER_ERROR",
        "selected_date": date(2026, 9, 16),
        "resolved_date": date(2026, 9, 16),
        "advanced": False,
    }


def test_empty_slate_notice_filter_is_narrow() -> None:
    controller = _controller()
    assert controller.is_empty_slate_notice("No verified NFL games were returned for this date.") is True
    assert controller.is_empty_slate_notice("No NFL games are scheduled on 2026-09-16.") is True
    assert controller.is_empty_slate_notice("NFL schedule provider did not return a usable slate.") is False
    assert controller.is_empty_slate_notice("Schedule verification failed") is False


def test_v11_is_additive_over_frozen_v10_and_uses_existing_receiving_state_keys() -> None:
    source = Path("nfl_receiving_yards_hub_v11.py").read_text()
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v10"' in source
    assert 'DATE_KEY = "nfl_receiving_yards_v1_date"' in source
    assert 'DATE_INPUT_KEY = "nfl_receiving_yards_v1_date_input"' in source
    assert "resolve_next_verified_slate_date" in source
    assert "find_next_verified_slate" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_router_v142_advances_only_receiving_yards() -> None:
    source = Path("streamlit_memory_lazy_router_v142.py").read_text()
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v141"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v11"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_bootstraps_router_v142() -> None:
    source = Path("app.py").read_text()
    assert "from streamlit_memory_lazy_router_v142 import record_bootstrap_import_ms, render_app" in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V142_NFL_RECEIVING_YARDS_SMART_SLATE_2026-09-16"' in source
