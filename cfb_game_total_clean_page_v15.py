"""CFB Game Total Clean Page V15 — V164 universal exact team logos.

Additive presentation-only successor to permanently frozen V163/V14. V164 keeps
all V163 selector, model, market, qualification and ranking behavior unchanged,
and enriches only missing display-logo team IDs from official ESPN event
identity before the frozen exact-ID logo resolver runs.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v14 as prior_v163
import cfb_game_total_team_logo_identity_v1 as logo_identity
import cfb_over_under_logo_resolver_v3 as frozen_logo

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V15 • V164 UNIVERSAL EXACT TEAM LOGOS"
MARKET = prior_v163.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v14"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V164 ACTIVE"
LOGO_POLICY = "official ESPN event_id -> exact ESPN team IDs -> ESPN NCAA logo CDN"

_FROZEN_RESOLVE_VISUALS = frozen_logo.resolve_visuals


def _selector_payload_for_game(game: Mapping[str, Any]) -> dict[str, Any]:
    requested_day = logo_identity._game_date(game)
    if not requested_day:
        return {}
    try:
        return prior_v163._fetch_selector_identity_payload(date.fromisoformat(requested_day))
    except (TypeError, ValueError):
        return {}


def _resolve_visuals_v164(game: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return logo_identity.resolve_visuals(
        game,
        _FROZEN_RESOLVE_VISUALS,
        _selector_payload_for_game(game),
    )


def _render_v164_identity() -> None:
    st.markdown(
        '<div data-testid="cfb-game-total-v164-active" '
        'style="display:none!important">'
        f'{ACTIVE_MARKER} • exact ESPN team logos • V163 frozen parent • '
        'sportsbook projection influence 0.0%</div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    original_resolver = frozen_logo.resolve_visuals
    frozen_logo.resolve_visuals = _resolve_visuals_v164
    try:
        result = prior_v163.render_game_total_hub(section_header, status_info, team_logo, h)
        _render_v164_identity()
        return result
    finally:
        frozen_logo.resolve_visuals = original_resolver


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V164 Game Total V15 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "LOGO_POLICY",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_resolve_visuals_v164",
    "_selector_payload_for_game",
    "render_cfb_hub",
    "render_game_total_hub",
]
