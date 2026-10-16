from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLATE = ROOT / "cfb_game_total_page2_clean_slate_v1.py"
ANALYSIS = ROOT / "cfb_game_total_page1_selected_analysis_v1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page_order_cleanup_v1.py"
ACTIVE = ROOT / "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_selected_game_is_page1_and_slate_is_page2() -> None:
    assert SLATE.exists(), "clean Page-2 slate owner is missing"
    assert ANALYSIS.exists(), "selected-game Page-1 owner is missing"
    slate = _read(SLATE)
    analysis = _read(ANALYSIS)
    assert "Page 2 of 2" in slate
    assert "Choose a Game" in slate
    assert "Page 1 of 2" in analysis
    assert "Back to Slate" in analysis
    assert "Page 2" in analysis


def test_page2_slate_removes_dense_analysis_wall_instead_of_squeezing_it() -> None:
    slate = _read(SLATE)
    assert "cfb_game_total_clean_page_v45 as prior" in slate
    assert "cfb_game_total_page1_compact_layout_v1" not in slate
    for selector in (
        ".gtvc2-tabs",
        ".gt159-total",
        ".gt227-section",
        ".gt159-section",
        ".gt159-final",
        ".gt159-top5",
    ):
        assert selector in slate
    assert "display:none!important" in slate
    assert "grid-template-columns:minmax(0,1fr) 24px minmax(0,1fr)" not in slate


def test_cfb_context_reverses_semantics_without_rewriting_frozen_analytics() -> None:
    router = _read(ROUTER)
    assert "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1 as cfb_route" in router
    assert "streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1 as page1_repair" in router
    assert 'cfb_route.SAME_PAGE_RUNTIME = "cfb_game_total_page1_selected_analysis_v1"' in router
    assert 'page1_repair.PAGE1_REPAIR_ROUTE = "cfb_game_total_page2_clean_slate_v1"' in router
    assert "finally:" in router
    assert "MAY_MODIFY_MODEL = False" in router
    assert "MAY_MODIFY_PROJECTION = False" in router
    assert "MAY_MODIFY_PROBABILITY = False" in router
    assert "NETWORK_CALLS_ADDED = 0" in router


def test_current_production_outer_router_installs_cfb_context_only_around_prior() -> None:
    active = _read(ACTIVE)
    assert "import streamlit_memory_lazy_router_cfb_game_total_page_order_cleanup_v1 as cfb_page_order" in active
    assert "with cfb_page_order.install_page_order_cleanup():" in active
    assert "return prior.render_app()" in active
