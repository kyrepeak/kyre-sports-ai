"""NFL V2.2 routing wrapper.

Preserves NFL V2.1 behavior for every existing market and advances only
Passing Yards to Step 3 opponent pass-defense matchup context.
"""
from __future__ import annotations

import nfl_hub_v21 as base

MODEL_VERSION = "NFL V2.2 • PASSING YARDS STEP 3 PASS DEFENSE • V2.1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v4 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
