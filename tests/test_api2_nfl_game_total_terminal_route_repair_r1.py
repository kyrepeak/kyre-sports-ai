from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TERMINAL = "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_production_entrypoint_uses_terminal_chain_that_owns_game_total():
    app = _read("app.py")
    density = _read("streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1.py")
    terminal = _read(TERMINAL)

    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1" in app
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1 as prior" in density
    assert 'route.market_id in {"rushing-yards", "spread", "game-total"}' in terminal
    assert "return canonical_loader.resolve_destination(route)" in terminal


def test_game_total_terminal_route_reaches_compact_v10_projection_stack():
    terminal = _read(TERMINAL)
    canonical = _read("universal_runtime_v5_loader.py")
    compact = _read("nfl_game_totals_compact_layout_v1.py")
    v10 = _read("nfl_game_totals_hub_v10.py")

    assert 'route.market_id in {"rushing-yards", "spread", "game-total"}' in terminal
    assert 'return _import("nfl_game_totals_compact_layout_v1")' in canonical
    assert "import nfl_game_totals_hub_v10 as v10" in compact
    assert "TOTAL_PROJECTION_ENABLED = True" in v10
    assert "PAGE_BUILD_STEP = 10" in v10
    assert "PAGE_BUILD_TOTAL = 10" in v10


def test_game_total_terminal_repair_preserves_projection_firewall():
    terminal = _read(TERMINAL)
    canonical = _read("universal_runtime_v5_loader.py")
    v10 = _read("nfl_game_totals_hub_v10.py")

    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in terminal
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in v10
    assert 'route.market_id == "game-total"' in canonical
