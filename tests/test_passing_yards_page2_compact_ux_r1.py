from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V86 = ROOT / "nfl_passing_yards_hub_v86.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v239.py"


def test_v86_compact_page2_module_exists() -> None:
    assert V86.exists(), "Passing Yards Page 2 compact V86 has not been implemented yet"


def test_v86_is_presentation_only_over_frozen_v85() -> None:
    source = V86.read_text(encoding="utf-8")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v85"' in source
    assert 'PAGE2_COMPACT_UX_VERSION = "v86"' in source
    assert "PRESENTATION_ONLY = True" in source
    assert "DISPLAY_ONLY = True" in source
    for flag in (
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_CONTEXT_MATH = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_MARKET_MATH = False",
        "MAY_MODIFY_SPORTSBOOK_BEHAVIOR = False",
        "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False",
        "MAY_MODIFY_WIDGET_KEYS = False",
        "MAY_MODIFY_NAVIGATION_STATE = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
        "STAKE_SIZING_ENABLED = False",
    ):
        assert flag in source


def test_v86_compacts_page2_reading_path_without_dropping_evidence() -> None:
    source = V86.read_text(encoding="utf-8")
    for token in (
        'data-passing-yards-page2-compact-ux="v86"',
        "Quick Read",
        "Expected Range",
        "ks-py86-range",
        "ks-py69-clean-detail",
        "Show Advanced Evidence",
        "ks-py76-guide",
        "ks-py71-explain",
        "ks-py72-matchup",
        "ks-py74",
        "ks-py75",
        "_compact_selected_analysis",
    ):
        assert token in source


def test_v239_routes_only_passing_yards_to_v86() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v86"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v238"' in source
    assert 'PASSING_MARKET = "Passing Yards"' in source
    assert "return prior.render_app()" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_CONTEXT_MATH = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_MARKET_MATH = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
