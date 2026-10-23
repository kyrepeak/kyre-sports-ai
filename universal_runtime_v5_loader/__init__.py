"""Successor overlay adding the dedicated NFL Rushing Yards V5 destination.

The frozen Universal Runtime V5 implementation remains unchanged. This package
loads it verbatim, preserves every existing route, and intercepts only the NFL
Rushing Yards destination so it uses the Kyre Sports API RB-board successor.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "universal_runtime_v5_loader.py"
_SPEC = importlib.util.spec_from_file_location("_universal_runtime_v5_loader_verified", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("Universal Runtime V5 implementation unavailable")
_legacy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _legacy
_SPEC.loader.exec_module(_legacy)

for _name, _value in vars(_legacy).items():
    if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__file__", "__cached__"}:
        globals().setdefault(_name, _value)

_ORIGINAL_RESOLVE_DESTINATION = _legacy.resolve_destination


def _nfl_rushing_yards_adapter(route):
    """Dedicated Kyre-gateway adapter; legacy Rushing Yards owners are not imported."""
    def loader():
        _legacy._import("nfl_rushing_yards_professional_v1")
        return _legacy._import("nfl_rushing_yards_simple_rb_grid_v1")

    def renderer(page):
        return page.render_nfl_rushing_yards_simple_rb_grid()

    return _legacy.DestinationAdapter(
        (route.sport_id, route.market_id),
        loader,
        renderer,
        "nfl_rushing_yards_simple_rb_grid_v1",
        20_000,
    )


def resolve_destination(route):
    if route.sport_id == "nfl" and route.market_id == "rushing-yards":
        return _nfl_rushing_yards_adapter(route)
    return _ORIGINAL_RESOLVE_DESTINATION(route)


# Legacy helper functions resolve this global at call time; binding the successor
# here ensures internal callers and package callers share one authoritative route.
_legacy.resolve_destination = resolve_destination

__all__ = sorted(set(getattr(_legacy, "__all__", [])) | {"_nfl_rushing_yards_adapter", "resolve_destination"})
