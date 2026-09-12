"""NFL Passing Yards V25 — Step 4 bounded pressure fallback hotfix.

Additive wrapper over certified V24. V25 changes only the pressure builder
reference owned by V19 so the active V24 -> ... -> V19 chain uses pressure V4.

V24/V23/V22/V21 presentation, V20 Kyre Sports API Step 10 integration, frozen
projection/distribution/market math, exact-ID protections, sportsbook projection
influence 0.0%, and stake sizing OFF remain untouched.
"""
from __future__ import annotations

from typing import Any

import nfl_passing_yards_hub_v19 as pressure_bridge_owner
import nfl_passing_yards_hub_v24 as prior
import nfl_passing_yards_pressure_v4 as pressure_v4

MODEL_VERSION = "NFL PASSING YARDS V25 • STEP 4 BOUNDED EXACT-ID PRESSURE FALLBACK"
FROZEN_PRIOR = "nfl_passing_yards_hub_v24"


class _PressureV4Proxy:
    """Replace only the active V19 pressure builder; forward every other read."""

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        if name == "build_pressure_matchup":
            return pressure_v4.build_pressure_matchup
        return getattr(self._wrapped, name)


def render_nfl_passing_yards_hub() -> None:
    original_pressure_module = pressure_bridge_owner.pressure_v3
    pressure_bridge_owner.pressure_v3 = _PressureV4Proxy(original_pressure_module)
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        pressure_bridge_owner.pressure_v3 = original_pressure_module


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_PressureV4Proxy",
    "render_nfl_passing_yards_hub",
]
