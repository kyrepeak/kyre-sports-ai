from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py"
APP = ROOT / "app.py"


def test_terminal_production_overlay_owns_nfl_passing_yards() -> None:
    source = TERMINAL.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")

    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1" in app
    assert "import universal_runtime_v5_loader as canonical_loader" in source
    assert 'route.sport_id == "nfl" and route.market_id == "passing-yards"' in source
    assert "return canonical_loader.resolve_destination(route)" in source


def test_terminal_overlay_keeps_nba_pra_override_and_uses_upstream_for_other_routes() -> None:
    source = TERMINAL.read_text(encoding="utf-8")
    assert 'route.sport_id == "nba" and route.market_id == "pra"' in source
    assert "return _v1_resolve_destination(route)" in source
