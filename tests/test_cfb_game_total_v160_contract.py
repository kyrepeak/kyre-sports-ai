from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "cfb_game_total_clean_page_v10.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v155.py"
APP = ROOT / "app.py"


V160_MARKERS = (
    "CFB GAME TOTAL • CLEAN PAGE V160 ACTIVE",
    "Matchup Foundation",
    "Game Total Answer",
    "Team Evidence",
    "Step 8 • DATA LIMITED",
    "Final Model Summary",
    "Top 5",
)


def test_v160_renderer_is_additive_over_frozen_v159_presentation():
    assert RENDERER.exists(), "V160 must add a new renderer instead of mutating V159"
    source = RENDERER.read_text(encoding="utf-8")
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v9"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    for marker in V160_MARKERS:
        assert marker in source


def test_v160_temporarily_replaces_only_frozen_v9_stylesheet_then_restores_it():
    source = RENDERER.read_text(encoding="utf-8")
    assert "original_css = prior._V159_CSS" in source
    assert "prior._V159_CSS = _V160_CSS" in source
    assert "finally:" in source
    assert "prior._V159_CSS = original_css" in source


def test_v155_router_changes_only_cfb_game_total_and_delegates_everything_else():
    assert ROUTER.exists(), "V160 must add a new router instead of mutating V154"
    source = ROUTER.read_text(encoding="utf-8")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v154"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v10"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert '"College Football"' in source
    assert '"Game Total"' in source
    assert "prior.render_app" in source


def test_production_entrypoint_activates_router_v155_only():
    source = APP.read_text(encoding="utf-8")
    assert "STREAMLIT_MAIN_V155_CFB_GAME_TOTAL_V160_VISUAL_PARITY_2026-09-17" in source
    assert "from streamlit_memory_lazy_router_v155 import record_bootstrap_import_ms, render_app" in source
