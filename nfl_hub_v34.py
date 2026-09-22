"""NFL V3.4 routing wrapper — Passing Yards cleanup step 4.

Preserves NFL V3.3 for every other NFL market and advances only Passing Yards
to V16's matchup-spotlight presentation. Certified Steps 1–10, verified slate
behavior, model independence, and all permanent protections are preserved.
"""
from __future__ import annotations

import nfl_hub_v33 as base

MODEL_VERSION = "NFL V3.4 • PASSING YARDS CLEANUP STEP 4 • V3.3 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v16 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
