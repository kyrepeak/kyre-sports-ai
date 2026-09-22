"""NFL V1.4 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline only through
V4.0 Step 4A team-strength baseline. Step 3 remains the preseason final-output
safety gate; sportsbook pricing, calibrated P(win), Monte Carlo and grading remain OFF.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.4 • MONEYLINE STEP 4A TEAM STRENGTH • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v4 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
