from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compatibility_router_points_to_cleanup_step12():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v52 import" in source
    assert "mlb_matchup_hub_v51" not in source


def test_step12_builds_on_certified_step11_selector_surface():
    source = _text("mlb_matchup_hub_v52.py")
    assert "import mlb_matchup_hub_v51 as step11_ui" in source
    assert 'FROZEN_STEP11_PRESENTATION = "mlb_matchup_hub_v51"' in source
    assert "step11_ui._render_stable_selectors(games_df)" in source
    assert "step11_ui._render_spotlight(hero_slot, context, None)" in source
    assert "step11_ui._phoenix_time_text" in source
    assert "step11_ui._team_logo_url" in source


def test_step12_maps_all_twelve_certified_layers_into_one_card():
    source = _text("mlb_matchup_hub_v52.py")
    expected_titles = (
        "Player + Opportunity Foundation",
        "Hitter True-Talent Profile",
        "Starting Pitcher Quality",
        "Platoon + Batter-vs-Pitcher",
        "Pitch-Mix Matchup",
        "Batted-Ball Quality",
        "Park + Weather + Defense",
        "Bullpen Path",
        "Plate Appearance Opportunity",
        "Recent Form + Stability",
        "Raw Hit Probability Engine",
        "Calibration + Final Intelligence",
    )
    for title in expected_titles:
        assert title in source
    for number in range(1, 13):
        assert f"_step({number}," in source


def test_step12_matches_gold_rail_premium_scouting_layout():
    source = _text("mlb_matchup_hub_v52.py")
    assert ".mx52-shell" in source
    assert "border-left:7px solid #e0b52d" in source
    assert "Full 1+ Hit Matchup Intelligence" in source
    assert "Verified player • Matchup Intelligence V2" in source
    assert "FINAL • MATCHUP EVIDENCE SUMMARY" in source
    assert ".mx52-big" in source
    assert ".mx52-grid" in source
    assert "repeat(2,minmax(0,1fr))" in source
    assert "Strongest verified evidence" in source
    assert "Watchlist" in source


def test_step12_keeps_phoenix_time_and_team_logos_in_player_header():
    source = _text("mlb_matchup_hub_v52.py")
    assert "🌵" in source
    assert "_phoenix_time_text(context['row'])" in source
    assert "_team_logo_url(team_id)" in source
    assert "mx52-teamlogo" in source
    assert "_headshot_url(player_id)" in source


def test_step12_captures_existing_render_points_instead_of_running_second_model():
    source = _text("mlb_matchup_hub_v52.py")
    assert "_capture_renderer" in source
    assert '(p1, "_render_step1", p1._build_foundation, "step1")' in source
    assert '(p2, "_render_step2", p2._build_profile, "step2")' in source
    assert '(p10, "_render_step10", p10._build_step10, "step10")' in source
    assert "final_layer._render_step11_profile = capture_raw" in source
    assert "final_layer._render_step12_profile = capture_final" in source
    assert 'captured["step11"] = profile' in source
    assert 'captured["step12"] = profile' in source


def test_step12_restores_every_temporary_renderer_and_streamlit_patch():
    source = _text("mlb_matchup_hub_v52.py")
    assert "original_renders =" in source
    assert "finally:" in source
    assert "for module, name, original in original_renders:" in source
    assert "setattr(module, name, original)" in source
    assert "final_layer._render_step11_profile = original_raw_profile" in source
    assert "final_layer._render_step12_profile = original_final_profile" in source
    assert "st.markdown = original_markdown" in source
    assert "st.selectbox = original_selectbox" in source


def test_step12_final_summary_uses_only_existing_final_profile_fields():
    source = _text("mlb_matchup_hub_v52.py")
    for field in (
        "final_p1_plus",
        "final_p0",
        "final_p2_plus",
        "final_expected_hits",
        "final_fair_odds_1_plus",
        "final_confidence",
        "final_confidence_label",
        "reliability_low",
        "reliability_high",
        "calibration_status_step12",
    ):
        assert field in source
    assert "Presentation synthesis only" in source
    assert "V2 probability unchanged" in source


def test_step12_is_presentation_only():
    source = _text("mlb_matchup_hub_v52.py")
    for forbidden in (
        "build_probability_profile(",
        "build_final_intelligence(",
        "_build_step12(",
        "5_000_000",
        "np.random",
        "def _run_monte_carlo",
        "render_daily_rankings(",
        "mlb_moneyline",
    ):
        assert forbidden not in source
    # Reading the certified convergence flag for display is allowed; the wrapper
    # must not execute or reimplement the simulation itself.
    assert "monte_carlo_converged" in source


def test_historical_step11_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step11-stable-selectors-phoenix.yml")
    assert "Historical exact-scope certification belongs only to its original branch" in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step11-stable-selectors-phoenix'" in source
