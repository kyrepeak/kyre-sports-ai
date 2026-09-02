from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v27_is_compatibility_entrypoint_only():
    source = _text("mlb_matchup_hub_v27.py")
    assert "mlb_matchup_hub_v28" in source
    assert "render_matchup_hub" in source
    for forbidden in (
        "_verdict_score",
        "_calibration_from_verdict",
        "deep_scan(",
        "_simulate(",
        "render_daily_rankings(games_df)",
    ):
        assert forbidden not in source


def test_v28_declares_frozen_matchup_chain_and_mobile_ui_only():
    source = _text("mlb_matchup_hub_v28.py")
    for module in (
        '"mlb_matchup_player_v21"',
        '"mlb_matchup_player_v20"',
        '"mlb_matchup_player_v19"',
        '"mlb_matchup_player_v18"',
        '"mlb_matchup_player_v15"',
        '"mlb_matchup_hub_v14"',
        '"mlb_matchup_hub_v13"',
        '"mlb_matchup_hub_v12"',
    ):
        assert module in source
    assert "cleaner mobile presentation only" in source
    assert 'st.expander("🏅 Daily Top 5 — 1+ Hit rankings", expanded=False)' in source
    assert ".mx22-snapshot{" in source
    assert "@media(max-width:640px)" in source


def test_v22_reuses_frozen_step5_grade_and_step4_result():
    source = _text("mlb_matchup_player_v22.py")
    assert "frozen._grade" in source
    assert "v20._current_step4_info" in source
    assert "v19._verdict_score" in source
    assert "MATCHUP SNAPSHOT" in source
    assert 'st.expander("🔎 More matchup evidence", expanded=False)' in source


def test_clean_ui_does_not_reimplement_matchup_math():
    combined = _text("mlb_matchup_player_v22.py") + _text("mlb_matchup_hub_v28.py")
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


def test_moneyline_is_not_imported_or_mutated_by_matchup_ui():
    combined = (
        _text("mlb_matchup_hub_v27.py")
        + _text("mlb_matchup_hub_v28.py")
        + _text("mlb_matchup_player_v22.py")
    ).lower()
    assert "moneyline_hub" not in combined
    assert "mlb_moneyline" not in combined
