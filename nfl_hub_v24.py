"""NFL V2.4 routing wrapper.

Preserves NFL V2.3 behavior for every existing market and advances only
Passing Yards to Step 5 weapons + injuries personnel context.
"""
from __future__ import annotations

import nfl_hub_v23 as base

MODEL_VERSION = "NFL V2.4 • PASSING YARDS STEP 5 PERSONNEL • V2.3 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v6 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
