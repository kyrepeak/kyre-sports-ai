from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compatibility_router_points_to_cleanup_step6():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v47 import" in source
    assert "render_matchup_hub" in source
    assert "mlb_matchup_hub_v46" not in source


def test_step6_wraps_certified_step5_and_v2_without_rebuilding_math():
    source = _text("mlb_matchup_hub_v47.py")
    assert "import mlb_matchup_hub_v46 as step5" in source
    assert "import mlb_matchup_hub_v45 as step4" in source
    assert "import mlb_matchup_hub_v41 as current" in source
    assert 'FROZEN_STEP5_PRESENTATION = "mlb_matchup_hub_v46"' in source
    assert 'FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"' in source


def test_step6_defaults_heavy_game_and_roster_controls_closed():
    source = _text("mlb_matchup_hub_v47.py")
    assert '"Change matchup"' in source
    assert 'key="mx47_show_games"' in source
    assert '"Change player"' in source
    assert 'key="mx47_show_players"' in source
    assert source.count("value=False") >= 2
    assert "if show_games:" in source
    assert "step2._render_game_cards(games_df)" in source
    assert "if show_players:" in source
    assert "step3._render_roster_groups(games_df, game_index)" in source


def test_step6_game_to_player_handoff_and_player_autocollapse():
    source = _text("mlb_matchup_hub_v47.py")
    assert 'st.session_state["mx47_show_games"] = False' in source
    assert 'st.session_state["mx47_show_players"] = True' in source
    assert source.count('st.session_state["mx47_show_players"] = False') >= 1
    assert "step2._choose_game = _game_callback(original_choose_game)" in source
    assert "step2._choose_game = original_choose_game" in source
    assert "step3._choose_player = _player_callback(original_choose_player)" in source
    assert "step3._choose_player = original_choose_player" in source


def test_step6_keeps_summary_and_hero_before_deep_research():
    source = _text("mlb_matchup_hub_v47.py")
    summary_pos = source.index("_STEP6_CSS + _selection_summary_html(context)")
    hero_pos = source.index("hero_slot = st.empty()")
    current_pos = source.index("current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)", hero_pos)
    assert summary_pos < hero_pos < current_pos
    assert "step4._render_hero(hero_slot, context, None)" in source


def test_step6_preserves_step5_collapsed_research_behavior():
    source = _text("mlb_matchup_hub_v47.py")
    assert "original_expander = st.expander" in source
    assert "st.expander = step5._collapsed_expander(original_expander)" in source
    assert "st.expander = original_expander" in source
    assert "step4._step12_profile_with_hero" in source


def test_step6_mobile_css_reduces_selection_clutter_without_touching_model():
    source = _text("mlb_matchup_hub_v47.py")
    assert "@media(max-width:640px)" in source
    assert ".mx43-head-sub,.mx44-head-sub{display:none!important}" in source
    assert ".mx44-selected{display:none!important}" in source
    assert ".mx45-note{display:none!important}" in source
    assert "Controls stay collapsed after a selection" in source


def test_step6_is_presentation_only():
    source = _text("mlb_matchup_hub_v47.py")
    for forbidden in (
        "build_probability_profile(",
        "build_final_intelligence(",
        "5_000_000",
        "np.random",
        "monte_carlo",
        "def _calibration_from_verdict",
        "def _verdict_score",
        "render_daily_rankings(",
        "mlb_moneyline",
    ):
        assert forbidden not in source


def test_historical_step5_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step5-collapsed-research.yml")
    assert "Historical exact-scope certification belongs only to its original branch" in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step5-collapsed-research'" in source
