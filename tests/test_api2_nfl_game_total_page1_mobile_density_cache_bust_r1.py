from __future__ import annotations

from pathlib import Path


def test_production_entrypoint_evicts_stale_game_total_page_module_before_router_import() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    eviction = 'sys.modules.pop("nfl_game_totals_page1_s_tier_v1", None)'
    terminal_import = "from streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1 import"
    assert "import importlib" in source
    assert "import sys" in source
    assert eviction in source
    assert "importlib.invalidate_caches()" in source
    assert source.index(eviction) < source.index(terminal_import)


def test_cache_bust_is_narrow_and_preserves_canonical_v1_route_identity() -> None:
    app_source = Path("app.py").read_text(encoding="utf-8")
    loader_source = Path("universal_runtime_v5_loader.py").read_text(encoding="utf-8")
    block = loader_source.split("def _nfl_game_total_adapter", 1)[1].split("def _nfl_passing_yards_adapter", 1)[0]
    assert "sys.modules.clear" not in app_source
    assert 'return _import("nfl_game_totals_page1_s_tier_v1")' in block
    assert '"nfl_game_totals_page1_s_tier_v1"' in block


def test_production_entrypoint_exposes_cache_bust_deployment_marker() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    assert "API2_NFL_GAME_TOTAL_PAGE1_MODULE_CACHE_BUST_R1_20261026" in source
