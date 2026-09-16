from datetime import date
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _controller():
    return importlib.import_module("nfl_passing_yards_slate_controller_v1")


class _Games:
    def __init__(self, empty: bool) -> None:
        self.empty = empty


def test_smart_slate_advances_from_empty_day_to_next_verified_games() -> None:
    controller = _controller()
    seen: list[str] = []
    empty_by_day = {
        "2026-09-15": True,
        "2026-09-16": True,
        "2026-09-17": False,
    }

    def loader(day_str: str):
        seen.append(day_str)
        return _Games(empty_by_day[day_str]), {"request_ok": True}

    result = controller.resolve_next_verified_slate_date(
        date(2026, 9, 15), loader, max_lookahead_days=3
    )

    assert result["state"] == "FOUND"
    assert result["resolved_date"] == date(2026, 9, 17)
    assert result["advanced"] is True
    assert seen == ["2026-09-15", "2026-09-16", "2026-09-17"]


def test_smart_slate_keeps_selected_day_when_games_already_exist() -> None:
    controller = _controller()
    seen: list[str] = []

    def loader(day_str: str):
        seen.append(day_str)
        return _Games(False), {"request_ok": True}

    result = controller.resolve_next_verified_slate_date(
        date(2026, 9, 17), loader, max_lookahead_days=7
    )

    assert result["state"] == "FOUND"
    assert result["resolved_date"] == date(2026, 9, 17)
    assert result["advanced"] is False
    assert seen == ["2026-09-17"]


def test_smart_slate_fails_closed_when_schedule_provider_fails() -> None:
    controller = _controller()
    seen: list[str] = []

    def loader(day_str: str):
        seen.append(day_str)
        return _Games(True), {"request_ok": False, "error": "provider down"}

    result = controller.resolve_next_verified_slate_date(
        date(2026, 9, 15), loader, max_lookahead_days=7
    )

    assert result["state"] == "PROVIDER_ERROR"
    assert result["resolved_date"] == date(2026, 9, 15)
    assert result["advanced"] is False
    assert seen == ["2026-09-15"]


def test_empty_slate_notice_filter_matches_old_and_auto_advance_messages() -> None:
    controller = _controller()
    assert controller.is_empty_slate_notice(
        "No NFL games are scheduled on 2026-09-15 ET. Opened the next verified NFL slate: 2026-09-17 ET."
    )
    assert controller.is_empty_slate_notice(
        "No verified NFL games were returned for this ET date."
    )
    assert not controller.is_empty_slate_notice("NFL schedule verification failed.")


def test_v37_is_additive_over_frozen_v36_and_primes_v8_slate_state() -> None:
    source = _source("nfl_passing_yards_hub_v37.py")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v36"' in source
    assert "SMART_NEXT_SLATE = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source
    assert "nfl_passing_yards_v8_date_input" in source
    assert "nfl_passing_yards_v8_date" in source
    assert "nfl_passing_yards_v8_matchup" in source
    assert "resolve_next_verified_slate_date" in source


def test_router_v138_routes_only_passing_yards_to_v37_and_filters_empty_notice() -> None:
    source = _source("streamlit_memory_lazy_router_v138.py")
    assert 'ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v37"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v137"' in source
    assert 'PASSING_YARDS_MARKET = "Passing Yards"' in source
    assert "is_empty_slate_notice" in source
    assert "return prior.render_app()" in source


def test_app_bootstraps_router_v138() -> None:
    source = _source("app.py")
    assert "streamlit_memory_lazy_router_v138" in source
    assert "STREAMLIT_MAIN_V138_NFL_PASSING_YARDS_SMART_SLATE" in source
