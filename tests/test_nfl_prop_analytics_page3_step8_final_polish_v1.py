from pathlib import Path

import nfl_prop_analytics_page3_final_polish_v1 as step8

STEP8_SRC = Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()
PAGE_SRC = Path("nfl_prop_analytics_prop_page_v1.py").read_text()


def test_step8_contract_is_presentation_only_and_protects_steps_1_to_7():
    assert step8.PAGE3_FINAL_POLISH_STEP == 8
    assert step8.PAGE3_FINAL_POLISH_VERSION == "v1"
    assert step8.PRESENTATION_ONLY is True
    assert step8.FROZEN_STEPS_1_TO_7_PROTECTED is True
    assert step8.PROJECTION_LOGIC is False
    assert step8.PROBABILITY_LOGIC is False
    assert step8.RECOMMENDATION_LOGIC is False
    assert step8.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step8.STAKE_SIZING_ENABLED is False
    assert step8.WAGER_ACTIONS is False


def test_step8_responsive_and_accessibility_contract_tokens_exist():
    for token in (
        'MIN_TOUCH_TARGET_PX = 44',
        'CERTIFIED_VIEWPORTS = (390, 768, 1440)',
        'data-prop-page3-step8-final-polish="',
        'data-prop-page3-step8-state="ready"',
        'data-prop-page3-step8-presentation-only="true"',
        'data-prop-page3-step8-frozen-steps-1-7="true"',
        'data-prop-page3-step8-projection-weight="0.0"',
        'data-prop-page3-step8-recommendations="0"',
        'data-prop-page3-step8-wager-actions="0"',
        ':focus-visible',
        '@media(prefers-reduced-motion:reduce)',
        'min-height:44px!important',
    ):
        assert token in STEP8_SRC, token


def test_step8_polish_preserves_professional_universal_theme_contract():
    for token in (
        'rgba(125,211,252',
        'rgba(56,189,248',
        'max-width:100%',
        'min-width:0',
        'overflow',
    ):
        assert token in STEP8_SRC, token


def test_prop_page_wires_final_polish_after_step7_state():
    for token in (
        'from nfl_prop_analytics_page3_final_polish_v1 import (',
        'render_final_polish(',
        'step7_state=market_insights.get("state")',
        '"final_polish": final_polish',
    ):
        assert token in PAGE_SRC, token
    assert PAGE_SRC.index("render_market_insights(") < PAGE_SRC.index("render_final_polish(")


def test_step8_does_not_redefine_frozen_data_owners():
    forbidden = (
        "load_player_history",
        "render_analysis_line_control",
        "render_game_chart",
        "render_supporting_stats",
        "load_verified_market",
        "fetch_event_market",
        "resolve_matchup_handoff",
        "load_verified_roster_truth",
        "load_availability_depth_truth",
    )
    for token in forbidden:
        assert token not in STEP8_SRC, token
