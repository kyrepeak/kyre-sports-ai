from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page2_route_restore_v1.py"


def test_app_activates_new_moneyline_page2_terminal_identity():
    source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page2_route_restore_v1" in source
    assert "API2_NFL_MONEYLINE_PAGE2_WAR_ROOM_ROUTE_RESTORE_R1_20261026" in source


def test_terminal_shadows_only_nfl_moneyline_to_v20():
    assert TERMINAL.exists(), "Moneyline Page2 route-restore terminal is missing"
    source = TERMINAL.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1 as prior" in source
    assert 'route.sport_id == "nfl" and route.market_id == "moneyline"' in source
    assert '"nfl_moneyline_hub_v20"' in source
    assert "return prior.resolve_destination(route)" in source
    assert "frozen_runtime.resolve_destination = resolve_destination" in source


def test_route_restore_preserves_moneyline_safety_contract():
    source = TERMINAL.read_text(encoding="utf-8") if TERMINAL.exists() else ""
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source
