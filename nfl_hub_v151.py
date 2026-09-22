"""NFL V1.5.1 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline through V5.1,
which keeps Steps 1-4C unchanged and repairs only Step-5 pregame quote-age and
fallback handling.

Sportsbook prices remain display/market normalization only. They never alter the
Step-4C calibrated base P(win). Monte Carlo, edge/EV and final grading remain
locked. During preseason, Step 3 remains the final-output game-plan/QB-rotation
safety gate.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.5.1 • MONEYLINE STEP 5.1 FRESHNESS REPAIR • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v51 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
