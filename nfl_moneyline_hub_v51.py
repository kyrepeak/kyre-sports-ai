"""Kyre Sports AI — NFL Moneyline V5.1 Step-5 quote freshness repair.

Preserves V5 exactly except for the isolated sportsbook transport/freshness seam.
V5.1 uses nfl_moneyline_market_v11 so stable pregame lines are not falsely marked
stale after only three minutes, and usability-aware fallback can replace a truly
stale/incomplete primary row.

Steps 1-4C remain unchanged. Step-4C P(win) remains model-only. Sportsbook prices
do not feed back into the model. Monte Carlo, edge/EV, ranking and final grading
remain locked. During preseason, Step 3 remains the final-output safety gate.
"""
from __future__ import annotations

import streamlit as st

import nfl_moneyline_hub_v5 as v5
import nfl_moneyline_market_v11 as market

MODEL_VERSION = "NFL MONEYLINE V5.1 • STEP 5 PREGAME QUOTE-AGE + FALLBACK REPAIR"

# Route V5's existing UI/math through the repaired market transport only.
v5.market = market


def render_nfl_moneyline_hub():
    real_caption = st.caption

    def _caption(body, *args, **kwargs):
        if isinstance(body, str) and body.startswith(
            "Pregame full-game ML only • SportsGameOdds primary"
        ):
            body = (
                "Pregame full-game ML only • SportsGameOdds primary → Odds-API.io fallback • "
                "FanDuel / DraftKings / BetMGM / Caesars when available • same-book no-vig • "
                "QUOTE LAST-CHANGE AGE: FRESH ≤3m • AGING 3–15m • STALE >15m excluded. "
                "The provider response itself is refreshed separately; an unchanged line is not treated as a dead feed."
            )
        return real_caption(body, *args, **kwargs)

    st.caption = _caption
    try:
        return v5.render_nfl_moneyline_hub()
    finally:
        st.caption = real_caption


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
