from pathlib import Path
import nfl_prop_analytics_page3_final_coherence_polish_v1 as final5

SRC = Path("nfl_prop_analytics_page3_final_coherence_polish_v1.py").read_text()
FINAL = Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()

def test_step5_contract():
    assert final5.PAGE3_FUN_POLISH_STEP == 5
    assert final5.PAGE3_FINAL_COHERENCE_VERSION == "v1"
    assert final5.PRESENTATION_ONLY is True
    assert final5.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED is True
    assert final5.FROZEN_POLISH_STEPS_1_TO_4_PROTECTED is True
    assert final5.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert final5.PROJECTION_LOGIC is False
    assert final5.PROBABILITY_LOGIC is False
    assert final5.RECOMMENDATION_LOGIC is False
    assert final5.STAKE_SIZING_ENABLED is False
    assert final5.WAGER_ACTIONS is False
    assert final5.CERTIFIED_VIEWPORTS == (390, 768, 1440)

def test_step5_visual_tokens():
    for token in (
        'data-prop-page3-fun-polish-step5="',
        '.ks-pa3-hero,.ks-pa3-stats,.ks-pa4-line,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi,.ks-pa8-page',
        '.ks-pa3-stat-grid,.ks-pa4-line-grid,.ks-pa6-grid,.ks-pa7mi-grid,.ks-pa7mi-insights',
        '.ks-pa5-scroll::-webkit-scrollbar-thumb',
        '[data-testid="stSegmentedControl"]',
        '[data-testid="stSlider"]',
        '@media(max-width:560px)',
        '@media(prefers-reduced-motion:reduce)',
    ):
        assert token in SRC, token

def test_step5_does_not_own_frozen_behavior():
    forbidden = (
        "query_params", "session_state", "load_player_history",
        "render_analysis_line_control", "build_game_chart_spec",
        "render_supporting_stats", "load_verified_market", "fetch_event_market",
        "st.segmented_control(", "st.slider(", "st.button(",
        "resolve_matchup_handoff", "load_verified_roster_truth",
    )
    for token in forbidden:
        assert token not in SRC, token

def test_step5_is_ordered_after_steps_1_to_4():
    assert "from nfl_prop_analytics_page3_final_coherence_polish_v1 import render_final_coherence_polish" in FINAL
    assert "final_coherence_polish = render_final_coherence_polish()" in FINAL
    assert '"final_coherence_polish": final_coherence_polish' in FINAL
    assert FINAL.index("cleanup_polish = render_cleanup_polish()") < FINAL.index(
        "hero_polish = render_hero_polish()"
    ) < FINAL.index("controls_polish = render_controls_polish()") < FINAL.index(
        "data_panels_polish = render_data_panels_polish()"
    ) < FINAL.index("final_coherence_polish = render_final_coherence_polish()")
