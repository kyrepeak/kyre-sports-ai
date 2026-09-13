"""KYRE Streamlit Router V105 — NFL Rushing Yards Page Step 6 final support/concerns."""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v104 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V105 • NFL RUSHING YARDS PAGE STEP 6 SUPPORT CONCERNS"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v104"
ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v9"
RUSHING_YARDS_MARKET = "Rushing Yards"

_PRIOR_RENDER_NFL = prior._render_nfl_v104


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v105(market: str) -> None:
    market = str(market or "Slate")
    if market == RUSHING_YARDS_MARKET:
        module = root._import(ACTIVE_RUSHING_YARDS_HUB)
        return module.render_nfl_hub(market)
    return _PRIOR_RENDER_NFL(market)


def render_app() -> None:
    original_handler = prior._render_nfl_v104
    prior._render_nfl_v104 = _render_nfl_v105
    try:
        return prior.render_app()
    finally:
        prior._render_nfl_v104 = original_handler


__all__ = [
    "ACTIVE_RUSHING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "RUSHING_YARDS_MARKET",
    "_render_nfl_v105",
    "record_bootstrap_import_ms",
    "render_app",
]
