"""CFB Game Total Page 1 visual cleanup Step 2 runtime overlay.

Additive above the current active WNBA final-integration parent. The overlay is
strictly scoped to the exact CFB Game Total route. Because Router V160 purges
CFB modules before importing the active page, this wrapper intercepts the fresh
V38 import boundary and patches only the freshly imported Step-3 presentation
builder for the duration of that render. All other routes delegate unchanged.
"""
from __future__ import annotations

import importlib
from threading import RLock
from typing import Any

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v181 as route_owner
import streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration as prior
from cfb_game_total_page1_visual_cleanup_step2_top_shell_v1 import build_top_shell_html

MODEL_VERSION = "CFB GAME TOTAL PAGE1 VISUAL CLEANUP • STEP 2 TOP SHELL"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration"
TARGET_PAGE = "cfb_game_total_clean_page_v38"
PRESENTATION_MODULE = "cfb_game_total_page1_step3_presentation_v1"
PROOF_MARKER = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_STEP2_TOP_SHELL_ACTIVE"
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0

_LOCK = RLock()


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> Any:
    """Apply the top-shell builder only after the fresh V38 graph is imported."""
    if not route_owner._game_total_route_active():
        return prior.render_app()

    with _LOCK:
        original_import = root._import
        patched_presentations: list[tuple[Any, Any]] = []

        def import_with_step2_overlay(name: str):
            page = original_import(name)
            if str(name) == TARGET_PAGE:
                presentation = importlib.import_module(PRESENTATION_MODULE)
                original_builder = presentation.build_matchup_hero_html
                presentation.build_matchup_hero_html = build_top_shell_html
                patched_presentations.append((presentation, original_builder))
            return page

        root._import = import_with_step2_overlay
        try:
            return prior.render_app()
        finally:
            for presentation, original_builder in reversed(patched_presentations):
                if getattr(presentation, "build_matchup_hero_html", None) is build_top_shell_html:
                    presentation.build_matchup_hero_html = original_builder
            root._import = original_import


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PRESENTATION_MODULE",
    "PROOF_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TARGET_PAGE",
    "record_bootstrap_import_ms",
    "render_app",
]
