from pathlib import Path
import re


def test_step7_is_presentation_only_over_frozen_step6() -> None:
    source = Path("nfl_passing_yards_hub_v57.py").read_text(encoding="utf-8")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v56"' in source
    assert 'VISUAL_UPGRADE_STEP = 7' in source
    assert 'RESPONSIVE_SYSTEM_VERSION = "v57"' in source
    assert 'PRESENTATION_ONLY = True' in source
    assert 'DISPLAY_ONLY = True' in source
    assert 'MAY_MODIFY_PROJECTION = False' in source
    assert 'MAY_MODIFY_PROBABILITY = False' in source
    assert 'MAY_MODIFY_MARKET_MATH = False' in source
    assert 'MAY_MODIFY_WIDGET_KEYS = False' in source
    assert 'MAY_MODIFY_ROUTING = False' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert 'STAKE_SIZING_ENABLED = False' in source
    assert 'data-passing-yards-responsive-system="v57"' in source
    assert 'build_semantic_tokens_css() + _RESPONSIVE_CSS' in source


def test_step7_css_has_required_responsive_breakpoints_and_no_local_colors() -> None:
    source = Path("nfl_passing_yards_hub_v57.py").read_text(encoding="utf-8")
    css = source.split('_RESPONSIVE_CSS = r"""', 1)[1].split('"""', 1)[0]
    assert not re.search(r'#[0-9a-fA-F]{3,8}', css)
    assert "rgba(" not in css
    for token in (
        "@media(max-width:1120px)",
        "@media(max-width:900px)",
        "@media(max-width:680px)",
        "@media(max-width:430px)",
        ".ks-py48-grid",
        ".ks-py48-evidence",
        ".ks-py48-support",
        ".st-key-kyre_passing_yards_top_v46",
        'input[aria-label="Sportsbook / source"]',
        "grid-template-columns:1fr!important",
        "min-height:48px!important",
        '[data-testid="stDateInput"] input',
        '[data-testid="stDateInput"] [role="textbox"]',
        '[data-testid="stSelectbox"] [role="combobox"]',
        "box-sizing:border-box!important",
        "max-width:100%!important",
    ):
        assert token in css, token


def test_step7_owns_no_model_data_widget_or_route_behavior() -> None:
    source = Path("nfl_passing_yards_hub_v57.py").read_text(encoding="utf-8")
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
        "st.session_state[",
    ):
        assert forbidden not in source, forbidden


def test_v208_advances_only_passing_yards_to_v57() -> None:
    router = Path("streamlit_memory_lazy_router_v208.py").read_text(encoding="utf-8")
    assert 'import streamlit_memory_lazy_router_v207 as prior' in router
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v207"' in router
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v57"' in router
    assert 'data-passing-yards-v208-runtime="step7"' in router
    assert 'prior.PASSING_HUB = PASSING_HUB' in router
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in router


def test_app_boots_v208_and_preserves_step6_source() -> None:
    app = Path("app.py").read_text(encoding="utf-8")
    assert 'PASSING_YARDS_UNIVERSAL_STEP7_RUNTIME = "NFL_PASSING_YARDS_V57_RESPONSIVE_TABLET_MOBILE_2026_09_21"' in app
    assert "from streamlit_memory_lazy_router_v208 import record_bootstrap_import_ms, render_app" in app
    assert "Frozen Passing Yards Step 6 V207 certification compatibility" in app

    frozen = Path("nfl_passing_yards_hub_v56.py").read_text(encoding="utf-8")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v55"' in frozen
    assert 'data-passing-yards-control-system="v56"' in frozen
