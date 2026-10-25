from pathlib import Path

from api2_universal_sports_router_registry_v1 import ROUTER_REGISTRY, validate_router_registry


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_daily_picks_registry_has_first_class_step2d_step2e_ownership():
    registration = ROUTER_REGISTRY[("nfl", "daily-picks")]
    assert registration.adapter_kind == "nfl-daily-picks"
    assert registration.target == "nfl_daily_picks_command_center_v4"
    assert registration.data_gateway == "kyre_sports_api"
    assert registration.data_truth_gate == "api2_step2d_data_truth_gate_v1"
    assert registration.frontend_direct_provider is False


def test_daily_picks_canonical_path_does_not_use_generic_nfl_hub_target():
    registration = ROUTER_REGISTRY[("nfl", "daily-picks")]
    assert registration.target not in {"nfl_hub_v1", "nfl_hub_v18"}


def test_existing_v4_product_owner_remains_frozen_and_projection_independent():
    source = _read("nfl_daily_picks_command_center_v4.py")
    assert 'MODEL_VERSION = "NFL DAILY PICKS V4' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "def render_nfl_daily_picks_command_center()" in source


def test_universal_loader_resolves_daily_picks_through_dedicated_v4_adapter():
    source = _read("universal_runtime_v5_loader.py")
    assert "def _nfl_daily_picks_adapter(route: RuntimeRoute) -> DestinationAdapter:" in source
    assert 'return _import("nfl_daily_picks_command_center_v4")' in source
    assert "return page.render_nfl_daily_picks_command_center()" in source
    assert 'route.market_id == "daily-picks"' in source
    assert "return _nfl_daily_picks_adapter(route)" in source


def test_daily_picks_registration_keeps_full_step2e_coverage_green():
    assert validate_router_registry() == ()
