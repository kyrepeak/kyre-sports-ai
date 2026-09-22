"""NFL V1.2 routing wrapper.

Preserves the verified NFL V1 Slate page unchanged and activates only the
Moneyline market through NFL Moneyline V2 Step 2. All other NFL markets remain
reserved/foundation views.
"""
from __future__ import annotations

import nfl_hub_v1 as base

MODEL_VERSION = "NFL V1.2 • MONEYLINE STEP 2 ACTIVE • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Moneyline":
        from nfl_moneyline_hub_v2 import render_nfl_moneyline_hub

        return render_nfl_moneyline_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
