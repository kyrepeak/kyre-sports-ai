"""API 2 NFL Spread + MONSTER CFB Page-2 additive activation overlay.

The current production ancestry already enters through this module beneath
Universal Navigation. NFL Spread keeps its frozen V5 bridge. Exact selected CFB
Game Total temporarily receives the Page-2 Complete Repair R1 runtime by changing
one existing SAME_PAGE_RUNTIME pointer and restoring it after every render.
"""
from __future__ import annotations

import sys
from typing import Any, Callable

import streamlit as st

import nfl_spread_hub_v5 as spread_v5
import streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "API2 NFL SPREAD + MONSTER CFB PAGE2 COMPLETE REPAIR ACTIVATION V2"
FROZEN_PARENT = "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1"
ACTIVE_SPREAD_PAGE = "nfl_spread_hub_v5"
CFB_PAGE2_RUNTIME = "cfb_game_total_page2_complete_repair_r1"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_OTHER_MARKETS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _exact_nfl_spread(market: str) -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == "NFL"
        and str(market or "") == "Spread"
    )


def _make_render_nfl_bridge(delegate: Callable[[str], Any]) -> Callable[[str], Any]:
    if getattr(delegate, "_api2_nfl_spread_next_slate_bridge", False):
        return delegate

    def _bridge(market: str) -> Any:
        if _exact_nfl_spread(str(market or "")):
            return spread_v5.render_nfl_hub("Spread")
        return delegate(market)

    _bridge._api2_nfl_spread_next_slate_bridge = True  # type: ignore[attr-defined]
    _bridge._api2_nfl_spread_next_slate_delegate = delegate  # type: ignore[attr-defined]
    return _bridge


def _patch_loaded_router_seams() -> Callable[[str], Any]:
    original_root_render_nfl = root._render_nfl
    root._render_nfl = _make_render_nfl_bridge(original_root_render_nfl)

    for name, module in list(sys.modules.items()):
        if not name.startswith("streamlit_memory_lazy_router") or module is None:
            continue
        renderer = getattr(module, "_ORIGINAL_RENDER_NFL", None)
        if callable(renderer):
            setattr(module, "_ORIGINAL_RENDER_NFL", _make_render_nfl_bridge(renderer))
    return original_root_render_nfl


def _restore_loaded_router_seams(original_root_render_nfl: Callable[[str], Any]) -> None:
    for name, module in list(sys.modules.items()):
        if not name.startswith("streamlit_memory_lazy_router") or module is None:
            continue
        renderer = getattr(module, "_ORIGINAL_RENDER_NFL", None)
        if getattr(renderer, "_api2_nfl_spread_next_slate_bridge", False):
            setattr(
                module,
                "_ORIGINAL_RENDER_NFL",
                getattr(renderer, "_api2_nfl_spread_next_slate_delegate"),
            )
    root._render_nfl = original_root_render_nfl


def render_app() -> Any:
    original_root_render_nfl = _patch_loaded_router_seams()
    original_page2_runtime = prior.SAME_PAGE_RUNTIME
    prior.SAME_PAGE_RUNTIME = CFB_PAGE2_RUNTIME
    try:
        return prior.render_app()
    finally:
        prior.SAME_PAGE_RUNTIME = original_page2_runtime
        _restore_loaded_router_seams(original_root_render_nfl)


__all__ = [
    "ACTIVE_SPREAD_PAGE",
    "CFB_PAGE2_RUNTIME",
    "FROZEN_PARENT",
    "MAY_MODIFY_OTHER_MARKETS",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE1",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_exact_nfl_spread",
    "_make_render_nfl_bridge",
    "record_bootstrap_import_ms",
    "render_app",
]
