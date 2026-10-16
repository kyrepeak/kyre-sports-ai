"""NBA Spread Page V6 — additive post-freeze live-data repair.

The frozen Step-10 page remains the product owner. This wrapper reconnects
already-certified observation transports at runtime and restores every patched
loader after render. It does not alter any Step 1-10 model or decision math.
"""
from __future__ import annotations

import streamlit as st

import nba_spread_page_v1 as base_page
import nba_spread_page_v4 as step9_page
import nba_spread_page_v5 as step10_page
from nba_spread_live_data_repair_v1 import (
    build_market_feature,
    build_public_betting_features,
    load_market_payload,
    load_public_betting_payload,
)

MODEL_VERSION = "NBA_SPREAD_PAGE_V6_POST_FREEZE_LIVE_DATA_REPAIR"
LIVE_DATA_REPAIR_HEARTBEAT = "NBA_SPREAD_LIVE_DATA_REPAIR_V1_ACTIVE"
FROZEN_PARENT_PAGE = "nba_spread_page_v5"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_FROZEN_STEPS = False


@st.cache_data(ttl=90, show_spinner=False)
def _load_public_bundle(games: list[dict]) -> dict:
    payload = load_public_betting_payload(games)
    return build_public_betting_features(games, payload=payload)


def _load_most_bet(games: list[dict]) -> dict:
    return dict(_load_public_bundle(games).get("most_bet") or {})


def _load_sharp_money(games: list[dict]) -> dict:
    return dict(_load_public_bundle(games).get("sharp_money") or {})


@st.cache_data(ttl=90, show_spinner=False)
def _load_verified_market_payload(games: list[dict]) -> dict:
    return load_market_payload(games)


def _load_market_lines(games: list[dict]) -> dict:
    return build_market_feature(games, payload=_load_verified_market_payload(games))


def render_nba_spread_page() -> None:
    st.markdown(
        f'<div data-testid="nba-spread-live-data-repair-active" data-heartbeat="{LIVE_DATA_REPAIR_HEARTBEAT}" style="display:none!important"></div>',
        unsafe_allow_html=True,
    )

    original_most_bet = base_page._load_most_bet
    original_sharp_money = base_page._load_sharp_money
    original_market_lines = base_page._load_market_lines
    original_step9_market = step9_page._load_sportsbook_observations

    base_page._load_most_bet = _load_most_bet
    base_page._load_sharp_money = _load_sharp_money
    base_page._load_market_lines = _load_market_lines
    step9_page._load_sportsbook_observations = _load_verified_market_payload
    try:
        return step10_page.render_nba_spread_page()
    finally:
        base_page._load_most_bet = original_most_bet
        base_page._load_sharp_money = original_sharp_money
        base_page._load_market_lines = original_market_lines
        step9_page._load_sportsbook_observations = original_step9_market


__all__ = [
    "MODEL_VERSION",
    "LIVE_DATA_REPAIR_HEARTBEAT",
    "FROZEN_PARENT_PAGE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_FROZEN_STEPS",
    "render_nba_spread_page",
]
