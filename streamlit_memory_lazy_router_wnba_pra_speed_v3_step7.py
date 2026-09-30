"""Active router wrapper for WNBA PRA Speed V3 Step 7 precompute."""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step6 as frozen_parent
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_speed_v3_step4_cache as step4_cache
import wnba_pra_speed_v3_step7_precompute as step7

MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 7 PRECOMPUTE"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step6"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def render_app() -> Any:
    """Start precompute as soon as the frozen Game Center payload is available."""
    original_game_loader = performance._FROZEN_GAME_LOADER
    original_bundle_loader = step4_cache.load_cached_bundle_pair

    def game_loader_with_precompute(*args: Any, **kwargs: Any):
        payload = original_game_loader(*args, **kwargs)
        step7.schedule_precompute(payload)
        return payload

    def bundle_loader_with_memory(game_id: str, player_id: int):
        return step7.load_precomputed_bundle_pair(
            game_id,
            player_id,
            original_bundle_loader,
        )

    performance._FROZEN_GAME_LOADER = game_loader_with_precompute
    step4_cache.load_cached_bundle_pair = bundle_loader_with_memory
    try:
        return step7.render_step7_route(frozen_parent.render_app)
    finally:
        step4_cache.load_cached_bundle_pair = original_bundle_loader
        performance._FROZEN_GAME_LOADER = original_game_loader


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
