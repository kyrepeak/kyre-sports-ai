"""NFL V1.8 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline through V8,
which keeps Steps 1-7 intact and adds the final decision / grading layer.

Final grading is eligibility-gated. During preseason, unresolved Step-3 QB
participation/rotation forces a GATED state regardless of model edge/EV. Market
prices remain comparison inputs only and never alter the Step-4C/6 model.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.8 • MONEYLINE FINAL DECISION + GRADING • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v8 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
