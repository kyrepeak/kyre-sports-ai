from pathlib import Path

from api2_universal_sports_router_registry_v1 import ROUTER_REGISTRY, validate_router_registry


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_moneyline_registry_has_first_class_step2d_step2e_ownership():
    registration = ROUTER_REGISTRY[("nfl", "moneyline")]
    assert registration.adapter_kind == "nfl-moneyline"
    assert registration.target == "nfl_moneyline_hub_v19"
    assert registration.data_gateway == "kyre_sports_api"
    assert registration.data_truth_gate == "api2_step2d_data_truth_gate_v1"
    assert registration.frontend_direct_provider is False


def test_moneyline_canonical_path_does_not_use_generic_nfl_hub_target():
    registration = ROUTER_REGISTRY[("nfl", "moneyline")]
    assert registration.target not in {"nfl_hub_v1", "nfl_hub_v18"}


def test_existing_v19_consumer_owner_remains_frozen_and_projection_independent():
    source = _read("nfl_moneyline_hub_v19.py")
    assert 'MODEL_VERSION = "NFL MONEYLINE V19' in source
    assert 'API_ADAPTER = "nfl_moneyline_market_api_v1"' in source
    assert "PRESENTATION_ONLY = True" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_MARKET_MATH = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "def render_nfl_moneyline_hub()" in source


def test_universal_loader_resolves_moneyline_through_dedicated_v19_adapter():
    source = _read("universal_runtime_v5_loader.py")
    assert "def _nfl_moneyline_adapter(route: RuntimeRoute) -> DestinationAdapter:" in source
    assert 'return _import("nfl_moneyline_hub_v19")' in source
    assert "return page.render_nfl_moneyline_hub()" in source
    assert 'route.market_id == "moneyline"' in source
    assert "return _nfl_moneyline_adapter(route)" in source


def test_existing_terminal_v21_moneyline_override_still_points_to_v19():
    source = _read("universal_runtime_v5_loader_v21.py")
    assert 'route.sport_id == "nfl" and route.market_id == "moneyline"' in source
    assert '"nfl_moneyline_hub_v19"' in source


def test_moneyline_registration_keeps_full_step2e_coverage_green():
    assert validate_router_registry() == ()
