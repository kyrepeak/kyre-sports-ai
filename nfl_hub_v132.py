"""NFL V1.3.2 routing wrapper.

Preserves NFL Slate V1 and all reserved markets. Routes Moneyline only through
V3.2, which preserves Step 3 classification/locks while repairing ESPN team-news
intake so HTTP-200 empty payloads cannot masquerade as usable news feeds.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.3.2 • MONEYLINE STEP 3 NEWS SCANNER REPAIR • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v32 import render_nfl_moneyline_hub
        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
