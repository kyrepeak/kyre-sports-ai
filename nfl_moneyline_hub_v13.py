"""NFL Moneyline V13 — universal black + glacier-blue presentation.

Presentation-only wrapper over frozen V12. V12/V11/V10/V9/V8 remain the
owners of performance, transport, visible matchup data, and analytical logic.
V13 swaps only V9's CSS during the render call, then restores it.
"""
from __future__ import annotations

import nfl_moneyline_hub_v9 as presentation
import nfl_moneyline_hub_v12 as prior
from kyre_moneyline_theme_v1 import build_moneyline_theme_css

MODEL_VERSION = "NFL MONEYLINE V13 • UNIVERSAL BLACK + GLACIER BLUE"
FROZEN_PRIOR = "nfl_moneyline_hub_v12"
FROZEN_PRESENTATION = "nfl_moneyline_hub_v9"
PRESENTATION_ONLY = True
SPORTSBOOK_MODEL_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000

def render_nfl_hub(market: str = "Moneyline"):
    if str(market or "Moneyline") != "Moneyline":
        raise RuntimeError("Moneyline V13 direct handler is Moneyline only.")
    original_css = presentation._CSS
    presentation._CSS = build_moneyline_theme_css(original_css)
    try:
        return prior.render_nfl_hub(market)
    finally:
        presentation._CSS = original_css

__all__ = [
    "FROZEN_PRESENTATION",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "MONTE_CARLO_SIMULATIONS",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "render_nfl_hub",
]
