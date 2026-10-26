from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TERMINAL = "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_production_terminal_forwards_game_total_to_canonical_loader():
    terminal = _read(TERMINAL)
    assert 'route.sport_id == "nfl"' in terminal
    routing_block = terminal.split('if route.sport_id == "nfl"', 1)[1].split("return _prior_resolve_destination(route)", 1)[0]
    assert '"game-total"' in routing_block
    assert "return canonical_loader.resolve_destination(route)" in routing_block


def test_canonical_loader_has_dedicated_game_total_s_tier_adapter():
    source = _read("universal_runtime_v5_loader.py")
    assert "def _nfl_game_total_adapter(route: RuntimeRoute) -> DestinationAdapter:" in source
    adapter = source.split("def _nfl_game_total_adapter", 1)[1].split("\ndef ", 1)[0]
    assert 'return _import("nfl_game_totals_page1_s_tier_v1")' in adapter
    assert "return page.render_nfl_game_totals_hub()" in adapter
    assert '"nfl_game_totals_page1_s_tier_v1"' in adapter
    assert 'if route.market_id == "game-total":' in source
    assert "return _nfl_game_total_adapter(route)" in source


def test_game_total_production_target_preserves_certified_v10_projection_contract():
    s_tier = _read("nfl_game_totals_page1_s_tier_v1.py")
    compact = _read("nfl_game_totals_compact_layout_v1.py")
    v10 = _read("nfl_game_totals_hub_v10.py")

    assert "import nfl_game_totals_hub_v10 as v10" in s_tier
    assert "import nfl_game_totals_hub_v10 as v10" in compact
    assert "TOTAL_PROJECTION_ENABLED = True" in v10
    assert "PROJECTION_MODEL_ENABLED = True" in v10
    assert "PAGE_BUILD_STEP = 10" in v10
    assert "PAGE_BUILD_TOTAL = 10" in v10
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in v10


def test_game_total_no_longer_depends_on_generic_nfl_hub_fallback():
    source = _read("universal_runtime_v5_loader.py")
    adapter = source.split("def _nfl_game_total_adapter", 1)[1].split("\ndef ", 1)[0]
    assert "nfl_hub_v18" not in adapter
    assert "nfl_active_slate_runtime_v1" not in adapter
    assert "nfl_passing_yards_next_slate_v1" not in adapter
