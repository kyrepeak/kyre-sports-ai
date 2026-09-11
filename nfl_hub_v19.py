"""NFL V1.9 routing wrapper.

Preserves NFL V1.8 behavior for every existing market. Adds only a dedicated
Passing Yards route so its compact foundation can evolve independently without
changing frozen Moneyline behavior or the shared NFL Slate foundation.
"""
from __future__ import annotations

import nfl_hub_v18 as base

MODEL_VERSION = "NFL V1.9 • PASSING YARDS COMPACT FOUNDATION • V1.8 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v1 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
