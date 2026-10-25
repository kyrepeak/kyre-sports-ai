from pathlib import Path

from api2_universal_sports_router_registry_v1 import ROUTER_REGISTRY, validate_router_registry


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_game_total_registry_has_first_class_step2d_step2e_ownership():
    registration = ROUTER_REGISTRY[("nfl", "game-total")]
    assert registration.adapter_kind == "nfl-game-total"
    assert registration.target == "nfl_game_totals_compact_layout_v1"
    assert registration.data_gateway == "kyre_sports_api"
    assert registration.data_truth_gate == "api2_step2d_data_truth_gate_v1"
    assert registration.frontend_direct_provider is False


def test_game_total_canonical_path_does_not_use_generic_nfl_hub_target():
    registration = ROUTER_REGISTRY[("nfl", "game-total")]
    assert registration.target not in {"nfl_hub_v1", "nfl_hub_v18", "nfl_hub_v36"}


def test_certified_compact_layout_remains_v10_backed_and_projection_isolated():
    source = _read("nfl_game_totals_compact_layout_v1.py")
    assert 'MODEL_VERSION = "NFL GAME TOTALS COMPACT LAYOUT V1' in source
    assert "import nfl_game_totals_hub_v10 as v10" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = v10.SPORTSBOOK_PROJECTION_INFLUENCE" in source
    assert "STAKE_SIZING_ENABLED = v10.STAKE_SIZING_ENABLED" in source
    assert "WAGER_ACTIONS_ENABLED = v10.WAGER_ACTIONS_ENABLED" in source
    assert "def render_nfl_game_totals_hub()" in source


def test_universal_loader_resolves_game_total_through_dedicated_compact_adapter():
    source = _read("universal_runtime_v5_loader.py")
    assert "def _nfl_game_total_adapter(route: RuntimeRoute) -> DestinationAdapter:" in source
    assert 'return _import("nfl_game_totals_compact_layout_v1")' in source
    assert "return page.render_nfl_game_totals_hub()" in source
    assert 'route.market_id == "game-total"' in source
    assert "return _nfl_game_total_adapter(route)" in source


def test_existing_streamlit_game_total_bridge_still_points_to_compact_page():
    hub = _read("nfl_hub_v36.py")
    router = _read("streamlit_memory_lazy_router_v97.py")
    assert 'if market == "Game Total":' in hub
    assert "from nfl_game_totals_compact_layout_v1 import render_nfl_game_totals_hub" in hub
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v36"' in router
    assert 'GAME_TOTAL_MARKET = "Game Total"' in router


def test_game_total_registration_keeps_full_step2e_coverage_green():
    assert validate_router_registry() == ()
