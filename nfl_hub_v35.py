"""NFL V3.5 routing wrapper — Passing Yards verified Kyre API + visual identity.

Preserves NFL V3.4 for every other NFL market and advances only Passing Yards
to V21. V21 is a visual-only exact-ID team-logo overlay over certified V20.
V20's Kyre Sports API Step 10 bridge, frozen projection math, market evaluator,
0.0% sportsbook projection influence, and fail-closed protections remain intact.
"""
from __future__ import annotations

import nfl_hub_v34 as base

MODEL_VERSION = "NFL V3.5 • PASSING YARDS V21 EXACT-ID TEAM LOGOS • V20 FROZEN • V3.4 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        # Keep the certified V20 route contract explicitly importable, then
        # render V21, which is a presentation-only wrapper over that exact V20.
        from nfl_passing_yards_hub_v20 import render_nfl_passing_yards_hub
        from nfl_passing_yards_hub_v21 import render_nfl_passing_yards_hub as render_v21
        _ = render_nfl_passing_yards_hub
        return render_v21()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
