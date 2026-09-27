from pathlib import Path

import nfl_prop_analytics_page3_cleanup_polish_v1 as polish

POLISH_SRC = Path("nfl_prop_analytics_page3_cleanup_polish_v1.py").read_text()
FINAL_SRC = Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()


def test_cleanup_step1_is_presentation_only_and_freezes_page3_data():
    assert polish.PAGE3_FUN_POLISH_STEP == 1
    assert polish.PAGE3_FUN_POLISH_VERSION == "v1"
    assert polish.PRESENTATION_ONLY is True
    assert polish.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED is True
    assert polish.PROJECTION_LOGIC is False
    assert polish.PROBABILITY_LOGIC is False
    assert polish.RECOMMENDATION_LOGIC is False
    assert polish.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert polish.STAKE_SIZING_ENABLED is False
    assert polish.WAGER_ACTIONS is False


def test_cleanup_step1_targets_only_visible_markup_and_locked_card_presentation():
    for token in (
        'data-prop-page3-fun-polish-step1="',
        '[data-testid="stMarkdown"]:has(.ks-pa5-chart) pre',
        '[data-testid="stMarkdown"]:has(.ks-pa5-chart) code',
        '.ks-pa7mi-locked',
        '.ks-pa7mi-locked .ks-pa7mi-head',
        '.ks-pa7mi-locked>p',
        'rgba(56,189,248',
        'max-width:100%',
    ):
        assert token in POLISH_SRC, token


def test_cleanup_step1_does_not_own_any_frozen_data_path():
    forbidden = (
        "load_player_history",
        "render_analysis_line_control",
        "build_game_chart_spec",
        "render_supporting_stats",
        "load_verified_market",
        "fetch_event_market",
        "resolve_matchup_handoff",
        "load_verified_roster_truth",
        "load_availability_depth_truth",
        "query_params",
        "session_state",
    )
    for token in forbidden:
        assert token not in POLISH_SRC, token


def test_final_step8_layer_wires_cleanup_after_existing_step8_markup():
    assert "from nfl_prop_analytics_page3_cleanup_polish_v1 import render_cleanup_polish" in FINAL_SRC
    assert "cleanup_polish = render_cleanup_polish()" in FINAL_SRC
    assert '"cleanup_polish": cleanup_polish' in FINAL_SRC
    assert FINAL_SRC.index("st.markdown(") < FINAL_SRC.index("cleanup_polish = render_cleanup_polish()")
