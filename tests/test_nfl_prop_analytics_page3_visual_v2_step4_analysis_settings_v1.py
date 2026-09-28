from pathlib import Path

import nfl_prop_analytics_page3_visual_v2_step4_analysis_settings_v1 as v2

SRC = Path("nfl_prop_analytics_page3_visual_v2_step4_analysis_settings_v1.py").read_text()
PAGE = Path("nfl_prop_analytics_prop_page_v1.py").read_text()
CONTRACT = Path(
    "devsystem/contracts/nfl-prop-page3-visual-composition-v2-contract-v1.json"
).read_text()


def test_step4_contract_identity():
    assert v2.VISUAL_SERIES == "v2"
    assert v2.VISUAL_STEP == 4
    assert v2.VISUAL_VERSION == "v1"
    assert v2.REAL_COMPOSITION_REBUILD is True
    assert v2.PRESENTATION_ONLY is True
    assert v2.FROZEN_STEP2_HERO_PROTECTED is True
    assert v2.FROZEN_STEP3_RIBBON_PROTECTED is True
    assert v2.FROZEN_WIDGET_KEYS_PROTECTED is True
    assert v2.DATA_OWNERSHIP_CHANGED is False
    assert v2.INTERACTION_BEHAVIOR_CHANGED is False
    assert v2.QUERY_SEMANTICS_CHANGED is False
    assert v2.MIN_TOUCH_TARGET_PX == 44
    assert v2.CERTIFIED_VIEWPORTS == (390, 768, 1440)


def test_step4_matches_locked_analysis_settings_contract():
    for token in (
        '"id": "analysis_settings"',
        '"Single bordered control deck with header row, Manual Line Lab action at upper-right, then two equal control cards beneath."',
        '"left_control_card": "History Window"',
        '"right_control_card": "Prop Category"',
        '"interaction_rule": "Existing Streamlit controls remain real, tappable controls; do not replace with static HTML."',
        '{"step": 4, "scope": "Analysis Settings composition rebuild"}',
    ):
        assert token in CONTRACT, token

    for token in (
        'class="ks-v2-analysis-settings-head"',
        'data-page3-visual-v2-step4="',
        'data-page3-visual-v2-step4-real-composition="true"',
        "MANUAL LINE LAB",
        "BELOW ↓",
        f".st-key-{v2.CONTAINER_KEY}",
        '[data-testid="stColumn"]',
        "min-height:{MIN_TOUCH_TARGET_PX}px",
        '.ks-pa3-nav-marker{{',
        "display:none!important",
    ):
        assert token in SRC, token


def test_step4_module_is_presentation_only():
    for token in (
        "st.segmented_control(",
        "st.query_params",
        "st.slider(",
        "st.button(",
        "requests.get(",
        "load_player_history(",
        "summarize_history(",
        "render_analysis_line_control(",
    ):
        assert token not in SRC, token


def test_step4_wires_frozen_native_controls_without_key_or_query_changes():
    assert (
        "from nfl_prop_analytics_page3_visual_v2_step4_analysis_settings_v1 import ("
        in PAGE
    )
    assert 'key="nfl_prop_analytics_page3_step2_history_nav_v1"' in PAGE
    assert 'key="nfl_prop_analytics_page3_step2_market_nav_v1"' in PAGE
    assert PAGE.count('key="nfl_prop_analytics_page3_step2_history_nav_v1"') == 1
    assert PAGE.count('key="nfl_prop_analytics_page3_step2_market_nav_v1"') == 1
    assert "st.query_params[HISTORY_QUERY_KEY] = chosen_history_key" in PAGE
    assert "st.query_params[MARKET_QUERY_KEY] = chosen_key" in PAGE

    assert "analysis_settings_container = st.container(" in PAGE
    assert "key=VISUAL_V2_STEP4_CONTAINER_KEY" in PAGE
    assert 'history_control_col, market_control_col = st.columns(2, gap="small")' in PAGE
    assert "with history_control_col:" in PAGE
    assert "with market_control_col:" in PAGE
    assert "visual_v2_step4_header_slot = st.empty()" in PAGE
    assert "target=visual_v2_step4_header_slot" in PAGE
    assert '"visual_v2_step4_analysis_settings": visual_v2_step4_analysis_settings' in PAGE


def test_step4_keeps_visual_v2_ordering_contract():
    hero = PAGE.index("visual_v2_step2_hero = render_visual_v2_hero(")
    ribbon_slot = PAGE.index("visual_v2_step3_ribbon_slot = st.empty()")
    nav_marker = PAGE.index('class="ks-pa3-nav-marker"')
    deck = PAGE.index("analysis_settings_container = st.container(")
    history_load = PAGE.index("history_payload = load_player_history(")

    assert hero < ribbon_slot < nav_marker < deck < history_load
