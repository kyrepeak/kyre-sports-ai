"""Streamlit router for WNBA PRA Speed V3 Step 3 detail bundle."""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step2 as frozen_step2
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_speed_v3_step2_transport as step2_transport
import wnba_pra_speed_v3_step3_bundle as bundle


MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 3 DETAIL BUNDLE"
FROZEN_SPEED_V3_STEP2_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step2"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_step2.record_bootstrap_import_ms(value)


def render_app() -> Any:
    original_cold_loader = performance._FROZEN_PLAYER_LOADER
    original_step2_route = step2_transport.render_step2_route

    performance._FROZEN_PLAYER_LOADER = bundle.load_bundle_pair

    def layered_step2_route(frozen_renderer):
        return bundle.render_step3_route(
            lambda: original_step2_route(frozen_renderer)
        )

    step2_transport.render_step2_route = layered_step2_route
    try:
        return frozen_step2.render_app()
    finally:
        performance._FROZEN_PLAYER_LOADER = original_cold_loader
        step2_transport.render_step2_route = original_step2_route


__all__ = [
    "FROZEN_SPEED_V3_STEP2_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
