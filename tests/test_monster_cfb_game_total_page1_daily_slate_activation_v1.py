from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1.py"
OUTER = ROOT / "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py"
OLD_CONTEXT = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page_order_cleanup_v1.py"
OLD_SLATE = ROOT / "cfb_game_total_page2_clean_slate_v1.py"
OLD_ANALYSIS = ROOT / "cfb_game_total_page1_selected_analysis_v1.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_daily_slate_activation_context_is_page1_only_and_restores() -> None:
    assert CONTEXT.exists(), "Daily Slate activation context is not implemented yet"
    source = _read(CONTEXT)
    assert 'PAGE1_DAILY_SLATE_ROUTE = "cfb_game_total_page1_daily_slate_v1"' in source
    assert "page1_repair.PAGE1_REPAIR_ROUTE = PAGE1_DAILY_SLATE_ROUTE" in source
    assert "original_page1_route = page1_repair.PAGE1_REPAIR_ROUTE" in source
    assert "finally:" in source
    assert "page1_repair.PAGE1_REPAIR_ROUTE = original_page1_route" in source
    assert ".SAME_PAGE_RUNTIME =" not in source
    assert "MAY_MODIFY_SELECTED_GAME_RUNTIME = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_outer_router_uses_daily_slate_context_only_around_prior() -> None:
    source = _read(OUTER)
    assert "import streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1 as cfb_daily_slate" in source
    assert "with cfb_daily_slate.install_daily_slate_page1():" in source
    assert "import streamlit_memory_lazy_router_cfb_game_total_page_order_cleanup_v1 as cfb_page_order" not in source
    assert "install_page_order_cleanup()" not in source
    assert "return prior.render_app()" in source


def test_frozen_old_presentation_artifacts_remain_present_but_not_active() -> None:
    assert OLD_CONTEXT.exists()
    assert OLD_SLATE.exists()
    assert OLD_ANALYSIS.exists()
    outer = _read(OUTER)
    assert "cfb_game_total_page2_clean_slate_v1" not in outer
    assert "cfb_game_total_page1_selected_analysis_v1" not in outer
