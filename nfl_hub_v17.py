"""NFL V1.7 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline through V7,
which keeps Steps 1-6 intact and adds Step-7 no-vig edge, fair-price and expected-
value diagnostics.

Sportsbook prices remain comparison targets only and never alter Steps 4C/6.
Final grading and recommendations remain gated. During preseason, Step 3 remains
the final-output game-plan/QB-rotation safety gate.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.7 • MONEYLINE STEP 7 EDGE + EV DIAGNOSTICS • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v7 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
