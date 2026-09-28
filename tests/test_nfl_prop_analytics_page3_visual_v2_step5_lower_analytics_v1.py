from pathlib import Path

import nfl_prop_analytics_page3_visual_v2_step5_lower_analytics_v1 as v2

SRC = Path("nfl_prop_analytics_page3_visual_v2_step5_lower_analytics_v1.py").read_text()
PAGE = Path("nfl_prop_analytics_prop_page_v1.py").read_text()
CONTRACT = Path(
    "devsystem/contracts/nfl-prop-page3-visual-composition-v2-contract-v1.json"
).read_text()


def test_step5_contract_identity():
    assert v2.VISUAL_SERIES == "v2"
    assert v2.VISUAL_STEP == 5
    assert v2.VISUAL_VERSION == "v1"
    assert v2.REAL_COMPOSITION_REBUILD is True
    assert v2.PRESENTATION_ONLY is True
    assert v2.FROZEN_STEP2_HERO_PROTECTED is True
    assert v2.FROZEN_STEP3_RIBBON_PROTECTED is True
    assert v2.FROZEN_STEP4_SETTINGS_PROTECTED is True
    assert v2.FROZEN_LINE_CONTROL_PROTECTED is True
    assert v2.FROZEN_GAME_CHART_PROTECTED is True
    assert v2.DATA_OWNERSHIP_CHANGED is False
    assert v2.INTERACTION_BEHAVIOR_CHANGED is False
    assert v2.QUERY_SEMANTICS_CHANGED is False
    assert v2.CERTIFIED_VIEWPORTS == (390, 768, 1440)


def test_step5_matches_locked_composition_contract():
    for token in (
        '"id": "line_lab"',
        '"id": "live_recalculation"',
        '"id": "game_chart"',
        '"required_cards": ["analysis_line", "over_percent", "under_percent", "average_stat"]',
        '{"step": 5, "scope": "Line Lab + lower analytics/chart composition rebuild"}',
        '"interaction_rule": "Existing analysis-line slider semantics, min/max, selected value, callbacks, and recalculation behavior must remain unchanged."',
    ):
        assert token in CONTRACT, token

    for token in (
        'data-page3-visual-v2-step5-region="line-lab"',
        'data-page3-visual-v2-step5-region="live-recalculation"',
        'data-page3-visual-v2-step5-region="game-chart"',
        'data-page3-visual-v2-step5-live-card-count="4"',
        'data-v2-live-card="analysis-line"',
        'data-v2-live-card="over-percent"',
        'data-v2-live-card="under-percent"',
        'data-v2-live-card="average-stat"',
        ".st-key-{LINE_CONTAINER_KEY}",
        ".st-key-{CHART_CONTAINER_KEY}",
    ):
        assert token in SRC, token


def test_step5_module_does_not_take_functional_ownership():
    for token in (
        "st.slider(",
        "load_player_history(",
        "summarize_history(",
        "render_analysis_line_control(",
        "render_game_chart(",
        "st.query_params",
        "requests.get(",
    ):
        assert token not in SRC, token


def test_step5_page_keeps_frozen_owners_and_wraps_them():
    assert (
        "from nfl_prop_analytics_page3_visual_v2_step5_lower_analytics_v1 import ("
        in PAGE
    )
    assert "key=VISUAL_V2_STEP5_LINE_CONTAINER_KEY" in PAGE
    assert "visual_v2_step5_line_header_slot = st.empty()" in PAGE
    assert "line_control = render_analysis_line_control(" in PAGE
    assert "target=visual_v2_step5_line_header_slot" in PAGE
    assert "render_visual_v2_live_recalculation(" in PAGE
    assert "key=VISUAL_V2_STEP5_CHART_CONTAINER_KEY" in PAGE
    assert "render_visual_v2_game_chart_marker(" in PAGE
    assert "game_chart = render_game_chart(" in PAGE
    assert '"visual_v2_step5_lower_analytics": {' in PAGE


def test_step5_vertical_source_order_is_after_frozen_settings():
    settings = PAGE.index("analysis_settings_container = st.container(")
    line = PAGE.index("visual_v2_step5_line_container = st.container(")
    live = PAGE.index("render_visual_v2_live_recalculation(")
    chart = PAGE.index("visual_v2_step5_chart_container = st.container(")
    supporting = PAGE.index("supporting_stats = render_supporting_stats(")
    assert settings < line < live < chart < supporting
