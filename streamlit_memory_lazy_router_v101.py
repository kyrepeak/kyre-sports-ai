"""KYRE Streamlit Router V101 — NFL Rushing Yards Page Step 2."""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v100 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V101 • NFL RUSHING YARDS PAGE STEP 2 SUMMARY METRICS"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v100"
ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v5"
RUSHING_YARDS_MARKET = "Rushing Yards"

_PRIOR_RENDER_NFL = prior._render_nfl_v100


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v101(market: str) -> None:
    market = str(market or "Slate")
    if market == RUSHING_YARDS_MARKET:
        module = root._import(ACTIVE_RUSHING_YARDS_HUB)
        return module.render_nfl_hub(market)
    return _PRIOR_RENDER_NFL(market)


def render_app() -> None:
    original_handler = prior._render_nfl_v100
    prior._render_nfl_v100 = _render_nfl_v101
    try:
        return prior.render_app()
    finally:
        prior._render_nfl_v100 = original_handler


__all__ = [
    "ACTIVE_RUSHING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "RUSHING_YARDS_MARKET",
    "_render_nfl_v101",
    "record_bootstrap_import_ms",
    "render_app",
]
