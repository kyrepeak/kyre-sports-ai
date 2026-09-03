"""KYRE Streamlit router V5 — additive MLB Moneyline Step 2 route.

Router V4 remains frozen. This wrapper advances only MLB `Moneyline` from the
frozen V16.6 Step 1 presentation to additive Moneyline UI V16.7 Step 2.
Hits, Matchup Explorer, and every other market continue through Router V4/V3/V2/V1
unchanged. V4 itself is never modified at runtime on disk; its renderer is patched
only for the duration of the delegated render call and restored in `finally`.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v4 as frozen_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER V5 • Moneyline Step 2"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v4"


def _render_mlb_v5_base(market: str) -> None:
    if market != "Moneyline":
        return frozen_router._BASE_MLB_ROUTE(market)

    import mlb_moneyline_hub_v167 as moneyline

    original = frozen_router.prior._BASE_RENDER_MLB
    frozen_router.prior._BASE_RENDER_MLB = moneyline.render_moneyline_hub
    try:
        return frozen_router._BASE_MLB_ROUTE(market)
    finally:
        frozen_router.prior._BASE_RENDER_MLB = original


def render_app() -> None:
    original = frozen_router._render_mlb_v4_base
    frozen_router._render_mlb_v4_base = _render_mlb_v5_base
    try:
        frozen_router.render_app()
    finally:
        frozen_router._render_mlb_v4_base = original


__all__ = ["FROZEN_ROUTER", "MODEL_VERSION", "_render_mlb_v5_base", "render_app"]
