"""NFL Rushing Yards V11 — display-only HTML whitespace repair.

V11 is additive over certified performance owner V10. It changes no football
data, projection math, market data, exact-ID behavior, freshness rules, page
content, or betting semantics. It only normalizes leading indentation in the
three historical multi-line HTML card builders before Streamlit Markdown sees
them, preventing subsequent <article> fragments from being interpreted as
Markdown code blocks.

Frozen V1/V2/V3 and V10 remain untouched. Sportsbook projection influence stays
exactly 0.0%.
"""
from __future__ import annotations

from textwrap import dedent
from typing import Any, Callable

import nfl_rushing_yards_hub_v1 as context_page
import nfl_rushing_yards_hub_v2 as projection_page
import nfl_rushing_yards_hub_v3 as market_page
import nfl_rushing_yards_hub_v10 as prior

MODEL_VERSION = "NFL RUSHING YARDS V11 • HTML RENDER REPAIR V1"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v10"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _normalize_html(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return dedent(value).strip()


def _normalized_builder(original: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        return _normalize_html(original(*args, **kwargs))

    return wrapped


def render_nfl_rushing_yards_hub() -> None:
    """Render frozen V10 with whitespace-only HTML normalization."""
    original_game_card = context_page._game_card
    original_projection_card = projection_page._projection_card
    original_market_card = market_page._market_card

    context_page._game_card = _normalized_builder(original_game_card)
    projection_page._projection_card = _normalized_builder(original_projection_card)
    market_page._market_card = _normalized_builder(original_market_card)

    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        context_page._game_card = original_game_card
        projection_page._projection_card = original_projection_card
        market_page._market_card = original_market_card


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V11 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_normalize_html",
    "_normalized_builder",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
