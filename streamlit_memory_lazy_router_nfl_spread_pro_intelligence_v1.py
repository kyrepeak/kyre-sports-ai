"""Fresh NFL Spread V7 production activation for long-lived Streamlit runtimes.

This module intentionally has a brand-new import identity.  The prior production
entry module existed before V7, so a warm Streamlit interpreter could retain the
pre-V7 object in ``sys.modules`` even after repository contents changed.  This
fresh module binds the exact NFL -> Spread seam to V7 while preserving the
certified tap-only mobile market picker and every non-Spread route unchanged.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

import streamlit as st

import nfl_spread_hub_v7 as spread_v7
import streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1 as prior


MODEL_VERSION = "API2 NFL SPREAD • FRESH V7 LIVE ACTIVATION • PRO INTELLIGENCE V1"
FROZEN_PARENT = "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1"
ACTIVE_SPREAD_PAGE = "nfl_spread_hub_v7"
FRESH_MODULE_IDENTITY = True
TAP_ONLY_NFL_MARKET_NAV = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _tap_only_nfl_market_picker(
    options: Iterable[Any],
    *,
    key: str = "ks_nfl_market_touch",
    index: int = 0,
) -> Any:
    values = list(options)
    if not values:
        raise ValueError("NFL market options are required")

    safe_index = max(0, min(int(index), len(values) - 1))
    current = st.session_state.get(key)
    if current not in values:
        current = values[safe_index]
        st.session_state[key] = current

    with st.popover(str(current), use_container_width=True):
        st.caption("🎯 NFL Market")
        for position, option in enumerate(values):
            selected = option == current
            button_key = f"{key}__tap_only__{position}"
            if st.button(
                ("✓ " if selected else "") + str(option),
                key=button_key,
                use_container_width=True,
                type="primary" if selected else "secondary",
            ):
                st.session_state[key] = option
                st.rerun()
    return current


def _make_selectbox_bridge(
    delegate: Callable[..., Any],
) -> Callable[..., Any]:
    def _bridge(label: str, options, *args, **kwargs):
        if (
            str(label or "") == "🎯 NFL Market"
            and str(st.session_state.get("ks_sport_touch") or "") == "NFL"
        ):
            index = kwargs.get("index", args[0] if args else 0)
            key = str(kwargs.get("key") or "ks_nfl_market_touch")
            return _tap_only_nfl_market_picker(options, key=key, index=index)
        return delegate(label, options, *args, **kwargs)

    return _bridge


def render_app() -> Any:
    original_selectbox = st.selectbox
    original_spread_page = prior.spread_v5
    st.selectbox = _make_selectbox_bridge(original_selectbox)
    prior.spread_v5 = spread_v7
    try:
        return prior.render_app()
    finally:
        prior.spread_v5 = original_spread_page
        st.selectbox = original_selectbox


__all__ = [
    "ACTIVE_SPREAD_PAGE",
    "FRESH_MODULE_IDENTITY",
    "FROZEN_PARENT",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "TAP_ONLY_NFL_MARKET_NAV",
    "WAGER_ACTIONS_ENABLED",
    "_tap_only_nfl_market_picker",
    "record_bootstrap_import_ms",
    "render_app",
]
