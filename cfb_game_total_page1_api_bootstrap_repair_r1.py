"""CFB Game Total Page 1 API bootstrap repair R1.

Additive successor around the frozen S-tier Page 1. It changes only the
application-facing Kyre Sports API base resolution: explicit environment and
Streamlit secret overrides still win; otherwise the canonical production Kyre
Sports API Vercel gateway is used. No provider, market, model, projection,
probability, ranking, selection, or Page 2 logic is owned here.
"""
from __future__ import annotations

import os

import streamlit as st

import cfb_game_total_page1_stier_v1 as prior

MODEL_VERSION = "CFB GAME TOTAL PAGE1 API BOOTSTRAP REPAIR R1"
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
    original = prior._api_base
    prior._api_base = _api_base
    try:
        return prior.render_game_total_page1()
    finally:
        prior._api_base = original


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
