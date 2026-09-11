from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_passing_yards_gets_a_dedicated_compact_route_only() -> None:
    hub = _read("nfl_hub_v19.py")
    page = _read("nfl_passing_yards_hub_v1.py")

    assert 'if market == "Passing Yards":' in hub
    assert 'from nfl_passing_yards_hub_v1 import render_nfl_passing_yards_hub' in hub
    assert 'return base.render_nfl_hub(market)' in hub
    assert 'NFL PASSING YARDS V1 • COMPACT FOUNDATION • VERIFIED SLATE' in page
    assert 'base.load_nfl_slate(day_str)' in page


def test_compact_page_does_not_enable_uncertified_betting_logic() -> None:
    page = _read("nfl_passing_yards_hub_v1.py")

    assert 'MODEL OFF' in page
    assert 'no projection or sportsbook influence enabled.' in page
    assert 'QB starter identity, passing data, matchup engines, projections, probabilities, and rankings are not active yet.' in page
    assert 'st.metric(' not in page
    assert 'Monte Carlo' not in page


def test_compact_layout_reduces_above_fold_vertical_weight() -> None:
    page = _read("nfl_passing_yards_hub_v1.py")

    assert '.ks-shell{padding:10px 14px!important' in page
    assert '.ks-title{font-size:1.55rem!important' in page
    assert '.kpy-head' in page
    assert '.kpy-strip' in page
    assert '.kpy-grid' in page


def test_router_v80_preserves_cfb_v79_and_advances_only_nfl_hub() -> None:
    router = _read("streamlit_memory_lazy_router_v80.py")
    app = _read("app.py")

    assert 'import streamlit_memory_lazy_router_v79 as prior' in router
    assert 'nfl_hub_v19' in router
    assert 'streamlit_memory_lazy_router_v80' in app
    assert 'STREAMLIT_MAIN_V80_NFL_PASSING_YARDS_COMPACT_2026-09-11' in app
