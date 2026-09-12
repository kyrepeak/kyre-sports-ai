"""NFL V3.0 routing wrapper — Passing Yards live-route/slate hotfix.

Preserves NFL V2.9 for every other NFL market and advances only Passing Yards
to V12. The certified Steps 1–10 model and market logic remain unchanged.
"""
from __future__ import annotations

import nfl_hub_v29 as base

MODEL_VERSION = "NFL V3.0 • PASSING YARDS LIVE ROUTE + AUTO VERIFIED SLATE • V2.9 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        from nfl_passing_yards_hub_v12 import render_nfl_passing_yards_hub
        return render_nfl_passing_yards_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
