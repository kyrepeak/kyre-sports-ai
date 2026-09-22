"""KYRE Streamlit Router V103 — NFL Rushing Yards Page Step 4."""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v102 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V103 • NFL RUSHING YARDS PAGE STEP 4 OPPONENT RUN DEFENSE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v102"
ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v7"
RUSHING_YARDS_MARKET = "Rushing Yards"

_PRIOR_RENDER_NFL = prior._render_nfl_v102


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v103(market: str) -> None:
    market = str(market or "Slate")
    if market == RUSHING_YARDS_MARKET:
        module = root._import(ACTIVE_RUSHING_YARDS_HUB)
        return module.render_nfl_hub(market)
    return _PRIOR_RENDER_NFL(market)


def render_app() -> None:
    original_handler = prior._render_nfl_v102
    prior._render_nfl_v102 = _render_nfl_v103
    try:
        return prior.render_app()
    finally:
        prior._render_nfl_v102 = original_handler


__all__ = [
    "ACTIVE_RUSHING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "RUSHING_YARDS_MARKET",
    "_render_nfl_v103",
    "record_bootstrap_import_ms",
    "render_app",
]
