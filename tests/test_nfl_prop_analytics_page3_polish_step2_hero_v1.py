from pathlib import Path

import nfl_prop_analytics_page3_hero_polish_v1 as hero

HERO_SRC = Path("nfl_prop_analytics_page3_hero_polish_v1.py").read_text()
FINAL_SRC = Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()


def test_polish_step2_is_presentation_only_and_preserves_frozen_layers():
    assert hero.PAGE3_FUN_POLISH_STEP == 2
    assert hero.PAGE3_HERO_POLISH_VERSION == "v1"
    assert hero.PRESENTATION_ONLY is True
    assert hero.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED is True
    assert hero.FROZEN_POLISH_STEP1_PROTECTED is True
    assert hero.PROJECTION_LOGIC is False
    assert hero.PROBABILITY_LOGIC is False
    assert hero.RECOMMENDATION_LOGIC is False
    assert hero.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert hero.STAKE_SIZING_ENABLED is False
    assert hero.WAGER_ACTIONS is False
    assert len(hero.TEAM_ACCENTS) == 32


def test_polish_step2_hero_visual_contract_tokens_exist():
    for token in (
        'data-prop-page3-fun-polish-step2="',
        '--ks-pa3-team-accent',
        '--ks-pa3-opp-accent',
        'conic-gradient(',
        'color-mix(in srgb',
        '.ks-pa3-headshot-wrap',
        '.ks-pa3-team-logo',
        '.ks-pa3-player-copy p',
        '.ks-pa3-player-meta span',
        '.ks-pa3-matchup-strip',
        '@media(max-width:560px)',
        '@media(prefers-reduced-motion:reduce)',
    ):
        assert token in HERO_SRC, token


def test_polish_step2_has_team_and_opponent_accent_rules_for_all_nfl_teams():
    for team in hero.TEAM_ACCENTS:
        assert f'data-prop-page3-player-team="{team}"' in hero._team_css()
        assert f'data-prop-page3-opponent="{team}"' in hero._team_css()


def test_polish_step2_does_not_own_frozen_data_or_navigation():
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
        "st.button(",
        "st.segmented_control(",
        "st.slider(",
    )
    for token in forbidden:
        assert token not in HERO_SRC, token


def test_final_polish_orders_step2_after_frozen_cleanup_step1():
    assert "from nfl_prop_analytics_page3_hero_polish_v1 import render_hero_polish" in FINAL_SRC
    assert "hero_polish = render_hero_polish()" in FINAL_SRC
    assert '"hero_polish": hero_polish' in FINAL_SRC
    assert FINAL_SRC.index("cleanup_polish = render_cleanup_polish()") < FINAL_SRC.index(
        "hero_polish = render_hero_polish()"
    )
