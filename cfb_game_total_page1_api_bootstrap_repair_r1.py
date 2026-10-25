"""CFB Game Total Page 1 API bootstrap repair R1 + A-tier Page 1 V7 readability activation.

The application-facing API base resolver remains unchanged. This wrapper hands
only Page 1 presentation to the approved readability successor. Page 2,
model/projection math, rankings, and the production app entrypoint remain
outside this module's ownership.
"""
from __future__ import annotations

import os

import streamlit as st

import cfb_game_total_page1_stier_v1 as prior

MODEL_VERSION = "CFB GAME TOTAL PAGE1 API BOOTSTRAP REPAIR R1 • A-TIER V7 READABILITY ACTIVATION"
MARKET = prior.MARKET
PAGE1_ENDPOINT = prior.PAGE1_ENDPOINT
KYRE_SPORTS_API_BASE_URL = prior.KYRE_SPORTS_API_BASE_URL
DEFAULT_KYRE_SPORTS_API_BASE_URL = "https://kyre-sports-api.vercel.app"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False


def _clean(value: object) -> str:
    return str(value or "").strip()


def _api_base() -> str:
    value = _clean(os.getenv(KYRE_SPORTS_API_BASE_URL))
    if not value:
        try:
            value = _clean(st.secrets.get(KYRE_SPORTS_API_BASE_URL))
        except Exception:
            value = ""
    return (value or DEFAULT_KYRE_SPORTS_API_BASE_URL).rstrip("/")


def render_game_total_page1() -> None:
    import cfb_game_total_page1_atier_v7 as atier

    return atier.render_game_total_page1()


def render_cfb_hub(market: str, *args, **kwargs) -> None:
    del args, kwargs
    if market != MARKET:
        raise ValueError(f"CFB Game Total bootstrap repair cannot render market={market!r}")
    return render_game_total_page1()


__all__ = [
    "DEFAULT_KYRE_SPORTS_API_BASE_URL",
    "KYRE_SPORTS_API_BASE_URL",
    "MARKET",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "PAGE1_ENDPOINT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_page1",
]
