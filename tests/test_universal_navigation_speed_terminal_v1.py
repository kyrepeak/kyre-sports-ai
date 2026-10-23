from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_v1.py"
APP = ROOT / "app.py"


def test_terminal_collapses_current_runtime_lineage_without_changing_route_semantics() -> None:
    assert TERMINAL.exists()
    source = TERMINAL.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1 as prior" in source
    assert "cfb_top_picks_page_v19" in source
    assert "render_page_experience_app_v2" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_app_activates_only_the_new_terminal_overlay() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_v1" in source
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v1" not in source
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v2" not in source
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v3" not in source
