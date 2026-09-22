from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def test_v55_is_presentation_only_over_frozen_v54() -> None:
    source = (ROOT / "nfl_passing_yards_hub_v55.py").read_text()
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v54"' in source
    assert 'VISUAL_UPGRADE_STEP = 5' in source
    assert 'ANALYSIS_SYSTEM_VERSION = "v55"' in source
    assert 'PRESENTATION_ONLY = True' in source
    assert 'DISPLAY_ONLY = True' in source
    assert 'MAY_MODIFY_PROJECTION = False' in source
    assert 'MAY_MODIFY_MARKET_MATH = False' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert 'STAKE_SIZING_ENABLED = False' in source
    assert 'data-passing-yards-analysis-system="v55"' in source

def test_v55_analysis_css_uses_semantic_tokens_and_expected_surfaces() -> None:
    source = (ROOT / "nfl_passing_yards_hub_v55.py").read_text()
    css = source.split('_ANALYSIS_CSS = r"""', 1)[1].split('"""', 1)[0]
    assert not re.search(r'#[0-9a-fA-F]{3,8}', css)
    assert 'rgba(' not in css
    for marker in (
        '.ks-py48-board-title',
        '.ks-py48-step',
        '.ks-py48-stepnum',
        '.kpy-proj',
        '.kpy8-card',
        '.kpy9-card',
        '.kpy10-card',
        '.kpy9-q',
        '.ks-py48-support details',
        '--kyre-sem-surface-panel',
        '--kyre-sem-border-medium',
        '--kyre-sem-radius-section',
        '--kyre-sem-shadow-card',
    ):
        assert marker in css, marker

def test_v55_does_not_own_analysis_math_or_widgets() -> None:
    source = (ROOT / "nfl_passing_yards_hub_v55.py").read_text()
    forbidden = (
        'build_baseline_projection(',
        'build_context_projection(',
        'build_distribution(',
        'evaluate_market(',
        'projection_yards',
        'fair_odds',
        'no_vig',
        'over_ev',
        'under_ev',
        'requests.get(',
        'st.selectbox(',
        'st.date_input(',
        'st.text_input(',
    )
    for token in forbidden:
        assert token not in source, token

def test_v206_routes_only_passing_yards_to_v55() -> None:
    source = (ROOT / "streamlit_memory_lazy_router_v206.py").read_text()
    assert 'import streamlit_memory_lazy_router_v205 as prior' in source
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v55"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v205"' in source
    assert 'prior.PASSING_HUB = PASSING_HUB' in source
    assert 'data-passing-yards-v206-runtime="step5"' in source
    assert 'handoff._query_value(handoff.SPORT_JUMP_QUERY_KEY)' in source
    assert 'handoff._query_value(handoff.MARKET_JUMP_QUERY_KEY)' in source

def test_app_boots_v206_and_keeps_v205_certification_reference() -> None:
    source = (ROOT / "app.py").read_text()
    assert 'from streamlit_memory_lazy_router_v206 import record_bootstrap_import_ms, render_app' in source
    assert 'from streamlit_memory_lazy_router_v205 import record_bootstrap_import_ms, render_app' in source
    assert 'PASSING_YARDS_UNIVERSAL_STEP5_RUNTIME' in source
