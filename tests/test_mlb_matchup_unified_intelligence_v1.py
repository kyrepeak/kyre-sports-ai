from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v27_points_only_to_current_unified_presentation():
    source = _text("mlb_matchup_hub_v27.py")
    assert "mlb_matchup_hub_v29" in source
    assert "render_matchup_hub" in source
    for forbidden in (
        "_verdict_score",
        "_calibration_from_verdict",
        "deep_scan(",
        "_simulate(",
        "render_daily_rankings(games_df)",
    ):
        assert forbidden not in source


def test_v23_groups_frozen_detailed_chain_in_one_panel():
    source = _text("mlb_matchup_player_v23.py")
    assert 'FULL_INTELLIGENCE_LABEL = "🧠 Full Matchup Intelligence — all steps"' in source
    assert "with st.expander(FULL_INTELLIGENCE_LABEL, expanded=False):" in source
    assert "frozen_detail.render_player_layer(" in source
    assert "clean._render_snapshot(snapshot_slot, games_df)" in source
    assert source.index("frozen_detail.render_player_layer(") < source.index("clean._render_snapshot(snapshot_slot, games_df)")


def test_compact_snapshot_remains_outside_unified_detail_panel():
    source = _text("mlb_matchup_player_v23.py")
    assert "snapshot_slot = st.empty()" in source
    assert source.index("snapshot_slot = st.empty()") < source.index("with st.expander(FULL_INTELLIGENCE_LABEL")
    assert source.index("clean._render_snapshot(snapshot_slot, games_df)") > source.index("with st.expander(FULL_INTELLIGENCE_LABEL")


def test_v29_preserves_collapsed_daily_rankings_and_previous_mobile_css():
    source = _text("mlb_matchup_hub_v29.py")
    assert "import mlb_matchup_hub_v28 as clean" in source
    assert "import mlb_matchup_player_v23 as player_layer" in source
    assert "clean._CSS + _EXTRA_CSS" in source
    assert 'st.expander("🏅 Daily Top 5 — 1+ Hit rankings", expanded=False)' in source


def test_unified_ui_does_not_reimplement_model_math():
    combined = _text("mlb_matchup_player_v23.py") + _text("mlb_matchup_hub_v29.py")
    for forbidden in (
        "def _calibration_from_verdict",
        "def _verdict_score",
        "def _matchup_score",
        "def _shrink",
        "def _hit_projection",
        "def _hr_projection",
        "def _hrr_projection",
        "def _render_hit_cal",
        "def _render_hr_cal",
        "def _render_hrr_cal",
    ):
        assert forbidden not in combined


def test_moneyline_is_not_imported_or_mutated_by_unified_matchup_ui():
    combined = (
        _text("mlb_matchup_hub_v27.py")
        + _text("mlb_matchup_hub_v29.py")
        + _text("mlb_matchup_player_v23.py")
    ).lower()
    assert "moneyline_hub" not in combined
    assert "mlb_moneyline" not in combined
