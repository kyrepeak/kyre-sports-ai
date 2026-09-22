"""NFL Passing Yards V19 — Step 4 UTC-safe pressure bridge routing.

V18 isolates V17's shared-module writes so the early-season bridges cannot call
themselves recursively. V19 preserves that protection and advances only V17's
pressure bridge reference from V2 to UTC-safe V3.

The replacement is a module proxy attached only to V17's local ``pressure_v2``
reference. The real V2 module object remains untouched so V3 can delegate to it
without recursion. The original V17 module reference is restored in a
``finally`` block.

No projection math, probability, market grading, identity, CFB behavior, source
hierarchy, or fail-closed contract changes. Sportsbook influence remains 0.0%
and stake sizing remains OFF.
"""
from __future__ import annotations

from typing import Any

import nfl_passing_yards_hub_v17 as bridge_owner
import nfl_passing_yards_hub_v18 as prior
import nfl_passing_yards_pressure_v3 as pressure_v3

MODEL_VERSION = "NFL PASSING YARDS V19 • STEP 4 UTC-SAFE PRESSURE BRIDGE"
FROZEN_PRIOR = "nfl_passing_yards_hub_v18"


class _PressureBridgeProxy:
    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        if name == "build_pressure_matchup":
            return pressure_v3.build_pressure_matchup
        return getattr(self._wrapped, name)


def render_nfl_passing_yards_hub() -> None:
    original_pressure_module = bridge_owner.pressure_v2
    bridge_owner.pressure_v2 = _PressureBridgeProxy(original_pressure_module)
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        bridge_owner.pressure_v2 = original_pressure_module


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "render_nfl_passing_yards_hub",
]
