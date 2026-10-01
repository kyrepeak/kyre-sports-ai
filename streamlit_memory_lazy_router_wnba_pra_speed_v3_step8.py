"""Active router wrapper for WNBA PRA Speed V3 Step 8 visible-first rendering."""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step7 as frozen_parent
import wnba_pra_game_center_v2_step3 as game_center
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_speed_v3_step8_visible_first as step8

MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 8 VISIBLE FIRST"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step7"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def render_app() -> Any:
    """Keep PRA visible before the rerun, then preserve the frozen Step-7 path."""
    state = step8.navigation.current_state()
    shell_slot = step8.render_visible_shell_early(state)
    original_loader = performance.load_player_intelligence_same_session
    original_player_card = game_center._render_player_card

    if state.page == step8.navigation.PAGE_GAME:
        step8.render_client_preview_css()

        def client_preview_player_card(player, game_id):
            return step8.render_game_player_with_client_preview(
                original_player_card,
                player,
                game_id,
            )

        game_center._render_player_card = client_preview_player_card

    def visible_first_loader(game_id: str, player_id: int):
        return step8.load_player_intelligence_visible_first(
            original_loader,
            game_id,
            player_id,
            shell_slot=shell_slot,
        )

    performance.load_player_intelligence_same_session = visible_first_loader
    try:
        return step8.render_step8_route(frozen_parent.render_app)
    finally:
        performance.load_player_intelligence_same_session = original_loader
        game_center._render_player_card = original_player_card


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
