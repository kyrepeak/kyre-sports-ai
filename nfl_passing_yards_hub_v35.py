"""NFL Passing Yards V35 — production transport + caption cleanup.

Additive production wrapper over certified V34 combined player cards. V35 does
not modify the combined-card composition or any analytical owner. It temporarily
routes the frozen V20 Step 10 Kyre Sports API bridge through Market API V2 and
suppresses only the obsolete V20-V24 developer certification captions that leak
onto the customer-facing page.

Frozen:
- V34 player-first composition;
- V33/V28 analytical values and fail-closed rules;
- exact ESPN identity contracts;
- Receiving/Rushing owners;
- sportsbook projection influence = 0.0%;
- stake sizing OFF.
"""
from __future__ import annotations

from typing import Any

import nfl_passing_yards_hub_v20 as v20
import nfl_passing_yards_hub_v21 as v21
import nfl_passing_yards_hub_v22 as v22
import nfl_passing_yards_hub_v23 as v23
import nfl_passing_yards_hub_v24 as v24
import nfl_passing_yards_hub_v34 as prior
import nfl_passing_yards_market_api_v2 as market_api_v2

MODEL_VERSION = "NFL PASSING YARDS V35 • PRODUCTION TRANSPORT + CAPTION CLEANUP"
FROZEN_PRIOR = "nfl_passing_yards_hub_v34"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
ACTIVE_MARKET_TRANSPORT = "nfl_passing_yards_market_api_v2"
PRODUCTION_CLEANUP_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_LEGACY_CAPTION_PREFIXES = tuple(f"NFL PASSING YARDS V{version} •" for version in range(20, 25))
_CAPTION_OWNERS = (v20, v21, v22, v23, v24)


class _CaptionCleanupStreamlitProxy:
    """Suppress only obsolete V20-V24 certification captions; delegate all else."""

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any):
        text = str(body if body is not None else "").strip()
        if text.startswith(_LEGACY_CAPTION_PREFIXES):
            return None
        return self._wrapped.caption(body, *args, **kwargs)


def _caption_is_suppressed(text: Any) -> bool:
    return str(text if text is not None else "").strip().startswith(_LEGACY_CAPTION_PREFIXES)


def render_nfl_passing_yards_hub() -> None:
    """Render frozen V34 with V2 transport and production-only caption cleanup."""
    original_market_api = v20.market_api
    original_streamlit_refs = [(owner, owner.st) for owner in _CAPTION_OWNERS]

    v20.market_api = market_api_v2
    for owner, streamlit_ref in original_streamlit_refs:
        owner.st = _CaptionCleanupStreamlitProxy(streamlit_ref)
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        v20.market_api = original_market_api
        for owner, streamlit_ref in original_streamlit_refs:
            owner.st = streamlit_ref


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V35 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "ACTIVE_MARKET_TRANSPORT",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PRODUCTION_CLEANUP_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_CaptionCleanupStreamlitProxy",
    "_caption_is_suppressed",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
