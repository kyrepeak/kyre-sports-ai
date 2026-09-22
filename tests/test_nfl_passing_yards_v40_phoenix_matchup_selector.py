from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _v40():
    return importlib.import_module("nfl_passing_yards_hub_v40")


def test_verified_matchup_option_displays_phoenix_time_without_changing_identity_text() -> None:
    label = "Detroit Lions @ Buffalo Bills • 8:15 PM ET"
    assert _v40()._phoenix_matchup_option(label, "2026-09-17") == (
        "Detroit Lions @ Buffalo Bills • 5:15 PM MST"
    )


def test_tbd_matchup_option_fails_closed() -> None:
    label = "Detroit Lions @ Buffalo Bills • TBD"
    assert _v40()._phoenix_matchup_option(label, "2026-09-17") == label


def test_v40_patches_only_verified_matchup_selector_display() -> None:
    source = _source("nfl_passing_yards_hub_v40.py")
    assert "FROZEN_PRIOR = \"nfl_passing_yards_hub_v39\"" in source
    assert "label == \"Verified matchup\"" in source
    assert "format_func" in source
    assert "original_selectbox" in source
    assert "DISPLAY_ONLY = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_router_v141_routes_only_passing_yards_to_v40() -> None:
    source = _source("streamlit_memory_lazy_router_v141.py")
    assert "nfl_passing_yards_hub_v40" in source
    assert "streamlit_memory_lazy_router_v140" in source


def test_app_bootstraps_router_v141() -> None:
    source = _source("app.py")
    assert "streamlit_memory_lazy_router_v141" in source
    assert "STREAMLIT_MAIN_V141_NFL_PASSING_YARDS_PHOENIX_SELECTOR" in source
