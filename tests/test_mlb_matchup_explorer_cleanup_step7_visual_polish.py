from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compatibility_router_points_to_cleanup_step7():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v48 import" in source
    assert "render_matchup_hub" in source
    assert "mlb_matchup_hub_v47" not in source


def test_step7_wraps_certified_step6_and_v2_without_rebuilding_math():
    source = _text("mlb_matchup_hub_v48.py")
    assert "import mlb_matchup_hub_v47 as step6" in source
    assert "import mlb_matchup_hub_v46 as step5" in source
    assert "import mlb_matchup_hub_v45 as step4" in source
    assert "import mlb_matchup_hub_v41 as current" in source
    assert 'FROZEN_STEP6_PRESENTATION = "mlb_matchup_hub_v47"' in source
    assert 'FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"' in source


def test_step7_removes_redundant_legacy_summary_shell():
    source = _text("mlb_matchup_hub_v48.py")
    assert ".mh-hero,.mh-game,.mh-player{display:none!important}" in source
    assert ".mx46-note,.mx47-helper,.mx45-note{display:none!important}" in source
    assert 'Matchup Explorer' in source
    assert 'the final player result stays front and center' in source


def test_step7_shortens_player_result_labels_without_changing_values():
    source = _text("mlb_matchup_hub_v48.py")
    assert "source = step4._hero_html(context, final)" in source
    assert '"Final 1+ hit probability": "1+ hit"' in source
    assert '"Expected hits": "Exp. hits"' in source
    assert '"Final V2:": "Model:"' in source
    assert 'source.replace("Model: WAITING", "Model: calculating…")' in source


def test_step7_keeps_compact_controls_and_collapsed_research():
    source = _text("mlb_matchup_hub_v48.py")
    assert "step6._render_compact_controls(games_df)" in source
    assert "st.expander = step5._collapsed_expander(original_expander)" in source
    assert "st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)" in source
    assert "current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)" in source


def test_step7_updates_hero_from_existing_step12_profile_once_rendered():
    source = _text("mlb_matchup_hub_v48.py")
    assert "_step12_profile_with_polished_hero" in source
    assert "_render_polished_hero(slot, context, profile)" in source
    assert "return original(profile)" in source
    assert "final_layer._render_step12_profile = _step12_profile_with_polished_hero(" in source


def test_step7_restores_all_temporary_streamlit_patches():
    source = _text("mlb_matchup_hub_v48.py")
    assert "original_selectbox = st.selectbox" in source
    assert "original_expander = st.expander" in source
    assert "original_step12_profile = final_layer._render_step12_profile" in source
    assert "finally:" in source
    assert "final_layer._render_step12_profile = original_step12_profile" in source
    assert "st.expander = original_expander" in source
    assert "st.selectbox = original_selectbox" in source


def test_step7_mobile_css_strengthens_result_hierarchy():
    source = _text("mlb_matchup_hub_v48.py")
    assert "@media(max-width:640px)" in source
    assert ".mx45-name{font-size:1.58rem!important" in source
    assert ".mx45-final-cell.mx45-prob b{font-size:1.38rem!important}" in source
    assert ".mx47-kicker{display:none!important}" in source


def test_step7_is_presentation_only():
    source = _text("mlb_matchup_hub_v48.py")
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


def test_historical_step6_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step6-mobile-controls.yml")
    assert "Historical exact-scope certification belongs only to its original branch" in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step6-mobile-controls'" in source
