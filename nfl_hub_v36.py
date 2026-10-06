"""NFL V3.6 routing wrapper — Game Totals final connected page.

Preserves NFL V3.5 behavior for every existing market. Advances only Game Total
to the certified V10 page while leaving Passing Yards and every other market on
the frozen V3.5 chain.
"""
from __future__ import annotations

import nfl_hub_v35 as base

MODEL_VERSION = "NFL V3.6 • GAME TOTALS V10 FINAL CONNECTED PAGE • V3.5 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Game Total":
        from nfl_game_totals_hub_v10 import render_nfl_game_totals_hub
        return render_nfl_game_totals_hub()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
