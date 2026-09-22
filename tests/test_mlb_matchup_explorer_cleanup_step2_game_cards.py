from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compatibility_router_points_to_cleanup_step2():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v43 import" in source
    assert "render_matchup_hub" in source
    assert "mlb_matchup_hub_v42" not in source


def test_step2_builds_on_certified_step1_and_v2_without_rebuilding_models():
    source = _text("mlb_matchup_hub_v43.py")
    assert "import mlb_matchup_hub_v42 as step1" in source
    assert "import mlb_matchup_hub_v41 as current" in source
    assert 'FROZEN_STEP1_PRESENTATION = "mlb_matchup_hub_v42"' in source
    assert 'FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"' in source
    assert "current.render_matchup_hub" in source


def test_step2_replaces_game_dropdown_with_compact_game_cards():
    source = _text("mlb_matchup_hub_v43.py")
    for marker in (
        "def _game_card_html",
        "def _render_game_cards",
        "Choose a matchup",
        "View players",
        "venue_name",
        "away_pitcher",
        "home_pitcher",
        "first_pitch_et",
        "status",
        "st.columns(2",
    ):
        assert marker in source
    assert 'st.selectbox(\n        "Game"' not in source
    assert 'key="mx42_game"' not in source


def test_step2_card_selection_uses_existing_session_state_contract():
    source = _text("mlb_matchup_hub_v43.py")
    assert 'st.session_state["mh12_game"] = int(index)' in source
    assert 'st.session_state["mh12_player"] = 0' in source
    assert "on_click=_choose_game" in source
    assert "args=(index,)" in source


def test_step2_preserves_step1_player_search_and_lineup_first_ordering():
    source = _text("mlb_matchup_hub_v43.py")
    for marker in (
        '"Search player"',
        '"Player"',
        "step1._ordered_player_indices(players)",
        "step1._matches_search(players[i], query)",
        "step1._player_label(players[int(i)])",
        'step1._role(p)[0] == "Confirmed"',
        'step1._role(p)[0] == "Projected"',
        'step1._role(p)[0] == "Bench"',
    ):
        assert marker in source


def test_step2_suppresses_legacy_picker_only_while_certified_renderer_runs():
    source = _text("mlb_matchup_hub_v43.py")
    assert "original_selectbox = st.selectbox" in source
    assert "st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)" in source
    assert "finally:" in source
    assert "st.selectbox = original_selectbox" in source


def test_step2_is_presentation_only_and_does_not_reimplement_model_math():
    source = _text("mlb_matchup_hub_v43.py")
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
