"""NFL V2.0 routing wrapper.

Preserves NFL V1.9 behavior for every existing market and advances only
Passing Yards to Step 1 verified matchup + quarterback identity.
"""
from __future__ import annotations

import nfl_hub_v19 as base

MODEL_VERSION = "NFL V2.0 • PASSING YARDS STEP 1 IDENTITY • V1.9 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v2 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
