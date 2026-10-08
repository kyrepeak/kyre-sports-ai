"""CFB Game Total Page 1 V2 Step 4 — public runtime owner repair.

The frozen Step-4 V38 page is selected correctly, but the frozen V160 exact
surface purges CFB page modules immediately before importing V38. During the
fresh V38 -> V36 -> ... -> V21 -> V20 render chain, V21/V20 become the final
visible analysis owner and can replace the earlier Step-4 renderer.

This additive repair changes no frozen source file. It wraps only V160's exact
CFB Game Total surface. After V160's purge and fresh V38 import, the wrapper
points the freshly imported V21 presentation seam at V38's already-certified
Step-4 Prediction + Market Comparison renderer, then lets the frozen render
chain continue unchanged.
"""
from __future__ import annotations

import importlib
from threading import RLock
from typing import Any

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v160 as render_owner
import streamlit_memory_lazy_router_v181 as route_owner

MODEL_VERSION = "CFB GAME TOTAL PAGE1 V2 STEP4 • PUBLIC RUNTIME OWNER REPAIR V1"
TARGET_PAGE = "cfb_game_total_clean_page_v38"
LATE_OWNER = "cfb_game_total_clean_page_v21"
PROOF_MARKER = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PUBLIC_REPAIR_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
FROZEN_SOURCE_MUTATIONS = 0

_INSTALL_ATTR = "_cfb_step4_public_repair_installed"
_LOCK = RLock()


def install_public_repair() -> bool:
    """Install one idempotent wrapper on the exact V160 Game Total surface."""
    with _LOCK:
        current = render_owner._render_exact_game_total_surface
        if getattr(current, _INSTALL_ATTR, False):
            return True

        original = current

        def repaired_render_exact_game_total_surface(*args: Any, **kwargs: Any):
            # Fail closed outside the authoritative CFB Game Total route.
            if not route_owner._game_total_route_active():
                return original(*args, **kwargs)

            original_import = root._import

            def import_with_step4_repair(name: str):
                page = original_import(name)
                if str(name) == TARGET_PAGE:
                    late_owner = importlib.import_module(LATE_OWNER)
                    target = getattr(page, "_step4_prediction_market_html_v38", None)
                    if target is None:
                        raise RuntimeError(
                            "Step-4 public repair could not resolve the V38 renderer"
                        )
                    # Runtime symbol substitution only; frozen source files are untouched.
                    late_owner._game_total_hero_html_v21 = page._step4_prediction_market_html_v38
                return page

            root._import = import_with_step4_repair
            try:
                return original(*args, **kwargs)
            finally:
                root._import = original_import

        setattr(repaired_render_exact_game_total_surface, _INSTALL_ATTR, True)
        setattr(repaired_render_exact_game_total_surface, "_cfb_step4_public_repair_original", original)
        render_owner._render_exact_game_total_surface = repaired_render_exact_game_total_surface
        return True


__all__ = [
    "FROZEN_SOURCE_MUTATIONS",
    "LATE_OWNER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PROOF_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TARGET_PAGE",
    "install_public_repair",
]
