from pathlib import Path

from api2_universal_sports_router_registry_v1 import ROUTER_REGISTRY, validate_router_registry


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_spread_registry_promotes_certified_v10_to_first_class_owner():
    registration = ROUTER_REGISTRY[("nfl", "spread")]
    assert registration.adapter_kind == "nfl-spread"
    assert registration.target == "nfl_spread_hub_v10"
    assert registration.data_gateway == "kyre_sports_api"
    assert registration.data_truth_gate == "api2_step2d_data_truth_gate_v1"
    assert registration.frontend_direct_provider is False


def test_base_runtime_has_dedicated_spread_adapter_without_generic_nfl_hub_dependencies():
    source = _read("universal_runtime_v5_loader.py")
    assert "def _nfl_spread_adapter(route: RuntimeRoute) -> DestinationAdapter:" in source
    assert 'return _import("nfl_spread_hub_v10")' in source
    assert 'return page.render_nfl_hub("Spread")' in source
    assert 'route.market_id == "spread"' in source
    assert "return _nfl_spread_adapter(route)" in source

    adapter = source.split("def _nfl_spread_adapter", 1)[1].split("\ndef ", 1)[0]
    assert 'nfl_hub_v1' not in adapter
    assert 'nfl_active_slate_runtime_v1' not in adapter
    assert 'nfl_passing_yards_next_slate_v1' not in adapter


def test_current_api2_terminal_delegates_spread_to_canonical_loader():
    source = _read("streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py")
    assert 'route.sport_id == "nfl" and route.market_id in {"rushing-yards", "spread"}' in source
    assert "return canonical_loader.resolve_destination(route)" in source


def test_current_production_chain_preserves_rushing_density_and_reaches_route_restore():
    density = _read("streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1.py")
    app = _read("app.py")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1 as prior" in density
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1" in app


def test_spread_v10_product_and_model_boundaries_remain_frozen():
    source = _read("nfl_spread_hub_v10.py")
    assert 'MODEL_VERSION = "NFL SPREAD V10' in source
    assert 'FROZEN_PRIOR = "nfl_spread_hub_v9"' in source
    assert "PRESENTATION_ONLY = True" in source
    assert "LINE_LAB_SETTLEMENT_ONLY = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source
    assert "WAGER_ACTIONS_ENABLED = False" in source


def test_step2e_registry_stays_complete_after_spread_promotion():
    assert validate_router_registry() == ()
