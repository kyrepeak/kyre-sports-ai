"""NFL Passing Yards V26 — Step 4 live ESPN pressure recovery.

Additive wrapper over certified V25. V26 changes only the pressure builder
reference owned by V19 so the active V25 -> ... -> V19 chain uses pressure V5.

V25/V24/V23/V22/V21/V20 presentation, exact-ID protections, Kyre Sports API
Step 10 integration, frozen projection/distribution/market math, sportsbook
projection influence 0.0%, and stake sizing OFF remain untouched.
"""
from __future__ import annotations

from typing import Any

import nfl_passing_yards_hub_v19 as pressure_bridge_owner
import nfl_passing_yards_hub_v25 as prior
import nfl_passing_yards_pressure_v5 as pressure_v5

MODEL_VERSION = "NFL PASSING YARDS V26 • STEP 4 LIVE ESPN PRESSURE RECOVERY"
FROZEN_PRIOR = "nfl_passing_yards_hub_v25"


class _PressureV5Proxy:
    """Replace only the active V19 pressure builder; forward every other read."""

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        if name == "build_pressure_matchup":
            return pressure_v5.build_pressure_matchup
        return getattr(self._wrapped, name)


def render_nfl_passing_yards_hub() -> None:
    original_pressure_module = pressure_bridge_owner.pressure_v3
    pressure_bridge_owner.pressure_v3 = _PressureV5Proxy(original_pressure_module)
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        pressure_bridge_owner.pressure_v3 = original_pressure_module


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_PressureV5Proxy",
    "render_nfl_passing_yards_hub",
]
