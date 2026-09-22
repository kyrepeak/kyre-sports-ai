"""NFL V1.6 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline through V6,
which keeps Steps 1-5 intact and adds the Step-6 5,000,000-draw model-only Monte
Carlo uncertainty layer.

Sportsbook prices remain outside the simulation. Edge/EV and final grading remain
locked. During preseason, Step 3 remains the final-output game-plan/QB-rotation
safety gate.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.6 • MONEYLINE STEP 6 5M MONTE CARLO • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v6 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
