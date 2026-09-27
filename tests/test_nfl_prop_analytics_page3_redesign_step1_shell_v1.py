from pathlib import Path
import nfl_prop_analytics_page3_redesign_step1_shell_v1 as shell

SRC = Path("nfl_prop_analytics_page3_redesign_step1_shell_v1.py").read_text()
FINAL = Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()

def test_redesign_step1_contract():
    assert shell.PAGE3_REDESIGN_STEP == 1
    assert shell.PAGE3_REDESIGN_STEP1_VERSION == "v1"
    assert shell.PRESENTATION_ONLY is True
    assert shell.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED is True
    assert shell.FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED is True
    assert shell.INTERACTION_BEHAVIOR_CHANGED is False
    assert shell.DATA_OWNERSHIP_CHANGED is False
    assert shell.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert shell.PROJECTION_LOGIC is False
    assert shell.PROBABILITY_LOGIC is False
    assert shell.RECOMMENDATION_LOGIC is False
    assert shell.STAKE_SIZING_ENABLED is False
    assert shell.WAGER_ACTIONS is False
    assert shell.MIN_TOUCH_TARGET_PX == 44
    assert shell.CERTIFIED_VIEWPORTS == (390, 768, 1440)

def test_redesign_step1_shell_tokens():
    for token in (
        'data-prop-page3-redesign-step1="',
        '[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker)',
        '.ks-pa3-hero,',
        '.ks-pa3-stats,',
        '.ks-pa4-line,',
        '.ks-pa5-chart,',
        '.ks-pa6-support,',
        '.ks-pa7mi,',
        '.ks-pa8-page',
        '@media(max-width:560px)',
        '@media(prefers-reduced-motion:reduce)',
    ):
        assert token in SRC, token

def test_redesign_step1_does_not_own_behavior():
    forbidden = (
        "query_params", "session_state", "load_player_history",
        "render_analysis_line_control", "build_game_chart_spec",
        "render_supporting_stats", "load_verified_market", "fetch_event_market",
        "st.segmented_control(", "st.slider(", "st.button(",
        "resolve_matchup_handoff", "load_verified_roster_truth",
    )
    for token in forbidden:
        assert token not in SRC, token

def test_redesign_step1_runs_after_frozen_fun_polish():
    assert "from nfl_prop_analytics_page3_redesign_step1_shell_v1 import render_redesign_step1_shell" in FINAL
    assert "redesign_step1_shell = render_redesign_step1_shell()" in FINAL
    assert '"redesign_step1_shell": redesign_step1_shell' in FINAL
    assert FINAL.index("final_coherence_polish = render_final_coherence_polish()") < FINAL.index(
        "redesign_step1_shell = render_redesign_step1_shell()"
    )
