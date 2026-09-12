"""NFL V3.2 routing wrapper — Passing Yards cleanup step 2.

Preserves NFL V3.1 for every other NFL market and advances only Passing Yards
to V14. Certified Steps 1–10, V12 slate behavior, V13 final shell, projection
independence, and all permanent protections remain unchanged.
"""
from __future__ import annotations

import nfl_hub_v31 as base

MODEL_VERSION = "NFL V3.2 • PASSING YARDS CLEANUP STEP 2 • V3.1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v14 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
