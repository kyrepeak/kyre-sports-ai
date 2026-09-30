"""Streamlit router for WNBA PRA Speed V3 Step 2 pooled HTTP."""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step1 as frozen_step1
import wnba_pra_speed_v3_step1_profiler as profiler
import wnba_pra_speed_v3_step2_transport as transport


MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 2 POOLED HTTP"
FROZEN_SPEED_V3_STEP1_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step1"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_step1.record_bootstrap_import_ms(value)


def render_app() -> Any:
    original_profiled = profiler.render_profiled_step1_route

    def layered_profiled(frozen_renderer):
        return transport.render_step2_route(
            lambda: original_profiled(frozen_renderer)
        )

    profiler.render_profiled_step1_route = layered_profiled
    try:
        return frozen_step1.render_app()
    finally:
        profiler.render_profiled_step1_route = original_profiled


__all__ = [
    "FROZEN_SPEED_V3_STEP1_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
