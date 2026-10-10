from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
LAYOUT = ROOT / "cfb_game_total_games_on_day_step1_layout_v1.py"
THEME = ROOT / "kyre_remaining_pages_theme_v1.py"

REFRESH_MARKER = (
    "# CFB Game Total Games on This Day Step 1 full Streamlit redeploy trigger "
    "2026-10-10 R1"
)


def test_step1_runtime_refresh_forces_fresh_streamlit_process() -> None:
    requirements = REQUIREMENTS.read_text(encoding="utf-8")
    assert REFRESH_MARKER in requirements
    assert requirements.count(REFRESH_MARKER) == 1


def test_step1_runtime_refresh_preserves_the_certified_layout_owner() -> None:
    layout = LAYOUT.read_text(encoding="utf-8")
    assert 'MODEL_VERSION = "CFB GAME TOTAL • GAMES ON THIS DAY • STEP 1 CARD LAYOUT V1"' in layout
    assert "MAY_MODIFY_PROJECTION = False" in layout
    assert "MAY_MODIFY_OTHER_SPORTS = False" in layout
    assert "NETWORK_CALLS_ADDED = 0" in layout
    assert "grid-template-columns:1fr" in layout
    assert "overflow-x:visible" in layout


def test_step1_runtime_refresh_keeps_exact_cfb_game_total_activation() -> None:
    theme = THEME.read_text(encoding="utf-8")
    assert '(sport, market) == ("CFB", "Game Total")' in theme
    assert "install_games_on_day_step1_layout" in theme
