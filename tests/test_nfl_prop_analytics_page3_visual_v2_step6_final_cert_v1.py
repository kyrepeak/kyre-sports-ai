from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads(
    (ROOT / "devsystem/contracts/nfl-prop-page3-visual-composition-v2-contract-v1.json").read_text()
)
STEP2 = (ROOT / "nfl_prop_analytics_page3_visual_v2_step2_hero_v1.py").read_text()
STEP3 = (ROOT / "nfl_prop_analytics_page3_visual_v2_step3_stat_ribbon_v1.py").read_text()
STEP4 = (ROOT / "nfl_prop_analytics_page3_visual_v2_step4_analysis_settings_v1.py").read_text()
STEP5 = (ROOT / "nfl_prop_analytics_page3_visual_v2_step5_lower_analytics_v1.py").read_text()
PAGE = (ROOT / "nfl_prop_analytics_prop_page_v1.py").read_text()


def test_step6_contract_is_accessibility_and_responsive_closeout():
    global_contract = CONTRACT["global"]
    assert global_contract["minimum_touch_target_px"] == 44
    assert global_contract["focus_visible_required"] is True
    assert global_contract["reduced_motion_required"] is True
    assert global_contract["horizontal_document_overflow_forbidden"] is True
    assert global_contract["certified_viewports"] == [390, 768, 1440]


def test_step6_frozen_visual_layers_expose_required_accessibility_contracts():
    assert "@media(prefers-reduced-motion:reduce)" in STEP2
    assert "@media(prefers-reduced-motion:reduce)" in STEP3
    assert "@media(prefers-reduced-motion:reduce)" in STEP4
    assert "@media(prefers-reduced-motion:reduce)" in STEP5
    assert 'button:focus-visible' in STEP4
    assert "min-height:{MIN_TOUCH_TARGET_PX}px!important" in STEP4
    assert "min-width:{MIN_TOUCH_TARGET_PX}px!important" in STEP5
    assert "min-height:{MIN_TOUCH_TARGET_PX}px!important" in STEP5


def test_step6_required_composition_order_is_frozen_in_page_source():
    hero = PAGE.index("visual_v2_step2_hero = render_visual_v2_hero(")
    ribbon = PAGE.index("visual_v2_step3_ribbon_slot = st.empty()")
    settings = PAGE.index("analysis_settings_container = st.container(")
    line = PAGE.index("visual_v2_step5_line_container = st.container(")
    live = PAGE.index("render_visual_v2_live_recalculation(")
    chart = PAGE.index("visual_v2_step5_chart_container = st.container(")
    assert hero < ribbon < settings < line < live < chart


def test_step6_real_controls_and_frozen_owners_remain_wired():
    for token in (
        'key="nfl_prop_analytics_page3_step2_history_nav_v1"',
        'key="nfl_prop_analytics_page3_step2_market_nav_v1"',
        "line_control = render_analysis_line_control(",
        "game_chart = render_game_chart(",
        "key=VISUAL_V2_STEP5_LINE_CONTAINER_KEY",
        "key=VISUAL_V2_STEP5_CHART_CONTAINER_KEY",
    ):
        assert token in PAGE, token


def test_step6_keeps_non_betting_boundary():
    for source in (STEP2, STEP3, STEP4, STEP5):
        assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert 'data-prop-step8-sportsbook-lines="0"' in PAGE
    assert 'data-prop-step8-odds="0"' in PAGE
    assert 'data-prop-step8-projections="0"' in PAGE
    assert 'data-prop-step8-recommendations="0"' in PAGE
