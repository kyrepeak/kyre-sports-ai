"""NFL V1.3.3 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline only through
V3.3, which preserves Step-3 fail-closed logic while adding trusted secondary
news discovery when ESPN alone has no explicit preseason game-plan evidence.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.3.3 • MONEYLINE STEP 3B TRUSTED NEWS DISCOVERY • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v33 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
