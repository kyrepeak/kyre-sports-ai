from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_router_points_to_step14_selection_lock():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v54 import" in source
    assert "mlb_matchup_hub_v53" not in source


def test_step14_builds_on_certified_step13_and_step11_surfaces():
    source = _text("mlb_matchup_hub_v54.py")
    assert "import mlb_matchup_hub_v53 as step13_ui" in source
    assert "import mlb_matchup_hub_v51 as step11_ui" in source
    assert 'FROZEN_STEP13_PRESENTATION = "mlb_matchup_hub_v53"' in source
    assert 'FROZEN_STEP11_PRESENTATION = "mlb_matchup_hub_v51"' in source
    assert "step11_ui._render_stable_selectors(games_df)" in source
    assert "step13_ui._scouting_html" in source


def test_step14_freezes_one_game_and_player_identity_for_the_entire_render():
    source = _text("mlb_matchup_hub_v54.py")
    assert "def _selection_identity" in source
    assert '"game_pk"' in source
    assert '"player_id"' in source
    assert '"game_index"' in source
    assert '"player_index"' in source
    assert "def _reassert_selection" in source
    assert 'st.session_state["mh12_game"]' in source
    assert 'st.session_state["mh12_player"]' in source
    assert "_reassert_selection(identity)" in source


def test_hidden_legacy_selectors_are_locked_to_canonical_indices():
    source = _text("mlb_matchup_hub_v54.py")
    assert "def _locked_legacy_selectbox" in source
    assert 'if key == "mh12_game"' in source
    assert 'if key == "mh12_player"' in source
    assert "st.selectbox = _locked_legacy_selectbox(original_selectbox, identity)" in source


def test_step11_and_step12_profiles_must_match_game_pk_and_player_id():
    source = _text("mlb_matchup_hub_v54.py")
    assert "def _profile_matches" in source
    assert '_safe_int(profile.get("game_pk"), -1)' in source
    assert '_safe_int(profile.get("player_id"), -1)' in source
    assert "if not _profile_matches(profile, identity):" in source
    assert "if mismatch[\"value\"] or not _profile_matches(profile, identity):" in source
    assert "A result from another player/game was blocked by the selection lock" in source


def test_step1_visual_identity_is_checked_before_scouting_card_is_shown():
    source = _text("mlb_matchup_hub_v54.py")
    assert "first_step = captured_steps[0] if captured_steps else" in source
    assert "selected_name.lower() not in first_step.lower()" in source
    assert "_sync_wait_html(context, identity)" in source


def test_old_v1_matchup_snapshot_is_removed_from_normal_page():
    source = _text("mlb_matchup_hub_v54.py")
    assert "import mlb_matchup_player_v22 as legacy_snapshot" in source
    assert "def _suppress_legacy_snapshot" in source
    assert "legacy_snapshot._render_snapshot = _suppress_legacy_snapshot" in source
    assert "legacy_snapshot._render_snapshot = original_snapshot" in source
    assert ".mx22-snapshot" in source
    assert ".mx22-evidence" in source
    assert "different probability generation" in source


def test_stale_result_guard_is_selection_specific():
    source = _text("mlb_matchup_hub_v54.py")
    assert "def _signature" in source
    assert ".mx54-result{display:none!important}" in source
    assert ".mx54-current-" in source
    assert "mx54-owned" in source
    assert "_owned_scouting_html" in source


def test_step14_restores_all_temporary_runtime_patches():
    source = _text("mlb_matchup_hub_v54.py")
    assert "finally:" in source
    assert "legacy_snapshot._render_snapshot = original_snapshot" in source
    assert "final_layer._render_step12_profile = original_final_profile" in source
    assert "final_layer._render_step11_profile = original_raw_profile" in source
    assert "st.info = original_info" in source
    assert "st.warning = original_warning" in source
    assert "st.caption = original_caption" in source
    assert "st.expander = original_expander" in source
    assert "st.markdown = original_markdown" in source
    assert "st.text_input = original_text_input" in source
    assert "st.selectbox = original_selectbox" in source


def test_step14_is_presentation_only():
    source = _text("mlb_matchup_hub_v54.py")
    for forbidden in (
        "build_probability_profile(",
        "build_final_intelligence(",
        "_build_step12(",
        "5_000_000",
        "np.random",
        "default_rng",
        "render_daily_rankings(",
        "mlb_moneyline_hub",
    ):
        assert forbidden not in source


def test_historical_step13_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step13-scouting-card-hotfix.yml")
    assert "Historical exact-scope certification belongs only to Cleanup Step 13." in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step13-scouting-card-hotfix'" in source
