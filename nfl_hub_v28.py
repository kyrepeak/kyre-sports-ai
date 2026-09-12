"""NFL V2.8 routing wrapper.

Preserves NFL V2.7 behavior for every existing market and advances only
Passing Yards to Step 9 outcome distribution + probability.
"""
from __future__ import annotations

import nfl_hub_v27 as base

MODEL_VERSION = "NFL V2.8 • PASSING YARDS STEP 9 DISTRIBUTION + PROBABILITY • V2.7 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v10 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
