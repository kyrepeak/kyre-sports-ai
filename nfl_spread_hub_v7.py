"""NFL Spread V7 — professional decision-intelligence presentation over frozen V6."""
from __future__ import annotations

from typing import Any

import streamlit as st

import nfl_spread_hub_v4 as frozen_v4
import nfl_spread_hub_v6 as prior
import streamlit_memory_lazy_router_v136 as certified_guard
from nfl_spread_professional_intelligence_v1 import CSS, render_matchup_card

MODEL_VERSION = "NFL SPREAD V7 • PROFESSIONAL DECISION INTELLIGENCE • V6 FROZEN"
FROZEN_PRIOR = "nfl_spread_hub_v6"
FROZEN_PRESENTATION_BASE = "nfl_spread_hub_v4"
PRESENTATION_ONLY = True
PROFESSIONAL_INTELLIGENCE = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def resolve_default_slate(selected):
    return prior.resolve_default_slate(selected)


def _professional_matchup_card(
    game: dict[str, Any], market: dict[str, Any], analytics: dict[str, Any]
) -> str:
    return render_matchup_card(
        game,
        market,
        analytics,
        book=frozen_v4._first_book(market),
    )


def render_nfl_hub(market: str = "Spread") -> None:
    if str(market or "") != "Spread":
        raise RuntimeError("NFL Spread V7 only owns the Spread route.")

    certified_guard._install_html_guard(frozen_v4)
    original_matchup_card = frozen_v4._matchup_card
    frozen_v4._matchup_card = _professional_matchup_card
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        return prior.render_nfl_hub(market)
    finally:
        frozen_v4._matchup_card = original_matchup_card


__all__ = [
    "FROZEN_PRESENTATION_BASE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "PROFESSIONAL_INTELLIGENCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "render_nfl_hub",
    "resolve_default_slate",
]
