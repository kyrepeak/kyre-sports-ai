"""CFB Game Total Page 1 visual cleanup Step 4 runtime activation.

Installs presentation-only hooks after the exact CFB Game Total post-purge V38
module is imported. The dense legacy Overview evidence wall is replaced during
that render only; existing sidebar analysis controls remain untouched. Already
loaded schedule rows are captured and reused for Games on This Day, so Step 4
adds zero network calls.
"""
from __future__ import annotations

import importlib
from threading import RLock
from typing import Any, Mapping

from cfb_game_total_page1_visual_cleanup_step4_footer_evidence_v1 import (
    MAY_MODIFY_MARKET_OWNERSHIP,
    MAY_MODIFY_OTHER_SPORTS,
    MAY_MODIFY_PROJECTION,
    NETWORK_CALLS_ADDED,
    SPORTSBOOK_PROJECTION_INFLUENCE,
    STEP4_CSS,
    build_footer_html,
    build_games_on_day_html,
    build_relocated_analysis_html,
)

MODEL_VERSION = "CFB GAME TOTAL PAGE1 VISUAL CLEANUP • STEP 4 ACTIVATION V1"
TARGET_PAGE = "cfb_game_total_clean_page_v38"
_INSTALL_ATTR = "_cfb_game_total_visual_cleanup_step4_installed"
_LOCK = RLock()


def _capture_schedule_loader(loader, captured: dict[str, Any]):
    def wrapped(*args: Any, **kwargs: Any):
        result = loader(*args, **kwargs)
        selected_day = str(args[0] if args else kwargs.get("selected_day") or kwargs.get("game_date") or "")
        games: Any = []
        if isinstance(result, tuple) and result:
            games = result[0]
        elif isinstance(result, list):
            games = result
        captured["selected_day"] = selected_day
        captured["games"] = list(games or []) if isinstance(games, (list, tuple)) else []
        return result

    return wrapped


def _install_fresh_page_hook(page: Any, restores: list[tuple[Any, str, Any]]) -> None:
    if not hasattr(page, "render_cfb_hub"):
        raise RuntimeError("Step-4 V38 render owner unavailable")

    import streamlit as st

    base = importlib.import_module("cfb_game_total_clean_page_v9")
    schedule_owner = base.frozen_page.frozen_v2.frozen_v1.schedule
    original_render = page.render_cfb_hub

    def render_with_step4_footer(*args: Any, **kwargs: Any):
        captured: dict[str, Any] = {}
        original_combined = base._combined_flow_html
        original_loader = schedule_owner.load_with_diagnostics
        base._combined_flow_html = build_relocated_analysis_html
        schedule_owner.load_with_diagnostics = _capture_schedule_loader(original_loader, captured)
        st.markdown(STEP4_CSS, unsafe_allow_html=True)
        try:
            result = original_render(*args, **kwargs)
        finally:
            base._combined_flow_html = original_combined
            schedule_owner.load_with_diagnostics = original_loader

        games_html = build_games_on_day_html(
            captured.get("games") or [],
            str(captured.get("selected_day") or ""),
        )
        if games_html:
            st.markdown(games_html, unsafe_allow_html=True)
        st.markdown(build_footer_html(), unsafe_allow_html=True)
        return result

    page.render_cfb_hub = render_with_step4_footer
    restores.append((page, "render_cfb_hub", original_render))


def install_step4_footer_evidence() -> bool:
    """Install one exact-route post-purge wrapper; idempotent and presentation-only."""
    with _LOCK:
        root = importlib.import_module("streamlit_memory_lazy_router_v1")
        render_owner = importlib.import_module("streamlit_memory_lazy_router_v160")
        route_owner = importlib.import_module("streamlit_memory_lazy_router_v181")
        current = render_owner._render_exact_game_total_surface
        if getattr(current, _INSTALL_ATTR, False):
            return True
        original = current

        def repaired_render_exact_game_total_surface(*args: Any, **kwargs: Any):
            if not route_owner._game_total_route_active():
                return original(*args, **kwargs)
            original_import = root._import
            restores: list[tuple[Any, str, Any]] = []

            def import_with_step4(name: str):
                page = original_import(name)
                if str(name) == TARGET_PAGE:
                    _install_fresh_page_hook(page, restores)
                return page

            root._import = import_with_step4
            try:
                return original(*args, **kwargs)
            finally:
                root._import = original_import
                for owner, attr, value in reversed(restores):
                    setattr(owner, attr, value)

        setattr(repaired_render_exact_game_total_surface, _INSTALL_ATTR, True)
        setattr(repaired_render_exact_game_total_surface, "_cfb_gt_step4_original", original)
        render_owner._render_exact_game_total_surface = repaired_render_exact_game_total_surface
        return True


__all__ = [
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TARGET_PAGE",
    "install_step4_footer_evidence",
]
