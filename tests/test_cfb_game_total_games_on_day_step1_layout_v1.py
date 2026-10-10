from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = ROOT / "cfb_game_total_games_on_day_step1_layout_v1.py"
THEME = ROOT / "kyre_remaining_pages_theme_v1.py"


def test_step1_additive_layout_owner_exists_and_is_presentation_only() -> None:
    assert SUBJECT.exists(), "Step-1 additive layout owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert 'MODEL_VERSION = "CFB GAME TOTAL • GAMES ON THIS DAY • STEP 1 CARD LAYOUT V1"' in text
    assert "MAY_MODIFY_PROJECTION = False" in text
    assert "MAY_MODIFY_OTHER_SPORTS = False" in text
    assert "NETWORK_CALLS_ADDED = 0" in text
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in text


def test_step1_mobile_cards_stack_full_width_without_horizontal_clipping() -> None:
    assert SUBJECT.exists(), "Step-1 additive layout owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert "@media(max-width:760px)" in text
    assert ".gt163-game-scroller" in text
    assert "grid-template-columns:1fr" in text
    assert "overflow-x:visible" in text
    assert ".gt163-game-link,.gt163-game-disabled" in text
    assert "min-width:0" in text
    assert "max-width:none" in text
    assert "width:100%" in text
    assert "white-space:normal" in text


def test_step1_preserves_existing_selector_behavior_and_selected_state() -> None:
    assert SUBJECT.exists(), "Step-1 additive layout owner is not implemented yet"
    text = SUBJECT.read_text(encoding="utf-8")
    assert "_render_game_strip" not in text
    assert ".gt163-game-link.selected" in text
    assert "install_games_on_day_step1_layout" in text
    assert "_V163_CSS" in text


def test_step1_activation_is_exactly_scoped_to_cfb_game_total() -> None:
    theme = THEME.read_text(encoding="utf-8")
    assert '(sport, market) == ("CFB", "Game Total")' in theme
    assert "cfb_game_total_games_on_day_step1_layout_v1" in theme
    assert "install_games_on_day_step1_layout" in theme
