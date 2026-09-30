"""Active router wrapper for WNBA PRA Speed V3 Step 6 history cache.

Step 6 preserves the frozen Step-5 router/trampoline and replaces only the
history-only network reader during rendering. The Step-5 consumer-reuse and
all Steps 1-5 model/navigation behavior remain unchanged.
"""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step5 as frozen_parent
import wnba_pra_speed_v3_step5_consumer_reuse as step5
import wnba_pra_speed_v3_step6_history_cache as step6

MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 6 HISTORY CACHE"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step5"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def render_app() -> Any:
    original_history_reader = step5._read_fast_history
    step5._read_fast_history = step6.read_cached_history
    try:
        return step6.render_step6_route(frozen_parent.render_app)
    finally:
        step5._read_fast_history = original_history_reader


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
