import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _grader():
    return importlib.import_module("nfl_passing_yards_presentation_grade_v1")


def _label(html: str, surface: str) -> str:
    return _grader().grade_certified_html(html, surface=surface)["label"]


def test_deep_evidence_translates_existing_directional_labels_only() -> None:
    assert _label("<b>HELP</b>", "evidence") == "FAVORABLE"
    assert _label("<b>FAVORABLE</b>", "evidence") == "FAVORABLE"
    assert _label("<b>HURT</b>", "evidence") == "TOUGH"
    assert _label("<b>TOUGH</b>", "evidence") == "TOUGH"
    assert _label("<b>MIXED</b>", "evidence") == "MEDIUM"
    assert _label("<b>WATCH</b>", "evidence") == "MEDIUM"
    assert _label("<b>NEUTRAL</b>", "evidence") == "MEDIUM"


def test_monster_projection_translates_existing_certified_state_without_new_math() -> None:
    assert _label("<span>GREEN</span>", "projection") == "FAVORABLE"
    assert _label("<span>WATCH</span>", "projection") == "MEDIUM"
    assert _label("<span>CHECK</span>", "projection") == "MEDIUM"
    assert _label("<span>WITHHELD</span>", "projection") == "TOUGH"


def test_market_grade_translates_existing_final_lean() -> None:
    assert _label("<strong>LEAN OVER</strong>", "market") == "FAVORABLE"
    assert _label("<strong>LEAN UNDER</strong>", "market") == "TOUGH"
    assert _label("<span>MARKET CONTEXT</span>", "market") == "MEDIUM"


def test_unknown_or_missing_certified_direction_defaults_medium() -> None:
    grader = _grader()
    assert grader.grade_certified_html("", surface="evidence")["label"] == "MEDIUM"
    assert grader.grade_certified_html("<div>127.9 recent SD</div>", surface="evidence")["label"] == "MEDIUM"
    assert grader.grade_certified_html("<div>202.2 projection yards</div>", surface="projection")["label"] == "MEDIUM"


def test_v39_is_additive_presentation_only_wrapper_over_v38_and_v36_dashboard() -> None:
    source = _source("nfl_passing_yards_hub_v39.py")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v38"' in source
    assert 'FROZEN_DASHBOARD = "nfl_passing_yards_hub_v36"' in source
    assert "PRESENTATION_GRADES_ONLY = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source
    assert "dashboard._evidence" in source
    assert "dashboard._compact_player" in source
    assert "grade_certified_html" in source
    for grade in ("FAVORABLE", "MEDIUM", "TOUGH"):
        assert grade in source


def test_router_v140_routes_only_passing_yards_to_v39() -> None:
    source = _source("streamlit_memory_lazy_router_v140.py")
    assert 'ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v39"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v139"' in source
    assert 'PASSING_YARDS_MARKET = "Passing Yards"' in source
    assert "return prior.render_app()" in source


def test_app_bootstraps_router_v140() -> None:
    source = _source("app.py")
    assert "streamlit_memory_lazy_router_v140" in source
    assert "STREAMLIT_MAIN_V140_NFL_PASSING_YARDS_PRESENTATION_GRADES" in source
