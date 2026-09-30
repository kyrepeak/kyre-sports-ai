"""Streamlit router for WNBA PRA Speed V3 Step 1 profiler."""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_wnba_nav_v2_step7 as frozen_step7
import wnba_pra_final_v2_step7 as final
import wnba_pra_speed_v3_step1_profiler as profiler


MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 1 PROFILER"
FROZEN_WNBA_NAVIGATION_ROUTER = "streamlit_memory_lazy_router_wnba_nav_v2_step7"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_step7.record_bootstrap_import_ms(value)


def render_app() -> Any:
    original_render = final.render_step7_route
    final.render_step7_route = lambda: profiler.render_profiled_step1_route(original_render)
    try:
        return frozen_step7.render_app()
    finally:
        final.render_step7_route = original_render


__all__ = [
    "FROZEN_WNBA_NAVIGATION_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
