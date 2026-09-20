"""NFL Receiving Yards V17 — Step 7 render-time player identity gate.

Additive over frozen V16. The frozen cards/metrics remain untouched; cached
context is independently re-verified against exact event/current roster IDs
before any receiver identity reaches the renderer.
"""
from __future__ import annotations

import nfl_receiving_yards_hub_v2 as base_page
import nfl_receiving_yards_hub_v16 as prior
from nfl_prop_app_eligibility_v1 import guard_context_payload

MODEL_VERSION = "NFL RECEIVING YARDS V17 • STEP 7 APP IDENTITY FAIL-CLOSED"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v16"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_ALLOWED_POSITIONS = frozenset({"WR", "TE", "RB", "FB"})

_ORIGINAL_LOAD = base_page._load_receiving_context


def _load_receiving_context_step7(event_id: str) -> dict:
    payload = _ORIGINAL_LOAD(str(event_id))
    return guard_context_payload(
        payload,
        str(event_id),
        allowed_positions=_ALLOWED_POSITIONS,
    )


def render_nfl_receiving_yards_hub() -> None:
    original = base_page._load_receiving_context
    base_page._load_receiving_context = _load_receiving_context_step7
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        base_page._load_receiving_context = original


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V17 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_load_receiving_context_step7",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
