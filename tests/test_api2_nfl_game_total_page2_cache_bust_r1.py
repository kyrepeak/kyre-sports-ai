from pathlib import Path


APP = Path("app.py")
ROUTER_OWNER = "streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page1_live_route_restore_r1"
MARKER = "API2_NFL_GAME_TOTAL_PAGE2_STIER_CACHE_BUST_R1_20261027"


def test_page2_cache_bust_evicts_stale_route_modules_before_runtime_import() -> None:
    source = APP.read_text(encoding="utf-8")
    owner_import = source.index(f"from {ROUTER_OWNER} import")

    required_evictions = (
        'sys.modules.pop("universal_runtime_v5_loader", None)',
        f'sys.modules.pop("{ROUTER_OWNER}", None)',
        'sys.modules.pop("nfl_game_totals_hub_v12", None)',
    )
    for statement in required_evictions:
        assert statement in source
        assert source.index(statement) < owner_import


def test_page2_cache_bust_heartbeat_is_browser_visible() -> None:
    source = APP.read_text(encoding="utf-8")
    assert MARKER in source
    assert "_NFL_GAME_TOTAL_PAGE2_STIER_CACHE_BUST_HEARTBEAT" in source
    assert "_NFL_GAME_TOTAL_PAGE2_STIER_CACHE_BUST_HEARTBEAT}" in source


def test_page2_cache_bust_does_not_evict_frozen_page1_owner() -> None:
    source = APP.read_text(encoding="utf-8")
    assert 'sys.modules.pop("nfl_game_totals_page1_s_tier_v1", None)' in source
    assert 'sys.modules.pop("nfl_game_totals_hub_v11", None)' not in source
