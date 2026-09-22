from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def test_v56_is_presentation_only_over_frozen_v55() -> None:
    source = (ROOT / "nfl_passing_yards_hub_v56.py").read_text()
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v55"' in source
    assert 'VISUAL_UPGRADE_STEP = 6' in source
    assert 'CONTROL_SYSTEM_VERSION = "v56"' in source
    assert 'PRESENTATION_ONLY = True' in source
    assert 'DISPLAY_ONLY = True' in source
    assert 'MAY_MODIFY_PROJECTION = False' in source
    assert 'MAY_MODIFY_PROBABILITY = False' in source
    assert 'MAY_MODIFY_MARKET_MATH = False' in source
    assert 'MAY_MODIFY_WIDGET_KEYS = False' in source
    assert 'MAY_MODIFY_ROUTING = False' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert 'STAKE_SIZING_ENABLED = False' in source
    assert 'data-passing-yards-control-system="v56"' in source

def test_v56_control_css_uses_semantic_tokens() -> None:
    source = (ROOT / "nfl_passing_yards_hub_v56.py").read_text()
    css = source.split('_CONTROL_CSS = r"""', 1)[1].split('"""', 1)[0]
    assert not re.search(r'#[0-9a-fA-F]{3,8}', css)
    assert 'rgba(' not in css
    for marker in (
        '.st-key-kyre_passing_yards_top_v46',
        '[data-testid="stDateInput"]',
        '[data-testid="stSelectbox"]',
        '[data-testid="stExpander"]',
        '.ks-py48-support details',
        '[data-testid="stButton"] button',
        'input[aria-label="Sportsbook / source"]',
        '--kyre-sem-surface-control',
        '--kyre-sem-border-medium',
        '--kyre-sem-radius-control',
        '--kyre-sem-shadow-glow',
    ):
        assert marker in css, marker

def test_v56_does_not_own_widgets_navigation_or_math() -> None:
    source = (ROOT / "nfl_passing_yards_hub_v56.py").read_text()
    forbidden = (
        'build_baseline_projection(',
        'build_context_projection(',
        'build_distribution(',
        'evaluate_market(',
        'requests.get(',
        'st.selectbox(',
        'st.date_input(',
        'st.text_input(',
        'st.button(',
        'session_state[',
    )
    for token in forbidden:
        assert token not in source, token

def test_v207_routes_only_passing_yards_to_v56() -> None:
    source = (ROOT / "streamlit_memory_lazy_router_v207.py").read_text()
    assert 'import streamlit_memory_lazy_router_v206 as prior' in source
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v56"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v206"' in source
    assert 'prior.PASSING_HUB = PASSING_HUB' in source
    assert 'data-passing-yards-v207-runtime="step6"' in source

def test_app_boots_v207_and_keeps_v206_certification_reference() -> None:
    source = (ROOT / "app.py").read_text()
    assert 'from streamlit_memory_lazy_router_v207 import record_bootstrap_import_ms, render_app' in source
    assert 'from streamlit_memory_lazy_router_v206 import record_bootstrap_import_ms, render_app' in source
    assert 'PASSING_YARDS_UNIVERSAL_STEP6_RUNTIME' in source
