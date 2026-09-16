"""NFL Receiving Yards V16 — future multi-card render guard.

Additive display-only wrapper over frozen V15. It fixes a Markdown parsing edge
case where the frozen V2 identity-card HTML can surface as literal source text
when multiple future-slate receiver cards are concatenated. No player data,
projection, market, probability, exact-ID, or sportsbook math changes.
"""
from __future__ import annotations

from typing import Any

import nfl_receiving_yards_hub_v3 as base_page
import nfl_receiving_yards_hub_v15 as prior
from nfl_receiving_yards_future_card_render_v1 import normalize_receiver_identity_card_html

MODEL_VERSION = "NFL RECEIVING YARDS V16 • FUTURE MULTI-CARD RENDER GUARD"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v15"
FROZEN_BASE_CARD_OWNER = "nfl_receiving_yards_hub_v3"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_FROZEN_V2_CARD = base_page._ORIGINAL_PLAYER_CARD_V2


def _normalized_frozen_v2_card(
    player: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
) -> str:
    raw = _ORIGINAL_FROZEN_V2_CARD(player, team, opponent)
    return normalize_receiver_identity_card_html(raw)


def render_nfl_receiving_yards_hub() -> None:
    original = base_page._ORIGINAL_PLAYER_CARD_V2
    base_page._ORIGINAL_PLAYER_CARD_V2 = _normalized_frozen_v2_card
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        base_page._ORIGINAL_PLAYER_CARD_V2 = original


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V16 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_BASE_CARD_OWNER",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_normalized_frozen_v2_card",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
