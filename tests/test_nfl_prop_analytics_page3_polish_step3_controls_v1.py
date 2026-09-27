from pathlib import Path
import nfl_prop_analytics_page3_controls_polish_v1 as controls

SRC = Path("nfl_prop_analytics_page3_controls_polish_v1.py").read_text()
FINAL = Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()

def test_step3_contract():
    assert controls.PAGE3_FUN_POLISH_STEP == 3
    assert controls.PAGE3_CONTROLS_POLISH_VERSION == "v1"
    assert controls.PRESENTATION_ONLY is True
    assert controls.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED is True
    assert controls.FROZEN_POLISH_STEPS_1_TO_2_PROTECTED is True
    assert controls.MIN_TOUCH_TARGET_PX == 44
    assert controls.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert controls.PROJECTION_LOGIC is False
    assert controls.PROBABILITY_LOGIC is False
    assert controls.RECOMMENDATION_LOGIC is False
    assert controls.STAKE_SIZING_ENABLED is False
    assert controls.WAGER_ACTIONS is False

def test_step3_visual_tokens():
    for token in (
        'data-prop-page3-fun-polish-step3="',
        '[data-testid="stSegmentedControl"] button',
        'button[aria-pressed="true"]',
        '[data-testid="stSlider"] [role="slider"]',
        'min-height:44px',
        ':focus-visible',
        '@media(prefers-reduced-motion:reduce)',
        '.ks-pa4-line-intro',
        '.ks-pa4-line-grid .ks-pa4-line-value',
    ):
        assert token in SRC, token

def test_step3_does_not_own_frozen_behavior():
    forbidden = (
        "query_params", "session_state", "load_player_history",
        "render_analysis_line_control", "build_game_chart_spec",
        "st.segmented_control(", "st.slider(", "st.button(",
        "resolve_matchup_handoff", "load_verified_roster_truth",
    )
    for token in forbidden:
        assert token not in SRC, token

def test_step3_is_ordered_after_steps_1_and_2():
    assert "from nfl_prop_analytics_page3_controls_polish_v1 import render_controls_polish" in FINAL
    assert "controls_polish = render_controls_polish()" in FINAL
    assert '"controls_polish": controls_polish' in FINAL
    assert FINAL.index("cleanup_polish = render_cleanup_polish()") < FINAL.index("hero_polish = render_hero_polish()") < FINAL.index("controls_polish = render_controls_polish()")
