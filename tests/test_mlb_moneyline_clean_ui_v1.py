from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v164_is_lazy_compatibility_boundary_only():
    source = _text("mlb_moneyline_hub_v164.py")
    assert "mlb_moneyline_hub_v165" in source
    assert "from mlb_moneyline_hub_v165 import render_moneyline_hub" in source
    for forbidden in (
        "simulate_run_line",
        "build_game_model",
        "history_adjustment",
        "_moneyline_probabilities",
        "requests.get",
    ):
        assert forbidden not in source


def test_v165_explicitly_freezes_existing_model_chain():
    source = _text("mlb_moneyline_hub_v165.py")
    for module in (
        '"mlb_moneyline_hub_v163"',
        '"moneyline_hub_v162"',
        '"moneyline_hub_v161"',
        '"moneyline_hub_v16"',
    ):
        assert module in source
    assert "projection, simulation, probability" in source
    assert "ranking, selection and fair" in source


def test_v165_restores_real_mobile_card_layout():
    source = _text("mlb_moneyline_hub_v165.py")
    assert ".ks-pick-card{" in source
    assert 'grid-template-areas:"rank rank" "main right"' in source
    assert ".ks-prob{" in source
    assert ".ks-meta-line{" in source
    assert "@media(max-width:640px)" in source
    assert "white-space:nowrap" in source


def test_v165_collapses_live_board_and_keeps_details_optional():
    source = _text("mlb_moneyline_hub_v165.py")
    assert 'st.expander("📡 Live sportsbook board", expanded=False)' in source
    # Existing V16.1 cards own the H2H/recent-form <details>; V16.5 styles the
    # same element rather than rebuilding or expanding it.
    assert ".ks-card-details" in source
    assert "<details" not in source


def test_step7c_api_context_stays_display_only_exact_id_and_non_wagering():
    source = _text("mlb_moneyline_hub_v165.py")
    assert 'f"{root}/api/v1/mlb/odds"' in source
    assert "moneyline_api_context_for_result" in source
    assert "display-only" in source
    # The inherited Step 7C safety contract should explicitly report wagering
    # impact as false; the presentation wrapper must never enable it.
    assert '"wagering_impact": False' in source
    assert '"wagering_impact": True' not in source


def test_clean_ui_does_not_implement_model_math():
    source = _text("mlb_moneyline_hub_v165.py")
    for forbidden in (
        "def _moneyline_probabilities",
        "def _scan_game",
        "simulate_run_line(",
        "build_game_model(",
        "history_adjustment(",
    ):
        assert forbidden not in source
