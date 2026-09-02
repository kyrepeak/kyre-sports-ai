from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compatibility_router_points_to_cleanup_step5():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v46 import" in source
    assert "render_matchup_hub" in source
    assert "mlb_matchup_hub_v45" not in source


def test_step5_wraps_step4_and_certified_final_v2_without_rebuilding_math():
    source = _text("mlb_matchup_hub_v46.py")
    assert "import mlb_matchup_hub_v45 as step4" in source
    assert "import mlb_matchup_hub_v41 as current" in source
    assert "import mlb_matchup_player_v35 as final_layer" in source
    assert 'FROZEN_STEP4_PRESENTATION = "mlb_matchup_hub_v45"' in source
    assert 'FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"' in source


def test_step5_keeps_player_hero_above_deep_research():
    source = _text("mlb_matchup_hub_v46.py")
    hero_pos = source.index("hero_slot = st.empty()")
    render_hero_pos = source.index("step4._render_hero(hero_slot, context, None)")
    current_pos = source.index("current.render_matchup_hub")
    assert hero_pos < render_hero_pos < current_pos
    assert "Final result stays up top." in source


def test_step5_collapses_v2_legacy_and_rankings_by_default():
    source = _text("mlb_matchup_hub_v46.py")
    assert 'DEEP_RESEARCH_LABEL = "🔬 Deep Matchup Research — Steps 1–12"' in source
    assert 'LEGACY_RESEARCH_LABEL = "🧊 Legacy V1 Audit — optional"' in source
    assert "text == final_layer.V2_INTELLIGENCE_LABEL" in source
    assert "text == final_layer.LEGACY_AUDIT_LABEL" in source
    assert 'if "Daily Top 5" in text:' in source
    assert 'call_kwargs["expanded"] = False' in source


def test_step5_reuses_step4_final_payload_for_visible_hero():
    source = _text("mlb_matchup_hub_v46.py")
    assert "original_step12_profile = final_layer._render_step12_profile" in source
    assert "step4._step12_profile_with_hero" in source
    assert "final_layer._render_step12_profile =" in source
    assert "final_layer._render_step12_profile = original_step12_profile" in source


def test_step5_restores_streamlit_monkeypatches_in_finally():
    source = _text("mlb_matchup_hub_v46.py")
    assert "original_selectbox = st.selectbox" in source
    assert "original_expander = st.expander" in source
    assert "st.expander = _collapsed_expander(original_expander)" in source
    assert "finally:" in source
    assert "st.expander = original_expander" in source
    assert "st.selectbox = original_selectbox" in source


def test_step5_is_presentation_only():
    source = _text("mlb_matchup_hub_v46.py")
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


def test_historical_step4_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step4-player-hero.yml")
    assert "Historical exact-scope certification belongs only to its original branch" in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step4-player-hero'" in source
