"""Purge-safe activation for CFB Game Total Page 1 visual cleanup Step 2.

The active V160 exact Game Total route purges CFB modules before fresh-importing
V38. This additive wrapper composes around that exact surface, waits until the
fresh V38 graph has been imported, then replaces only the fresh Step-3 matchup
presentation builder for that render. Frozen/current route owners are not edited.
"""
from __future__ import annotations

import importlib
from threading import RLock
from typing import Any

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v160 as render_owner
import streamlit_memory_lazy_router_v181 as route_owner
from cfb_game_total_page1_visual_cleanup_step2_top_shell_v1 import build_top_shell_html

MODEL_VERSION = "CFB GAME TOTAL PAGE1 VISUAL CLEANUP • STEP 2 PURGE-SAFE ACTIVATION V1"
TARGET_PAGE = "cfb_game_total_clean_page_v38"
PRESENTATION_MODULE = "cfb_game_total_page1_step3_presentation_v1"
PROOF_MARKER = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_STEP2_TOP_SHELL_ACTIVE"
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0
FROZEN_SOURCE_MUTATIONS = 0

_INSTALL_ATTR = "_cfb_game_total_visual_cleanup_step2_installed"
_LOCK = RLock()


def install_step2_top_shell() -> bool:
    """Install one idempotent wrapper around the exact V160 Game Total surface."""
    with _LOCK:
        current = render_owner._render_exact_game_total_surface
        if getattr(current, _INSTALL_ATTR, False):
            return True

        original_surface = current

        def render_exact_with_step2(*args: Any, **kwargs: Any):
            if not route_owner._game_total_route_active():
                return original_surface(*args, **kwargs)

            original_import = root._import
            patched_presentations: list[tuple[Any, Any]] = []

            def import_with_step2_top_shell(name: str):
                page = original_import(name)
                if str(name) == TARGET_PAGE:
                    presentation = importlib.import_module(PRESENTATION_MODULE)
                    original_builder = presentation.build_matchup_hero_html
                    presentation.build_matchup_hero_html = build_top_shell_html
                    patched_presentations.append((presentation, original_builder))
                return page

            root._import = import_with_step2_top_shell
            try:
                return original_surface(*args, **kwargs)
            finally:
                for presentation, original_builder in reversed(patched_presentations):
                    if getattr(presentation, "build_matchup_hero_html", None) is build_top_shell_html:
                        presentation.build_matchup_hero_html = original_builder
                root._import = original_import

        setattr(render_exact_with_step2, _INSTALL_ATTR, True)
        setattr(render_exact_with_step2, "_cfb_gt_step2_original", original_surface)
        render_owner._render_exact_game_total_surface = render_exact_with_step2
        return True


__all__ = [
    "FROZEN_SOURCE_MUTATIONS",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PRESENTATION_MODULE",
    "PROOF_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TARGET_PAGE",
    "install_step2_top_shell",
]
