from pathlib import Path

from api2_universal_sports_router_registry_v1 import ROUTER_REGISTRY


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_passing_tds_registry_has_first_class_step2d_step2e_ownership():
    registration = ROUTER_REGISTRY[("nfl", "passing-tds")]
    assert registration.adapter_kind == "nfl-passing-tds"
    assert registration.target == "nfl_passing_tds_runtime_v1"
    assert registration.data_gateway == "kyre_sports_api"
    assert registration.data_truth_gate == "api2_step2d_data_truth_gate_v1"
    assert registration.frontend_direct_provider is False


def test_passing_tds_runtime_is_dedicated_provider_isolated_and_frozen():
    source = _read("nfl_passing_tds_runtime_v1.py")
    lowered = source.lower()

    assert "API2_NFL_PASSING_TDS_CANONICAL_ROUTER_V1_FROZEN = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "def render_nfl_passing_tds_runtime()" in source
    assert "semantic unavailable" in lowered

    for forbidden in (
        "nfl_hub_v1",
        "nfl_hub_v18",
        "espn",
        "espn bet",
        "sgo",
        "fanduel",
        "draftkings",
        "betmgm",
        "caesars",
        "bet365",
    ):
        assert forbidden not in lowered


def test_universal_loader_resolves_passing_tds_through_dedicated_adapter():
    source = _read("universal_runtime_v5_loader.py")
    assert "def _nfl_passing_tds_adapter(route: RuntimeRoute) -> DestinationAdapter:" in source
    assert 'route.market_id == "passing-tds"' in source
    assert "return _nfl_passing_tds_adapter(route)" in source
    assert 'return _import("nfl_passing_tds_runtime_v1")' in source
    assert "return page.render_nfl_passing_tds_runtime()" in source


def test_passing_tds_canonical_path_does_not_use_generic_nfl_hub_target():
    registration = ROUTER_REGISTRY[("nfl", "passing-tds")]
    assert registration.target not in {"nfl_hub_v1", "nfl_hub_v18"}
