from pathlib import Path
import nfl_prop_analytics_page3_redesign_step3_analysis_settings_v1 as r3

SRC = Path("nfl_prop_analytics_page3_redesign_step3_analysis_settings_v1.py").read_text()
FINAL = Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()

def test_redesign_step3_contract():
    assert r3.PAGE3_REDESIGN_STEP == 3
    assert r3.PAGE3_REDESIGN_STEP3_VERSION == "v1"
    assert r3.PRESENTATION_ONLY is True
    assert r3.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED is True
    assert r3.FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED is True
    assert r3.FROZEN_REDESIGN_STEPS_1_TO_2_PROTECTED is True
    assert r3.INTERACTION_BEHAVIOR_CHANGED is False
    assert r3.DATA_OWNERSHIP_CHANGED is False
    assert r3.MIN_TOUCH_TARGET_PX == 44
    assert r3.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert r3.PROJECTION_LOGIC is False
    assert r3.PROBABILITY_LOGIC is False
    assert r3.RECOMMENDATION_LOGIC is False
    assert r3.STAKE_SIZING_ENABLED is False
    assert r3.WAGER_ACTIONS is False
    assert r3.CERTIFIED_VIEWPORTS == (390, 768, 1440)

def test_redesign_step3_visual_tokens():
    for token in (
        'data-prop-page3-redesign-step3="',
        ".ks-pa3-nav-marker",
        "STEP 3  •  ANALYSIS SETTINGS",
        '[data-testid="stSegmentedControl"]',
        '[role="radiogroup"]',
        'button[aria-checked="true"]',
        "@media(max-width:560px)",
        "@media(prefers-reduced-motion:reduce)",
    ):
        assert token in SRC, token

def test_redesign_step3_does_not_own_behavior():
    for token in (
        "query_params", "session_state", "load_player_history",
        "render_analysis_line_control", "build_game_chart_spec",
        "render_supporting_stats", "load_verified_market", "fetch_event_market",
        "st.segmented_control(", "st.slider(", "st.button(",
        "resolve_matchup_handoff", "load_verified_roster_truth",
    ):
        assert token not in SRC, token

def test_redesign_step3_runs_after_frozen_step2():
    assert "from nfl_prop_analytics_page3_redesign_step3_analysis_settings_v1 import render_redesign_step3_analysis_settings" in FINAL
    assert "redesign_step3_analysis_settings = render_redesign_step3_analysis_settings()" in FINAL
    assert '"redesign_step3_analysis_settings": redesign_step3_analysis_settings' in FINAL
    assert FINAL.index("redesign_step2_hero_ribbon = render_redesign_step2_hero_ribbon()") < FINAL.index(
        "redesign_step3_analysis_settings = render_redesign_step3_analysis_settings()"
    )
