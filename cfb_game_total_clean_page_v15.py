"""CFB Game Total Clean Page V15 — V164 Render-hosted official identity.

Additive successor to V163/V14. V164 changes only selector identity transport:
missing official event IDs are resolved through the Kyre Sports API's read-only
server-side identity feed instead of relying on the Streamlit runtime to reach
provider identity sources directly.

Projection math, distribution math, Step-12 qualification, Top-5 ranking,
API/model behavior, and sportsbook projection influence remain unchanged.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence
import os

import requests
import streamlit as st

import cfb_game_total_clean_page_v14 as prior_v163

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V15 • V164 RENDER OFFICIAL IDENTITY"
MARKET = prior_v163.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v14"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V164 ACTIVE"
SELECTOR_IDENTITY_ENDPOINT = "/api/v1/cfb/identity/official-games"
SELECTOR_IDENTITY_SOURCE = "Kyre Sports API official-games identity"

DATE_QUERY_KEY = prior_v163.DATE_QUERY_KEY
EVENT_QUERY_KEY = prior_v163.EVENT_QUERY_KEY
ROUTE_QUERY_SPORT = prior_v163.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = prior_v163.ROUTE_QUERY_MARKET


def _clean(value: Any) -> str:
    return str(value or "").strip()


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_selector_identity_payload(selected_day: date) -> dict[str, Any]:
    """Read canonical event IDs from Render; Streamlit never calls ESPN."""
    v161 = prior_v163.v161
    base = _clean(os.environ.get(v161.ODDS_API_BASE_ENV)) or v161.ODDS_API_BASE_DEFAULT
    try:
        response = requests.get(
            f"{base.rstrip('/')}{SELECTOR_IDENTITY_ENDPOINT}",
            params={"game_date": selected_day.isoformat()},
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if payload.get("sportsbook_projection_influence_pct") not in (0, 0.0):
        return {}
    return payload


def _enrich_selector_ids_from_api(
    games: list[dict[str, Any]],
    payload: Mapping[str, Any],
    selected_day: date,
) -> int:
    """Attach one unambiguous canonical event ID to each schedule row."""
    target_date = selected_day.isoformat()
    rows = payload.get("games") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return 0

    used_ids = {
        prior_v163._game_id(game)
        for game in games
        if prior_v163._game_id(game)
    }
    matched = 0
    for game in games:
        if prior_v163._game_id(game):
            continue
        away = prior_v163._team_name(game, "away")
        home = prior_v163._team_name(game, "home")
        candidate_ids: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            if _clean(row.get("game_date")) != target_date:
                continue
            event_id = _clean(row.get("event_id"))
            if not event_id or event_id in used_ids:
                continue
            if not prior_v163._same_school(away, row.get("away_team")):
                continue
            if not prior_v163._same_school(home, row.get("home_team")):
                continue
            candidate_ids[event_id] = row

        # Identity stays fail-closed: exactly one canonical game must match.
        if len(candidate_ids) != 1:
            continue
        event_id = next(iter(candidate_ids))
        row = candidate_ids[event_id]
        game["espn_event_id"] = event_id
        game["selector_identity_source"] = SELECTOR_IDENTITY_SOURCE
        if _clean(row.get("venue")) and not _clean(game.get("venue")):
            game["venue"] = _clean(row.get("venue"))
        if _clean(row.get("broadcast")) and not _clean(game.get("broadcast")):
            game["broadcast"] = _clean(row.get("broadcast"))
        used_ids.add(event_id)
        matched += 1
    return matched


def _load_games(selected_day: date) -> list[Mapping[str, Any]]:
    schedule = prior_v163.v161.prior.frozen_page.frozen_v2.frozen_v1.schedule
    games, _diag = schedule.load_with_diagnostics(selected_day)
    copied = [dict(game) for game in (games or []) if isinstance(game, Mapping)]

    if any(not prior_v163._game_id(game) for game in copied):
        payload = _fetch_selector_identity_payload(selected_day)
        if payload:
            _enrich_selector_ids_from_api(copied, payload, selected_day)
    return copied


def _render_v164_identity() -> None:
    st.markdown(
        '<div style="display:none!important" data-testid="cfb-game-total-v164-active">'
        f'{ACTIVE_MARKER} • V163 frozen parent • Render official identity • sportsbook 0.0%</div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    """Render frozen V163 with only the selector identity transport replaced."""
    v161 = prior_v163.v161
    original_day_strip = v161._render_day_strip

    def day_strip_wrapper() -> date:
        selected_day = original_day_strip()
        games = _load_games(selected_day)
        selected_index = prior_v163._sync_frozen_matchup_state(selected_day, games)
        prior_v163._render_game_strip(selected_day, games, selected_index)
        _render_v164_identity()
        return selected_day

    v161._render_day_strip = day_strip_wrapper
    try:
        return prior_v163.prior_v162.render_game_total_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        v161._render_day_strip = original_day_strip


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V164 Game Total V15 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "DATE_QUERY_KEY",
    "EVENT_QUERY_KEY",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SELECTOR_IDENTITY_ENDPOINT",
    "SELECTOR_IDENTITY_SOURCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_enrich_selector_ids_from_api",
    "_fetch_selector_identity_payload",
    "_load_games",
    "render_cfb_hub",
    "render_game_total_hub",
]
