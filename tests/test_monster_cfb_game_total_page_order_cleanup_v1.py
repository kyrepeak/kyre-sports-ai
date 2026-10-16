from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_SLATE = ROOT / "cfb_game_total_page2_clean_slate_v1.py"
OLD_ANALYSIS = ROOT / "cfb_game_total_page1_selected_analysis_v1.py"
OLD_ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page_order_cleanup_v1.py"
NEW_PAGE1 = ROOT / "cfb_game_total_page1_daily_slate_v1.py"
NEW_ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1.py"
PAGE1_REPAIR = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1.py"
SELECTED_ROUTE = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1.py"
ACTIVE = ROOT / "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_historical_two_page_artifacts_remain_without_owning_active_page1() -> None:
    assert OLD_SLATE.exists(), "historical clean Page-2 slate artifact must remain"
    assert OLD_ANALYSIS.exists(), "historical selected-game Page-1 artifact must remain"
    assert OLD_ROUTER.exists(), "historical page-order context must remain for frozen history"
    assert NEW_PAGE1.exists(), "new canonical Daily Slate Page 1 owner is missing"

    slate = _read(OLD_SLATE)
    analysis = _read(OLD_ANALYSIS)
    assert "Page 2 of 2" in slate
    assert "Page 1 of 2" in analysis
    assert "CFB_GAME_TOTAL_PAGE1_DAILY_SLATE_V1_ACTIVE" in _read(NEW_PAGE1)


def test_new_daily_slate_context_only_rebinds_unselected_page1_owner() -> None:
    assert NEW_ROUTER.exists(), "new Daily Slate Page-1 routing context is missing"
    router = _read(NEW_ROUTER)
    assert "streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1 as page1_repair" in router
    assert 'PAGE1_DAILY_SLATE_ROUTE = "cfb_game_total_page1_daily_slate_v1"' in router
    assert "original_page1_route = page1_repair.PAGE1_REPAIR_ROUTE" in router
    assert "page1_repair.PAGE1_REPAIR_ROUTE = PAGE1_DAILY_SLATE_ROUTE" in router
    assert "page1_repair.PAGE1_REPAIR_ROUTE = original_page1_route" in router
    assert "finally:" in router
    assert "SAME_PAGE_RUNTIME =" not in router
    assert "MAY_MODIFY_MODEL = False" in router
    assert "MAY_MODIFY_PROJECTION = False" in router
    assert "MAY_MODIFY_PROBABILITY = False" in router
    assert "MAY_MODIFY_OTHER_SPORTS = False" in router
    assert "NETWORK_CALLS_ADDED = 0" in router
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in router


def test_selected_game_runtime_pointer_is_not_rewritten_by_daily_slate_context() -> None:
    selected = _read(SELECTED_ROUTE)
    assert 'SAME_PAGE_RUNTIME = "cfb_game_total_page2_same_page_shell_repair_v1"' in selected
    router = _read(NEW_ROUTER)
    assert "cfb_game_total_page2_same_page_shell_repair_v1" not in router
    assert "cfb_game_total_page1_selected_analysis_v1" not in router


def test_page1_repair_remains_dynamic_route_seam_for_unselected_page1() -> None:
    repair = _read(PAGE1_REPAIR)
    assert "PAGE1_REPAIR_ROUTE =" in repair
    assert "importlib.import_module(PAGE1_REPAIR_ROUTE)" in repair


def test_current_production_outer_router_activates_daily_slate_not_old_page_order_context() -> None:
    active = _read(ACTIVE)
    assert "import streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1 as cfb_daily_slate" in active
    assert "with cfb_daily_slate.install_daily_slate_page1():" in active
    assert "return prior.render_app()" in active
    assert "import streamlit_memory_lazy_router_cfb_game_total_page_order_cleanup_v1 as cfb_page_order" not in active
    assert "cfb_page_order.install_page_order_cleanup" not in active


def test_outer_router_preserves_all_existing_nfl_spread_repairs() -> None:
    active = _read(ACTIVE)
    for marker in (
        "apply_route_hygiene(st.session_state, st.query_params)",
        "original_selectbox = st.selectbox",
        "original_spread_page = prior.spread_v5",
        "original_direct_spread = spread_fast_route._render_direct_spread",
        "st.selectbox = _make_selectbox_bridge(original_selectbox)",
        "prior.spread_v5 = spread_v7",
        "spread_fast_route._render_direct_spread = _render_v7_direct_spread",
        "spread_fast_route._render_direct_spread = original_direct_spread",
        "prior.spread_v5 = original_spread_page",
        "st.selectbox = original_selectbox",
    ):
        assert marker in active
