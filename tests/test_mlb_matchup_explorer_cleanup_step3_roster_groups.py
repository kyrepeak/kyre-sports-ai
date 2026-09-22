from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compatibility_router_points_to_cleanup_step3():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v44 import" in source
    assert "render_matchup_hub" in source
    assert "mlb_matchup_hub_v43" not in source


def test_step3_builds_on_certified_step2_and_v2_renderer():
    source = _text("mlb_matchup_hub_v44.py")
    assert "import mlb_matchup_hub_v43 as step2" in source
    assert "import mlb_matchup_hub_v41 as current" in source
    assert 'FROZEN_STEP2_PRESENTATION = "mlb_matchup_hub_v43"' in source
    assert 'FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"' in source
    assert "step2._render_game_cards(games_df)" in source
    assert "current.render_matchup_hub" in source


def test_step3_replaces_player_dropdown_with_grouped_roster_buttons():
    source = _text("mlb_matchup_hub_v44.py")
    for marker in (
        "Choose a player",
        "Confirmed lineup",
        "Projected lineup",
        "Bench / active roster",
        "_render_player_buttons",
        "st.button(",
        "st.expander(",
        'st.session_state["mh12_player"]',
    ):
        assert marker in source
    assert "st.selectbox(" not in source


def test_step3_keeps_quick_player_search_and_role_filtering():
    source = _text("mlb_matchup_hub_v44.py")
    assert '"Search player"' in source
    assert "step1._matches_search" in source
    assert "step1._ordered_player_indices" in source
    assert 'groups = {"Confirmed": [], "Projected": [], "Bench": []}' in source


def test_step3_splits_each_roster_group_by_team_for_fast_scanning():
    source = _text("mlb_matchup_hub_v44.py")
    assert "def _team_split" in source
    assert '== "away"' in source
    assert '== "home"' in source
    assert 'st.columns(2, gap="small")' in source
    assert "_player_meta(player)" in source


def test_step3_bench_is_collapsed_unless_searched_or_selected():
    source = _text("mlb_matchup_hub_v44.py")
    assert 'bench_selected = selected_role == "Bench"' in source
    assert "expanded=bool(query) or bench_selected" in source


def test_step3_preserves_legacy_selection_contract_for_certified_renderer():
    source = _text("mlb_matchup_hub_v44.py")
    assert 'st.session_state["mh12_player"] = int(index)' in source
    assert "step1._legacy_selectbox_passthrough(original_selectbox)" in source
    assert "finally:" in source
    assert "st.selectbox = original_selectbox" in source


def test_step3_is_presentation_only_and_does_not_reimplement_model_math():
    source = _text("mlb_matchup_hub_v44.py")
    for forbidden in (
        "def _calibration_from_verdict",
        "def _verdict_score",
        "def build_probability_profile",
        "def build_final_intelligence",
        "deep_scan(",
        "5_000_000",
        "render_daily_rankings(",
        "mlb_matchup_probability_v1",
        "mlb_matchup_calibration_v1",
        "mlb_moneyline",
        "moneyline_hub",
    ):
        assert forbidden not in source


def test_historical_step2_exact_scope_workflow_is_scoped_to_its_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step2-game-cards.yml")
    assert "Historical exact-scope certification belongs only to its original branch" in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step2-game-cards'" in source
