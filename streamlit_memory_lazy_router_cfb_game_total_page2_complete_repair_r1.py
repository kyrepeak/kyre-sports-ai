"""MONSTER CFB Game Total Page 2 complete repair activation R1.

Additive overlay above frozen/current Universal Navigation V2. It changes one
selected-CFB-Game-Total seam only, restores it after every render, and delegates
all other sports/markets byte-for-behavior to the current universal owner.
"""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_universal_nav_v2 as prior
import streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1 as cfb_fast

MODEL_VERSION = "MONSTER CFB GAME TOTAL PAGE2 COMPLETE REPAIR ACTIVATION R1"
FROZEN_PARENT = "streamlit_memory_lazy_router_universal_nav_v2"
PAGE2_RUNTIME = "cfb_game_total_page2_complete_repair_r1"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> Any:
    original_runtime = cfb_fast.SAME_PAGE_RUNTIME
    cfb_fast.SAME_PAGE_RUNTIME = PAGE2_RUNTIME
    try:
        return prior.render_app()
    finally:
        cfb_fast.SAME_PAGE_RUNTIME = original_runtime


__all__ = [
    "FROZEN_PARENT", "MAY_MODIFY_MODEL", "MAY_MODIFY_OTHER_SPORTS", "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY", "MAY_MODIFY_PROJECTION", "MAY_MODIFY_RANKING", "MAY_MODIFY_SELECTION",
    "MODEL_VERSION", "PAGE2_RUNTIME", "SPORTSBOOK_PROJECTION_INFLUENCE", "record_bootstrap_import_ms", "render_app",
]
