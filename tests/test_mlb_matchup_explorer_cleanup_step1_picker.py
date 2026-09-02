from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compatibility_router_points_to_cleanup_step1():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v42 import" in source
    assert "render_matchup_hub" in source
    assert "mlb_matchup_hub_v41" not in source


def test_step1_wraps_certified_final_v2_instead_of_rebuilding_it():
    source = _text("mlb_matchup_hub_v42.py")
    assert "import mlb_matchup_hub_v41 as current" in source
    assert "FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN" in source
    assert 'FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"' in source
    assert "current.render_matchup_hub" in source


def test_step1_has_clean_game_search_player_flow():
    source = _text("mlb_matchup_hub_v42.py")
    for marker in (
        '"Game"',
        '"Search player"',
        '"Player"',
        '"mx42_game"',
        '"mh12_game"',
        '"mh12_player"',
        '"Confirmed"',
        '"Projected"',
        '"Bench"',
        "Lineup players are listed before the bench",
    ):
        assert marker in source


def test_step1_player_labels_are_short_and_role_aware():
    source = _text("mlb_matchup_hub_v42.py")
    assert "def _player_label" in source
    assert 'slot_text = f"#{slot} • "' in source
    assert 'details = " — ".join' in source
    assert "BENCH / ACTIVE ROSTER" not in source


def test_step1_suppresses_only_the_two_legacy_picker_widgets_and_restores_streamlit():
    source = _text("mlb_matchup_hub_v42.py")
    assert 'key in {"mh12_game", "mh12_player"}' in source
    assert "original_selectbox = st.selectbox" in source
    assert "st.selectbox = _legacy_selectbox_passthrough(original_selectbox)" in source
    assert "finally:" in source
    assert "st.selectbox = original_selectbox" in source


def test_step1_is_presentation_only_and_does_not_reimplement_model_math():
    source = _text("mlb_matchup_hub_v42.py")
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
