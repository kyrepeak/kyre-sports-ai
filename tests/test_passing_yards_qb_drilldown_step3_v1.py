from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V60 = (ROOT / "nfl_passing_yards_hub_v60.py").read_text()
V59 = (ROOT / "nfl_passing_yards_hub_v59.py").read_text()
R211 = (ROOT / "streamlit_memory_lazy_router_v211.py").read_text()
R210 = (ROOT / "streamlit_memory_lazy_router_v210.py").read_text()
APP = (ROOT / "app.py").read_text()


def test_v60_is_additive_over_frozen_v59():
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v59"' in V60
    assert 'import nfl_passing_yards_hub_v59 as prior' in V60
    assert 'DRILLDOWN_STEP = 3' in V60


def test_step3_header_has_durable_visible_markers():
    assert 'data-passing-yards-step3-header-css="v60"' in V60
    assert 'data-passing-yards-step3-header="v60"' in V60
    assert 'data-passing-yards-step3-slate="true"' in V60
    assert 'data-passing-yards-step3-controls="true"' in V60


def test_step3_header_css_and_visible_body_render_separately():
    assert 'header_body = header_html[len(_HEADER_CSS):]' in V60
    assert 'st.markdown(_HEADER_CSS, unsafe_allow_html=True)' in V60
    assert 'st.markdown(header_body, unsafe_allow_html=True)' in V60


def test_step3_header_matches_approved_structure():
    for token in [
        'Passing Yards',
        'Quarterback projection hub built for fast matchup scanning',
        'NFL • PASSING YARDS',
        'ALL QBs',
        'HOME',
        'AWAY',
        'AVAILABLE',
        'CERTIFIED ANALYSIS',
    ]:
        assert token in V60


def test_step3_header_is_responsive():
    assert '@media(max-width:760px)' in V60
    assert '@media(max-width:460px)' in V60
    assert 'grid-template-columns:1fr' in V60


def test_step3_header_reads_context_without_new_widgets_or_data_calls():
    assert 'st.query_params.get(' in V60
    forbidden = [
        'requests.get(',
        'fetch_odds(',
        'st.selectbox(',
        'st.date_input(',
        'st.text_input(',
        'st.button(',
        'calculate_projection(',
        'probability_model(',
    ]
    assert not any(token in V60 for token in forbidden)


def test_v60_preserves_frozen_v59_product_under_header():
    assert 'return prior.render_nfl_passing_yards_hub()' in V60
    assert 'data-passing-yards-qb-detail="v59"' in V59
    assert 'return prior._selection_screen(captured)' in V59


def test_v60_guardrails_are_frozen():
    for token in [
        'MAY_MODIFY_PROJECTION = False',
        'MAY_MODIFY_PROBABILITY = False',
        'MAY_MODIFY_MARKET_MATH = False',
        'MAY_MODIFY_WIDGET_KEYS = False',
        'MAY_MODIFY_DATA = False',
        'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
    ]:
        assert token in V60


def test_router_v211_only_advances_passing_yards_to_v60():
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v210"' in R211
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v60"' in R211
    assert 'return prior.render_app()' in R211


def test_v210_stays_frozen_under_v211():
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v209"' in R210
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v59"' in R210


def test_app_boots_v211_and_preserves_v210_compatibility():
    assert "from streamlit_memory_lazy_router_v211 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen QB Drill-Down Step 2 V210 compatibility" in APP
    assert 'PASSING_YARDS_QB_DRILLDOWN_STEP3_HEADER_RUNTIME = "NFL_PASSING_YARDS_V60_HEADER_2026_09_22"' in APP
