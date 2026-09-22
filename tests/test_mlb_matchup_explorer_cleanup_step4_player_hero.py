from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compatibility_router_points_to_cleanup_step4():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v45 import" in source
    assert "mlb_matchup_hub_v44" not in source


def test_step4_builds_on_step3_and_keeps_certified_v2_frozen():
    source = _text("mlb_matchup_hub_v45.py")
    assert "import mlb_matchup_hub_v44 as step3" in source
    assert "import mlb_matchup_hub_v41 as current" in source
    assert "import mlb_matchup_player_v35 as final_layer" in source
    assert 'FROZEN_STEP3_PRESENTATION = "mlb_matchup_hub_v44"' in source
    assert 'FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"' in source
    assert "step3._render_roster_groups" in source
    assert "current.render_matchup_hub" in source


def test_step4_hero_contains_requested_player_identity_and_matchup_fields():
    source = _text("mlb_matchup_hub_v45.py")
    for marker in (
        "Selected player • matchup summary",
        "batting slot",
        "opponent_pitcher",
        "batter_hand",
        "pitcher_hand",
        "Season AVG",
        "Season OPS",
        "Season hits",
        "Season HR",
    ):
        assert marker in source


def test_step4_adds_real_mlb_player_headshot_with_generic_fallback_transform():
    source = _text("mlb_matchup_hub_v45.py")
    assert "def _headshot_url" in source
    assert "img.mlbstatic.com/mlb-photos/image/upload" in source
    assert "d_people:generic:headshot:silo:current.png" in source
    assert "headshot/67/current" in source
    assert 'class="mx45-photo"' in source


def test_step4_hero_surfaces_certified_final_probability_confidence_and_expected_hits():
    source = _text("mlb_matchup_hub_v45.py")
    for marker in (
        "Final 1+ hit probability",
        "final_p1_plus",
        "final_confidence",
        "final_expected_hits",
        "Expected hits",
        "Confidence",
    ):
        assert marker in source


def test_step4_intercepts_existing_step12_result_instead_of_running_model_twice():
    source = _text("mlb_matchup_hub_v45.py")
    assert "original_step12_profile = final_layer._render_step12_profile" in source
    assert "final_layer._render_step12_profile = _step12_profile_with_hero" in source
    assert "final_layer._render_step12_profile = original_step12_profile" in source
    assert "hero_slot = st.empty()" in source
    assert "_build_step12(" not in source
    assert "build_final_intelligence(" not in source
    assert "build_probability_profile(" not in source
    assert "5_000_000" not in source


def test_step4_restores_all_temporary_runtime_patches():
    source = _text("mlb_matchup_hub_v45.py")
    assert "original_selectbox = st.selectbox" in source
    assert "finally:" in source
    assert "final_layer._render_step12_profile = original_step12_profile" in source
    assert "st.selectbox = original_selectbox" in source


def test_step4_does_not_touch_model_or_moneyline_implementations():
    source = _text("mlb_matchup_hub_v45.py")
    for forbidden in (
        "mlb_moneyline",
        "moneyline_hub",
        "def _calibration_from_verdict",
        "def _verdict_score",
        "render_daily_rankings(",
    ):
        assert forbidden not in source


def test_historical_step3_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step3-roster-groups.yml")
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step3-roster-groups'" in source
    assert "Historical exact-scope certification belongs only to its original branch" in source
