"""Active router wrapper for WNBA PRA Speed V3 Step 5.

WNBA -> PRA uses a shallow render trampoline after the current parent has
rendered the universal shell and selectors. This preserves every visible
navigation wrapper while avoiding the legacy V1->V245 page-render stack on
Player Intelligence.
"""
from __future__ import annotations

from typing import Any, Callable

import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9 as current_parent
import streamlit_memory_lazy_router_wnba_nav_v2_step7 as nav_step7_router
import wnba_pra_final_v2_step7 as final
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_speed_v3_step1_profiler as profiler
import wnba_pra_speed_v3_step2_transport as transport
import wnba_pra_speed_v3_step3_bundle as bundle
import wnba_pra_speed_v3_step4_cache as step4_cache
import wnba_pra_speed_v3_step5_consumer_reuse as step5

MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 5 CONSUMER REUSE"
CURRENT_PARENT_ROUTER = "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9"
FROZEN_SPEED_STEP4_PARENT = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step4"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PLAYER_ROUTER_STACK_TRAMPOLINE = True


class _DirectWNBAPRARoute(RuntimeError):
    """Private control-flow signal used only to unwind the legacy router stack."""


def record_bootstrap_import_ms(value: float) -> None:
    return current_parent.record_bootstrap_import_ms(value)


def _render_speed_v3_layers_direct() -> Any:
    """Compose frozen PRA layers directly after the shell stack has unwound."""
    original_cold_loader = performance._FROZEN_PLAYER_LOADER
    performance._FROZEN_PLAYER_LOADER = step4_cache.load_cached_bundle_pair
    try:
        return step5.render_step5_route(
            lambda: step4_cache.render_step4_route(
                lambda: bundle.render_step3_route(
                    lambda: transport.render_step2_route(
                        lambda: profiler.render_profiled_step1_route(
                            final.render_step7_route
                        )
                    )
                )
            )
        )
    finally:
        performance._FROZEN_PLAYER_LOADER = original_cold_loader


def _raise_after_shell_for_pra(
    market: str,
    frozen_renderer: Callable[[str], Any],
) -> Any:
    if str(market or "").strip() == "PRA":
        raise _DirectWNBAPRARoute()
    return frozen_renderer(market)


def render_app() -> Any:
    original_loader = performance.load_player_intelligence_same_session
    original_step7_dispatch = nav_step7_router._render_wnba_step7

    performance.load_player_intelligence_same_session = (
        step5.load_player_intelligence_cross_player_reuse
    )

    def trampoline_dispatch(market: str, frozen_renderer: Callable[[str], Any]) -> Any:
        return _raise_after_shell_for_pra(market, original_step7_dispatch)

    nav_step7_router._render_wnba_step7 = trampoline_dispatch
    try:
        try:
            return step5.render_step5_route(current_parent.render_app)
        except _DirectWNBAPRARoute:
            return _render_speed_v3_layers_direct()
    finally:
        nav_step7_router._render_wnba_step7 = original_step7_dispatch
        performance.load_player_intelligence_same_session = original_loader


__all__ = [
    "CURRENT_PARENT_ROUTER",
    "FROZEN_SPEED_STEP4_PARENT",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "PLAYER_ROUTER_STACK_TRAMPOLINE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
