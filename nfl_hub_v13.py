"""NFL V1.3 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline only to the
V3 Step-3 preseason game-plan intelligence layer built on verified Step 2.1 depth
and injury foundations.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.3 • MONEYLINE STEP 3 GAME-PLAN INTELLIGENCE • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v3 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
