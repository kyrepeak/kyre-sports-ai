from pathlib import Path


def test_step1_v58_is_selection_architecture_over_frozen_v57() -> None:
    source = Path("nfl_passing_yards_hub_v58.py").read_text(encoding="utf-8")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v57"' in source
    assert 'DRILLDOWN_STEP = 1' in source
    assert 'SELECTION_SYSTEM_VERSION = "v58"' in source
    assert 'PRESENTATION_ONLY = True' in source
    assert 'MAY_MODIFY_PROJECTION = False' in source
    assert 'MAY_MODIFY_PROBABILITY = False' in source
    assert 'MAY_MODIFY_MARKET_MATH = False' in source
    assert 'MAY_MODIFY_WIDGET_KEYS = False' in source
    assert 'MAY_MODIFY_DATA = False' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert 'data-passing-yards-qb-selection="v58"' in source
    assert 'data-passing-yards-selection-screen="v58"' in source
    assert 'data-qb-selection-card=' in source
    assert 'data-qb-select=' in source
    assert 'View Analysis' in source
    assert 'Back to Quarterbacks' in source


def test_step1_replaces_v48_command_center_without_editing_frozen_chain() -> None:
    source = Path("nfl_passing_yards_hub_v58.py").read_text(encoding="utf-8")
    assert 'original_builder = evidence._steps_7_9_command_center_html' in source
    assert 'evidence._steps_7_9_command_center_html = _qb_drilldown_html' in source
    assert 'evidence._steps_7_9_command_center_html = original_builder' in source

    frozen = Path("nfl_passing_yards_hub_v57.py").read_text(encoding="utf-8")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v56"' in frozen
    assert 'data-passing-yards-responsive-system="v57"' in frozen


def test_step1_owns_no_model_or_data_computation() -> None:
    source = Path("nfl_passing_yards_hub_v58.py").read_text(encoding="utf-8")
    for forbidden in (
        "build_baseline_projection(",
        "build_context_projection(",
        "build_distribution(",
        "evaluate_market(",
        "requests.get(",
        "st.selectbox(",
        "st.date_input(",
        "st.text_input(",
        "st.button(",
    ):
        assert forbidden not in source, forbidden


def test_router_v209_advances_only_passing_yards_to_v58() -> None:
    router = Path("streamlit_memory_lazy_router_v209.py").read_text(encoding="utf-8")
    assert 'import streamlit_memory_lazy_router_v208 as prior' in router
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v208"' in router
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v58"' in router
    assert 'data-passing-yards-v209-runtime="qb-selection-step1"' in router
    assert 'prior.PASSING_HUB = PASSING_HUB' in router


def test_app_boots_v209_and_preserves_v208_compatibility() -> None:
    app = Path("app.py").read_text(encoding="utf-8")
    assert 'PASSING_YARDS_QB_DRILLDOWN_STEP1_RUNTIME = "NFL_PASSING_YARDS_V58_QB_SELECTION_2026_09_21"' in app
    assert "from streamlit_memory_lazy_router_v209 import record_bootstrap_import_ms, render_app" in app
    assert "Frozen Passing Yards Step 7 V208 certification compatibility" in app
