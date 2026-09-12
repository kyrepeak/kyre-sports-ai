"""NFL V3.5 routing wrapper — Passing Yards early-season verified bridge.

Preserves NFL V3.4 for every other NFL market and advances only Passing Yards
to V19. V19 preserves V18's recursion isolation and adds the UTC-safe Step 4
pressure bridge so timezone-aware ESPN event timestamps cannot crash the live
Passing Yards page when recent pressure context loads.
"""
from __future__ import annotations

import nfl_hub_v34 as base

MODEL_VERSION = "NFL V3.5 • PASSING YARDS V19 UTC-SAFE PRESSURE BRIDGE • V3.4 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v19 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
