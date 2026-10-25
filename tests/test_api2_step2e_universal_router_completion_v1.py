from pathlib import Path

from api2_universal_sports_router_registry_v1 import (
    API2_STEP2E_UNIVERSAL_ROUTER_COMPLETION_V1_FROZEN,
    ROUTER_REGISTRY,
    covered_route_keys,
    validate_router_registry,
)
from universal_sports_nav_registry_v1 import get_market, visible_sports


ROOT = Path(__file__).resolve().parents[1]
SCOPE = {"nfl", "cfb", "nba", "wnba"}


def _live_route_keys():
    return {
        (sport.id, market.id)
        for sport in visible_sports()
        if sport.id in SCOPE
        for market in sport.markets
        if market.live
    }


def test_step2e_registry_covers_every_live_api2_sports_route_explicitly():
    expected = _live_route_keys()
    assert expected
    assert covered_route_keys() == expected
    assert set(ROUTER_REGISTRY) == expected
    assert validate_router_registry() == ()


def test_step2e_registry_has_no_frontend_provider_bypasses_or_implicit_fallbacks():
    for key, registration in ROUTER_REGISTRY.items():
        assert registration.route_key == key
        assert registration.data_gateway == "kyre_sports_api"
        assert registration.data_truth_gate == "api2_step2d_data_truth_gate_v1"
        assert registration.frontend_direct_provider is False
        assert registration.adapter_kind not in {"implicit", "generic-fallback", "fail-closed"}
        assert registration.target


def test_step2e_closes_the_previously_known_router_gaps():
    required = {
        ("nfl", "receptions"),
        ("nfl", "passing-tds"),
        ("nfl", "anytime-td"),
        ("nfl", "daily-picks"),
        ("cfb", "player-props"),
        ("nba", "pra"),
    }
    assert required <= set(ROUTER_REGISTRY)
    for key in required:
        assert ROUTER_REGISTRY[key].adapter_kind != "generic-fallback"


def test_nba_pra_is_canonical_navigation_not_terminal_only_shadow():
    market = get_market("nba", "pra")
    assert market is not None
    assert market.live is True
    assert market.legacy_market == "PRA"


def test_universal_loader_consumes_step2e_registry_and_has_no_nfl_default_router():
    source = (ROOT / "universal_runtime_v5_loader.py").read_text(encoding="utf-8")
    assert "api2_universal_sports_router_registry_v1" in source
    assert "get_router_registration" in source
    assert 'targets.get(route.market_id, "nfl_hub_v18")' not in source
    assert 'route.market_id == "player-props"' in source
    assert 'route.market_id == "pra"' in source


def test_production_terminal_requires_step2e_registration_before_overlay_resolution():
    terminal = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py"
    source = terminal.read_text(encoding="utf-8")
    assert "api2_universal_sports_router_registry_v1" in source
    assert "require_registered_route" in source


def test_step2e_freeze_marker_is_hard_true_only_after_coverage_contract_exists():
    assert API2_STEP2E_UNIVERSAL_ROUTER_COMPLETION_V1_FROZEN is True
