"""NFL V1.3.4 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline only through
V3.4 Step-3C full-text evidence enrichment + rejection diagnostics.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.3.4 • MONEYLINE STEP 3C FULL-TEXT DIAGNOSTICS • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v34 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
