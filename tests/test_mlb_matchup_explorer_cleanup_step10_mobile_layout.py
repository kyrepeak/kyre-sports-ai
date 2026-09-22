from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_router_points_to_cleanup_step10():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v50 import" in source
    assert "mlb_matchup_hub_v49" not in source


def test_step10_wraps_step9_without_rebuilding_model():
    source = _text("mlb_matchup_hub_v50.py")
    assert "import mlb_matchup_hub_v49 as step9" in source
    assert "import mlb_matchup_hub_v41 as current" in source
    assert 'FROZEN_STEP9_PRESENTATION = "mlb_matchup_hub_v49"' in source
    assert 'FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"' in source


def test_step10_removes_blank_hidden_shell_containers():
    source = _text("mlb_matchup_hub_v50.py")
    assert ':has(.mx47-helper)' in source
    assert ':has(.mx44-selected)' in source
    assert ':has(.mh-hero)' in source
    assert ':has(.mh-game)' in source
    assert ':has(.mh-player)' in source
    assert 'display:none!important' in source


def test_step10_keeps_roster_metadata_inside_player_buttons():
    source = _text("mlb_matchup_hub_v50.py")
    assert "_compact_roster_button_label" in source
    assert 'return f"{base} • {position}" if position else base' in source
    assert ".mx44-meta{display:none!important}" in source
    assert "step3._button_label = _compact_roster_button_label(original_button_label)" in source
    assert "step3._button_label = original_button_label" in source


def test_step10_suppresses_only_downstream_duplicate_search_player():
    source = _text("mlb_matchup_hub_v50.py")
    assert "step6._render_compact_controls(games_df)" in source
    assert "_legacy_text_input_passthrough" in source
    assert 'str(label or "").strip().lower() == "search player"' in source
    # Player controls render before the temporary downstream text-input patch.
    assert source.index("step6._render_compact_controls(games_df)") < source.index("st.text_input = _legacy_text_input_passthrough")


def test_step10_loading_state_uses_animated_dots_and_short_status():
    source = _text("mlb_matchup_hub_v50.py")
    assert "mx50-load" in source
    assert "@keyframes mx50pulse" in source
    assert 'source.replace("V2 calculating…", "Analyzing matchup…")' in source
    assert '<span></span><span></span><span></span>' in source


def test_step10_does_not_create_legacy_shell_markdown():
    source = _text("mlb_matchup_hub_v50.py")
    assert "_legacy_markdown_passthrough" in source
    assert "markers = ('class=\"mh-hero\"', 'class=\"mh-game\"', 'class=\"mh-player\"')" in source
    assert "st.markdown = _legacy_markdown_passthrough(original_markdown)" in source


def test_step10_restores_all_temporary_runtime_patches():
    source = _text("mlb_matchup_hub_v50.py")
    for expected in (
        "final_layer._render_step12_profile = original_step12_profile",
        "st.caption = original_caption",
        "st.expander = original_expander",
        "st.markdown = original_markdown",
        "st.text_input = original_text_input",
        "st.selectbox = original_selectbox",
    ):
        assert expected in source


def test_step10_is_presentation_only():
    source = _text("mlb_matchup_hub_v50.py")
    for forbidden in (
        "build_probability_profile(",
        "build_final_intelligence(",
        "5_000_000",
        "np.random",
        "monte_carlo",
        "def _calibration_from_verdict",
        "render_daily_rankings(",
        "mlb_moneyline",
    ):
        assert forbidden not in source


def test_historical_step9_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step9-player-spotlight.yml")
    assert "Historical exact-scope certification belongs only to its original branch" in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step9-player-spotlight'" in source
