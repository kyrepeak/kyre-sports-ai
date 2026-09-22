"""NFL Moneyline V10 — Kyre Sports API transport wrapper over certified V9.

V10 changes transport only. It temporarily replaces the module object used by
frozen Moneyline V5 with ``nfl_moneyline_market_api_v1`` and then delegates the
entire page render through certified ``nfl_hub_v18``. That preserves the V9
matchup-card page, V8 grading, V7 edge/EV, V6 Monte Carlo, V5 no-vig/freshness
math, V4 calibrated model probability, and V3/V2 availability gates.
"""
from __future__ import annotations

import nfl_hub_v18 as frozen_hub
import nfl_moneyline_hub_v5 as frozen_v5
import nfl_moneyline_market_api_v1 as kyre_market

MODEL_VERSION = "NFL MONEYLINE V10 • KYRE SPORTS API TRANSPORT • V9/V8/V7/V6/V5 FROZEN"
FROZEN_PRESENTATION = "nfl_moneyline_hub_v9"
FROZEN_ENGINE = "nfl_moneyline_hub_v8"
FROZEN_MARKET_MATH = "nfl_moneyline_market_v1"
API_ADAPTER = "nfl_moneyline_market_api_v1"
TRANSPORT_ONLY = True
SPORTSBOOK_MODEL_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


def render_nfl_hub(market: str = "Moneyline"):
    """Render exact NFL Moneyline through V9 with only V5 transport swapped."""
    market = str(market or "Moneyline")
    if market != "Moneyline":
        raise RuntimeError("Moneyline V10 direct handler is Moneyline only.")

    original_market = frozen_v5.market
    frozen_v5.market = kyre_market
    try:
        return frozen_hub.render_nfl_hub("Moneyline")
    finally:
        frozen_v5.market = original_market


__all__ = [
    "API_ADAPTER",
    "FROZEN_ENGINE",
    "FROZEN_MARKET_MATH",
    "FROZEN_PRESENTATION",
    "MODEL_VERSION",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "TRANSPORT_ONLY",
    "render_nfl_hub",
]
