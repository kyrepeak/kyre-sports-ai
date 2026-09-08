"""KYRE Streamlit router V22 — root Hits route correction.

Why V21 could still display V13.16
---------------------------------
Router V3 is the first wrapper that intercepts MLB `1+ Hit`. Its
`_render_mlb_v3` handles Hits directly and only delegates non-Hits markets
through `_BASE_RENDER_MLB`.

Routers V17-V21 attempted to replace deeper delegation hooks. Those hooks are
never reached for `1+ Hit` because Router V3 returns first. Therefore the live
app could correctly boot current `app.py` / Router V21 yet still render frozen
Hits UI V13.16.

V22 patches the actual first-hit boundary: Router V3's `_render_mlb_v3`
callable. Only `MLB -> 1+ Hit` is redirected to certified Hits UI V13.21.
Every non-Hits route is delegated to the exact frozen Router V3 callable, which
preserves the current Moneyline/Matchup Explorer/etc. chain.

No model, probability, Monte Carlo, ranking, candidate, calibration, or history
logic lives here.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v21 as prior
import streamlit_memory_lazy_router_v3 as root_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER V22 • Hits root-route correction"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v21"
ROOT_ROUTE = "streamlit_memory_lazy_router_v3._render_mlb_v3"

_FROZEN = root_router.frozen
_BASE_ROOT_ROUTE = root_router._render_mlb_v3


def _render_mlb_v22_root(market: str) -> None:
    """Intercept only Hits at the first route boundary that actually handles it."""
    if market != "1+ Hit":
        return _BASE_ROOT_ROUTE(market)

    games_df, day = _FROZEN._load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")
    _FROZEN._install_step8f_for_market(market)
    mod = _FROZEN._import("mlb_hit_hub_v1321")
    mod.render_hit_hub(
        games_df,
        _FROZEN.section_header,
        _FROZEN.status_info,
        _FROZEN.team_logo,
        _FROZEN.h,
    )


def render_app() -> None:
    """Temporarily replace Router V3's direct Hits interceptor, then restore it."""
    original = root_router._render_mlb_v3
    root_router._render_mlb_v3 = _render_mlb_v22_root
    try:
        prior.render_app()
    finally:
        root_router._render_mlb_v3 = original


__all__ = [
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "ROOT_ROUTE",
    "_BASE_ROOT_ROUTE",
    "_render_mlb_v22_root",
    "render_app",
]
