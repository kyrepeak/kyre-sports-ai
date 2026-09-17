"""CFB Game Total Clean Page V14 — V163 visible game selector.

Additive successor to permanently frozen V162/V13. V163 adds one presentation
interaction only: after the frozen GAME DAY strip, every verified game returned
for that selected day is exposed in a horizontally scrollable on-page selector.
The selected matchup is persisted by official ESPN event_id and fed back into
the frozen V159/V161 analysis pipeline through its existing matchup widget key.

Projection math, distribution math, Step-12 qualification, Top-5 ranking,
API/model behavior, and sportsbook projection influence remain unchanged.
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape
import json
import os
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
import streamlit as st
import streamlit.components.v1 as components

import cfb_game_total_clean_page_v13 as prior_v162
import cfb_game_total_clean_page_v11 as v161

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V14 • V163 VISIBLE GAME SELECTOR"
MARKET = prior_v162.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v13"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V163 ACTIVE"

DATE_QUERY_KEY = v161.DATE_QUERY_KEY
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
CFB_SPORT_LABEL = "College Football"
GAME_TOTAL_MARKET = "Game Total"
MATCHUP_STATE_KEY_PREFIX = "cfb_v152_game_total_matchup_"
SELECTOR_IDENTITY_ENDPOINT = "/api/v1/cfb/selector/verified-games"
SELECTOR_IDENTITY_SOURCE = "Kyre Sports API full-slate verified identity"
WRAPPER_HISTORY_BRIDGE_MARKER = "CFB_V163_WRAPPER_HISTORY_BRIDGE_ACTIVE"

_V163_CSS = r"""
<style>
.gt163-game-wrap{max-width:900px;margin:0 auto 12px;padding:8px 10px 9px;border:1px solid rgba(84,153,194,.28);border-radius:13px;background:linear-gradient(120deg,rgba(6,24,35,.98),rgba(8,17,31,.98));box-sizing:border-box}
.gt163-game-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 2px 7px;color:#edf7ff}.gt163-game-title b{font-size:11px;letter-spacing:.10em}.gt163-game-title span{font-size:9px;color:#8099ad}
.gt163-game-scroller{display:flex;gap:8px;overflow-x:auto;overflow-y:hidden;padding:2px 2px 6px;scroll-snap-type:x proximity;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;scrollbar-width:thin}
.gt163-game-link{display:flex;align-items:center;min-width:225px;max-width:310px;min-height:44px;padding:7px 11px;border:1px solid rgba(79,153,194,.34);border-radius:10px;background:#071824;color:#c7d8e6!important;text-decoration:none!important;font-size:10px;font-weight:900;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;scroll-snap-align:start;box-sizing:border-box}
.gt163-game-link:hover{border-color:rgba(102,185,255,.70);background:#0a2130;color:#f6fbff!important}.gt163-game-link.selected{border-color:rgba(69,240,173,.72);background:linear-gradient(145deg,rgba(19,105,76,.70),rgba(7,35,40,.95));color:#f7fbff!important;box-shadow:0 0 14px rgba(69,240,173,.12)}
.gt163-game-disabled{display:flex;align-items:center;min-width:225px;min-height:44px;padding:7px 11px;border:1px solid rgba(244,206,99,.28);border-radius:10px;background:rgba(84,63,16,.14);color:#bcae80;font-size:10px;font-weight:850;box-sizing:border-box}
.gt163-identity{display:none!important}
@media(max-width:760px){.gt163-game-wrap{padding:7px 7px 7px;margin-bottom:9px}.gt163-game-title span{display:none}.gt163-game-link,.gt163-game-disabled{min-width:205px;min-height:40px;padding:6px 9px;font-size:9px;border-radius:8px}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _game_id(game: Mapping[str, Any]) -> str:
    """Return only an authoritative ESPN event identity for selector state."""
    for key in ("espn_event_id", "event_id"):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _query_event_id() -> str:
    try:
        raw = st.query_params.get(EVENT_QUERY_KEY)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return _clean(raw)


def _set_query_event_id(event_id: str) -> None:
    event_id = _clean(event_id)
    if not event_id:
        return
    try:
        if _query_event_id() != event_id:
            st.query_params[EVENT_QUERY_KEY] = event_id
    except Exception:
        pass


def _selected_game_index(games: Sequence[Mapping[str, Any]], event_id: str) -> int:
    target = _clean(event_id)
    if target:
        for index, game in enumerate(games):
            if _game_id(game) == target:
                return index
    return 0


def _team_name(game: Mapping[str, Any], side: str) -> str:
    candidates = (game.get(side), game.get(f"{side}_team"), game.get(f"{side}Team"))
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            nested_team = candidate.get("team")
            if isinstance(nested_team, Mapping):
                for key in ("display_name", "displayName", "short_display_name", "shortDisplayName", "name", "school", "location"):
                    value = _clean(nested_team.get(key))
                    if value:
                        return value
            for key in ("display_name", "displayName", "short_display_name", "shortDisplayName", "name", "team_name", "school", "location"):
                value = _clean(candidate.get(key))
                if value:
                    return value
        elif candidate is not None:
            value = _clean(candidate)
            if value:
                return value
    for key in (f"{side}_team_name", f"{side}_name", f"{side}_school"):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _kickoff_text(game: Mapping[str, Any]) -> str:
    for key in ("kickoff_et", "kickoff_iso", "start_time_utc", "kickoff_utc", "start_time", "kickoff", "start_date", "date"):
        raw = _clean(game.get(key))
        if not raw:
            continue
        if "T" not in raw and ":" not in raw:
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            if len(raw) <= 24:
                return raw
            continue
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("America/New_York"))
        local = parsed.astimezone(ZoneInfo("America/New_York"))
        return local.strftime("%I:%M %p ET").lstrip("0")
    return "TBD"


def _game_label(game: Mapping[str, Any], fallback: str = "") -> str:
    away = _team_name(game, "away")
    home = _team_name(game, "home")
    if away and home:
        return f"{_kickoff_text(game)} • {away} @ {home}"
    return _clean(fallback) or "Game"


def _selector_href(game: Mapping[str, Any], selected_day: date) -> str:
    event_id = _game_id(game)
    if not event_id:
        return ""
    params = {
        ROUTE_QUERY_SPORT: CFB_SPORT_LABEL,
        ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET,
        DATE_QUERY_KEY: selected_day.isoformat(),
        EVENT_QUERY_KEY: event_id,
    }
    # Navigate the Streamlit app frame; Streamlit mirrors query params to the wrapper URL.
    return "?" + urlencode(params)


def _school_tokens(value: Any) -> tuple[str, ...]:
    text = _clean(value).casefold().replace("&", " and ")
    text = re.sub(r"\([^)]*\)", " ", text)
    raw_tokens = re.findall(r"[a-z0-9]+", text)
    replacements = {"st": "state"}
    generic = {"the", "university", "college"}
    return tuple(
        replacements.get(token, token)
        for token in raw_tokens
        if token not in generic
    )


def _same_school(left: Any, right: Any) -> bool:
    left_tokens = set(_school_tokens(left))
    right_tokens = set(_school_tokens(right))
    if not left_tokens or not right_tokens:
        return False
    return (
        left_tokens == right_tokens
        or left_tokens.issubset(right_tokens)
        or right_tokens.issubset(left_tokens)
    )


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_selector_identity_payload(selected_day: date) -> dict[str, Any]:
    """Read the full selected-day official identity slate from Kyre Sports API."""
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
    if payload.get("synthetic_ids") is not False:
        return {}
    try:
        if float(payload.get("projection_weight")) != 0.0:
            return {}
    except (TypeError, ValueError):
        return {}
    return payload


def _enrich_selector_ids_from_api(
    games: list[dict[str, Any]],
    payload: Mapping[str, Any],
    selected_day: date,
) -> int:
    target_date = selected_day.isoformat()
    rows = payload.get("games") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return 0

    used_ids = {_game_id(game) for game in games if _game_id(game)}
    matched = 0
    for game in games:
        if _game_id(game):
            continue
        away = _team_name(game, "away")
        home = _team_name(game, "home")
        candidate_ids: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            if not isinstance(row, Mapping) or row.get("identity_verified") is not True:
                continue
            if _clean(row.get("game_date")) != target_date:
                continue
            official_id = _clean(row.get("event_id"))
            if not official_id or official_id in used_ids:
                continue
            if not _same_school(away, row.get("away_team")):
                continue
            if not _same_school(home, row.get("home_team")):
                continue
            candidate_ids[official_id] = row

        if len(candidate_ids) != 1:
            continue
        official_id = next(iter(candidate_ids))
        game["espn_event_id"] = official_id
        game["selector_identity_source"] = SELECTOR_IDENTITY_SOURCE
        used_ids.add(official_id)
        matched += 1
    return matched


def _load_games(selected_day: date) -> list[Mapping[str, Any]]:
    schedule = v161.prior.frozen_page.frozen_v2.frozen_v1.schedule
    games, _diag = schedule.load_with_diagnostics(selected_day)
    copied = [dict(game) for game in (games or []) if isinstance(game, Mapping)]

    if any(not _game_id(game) for game in copied):
        payload = _fetch_selector_identity_payload(selected_day)
        if payload:
            _enrich_selector_ids_from_api(copied, payload, selected_day)
    return copied


def _sync_frozen_matchup_state(selected_day: date, games: Sequence[Mapping[str, Any]]) -> int:
    if not games:
        return 0
    selected_index = _selected_game_index(games, _query_event_id())
    event_id = _game_id(games[selected_index])
    if event_id:
        _set_query_event_id(event_id)
    st.session_state[f"{MATCHUP_STATE_KEY_PREFIX}{selected_day}"] = selected_index
    return selected_index


def _sync_wrapper_history(selected_day: date, event_id: str) -> None:
    """Mirror the canonical app-frame query into the Streamlit Cloud wrapper URL."""
    event_id = _clean(event_id)
    if not event_id:
        return
    query = "?" + urlencode(
        {
            ROUTE_QUERY_SPORT: CFB_SPORT_LABEL,
            ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET,
            DATE_QUERY_KEY: selected_day.isoformat(),
            EVENT_QUERY_KEY: event_id,
        }
    )
    st.markdown(
        '<span data-testid="gt163-wrapper-history-bridge" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    components.html(
        f"""
        <script>
        (() => {{
          try {{
            const query = {json.dumps(query)};
            const wrapper = window.parent && window.parent.parent;
            if (wrapper && wrapper.history && wrapper.location.search !== query) {{
              wrapper.history.replaceState(null, "", query);
            }}
          }} catch (e) {{}}
        }})();
        </script>
        """,
        height=0,
    )


def _render_game_strip(selected_day: date, games: Sequence[Mapping[str, Any]], selected_index: int) -> None:
    st.markdown(_V163_CSS, unsafe_allow_html=True)
    if not games:
        return
    cards: list[str] = []
    identity_ui = v161.prior.frozen_page.frozen_v2.frozen_v1.identity_ui
    for index, game in enumerate(games):
        try:
            fallback = identity_ui._matchup_label(game)
        except Exception:
            fallback = f"Game {index + 1}"
        label = _game_label(game, fallback)
        event_id = _game_id(game)
        selected = index == selected_index
        if event_id:
            href = _selector_href(game, selected_day)
            selected_class = " selected" if selected else ""
            aria = ' aria-current="true"' if selected else ""
            prefix = "✓ " if selected else ""
            cards.append(
                f'<a class="gt163-game-link{selected_class}" data-event-id="{escape(event_id)}" '
                f'href="{escape(href, quote=True)}" target="_self"{aria}>{escape(prefix + label)}</a>'
            )
        else:
            cards.append(f'<span class="gt163-game-disabled">{escape(label)} • ESPN ID unavailable</span>')
    st.markdown(
        '<div class="gt163-game-wrap" data-testid="gt163-game-strip">'
        '<div class="gt163-game-title"><b>🏟️ GAMES ON THIS DAY</b><span>Swipe or scroll • tap a matchup to load its full analysis</span></div>'
        f'<div class="gt163-game-scroller">{"".join(cards)}</div></div>',
        unsafe_allow_html=True,
    )


def _render_v163_identity() -> None:
    st.markdown(
        '<div class="gt163-identity" data-testid="cfb-game-total-v163-active">'
        f'{ACTIVE_MARKER} • V162 frozen parent • exact ESPN event selector • sportsbook 0.0%</div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    """Render frozen V162, adding only the visible event selector under GAME DAY."""
    original_day_strip = v161._render_day_strip

    def day_strip_wrapper() -> date:
        selected_day = original_day_strip()
        games = _load_games(selected_day)
        selected_index = _sync_frozen_matchup_state(selected_day, games)
        selected_event = _game_id(games[selected_index]) if games else ""
        _sync_wrapper_history(selected_day, selected_event)
        _render_game_strip(selected_day, games, selected_index)
        _render_v163_identity()
        return selected_day

    v161._render_day_strip = day_strip_wrapper
    try:
        return prior_v162.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        v161._render_day_strip = original_day_strip


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V163 Game Total V14 page received unsupported market: {market}")
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
    "WRAPPER_HISTORY_BRIDGE_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_enrich_selector_ids_from_api",
    "_fetch_selector_identity_payload",
    "_game_id",
    "_game_label",
    "_load_games",
    "_query_event_id",
    "_same_school",
    "_selected_game_index",
    "_selector_href",
    "_set_query_event_id",
    "_sync_wrapper_history",
    "render_cfb_hub",
    "render_game_total_hub",
]
