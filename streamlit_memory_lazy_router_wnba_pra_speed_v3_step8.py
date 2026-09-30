"""Active router wrapper for WNBA PRA Speed V3 Step 8 visible-first rendering."""
from __future__ import annotations

from functools import partial
from typing import Any, Callable

import streamlit as st

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step7 as frozen_parent
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_speed_v3_step8_visible_first as step8

MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 8 VISIBLE FIRST"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step7"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def _preview_button(
    original: Callable[..., Any],
    label: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Keep frozen native navigation while pre-rendering an instant client preview."""
    key = str(kwargs.get("key") or "")
    prefix = "wnba_nav_v2_step3_player_"
    if not key.startswith(prefix):
        return original(label, *args, **kwargs)

    suffix = key.removeprefix(prefix)
    if "_" not in suffix:
        return original(label, *args, **kwargs)
    game_id, player_id = suffix.rsplit("_", 1)
    player = performance._game_player(game_id, player_id)
    if player is None:
        return original(label, *args, **kwargs)

    preview_key = f"ks_step8_preview_{player_id}"
    with st.container(key=preview_key):
        clicked = original(label, *args, **kwargs)
        step8.render_player_click_preview(game_id, player)
    return clicked


def render_app() -> Any:
    """Emit visible Player PRA before entering the frozen Step-7 render path."""
    state = step8.navigation.current_state()
    shell_slot = step8.render_visible_shell_early(state)
    original_loader = performance.load_player_intelligence_same_session
    original_button = st.button

    def visible_first_loader(game_id: str, player_id: int):
        return step8.load_player_intelligence_visible_first(
            original_loader,
            game_id,
            player_id,
            shell_slot=shell_slot,
        )

    performance.load_player_intelligence_same_session = visible_first_loader
    st.button = partial(_preview_button, original_button)
    try:
        return step8.render_step8_route(frozen_parent.render_app)
    finally:
        st.button = original_button
        performance.load_player_intelligence_same_session = original_loader


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_preview_button",
    "record_bootstrap_import_ms",
    "render_app",
]
