"""NFL Passing Yards V27 — preserve V25 chain while activating Pressure V5.

V26 proved Pressure V5 itself against live ESPN, but its outer patch targeted
V19's ``pressure_v3`` reference. The certified V25 wrapper subsequently replaces
that same reference with its own Pressure V4 proxy before V24/V19 render, so the
V5 builder can be shadowed in the real nested route.

V27 fixes only that wrapper-routing interaction. It temporarily replaces V25's
local ``pressure_v4`` module reference with a proxy whose build method is
Pressure V5, then executes the full V26 -> V25 -> V24 ... chain. V25 therefore
keeps every frozen gate/restoration behavior while its own proxy resolves the
Step 4 builder to V5. The local reference is restored in ``finally``.

No projection, probability, distribution, market, Step 10, identity, visual,
CFB/MLB/WNBA, or other NFL logic changes. Sportsbook projection influence stays
0.0%, pressure-source projection adjustment stays 0.0, and stake sizing stays
OFF.
"""
from __future__ import annotations

from typing import Any

import nfl_passing_yards_hub_v25 as v25_owner
import nfl_passing_yards_hub_v26 as prior
import nfl_passing_yards_pressure_v5 as pressure_v5

MODEL_VERSION = "NFL PASSING YARDS V27 • STEP 4 NESTED ROUTE FIX • PRESSURE V5 ACTIVE"
FROZEN_PRIOR = "nfl_passing_yards_hub_v26"


class _PressureV5ModuleProxy:
    """Forward V25's frozen pressure module except its active build function."""

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        if name == "build_pressure_matchup":
            return pressure_v5.build_pressure_matchup
        return getattr(self._wrapped, name)


def render_nfl_passing_yards_hub() -> None:
    original_pressure_module = v25_owner.pressure_v4
    v25_owner.pressure_v4 = _PressureV5ModuleProxy(original_pressure_module)
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        v25_owner.pressure_v4 = original_pressure_module


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_PressureV5ModuleProxy",
    "render_nfl_passing_yards_hub",
]
