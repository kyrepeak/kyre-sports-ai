from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compatibility_router_points_to_cleanup_step9():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v49 import" in source
    assert "render_matchup_hub" in source
    assert "mlb_matchup_hub_v48" not in source


def test_step9_builds_on_certified_step7_and_frozen_v2():
    source = _text("mlb_matchup_hub_v49.py")
    assert "import mlb_matchup_hub_v48 as step7" in source
    assert "import mlb_matchup_hub_v47 as step6" in source
    assert "import mlb_matchup_hub_v46 as step5" in source
    assert "import mlb_matchup_hub_v45 as step4" in source
    assert "import mlb_matchup_hub_v41 as current" in source
    assert 'FROZEN_STEP7_PRESENTATION = "mlb_matchup_hub_v48"' in source
    assert 'FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"' in source


def test_step9_has_real_player_spotlight_structure():
    source = _text("mlb_matchup_hub_v49.py")
    assert "Player Spotlight" in source
    assert "mx49-photo-shell" in source
    assert "mx49-matchup" in source
    assert "mx49-primary" in source
    assert "mx49-season" in source
    assert "🎯 1+ Hit" in source
    assert "🛡 Confidence" in source
    assert "📈 Exp. Hits" in source


def test_step9_uses_real_mlb_headshot_and_existing_context():
    source = _text("mlb_matchup_hub_v49.py")
    assert "context = step4._selected_context(games_df)" in source
    assert "photo = step4._headshot_url(player_id)" in source
    assert "stat = ui._season_hitting(player_id, season)" in source
    assert "roster._batter_hand(player_id)" in source
    assert "roster._pitcher_hand(pitcher_id)" in source


def test_step9_updates_prediction_tiles_from_existing_step12_profile():
    source = _text("mlb_matchup_hub_v49.py")
    assert "_step12_profile_with_spotlight" in source
    assert "_render_spotlight(slot, context, profile)" in source
    assert "return original(profile)" in source
    assert 'd.get("final_p1_plus")' in source
    assert "d.get('final_confidence')" in source
    assert 'd.get("final_expected_hits")' in source


def test_step9_suppresses_wall_of_text_engine_caption():
    source = _text("mlb_matchup_hub_v49.py")
    assert '_ENGINE_CAPTION_PREFIX = "🧠 Matchup Intelligence V2 COMPLETE"' in source
    assert "st.caption = _clean_engine_caption(original_caption)" in source
    assert "startswith(_ENGINE_CAPTION_PREFIX)" in source
    assert "st.caption = original_caption" in source


def test_step9_keeps_mobile_controls_and_collapsed_research():
    source = _text("mlb_matchup_hub_v49.py")
    assert "step6._render_compact_controls(games_df)" in source
    assert "st.expander = step5._collapsed_expander(original_expander)" in source
    assert "st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)" in source
    assert "current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)" in source


def test_step9_restores_all_temporary_patches():
    source = _text("mlb_matchup_hub_v49.py")
    assert "original_selectbox = st.selectbox" in source
    assert "original_expander = st.expander" in source
    assert "original_caption = st.caption" in source
    assert "original_step12_profile = final_layer._render_step12_profile" in source
    assert "finally:" in source
    assert "final_layer._render_step12_profile = original_step12_profile" in source
    assert "st.caption = original_caption" in source
    assert "st.expander = original_expander" in source
    assert "st.selectbox = original_selectbox" in source


def test_step9_mobile_css_is_compact_and_grid_based():
    source = _text("mlb_matchup_hub_v49.py")
    assert "@media(max-width:640px)" in source
    assert ".mx49-top{position:relative;display:grid;grid-template-columns:116px 1fr" in source
    assert ".mx49-primary{position:relative;display:grid;grid-template-columns:1.35fr 1fr 1fr" in source
    assert ".mx49-season{position:relative;display:grid;grid-template-columns:repeat(4,1fr)" in source


def test_step9_is_presentation_only():
    source = _text("mlb_matchup_hub_v49.py")
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


def test_historical_step7_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step7-visual-polish.yml")
    assert "Historical exact-scope certification belongs only to its original branch" in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step7-visual-polish'" in source
