"""NFL Moneyline V12 — additive speed/reliability transport over frozen V11.

V12 changes only which Kyre Sports API adapter V10 temporarily gives frozen V5.
V11 still owns no-flash execution, V10 remains the certified transport-swap
mechanism, V9 owns matchup cards, and V8/V7/V6/V5 own the frozen analytical and
market chain. No model, Monte Carlo, no-vig, edge/EV or grading math is changed.
"""
from __future__ import annotations

import nfl_moneyline_hub_v10 as v10
import nfl_moneyline_hub_v11 as frozen_v11
import nfl_moneyline_market_api_v2 as speed_market

MODEL_VERSION = "NFL MONEYLINE V12 • HOT MARKET CACHE • V11/V10/V9/V8 FROZEN"
FROZEN_HUB = "nfl_moneyline_hub_v11"
FROZEN_TRANSPORT_WRAPPER = "nfl_moneyline_hub_v10"
ACTIVE_MARKET_ADAPTER = "nfl_moneyline_market_api_v2"
TRANSPORT_SPEED_ONLY = True
SPORTSBOOK_MODEL_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


def render_nfl_hub(market: str = "Moneyline"):
    """Render exact frozen V11 while substituting only V10's adapter object."""
    market = str(market or "Moneyline")
    if market != "Moneyline":
        raise RuntimeError("Moneyline V12 direct handler is Moneyline only.")

    original_market = v10.kyre_market
    v10.kyre_market = speed_market
    try:
        return frozen_v11.render_nfl_hub(market)
    finally:
        v10.kyre_market = original_market


__all__ = [
    "ACTIVE_MARKET_ADAPTER",
    "FROZEN_HUB",
    "FROZEN_TRANSPORT_WRAPPER",
    "MODEL_VERSION",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "TRANSPORT_SPEED_ONLY",
    "render_nfl_hub",
]
