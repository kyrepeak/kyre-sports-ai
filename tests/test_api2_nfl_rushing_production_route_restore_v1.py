from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py"
CANONICAL = ROOT / "universal_runtime_v5_loader" / "__init__.py"


def test_app_activates_nfl_rushing_route_restore_terminal() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1" in source


def test_route_restore_terminal_routes_nfl_rushing_through_canonical_loader() -> None:
    assert TERMINAL.exists(), "production successor terminal is missing"
    source = TERMINAL.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_bootstrap_repair_r1 as prior" in source
    assert "import universal_runtime_v5_loader as canonical_loader" in source
    assert 'route.sport_id == "nfl" and route.market_id == "rushing-yards"' in source
    assert "return canonical_loader.resolve_destination(route)" in source


def test_route_restore_terminal_cannot_reintroduce_legacy_rushing_owner_or_banned_provider_ids() -> None:
    assert TERMINAL.exists(), "production successor terminal is missing"
    source = TERMINAL.read_text(encoding="utf-8")
    assert "nfl_rushing_yards_hub_v17" not in source
    assert "Ground Game Lab" not in source
    assert "ESPN" not in source
    assert "ESPN BET" not in source
    assert "SGO" not in source


def test_canonical_rushing_loader_owns_simple_rb_grid_and_deep_page2() -> None:
    source = CANONICAL.read_text(encoding="utf-8")
    assert 'route.sport_id == "nfl" and route.market_id == "rushing-yards"' in source
    assert '"nfl_rushing_yards_simple_rb_grid_v1"' in source
    assert '_legacy._import("nfl_rushing_yards_professional_v1")' in source
    assert "legacy Rushing Yards owners are not imported" in source
