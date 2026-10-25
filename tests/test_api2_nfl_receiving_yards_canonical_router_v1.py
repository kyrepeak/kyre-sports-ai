from __future__ import annotations

import ast
from pathlib import Path

from api2_universal_sports_router_registry_v1 import (
    DATA_GATEWAY,
    DATA_TRUTH_GATE,
    get_router_registration,
    validate_router_registry,
)

ROOT = Path(__file__).resolve().parents[1]
LOADER_PATH = ROOT / "universal_runtime_v5_loader.py"
PAGE_PATH = ROOT / "nfl_receiving_yards_hub_v21.py"


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"missing function: {function_name}")


def test_receiving_yards_registry_has_first_class_canonical_ownership() -> None:
    registration = get_router_registration("nfl", "receiving-yards")
    assert registration is not None
    assert registration.adapter_kind == "nfl-receiving-yards"
    assert registration.target == "nfl_receiving_yards_hub_v21"
    assert registration.data_gateway == DATA_GATEWAY == "kyre_sports_api"
    assert registration.data_truth_gate == DATA_TRUTH_GATE == "api2_step2d_data_truth_gate_v1"
    assert registration.frontend_direct_provider is False


def test_receiving_yards_registry_does_not_point_at_generic_nfl_hub() -> None:
    registration = get_router_registration("nfl", "receiving-yards")
    assert registration is not None
    assert not registration.target.startswith("nfl_hub_v")
    assert registration.adapter_kind not in {"nfl-hub", "nfl-dedicated-hub", "generic-fallback"}


def test_receiving_yards_has_dedicated_runtime_adapter() -> None:
    adapter = _function_source(LOADER_PATH, "_nfl_receiving_yards_adapter")
    assert '_import("nfl_receiving_yards_hub_v21")' in adapter
    assert "render_nfl_receiving_yards_hub()" in adapter
    assert '"nfl_receiving_yards_hub_v21"' in adapter
    assert "nfl_hub_v1" not in adapter
    assert "nfl_active_slate_runtime_v1" not in adapter
    assert "nfl_passing_yards_next_slate_v1" not in adapter


def test_receiving_yards_resolver_uses_dedicated_adapter_before_generic_fallback() -> None:
    resolver = _function_source(LOADER_PATH, "resolve_destination")
    dedicated = 'if route.market_id == "receiving-yards":\n            return _nfl_receiving_yards_adapter(route)'
    assert dedicated in resolver
    assert resolver.index(dedicated) < resolver.index("return _nfl_adapter(route, registration.target, ttl_ms=ttl)")


def test_frozen_receiving_yards_v21_page_contract_is_preserved() -> None:
    page = PAGE_PATH.read_text(encoding="utf-8")
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v20"' in page
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page
    assert "MULTI_SOURCE_REQUIRED = True" in page
    assert "DISPLAY_ONLY = True" in page
    assert "def render_nfl_receiving_yards_hub()" in page


def test_step2e_registry_remains_complete_after_receiving_yards_promotion() -> None:
    assert validate_router_registry() == ()
