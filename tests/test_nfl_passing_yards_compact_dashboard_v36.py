from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_v36_is_additive_presentation_wrapper_over_v35() -> None:
    source = _source("nfl_passing_yards_hub_v36.py")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v35"' in source
    assert 'FROZEN_COMPOSITION = "nfl_passing_yards_hub_v34"' in source
    assert "DISPLAY_ONLY = True" in source
    assert "COMPACT_DASHBOARD_ONLY = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source


def test_v36_has_compact_dashboard_and_semantic_color_contract() -> None:
    source = _source("nfl_passing_yards_hub_v36.py")
    for marker in (
        "kpass36-dashboard",
        "kpass36-matchup",
        "kpass36-grid",
        "kpass36-hero",
        "kpass36-why",
        "kpass36-reason",
        "kpass36-evidence",
        "kpass36-tone-green",
        "kpass36-tone-red",
        "kpass36-tone-amber",
        "kpass36-tone-blue",
        "kpass36-tone-purple",
        "kpass36-tone-gray",
    ):
        assert marker in source


def test_v36_keeps_projection_and_market_visible_and_deep_evidence_collapsed() -> None:
    source = _source("nfl_passing_yards_hub_v36.py")
    assert "Monster Projection" in source
    assert "Market + Edge" in source
    assert "Why This Projection" in source
    for reason in ("Volume", "Efficiency", "Pressure", "Personnel", "Weather"):
        assert reason in source
    assert "<details" in source
    assert "<summary" in source
    assert "Deep Evidence" in source


def test_v36_matchup_header_surfaces_verified_slate_kickoff_without_new_transport() -> None:
    source = _source("nfl_passing_yards_hub_v36.py")
    assert "kpass36-kickoff" in source
    assert "tip_et" in source
    assert "Verified kickoff" in source
    assert "load_nfl_slate" not in source
    assert "requests." not in source


def test_v36_mobile_contract_stacks_qbs_and_hero_metrics() -> None:
    source = _source("nfl_passing_yards_hub_v36.py")
    assert "@media(max-width:900px)" in source
    assert "grid-template-columns:1fr" in source
    assert "@media(max-width:640px)" in source


def test_router_v137_owns_only_exact_passing_yards_and_delegates_elsewhere() -> None:
    source = _source("streamlit_memory_lazy_router_v137.py")
    assert 'ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v36"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v136"' in source
    assert 'PASSING_YARDS_MARKET = "Passing Yards"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "return prior.render_app()" in source


def test_app_bootstraps_router_v137() -> None:
    source = _source("app.py")
    assert "streamlit_memory_lazy_router_v137" in source
    assert "STREAMLIT_MAIN_V137_NFL_PASSING_YARDS_COMPACT_DASHBOARD" in source
