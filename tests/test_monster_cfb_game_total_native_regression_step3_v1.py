from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
V44 = ROOT / "cfb_game_total_clean_page_v44.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function(source: str, name: str, next_name: str | None = None) -> str:
    start = source.index(f"def {name}(")
    if next_name is None:
        return source[start:]
    end = source.index(f"def {next_name}(", start)
    return source[start:end]


def test_step3_native_cfb_shell_and_market_set_survive_step2() -> None:
    source = _source(ROUTER)
    assert 'CFB_SPORT_LABEL = "College Football"' in source
    assert 'CFB_SHELL_MARKETS = ("Moneyline", "Over/Under", "Game Total", "Top Picks")' in source
    assert '"🎯 CFB Market"' in source
    assert "return root.render_app()" in source


def test_step3_page1_owner_and_step2_runtime_seam_are_composed() -> None:
    source = _source(ROUTER)
    shell = _function(source, "_render_page1_in_shared_shell", "_render_native_page1")
    assert 'PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v43"' in source
    assert "root._import(PAGE1_NATIVE_ROUTE)" in source
    assert "original_snapshot_render = snapshot_owner.render_game_total_hub" in shell
    assert "snapshot_owner.render_game_total_hub = runtime_repair._render_snapshot_without_stale_date_runtimeerror" in shell
    assert "snapshot_owner.render_game_total_hub = original_snapshot_render" in shell


def test_step3_selected_event_page2_remains_exact_and_isolated() -> None:
    source = _source(ROUTER)
    selected = _function(source, "_selected_game_total", "_make_page1_selectbox_bridge")
    render = _function(source, "render_app")
    assert "sync_id != event_id" in selected
    assert 'PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"' in source
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE2_RUNTIME" in render
    assert "live_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in render
    assert "render_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in render
    assert "finally:" in render
    assert "cfb_router.GAME_TOTAL_PAGE = original_cfb_page" in render
    assert "live_owner.ACTIVE_PAGE = original_live_page" in render
    assert "render_owner.ACTIVE_PAGE = original_render_page" in render


def test_step3_page1_temporary_seams_restore_after_render() -> None:
    source = _source(ROUTER)
    shell = _function(source, "_render_page1_in_shared_shell", "_render_native_page1")
    assert "original_selectbox = root.st.selectbox" in shell
    assert "original_render_nfl = root._render_nfl" in shell
    assert "original_prefixes = root._ROUTE_MODULE_PREFIXES" in shell
    assert "finally:" in shell
    assert "root.st.selectbox = original_selectbox" in shell
    assert "root._render_nfl = original_render_nfl" in shell
    assert "root._ROUTE_MODULE_PREFIXES = original_prefixes" in shell


def test_step3_product_boundaries_remain_frozen() -> None:
    router = _source(ROUTER)
    repair = _source(V44)
    for contract in (
        "MAY_MODIFY_OTHER_SPORTS = False",
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_MODEL = False",
        "MAY_MODIFY_MARKET_OWNERSHIP = False",
        "NETWORK_CALLS_ADDED = 0",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
    ):
        assert contract in router
    assert "MAY_MODIFY_PAGE2 = False" in repair
    assert "NEW_PROVIDER_PATHS_ADDED = 0" in repair
    assert "STALE_DOWNSTREAM_DAY_USES_PINNED_SNAPSHOT = True" in repair
