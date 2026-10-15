"""NBA Spread provider-resilience Step 1 page bridge.

Keeps the frozen NBA Spread page implementation intact and rebinds only its
schedule loader to the additive NBA Official CDN transport repair.
"""
from __future__ import annotations

import nba_spread_page_v1 as frozen_page
from nba_spread_schedule_provider_resilience_step1_r1 import load_verified_nba_schedule

MODEL_VERSION = "NBA_SPREAD_PAGE_PROVIDER_RESILIENCE_STEP1_R1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SOURCE_OWNERSHIP = False


def _bind_repaired_schedule_loader() -> None:
    if frozen_page.load_verified_nba_schedule is load_verified_nba_schedule:
        return
    frozen_page.load_verified_nba_schedule = load_verified_nba_schedule
    clear = getattr(frozen_page._load_verified_schedule, "clear", None)
    if callable(clear):
        clear()


def render_nba_spread_page():
    _bind_repaired_schedule_loader()
    return frozen_page.render_nba_spread_page()


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_SOURCE_OWNERSHIP",
    "render_nba_spread_page",
]
