"""NFL V3.5 routing wrapper — Passing Yards verified Kyre API bridge.

Preserves NFL V3.4 for every other NFL market and advances only Passing Yards
to V20. V20 preserves V19's recursion/timezone hardening and adds an exact-ID,
post-model Kyre Sports API bridge that can auto-fill only Step 10 market inputs.
Projection math remains untouched and sportsbook influence stays 0.0%.
"""
from __future__ import annotations

import nfl_hub_v34 as base

MODEL_VERSION = "NFL V3.5 • PASSING YARDS V20 KYRE API STEP 10 BRIDGE • V3.4 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v20 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
