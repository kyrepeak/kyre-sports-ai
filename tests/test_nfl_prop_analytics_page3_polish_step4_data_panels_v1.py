from pathlib import Path
import nfl_prop_analytics_page3_data_panels_polish_v1 as panels

SRC = Path("nfl_prop_analytics_page3_data_panels_polish_v1.py").read_text()
FINAL = Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()

def test_step4_contract():
    assert panels.PAGE3_FUN_POLISH_STEP == 4
    assert panels.PAGE3_DATA_PANELS_POLISH_VERSION == "v1"
    assert panels.PRESENTATION_ONLY is True
    assert panels.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED is True
    assert panels.FROZEN_POLISH_STEPS_1_TO_3_PROTECTED is True
    assert panels.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert panels.PROJECTION_LOGIC is False
    assert panels.PROBABILITY_LOGIC is False
    assert panels.RECOMMENDATION_LOGIC is False
    assert panels.STAKE_SIZING_ENABLED is False
    assert panels.WAGER_ACTIONS is False
    assert panels.CERTIFIED_VIEWPORTS == (390, 768, 1440)

def test_step4_visual_tokens():
    for token in (
        'data-prop-page3-fun-polish-step4="',
        '.ks-pa3-stats,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi',
        '.ks-pa3-stat-grid article',
        '.ks-pa5-legend',
        '.ks-pa5-scroll',
        '.ks-pa6-grid article',
        '.ks-pa7mi-grid article',
        '.ks-pa7mi-insights article',
        '.ks-pa7mi-selected',
        '@media(max-width:560px)',
        '@media(prefers-reduced-motion:reduce)',
    ):
        assert token in SRC, token

def test_step4_does_not_own_frozen_behavior():
    forbidden = (
        "query_params", "session_state", "load_player_history",
        "render_analysis_line_control", "build_game_chart_spec",
        "render_supporting_stats", "load_verified_market",
        "fetch_event_market", "st.segmented_control(", "st.slider(", "st.button(",
        "resolve_matchup_handoff", "load_verified_roster_truth",
    )
    for token in forbidden:
        assert token not in SRC, token

def test_step4_is_ordered_after_steps_1_to_3():
    assert "from nfl_prop_analytics_page3_data_panels_polish_v1 import render_data_panels_polish" in FINAL
    assert "data_panels_polish = render_data_panels_polish()" in FINAL
    assert '"data_panels_polish": data_panels_polish' in FINAL
    assert FINAL.index("cleanup_polish = render_cleanup_polish()") < FINAL.index(
        "hero_polish = render_hero_polish()"
    ) < FINAL.index("controls_polish = render_controls_polish()") < FINAL.index(
        "data_panels_polish = render_data_panels_polish()"
    )
