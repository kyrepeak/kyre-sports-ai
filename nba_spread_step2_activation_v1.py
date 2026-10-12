"""NBA Spread Step 2 — additive site-activation contract.

Pure helpers used by the production router overlay. This module owns no model,
projection, probability, sportsbook, injury, public/sharp, or schedule logic.
"""
from __future__ import annotations

from collections.abc import Iterable

MODEL_VERSION = "NBA_SPREAD_STEP2_SITE_ACTIVATION_V1"
NBA_SPORT_LABEL = "NBA"
NBA_MARKETS = ("Spread",)
NBA_DEFAULT_MARKET = "Spread"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_EXISTING_NBA_WORKSTREAMS = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def extend_sport_options(options: Iterable[object]) -> list[object]:
    """Append NBA exactly once without reordering the existing sport inventory."""
    choices = list(options)
    if NBA_SPORT_LABEL not in choices:
        choices.append(NBA_SPORT_LABEL)
    return choices


def is_nba_spread_route(sport: object, market: object) -> bool:
    return str(sport or "").strip() == NBA_SPORT_LABEL and str(market or "").strip() == NBA_DEFAULT_MARKET


__all__ = [
    "MODEL_VERSION",
    "NBA_SPORT_LABEL",
    "NBA_MARKETS",
    "NBA_DEFAULT_MARKET",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_EXISTING_NBA_WORKSTREAMS",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "extend_sport_options",
    "is_nba_spread_route",
]
