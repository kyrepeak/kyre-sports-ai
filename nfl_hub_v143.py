"""NFL V1.4.3 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline only through
V4.3 Step-4C historical win-probability calibration, including the V4.1 historical
fallback repair and V4.2 matchup/home-field feature layer.

Step 4C exposes a historical BASE P(win) only after chronological validation.
During preseason, Step 3 remains the final-output game-plan/QB-rotation safety
gate. Sportsbook pricing, Monte Carlo, no-vig edge/EV and final grading remain OFF.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.4.3 • MONEYLINE STEP 4C CALIBRATED BASE P(WIN) • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v43 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
