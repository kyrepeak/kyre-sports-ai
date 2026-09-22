from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_router_points_to_step13_hotfix():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v53 import" in source
    assert "mlb_matchup_hub_v52" not in source


def test_hotfix_restores_complete_player_spotlight_css_chain():
    source = _text("mlb_matchup_hub_v53.py")
    assert "step11_ui.step9._STEP9_CSS" in source
    assert "step11_ui.step10._STEP10_CSS" in source
    assert "step11_ui._STEP11_CSS" in source
    assert "step11_ui._render_spotlight(hero_slot, context, None)" in source
    assert "step11_ui._render_spotlight(hero_slot, context, profile)" in source


def test_hotfix_captures_finished_v2_html_instead_of_monkeypatching_step_builders():
    source = _text("mlb_matchup_hub_v53.py")
    assert "captured_steps: list[str] = []" in source
    assert "if '<div class=\"mxv2-step ' in text:" in source
    assert "captured_steps.append(text)" in source
    assert '"".join(step_html)' in source
    assert "setattr(module" not in source
    assert "_capture_renderer" not in source


def test_hotfix_keeps_certified_raw_and_final_renderers_in_the_same_run():
    source = _text("mlb_matchup_hub_v53.py")
    assert "original_raw_profile = final_layer._render_step11_profile" in source
    assert "original_final_profile = final_layer._render_step12_profile" in source
    assert "return original_raw_profile(profile)" in source
    assert "original_final_profile(profile)" in source
    assert 'profiles["raw"] = profile' in source
    assert 'profiles["final"] = profile' in source


def test_hotfix_gold_shell_and_mobile_two_column_metrics():
    source = _text("mlb_matchup_hub_v53.py")
    assert ".mx53-shell" in source
    assert "border-left:7px solid #e0b52d" in source
    assert "Full 1+ Hit Matchup Intelligence" in source
    assert "FINAL • MATCHUP EVIDENCE SUMMARY" in source
    assert "repeat(2,minmax(0,1fr))" in source
    assert "Certified evidence" in source
    assert "Watchlist" in source


def test_hotfix_header_keeps_headshot_logo_phoenix_time_and_lineup_role():
    source = _text("mlb_matchup_hub_v53.py")
    assert "hero_helpers._headshot_url(player_id)" in source
    assert "step11_ui._team_logo_url(team_id)" in source
    assert "step11_ui._phoenix_time_text(row)" in source
    assert "step11_ui.step1._role(player)" in source
    assert "Batting #" in source


def test_hotfix_suppresses_v2_notices_only_while_step_capture_is_active():
    source = _text("mlb_matchup_hub_v53.py")
    assert 'capture_active = {"value": False}' in source
    assert 'capture_active["value"] = True' in source
    assert 'capture_active["value"] = False' in source
    assert "notices.append" in source
    assert "return original_warning" in source
    assert "return original_info" in source


def test_hotfix_restores_every_streamlit_and_profile_patch():
    source = _text("mlb_matchup_hub_v53.py")
    assert "finally:" in source
    assert "final_layer._render_step12_profile = original_final_profile" in source
    assert "final_layer._render_step11_profile = original_raw_profile" in source
    assert "st.info = original_info" in source
    assert "st.warning = original_warning" in source
    assert "st.markdown = original_markdown" in source
    assert "st.selectbox = original_selectbox" in source


def test_hotfix_is_presentation_only_and_does_not_run_a_second_model():
    source = _text("mlb_matchup_hub_v53.py")
    for forbidden in (
        "build_probability_profile(",
        "build_final_intelligence(",
        "_build_step11_fallback(",
        "_build_step12(",
        "5_000_000",
        "np.random",
        "render_daily_rankings(",
        "mlb_moneyline",
    ):
        assert forbidden not in source


def test_historical_step12_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step12-scouting-card.yml")
    assert "Historical exact-scope certification belongs only to its original branch" in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step12-scouting-card'" in source
