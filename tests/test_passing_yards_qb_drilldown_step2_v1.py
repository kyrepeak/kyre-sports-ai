from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V59 = (ROOT / "nfl_passing_yards_hub_v59.py").read_text()
V58 = (ROOT / "nfl_passing_yards_hub_v58.py").read_text()
R210 = (ROOT / "streamlit_memory_lazy_router_v210.py").read_text()
APP = (ROOT / "app.py").read_text()


def test_v59_is_additive_over_frozen_v58():
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v58"' in V59
    assert 'import nfl_passing_yards_hub_v58 as prior' in V59


def test_step1_picker_is_inherited_not_rebuilt():
    assert 'return prior._selection_screen(captured)' in V59
    assert 'data-passing-yards-selection-screen="v58"' in V58


def test_selected_view_preserves_step1_navigation_contract():
    assert 'data-passing-yards-selected-qb=' in V59
    assert 'data-qb-back="true"' in V59
    assert 'SELECTED QUARTERBACK' in V59


def test_selected_view_has_durable_v59_markers():
    assert 'data-passing-yards-qb-detail="v59"' in V59
    assert 'data-selected-qb-analysis=' in V59
    assert 'data-qb-analysis-slot=' in V59
    assert 'data-qb-analysis-index=' in V59


def test_selected_view_has_complete_certified_analysis_sections():
    for call in [
        '_section("market", "Current Market + Edge", market)',
        '_section("projection", "Baseline Projection", projection)',
        '_section("context", "Context + Uncertainty", context)',
        '_section("distribution", "Distribution + Probability", distribution)',
        '_support("matchup", "Matchup Drivers"',
        '_support("conditions", "Conditions + Personnel"',
    ]:
        assert call in V59


def test_v59_uses_captured_payload_without_legacy_full_player_wrappers():
    assert '_piece(captured, "identity", index)' in V59
    assert '_piece(captured, "projection", index)' in V59
    assert '_piece(captured, "distribution", index)' in V59
    assert 'evidence._player(' not in V59
    assert 'class="ks-py48-player"' not in V59
    assert 'class="ks-py48-step"' not in V59


def test_selected_view_only_accepts_qb_slots_one_or_two():
    assert 'if raw in {"1", "2"}:' in V59


def test_v59_does_not_compute_model_or_market_values():
    forbidden = [
        "calculate_projection(",
        "projection_model(",
        "normal_cdf(",
        "probability_model(",
        "fetch_odds(",
        "requests.get(",
        "st.selectbox(",
        "st.date_input(",
        "st.text_input(",
        "st.button(",
    ]
    assert not any(token in V59 for token in forbidden)


def test_v59_guardrails_are_frozen():
    for token in [
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_MARKET_MATH = False",
        "MAY_MODIFY_WIDGET_KEYS = False",
        "MAY_MODIFY_DATA = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
    ]:
        assert token in V59


def test_router_v210_only_advances_passing_yards_to_v59():
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v209"' in R210
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v59"' in R210
    assert 'return prior.render_app()' in R210
    assert 'data-passing-yards-v210-runtime="qb-detail-step2"' in R210


def test_router_v210_guardrails_remain_frozen():
    for token in [
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_MARKET_MATH = False",
        "MAY_MODIFY_WIDGET_KEYS = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
    ]:
        assert token in R210


def test_app_boots_v210_and_keeps_v209_compatibility():
    assert "from streamlit_memory_lazy_router_v210 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen QB Drill-Down Step 1 V209 compatibility" in APP
    assert 'PASSING_YARDS_QB_DRILLDOWN_STEP2_RUNTIME = "NFL_PASSING_YARDS_V59_QB_DETAIL_2026_09_21"' in APP
