"""NFL V3.1 routing wrapper — Passing Yards cleanup step 1.

Preserves NFL V3.0 for every other NFL market and advances only Passing Yards
to V13. The certified Steps 1–10 logic and V12 verified-slate hotfix remain
unchanged; V13 is presentation-only.
"""
from __future__ import annotations

import nfl_hub_v30 as base

MODEL_VERSION = "NFL V3.1 • PASSING YARDS CLEANUP STEP 1 • V3.0 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v13 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
