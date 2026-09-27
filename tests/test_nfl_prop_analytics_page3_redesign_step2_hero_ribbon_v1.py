from pathlib import Path
import nfl_prop_analytics_page3_redesign_step2_hero_ribbon_v1 as r2

SRC = Path("nfl_prop_analytics_page3_redesign_step2_hero_ribbon_v1.py").read_text()
FINAL = Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()

def test_redesign_step2_contract():
    assert r2.PAGE3_REDESIGN_STEP == 2
    assert r2.PAGE3_REDESIGN_STEP2_VERSION == "v1"
    assert r2.PRESENTATION_ONLY is True
    assert r2.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED is True
    assert r2.FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED is True
    assert r2.FROZEN_REDESIGN_STEP1_PROTECTED is True
    assert r2.INTERACTION_BEHAVIOR_CHANGED is False
    assert r2.DATA_OWNERSHIP_CHANGED is False
    assert r2.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert r2.PROJECTION_LOGIC is False
    assert r2.PROBABILITY_LOGIC is False
    assert r2.RECOMMENDATION_LOGIC is False
    assert r2.STAKE_SIZING_ENABLED is False
    assert r2.WAGER_ACTIONS is False
    assert r2.CERTIFIED_VIEWPORTS == (390, 768, 1440)

def test_redesign_step2_visual_tokens():
    for token in (
        'data-prop-page3-redesign-step2="',
        ".ks-pa3-hero",
        ".ks-pa3-team-logo",
        ".ks-pa3-headshot-wrap",
        ".ks-pa3-player-line h1",
        ".ks-pa3-stat-grid",
        ".ks-pa3-hit-card",
        "@media(max-width:560px)",
        "@media(prefers-reduced-motion:reduce)",
    ):
        assert token in SRC, token

def test_redesign_step2_does_not_own_behavior():
    for token in (
        "query_params", "session_state", "load_player_history",
        "render_analysis_line_control", "build_game_chart_spec",
        "render_supporting_stats", "load_verified_market", "fetch_event_market",
        "st.segmented_control(", "st.slider(", "st.button(",
        "resolve_matchup_handoff", "load_verified_roster_truth",
    ):
        assert token not in SRC, token

def test_redesign_step2_runs_after_frozen_step1():
    assert "from nfl_prop_analytics_page3_redesign_step2_hero_ribbon_v1 import render_redesign_step2_hero_ribbon" in FINAL
    assert "redesign_step2_hero_ribbon = render_redesign_step2_hero_ribbon()" in FINAL
    assert '"redesign_step2_hero_ribbon": redesign_step2_hero_ribbon' in FINAL
    assert FINAL.index("redesign_step1_shell = render_redesign_step1_shell()") < FINAL.index(
        "redesign_step2_hero_ribbon = render_redesign_step2_hero_ribbon()"
    )
