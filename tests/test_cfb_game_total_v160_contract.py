from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "cfb_game_total_clean_page_v10.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v155.py"


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


def test_v155_router_changes_only_cfb_game_total_and_delegates_everything_else():
    assert ROUTER.exists(), "V160 must add a new router instead of mutating V154"
    source = ROUTER.read_text(encoding="utf-8")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v154"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v10"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert '"College Football"' in source
    assert '"Game Total"' in source
    assert "prior.run" in source
