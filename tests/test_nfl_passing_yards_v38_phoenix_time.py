from pathlib import Path
import importlib


ROOT = Path(__file__).resolve().parents[1]


def _source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _clock():
    return importlib.import_module("nfl_passing_yards_phoenix_time_v1")


def test_phoenix_time_converts_september_et_kickoff_with_dst() -> None:
    clock = _clock()
    result = clock.phoenix_kickoff("2026-09-17", "8:15 PM ET")
    assert result is not None
    assert result["clock"] == "5:15 PM MST"
    assert result["date"] == "2026-09-17"
    assert result["timezone"] == "America/Phoenix"


def test_phoenix_time_converts_winter_et_kickoff_without_hardcoded_offset() -> None:
    clock = _clock()
    result = clock.phoenix_kickoff("2026-12-17", "8:15 PM ET")
    assert result is not None
    assert result["clock"] == "6:15 PM MST"


def test_phoenix_time_fails_closed_for_tbd_or_missing_date() -> None:
    clock = _clock()
    assert clock.phoenix_kickoff("2026-09-17", "TBD") is None
    assert clock.phoenix_kickoff("", "8:15 PM ET") is None


def test_v38_is_additive_display_only_wrapper_over_v37() -> None:
    source = _source("nfl_passing_yards_hub_v38.py")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v37"' in source
    assert 'FROZEN_HEADER = "nfl_passing_yards_hub_v36"' in source
    assert "PHOENIX_TZ_NAME = \"America/Phoenix\"" in source
    assert "TIMEZONE_DISPLAY_ONLY = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source
    assert "nfl_passing_yards_v8_date_input" in source
    assert "nfl_passing_yards_v8_date" in source
    assert "header._matchup_header" in source
    assert "phoenix_kickoff" in source


def test_router_v139_routes_only_passing_yards_to_v38() -> None:
    source = _source("streamlit_memory_lazy_router_v139.py")
    assert 'ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v38"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v138"' in source
    assert 'PASSING_YARDS_MARKET = "Passing Yards"' in source
    assert "return prior.render_app()" in source


def test_app_bootstraps_router_v139() -> None:
    source = _source("app.py")
    assert "streamlit_memory_lazy_router_v139" in source
    assert "STREAMLIT_MAIN_V139_NFL_PASSING_YARDS_PHOENIX_TIME" in source
