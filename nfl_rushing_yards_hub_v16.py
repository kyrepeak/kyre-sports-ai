"""NFL Rushing Yards V16 — Step 7 render-time player identity gate.

Additive over frozen V15. It re-validates the cached/current context against the
exact ESPN event and current roster IDs immediately before player cards render.
"""
from __future__ import annotations

import nfl_rushing_yards_hub_v1 as base_page
import nfl_rushing_yards_hub_v15 as prior
from nfl_prop_app_eligibility_v1 import guard_context_payload

MODEL_VERSION = "NFL RUSHING YARDS V16 • STEP 7 APP IDENTITY FAIL-CLOSED"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v15"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_ALLOWED_POSITIONS = frozenset({"QB", "RB", "FB", "WR", "TE"})

_ORIGINAL_LOAD = base_page._load_rushing_context


def _load_rushing_context_step7(event_id: str) -> dict:
    payload = _ORIGINAL_LOAD(str(event_id))
    return guard_context_payload(
        payload,
        str(event_id),
        allowed_positions=_ALLOWED_POSITIONS,
    )


def render_nfl_rushing_yards_hub() -> None:
    original = base_page._load_rushing_context
    base_page._load_rushing_context = _load_rushing_context_step7
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        base_page._load_rushing_context = original


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V16 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_load_rushing_context_step7",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
