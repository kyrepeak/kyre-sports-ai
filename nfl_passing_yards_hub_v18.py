"""NFL Passing Yards V18 — recursion-safe early-season bridge wrapper.

V17 correctly advances the live Passing Yards surface to the verified early-
season bridges, but it temporarily replaces builder functions on the shared V1
module objects used by Step 7. The V2/V3 bridge implementations delegate back to
those same V1 modules, so replacing the shared function object can create a
self-referential call loop and surface as RecursionError in production.

V18 is presentation/routing-only. It places lightweight writable proxies at the
three Step 7 module overwrite points before V17 runs. V17 can still install its
bridged defense, pressure and environment builders, but those assignments land
on the proxies instead of mutating the shared V1 modules that the bridge code
calls internally. All modules are restored in a finally block.

No projection math, probability, sportsbook influence, stake sizing, identity,
CFB behavior, source hierarchy or fail-closed contract changes. Sportsbook
projection influence remains 0.0% and stake sizing remains OFF.
"""
from __future__ import annotations

from typing import Any

import nfl_passing_yards_hub_v17 as prior

MODEL_VERSION = "NFL PASSING YARDS V18 • RECURSION-SAFE EARLY-SEASON MODULE PROXIES"
FROZEN_PRIOR = "nfl_passing_yards_hub_v17"


class _WritableModuleProxy:
    """Forward reads to a wrapped module while keeping bridge writes isolated."""

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


def render_nfl_passing_yards_hub() -> None:
    step7 = prior.step7_ui

    original_defense_module = step7.defense
    original_pressure_module = step7.pressure
    original_environment_module = step7.environment

    step7.defense = _WritableModuleProxy(original_defense_module)
    step7.pressure = _WritableModuleProxy(original_pressure_module)
    step7.environment = _WritableModuleProxy(original_environment_module)
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        step7.defense = original_defense_module
        step7.pressure = original_pressure_module
        step7.environment = original_environment_module


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "render_nfl_passing_yards_hub",
]
