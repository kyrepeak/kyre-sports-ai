"""NFL Spread V8 — readable projection + display-only matchup history over frozen V7."""
from __future__ import annotations

from typing import Any

import nfl_spread_hub_v4 as frozen_v4
import nfl_spread_hub_v7 as prior
from nfl_spread_matchup_history_v1 import load_matchup_history
from nfl_spread_professional_intelligence_v2 import render_matchup_card

MODEL_VERSION = "NFL SPREAD V8 • READABLE PROJECTION + DISPLAY-ONLY MATCHUP HISTORY • V7 FROZEN"
FROZEN_PRIOR = "nfl_spread_hub_v7"
PRESENTATION_ONLY = True
MATCHUP_HISTORY_DISPLAY_ONLY = True
MATCHUP_HISTORY_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def resolve_default_slate(selected):
    return prior.resolve_default_slate(selected)


def _professional_matchup_card(
    game: dict[str, Any], market: dict[str, Any], analytics: dict[str, Any]
) -> str:
    history = load_matchup_history(game, limit=5)
    return render_matchup_card(
        game,
        market,
        analytics,
        book=frozen_v4._first_book(market),
        history=history,
    )


def render_nfl_hub(market: str = "Spread") -> None:
    if str(market or "") != "Spread":
        raise RuntimeError("NFL Spread V8 only owns the Spread route.")
    original_matchup_card = prior._professional_matchup_card
    prior._professional_matchup_card = _professional_matchup_card
    try:
        return prior.render_nfl_hub(market)
    finally:
        prior._professional_matchup_card = original_matchup_card


__all__ = [
    "FROZEN_PRIOR", "MATCHUP_HISTORY_DISPLAY_ONLY", "MATCHUP_HISTORY_MODEL_INFLUENCE",
    "MODEL_VERSION", "PRESENTATION_ONLY", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED", "WAGER_ACTIONS_ENABLED", "render_nfl_hub", "resolve_default_slate",
]
