"""NFL V1.5 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline only through
V5 Step-5 sportsbook market transport on top of the verified V4.3.1 calibrated
base probability stack.

Step 5 is display/market normalization only: sportsbook prices never feed back
into Step-4C P(win). Monte Carlo, edge/EV and final grading remain locked. During
preseason, Step 3 remains the final-output game-plan/QB-rotation safety gate.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.5 • MONEYLINE STEP 5 SPORTSBOOK MARKET • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v5 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
