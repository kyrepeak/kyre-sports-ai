"""API 2 NFL Spread mobile repair overlay.

Adds two presentation/runtime repairs above the frozen production parent:
1) exact NFL -> Spread delegates to V7 professional intelligence over V6 repeatable empty-date auto-advance;
2) the NFL market selector is rendered as a tap-only popover menu so mobile
   browsers never focus a searchable select input or summon the software keyboard.
All other sport/market behavior delegates to the current frozen parent unchanged.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

import streamlit as st

import nfl_spread_hub_v7 as spread_v7
import streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1 as prior


MODEL_VERSION = "API2 NFL SPREAD • AUTODATE + TAP-ONLY MOBILE NAV + PRO INTELLIGENCE V1"
FROZEN_PARENT = "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1"
ACTIVE_SPREAD_PAGE = "nfl_spread_hub_v7"
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

    # Popover + buttons is intentionally non-searchable. Unlike st.selectbox,
    # it has no text-entry target for iOS to focus, so tapping it cannot summon
    # the software keyboard.
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
