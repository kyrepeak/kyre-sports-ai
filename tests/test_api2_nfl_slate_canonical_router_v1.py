from pathlib import Path

from api2_universal_sports_router_registry_v1 import ROUTER_REGISTRY


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_slate_registry_has_first_class_step2d_step2e_ownership():
    registration = ROUTER_REGISTRY[("nfl", "slate")]
    assert registration.adapter_kind == "nfl-slate"
    assert registration.target == "nfl_slate_runtime_v1"
    assert registration.data_gateway == "kyre_sports_api"
    assert registration.data_truth_gate == "api2_step2d_data_truth_gate_v1"
    assert registration.frontend_direct_provider is False


def test_general_nfl_slate_api_route_exists_and_uses_certified_schedule_layer():
    source = _read("sports_api/api/nfl_slate_v1.py")
    lowered = source.lower()
    assert 'APIRouter(prefix="/api/v1/nfl/slate"' in source
    assert 'SCHEMA_VERSION = "nfl_slate_v1"' in source
    assert "nfl_passing_yards_slate_v1" in source
    assert "nflverse" in lowered
    for forbidden in ("espn", "sgo", "espn bet"):
        assert forbidden not in lowered


def test_slate_gateway_is_kyre_api_only_and_validates_payload():
    source = _read("nfl_slate_gateway_v1.py")
    lowered = source.lower()
    assert 'DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"' in source
    assert '"/api/v1/nfl/slate"' in source
    assert "canonical_ids" in source
    assert "missing_to_zero" in source
    for forbidden in ("espn", "sgo", "fanduel", "draftkings", "betmgm", "caesars", "bet365"):
        assert forbidden not in lowered


def test_slate_runtime_is_dedicated_and_provider_isolated():
    source = _read("nfl_slate_runtime_v1.py")
    lowered = source.lower()
    assert "API2_NFL_SLATE_CANONICAL_ROUTER_V1_FROZEN = True" in source
    assert "def render_nfl_slate_runtime()" in source
    assert "load_nfl_slate" in source
    for forbidden in ("nfl_hub_v1", "nfl_hub_v18", "espn", "sgo", "fanduel", "draftkings", "betmgm", "caesars", "bet365"):
        assert forbidden not in lowered


def test_universal_loader_resolves_slate_through_dedicated_adapter():
    source = _read("universal_runtime_v5_loader.py")
    assert "def _nfl_slate_adapter(route: RuntimeRoute) -> DestinationAdapter:" in source
    assert 'route.market_id == "slate"' in source
    assert "return _nfl_slate_adapter(route)" in source
    assert 'return _import("nfl_slate_runtime_v1")' in source
    assert "return page.render_nfl_slate_runtime()" in source


def test_vercel_api_mounts_general_nfl_slate_router():
    source = _read("kyre_sports_api_vercel_v1.py")
    assert "import sports_api.api.nfl_slate_v1 as nfl_slate_module" in source
    assert "nfl_slate_router = nfl_slate_module.router" in source
    assert "app.include_router(nfl_slate_router)" in source


def test_slate_canonical_path_does_not_use_generic_nfl_hub_target():
    registration = ROUTER_REGISTRY[("nfl", "slate")]
    assert registration.target not in {"nfl_hub_v1", "nfl_hub_v18"}
