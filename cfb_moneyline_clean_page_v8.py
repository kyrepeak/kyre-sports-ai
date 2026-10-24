"""CFB Moneyline Premium V8 — compact horizontal logo matchup rail.

Presentation-only wrapper over V7. It replaces only the native Streamlit
segmented matchup selector with a horizontal HTML rail, then restores the
original Streamlit function. All V7 analytics/model behavior remains owned by
V7 and its frozen ancestors.
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape
import json
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st

import cfb_moneyline_clean_page_v7 as prior

MODEL_VERSION = "CFB MONEYLINE PREMIUM V8 • COMPACT LOGO MATCHUP RAIL R1"
FROZEN_MONEYLINE_OWNER = prior.FROZEN_MONEYLINE_OWNER
FROZEN_RAW_MODEL = prior.FROZEN_RAW_MODEL
FROZEN_FINAL_MODEL = prior.FROZEN_FINAL_MODEL
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
TEAM_IDENTITY_ENDPOINT = "/api/v1/cfb/game-total/page1"
_api_base = prior._api_base
_ORIGINAL_LOAD_PAGE_PAYLOAD = prior._load_page_payload

_CONTEXT_GAMES: list[dict[str, Any]] = []
_CONTEXT_IDENTITIES: dict[str, dict[str, Any]] = {}
_CONTEXT_SELECTED_DAY = ""

_CSS = r"""
<style>
.cfbml8-rail{display:flex;flex-wrap:nowrap;gap:8px;overflow-x:auto;overflow-y:hidden;white-space:nowrap;padding:2px 34px 10px 0;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;scrollbar-width:thin}
.cfbml8-chip{display:inline-flex;flex:0 0 176px;width:176px;height:76px;box-sizing:border-box;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:9px 10px;border:1px solid rgba(94,160,193,.24);border-radius:14px;background:linear-gradient(145deg,#071722,#081b27);color:#d7edf6!important;text-decoration:none!important;scroll-snap-align:start;box-shadow:0 8px 18px rgba(0,0,0,.14)}
.cfbml8-chip.selected{border-color:#68d9ff;background:linear-gradient(145deg,#0a2434,#0b2b40);box-shadow:0 0 0 1px rgba(104,217,255,.13),0 8px 22px rgba(0,0,0,.20)}
.cfbml8-match{display:flex;align-items:center;justify-content:center;gap:6px;width:100%;min-width:0}.cfbml8-logo{position:relative;width:24px;height:24px;flex:0 0 24px;border-radius:50%;display:grid;place-items:center;background:#0a2332;border:1px solid rgba(103,197,238,.24);overflow:hidden;color:#7ddfff;font-size:.26rem;font-weight:1000}.cfbml8-logo img{position:absolute;inset:1px;width:22px;height:22px;object-fit:contain;border-radius:50%;background:#07141f}.cfbml8-abbr{font-size:.43rem;line-height:1;font-weight:1000;color:#f7fbff;letter-spacing:.02em;overflow:hidden;text-overflow:ellipsis;max-width:43px}.cfbml8-at{font-size:.34rem;font-weight:900;color:#66889a}.cfbml8-time{font-size:.30rem;line-height:1;font-weight:850;color:#86a7b7;letter-spacing:.025em}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _game_id(game: Mapping[str, Any]) -> str:
    return _clean(game.get("game_id") or game.get("identity_key"))


def _scalar(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return _clean(value)


def _requested_game() -> str:
    return _scalar(st.query_params.get("cfbml_game"))


def _rail_href(game: Mapping[str, Any], selected_day: date) -> str:
    gid = _game_id(game)
    if not gid:
        return ""
    day = selected_day.isoformat()
    return "?" + urlencode({"sport": "cfb", "market": "moneyline", "date": day, "ks_sport": "College Football", "ks_cfb_market": "Moneyline", "cfbml_game": gid})


def _identity_for(game: Mapping[str, Any], identities: Mapping[str, Any], side: str) -> Mapping[str, Any]:
    row = identities.get(_game_id(game)) if isinstance(identities, Mapping) else None
    value = row.get(side) if isinstance(row, Mapping) else None
    return value if isinstance(value, Mapping) else {}


def _monogram(name: str) -> str:
    parts = [part for part in _clean(name).replace("-", " ").replace(".", "").split() if part]
    return "".join(part[:1] for part in parts[:3]).upper() or "CFB"


def _abbr(game: Mapping[str, Any], identities: Mapping[str, Any], side: str) -> str:
    identity = _identity_for(game, identities, side)
    fallback = _clean(identity.get("fallback_monogram"))
    if fallback:
        return fallback.upper()[:6]
    return _monogram(_clean(game.get(f"{side}_team")) or side.title())[:6]


def _logo(game: Mapping[str, Any], identities: Mapping[str, Any], side: str) -> str:
    identity = _identity_for(game, identities, side)
    name = _clean(game.get(f"{side}_team")) or side.title()
    fallback = _abbr(game, identities, side)
    url = _clean(identity.get("logo_url"))
    img = f'<img src="{escape(url, quote=True)}" alt="{escape(name, quote=True)} logo" loading="lazy" onerror="this.style.display=\'none\'">' if url else ""
    return f'<span class="cfbml8-logo"><span>{escape(fallback)}</span>{img}</span>'


def _kickoff_time(game: Mapping[str, Any]) -> str:
    text = _clean(game.get("kickoff_iso") or game.get("start_time_utc"))
    if not text:
        return "Time TBD"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return "Time TBD"
        return parsed.astimezone(prior._PHOENIX).strftime("%-I:%M %p")
    except (TypeError, ValueError):
        return "Time TBD"


@st.cache_data(ttl=60, show_spinner=False)
def _load_identity_map(game_date: str) -> dict[str, dict[str, Any]]:
    day = _clean(game_date)
    if not day:
        return {}
    url = _api_base() + TEAM_IDENTITY_ENDPOINT + "?" + urlencode({"game_date": day})
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-CFB-Moneyline-V8/1"})
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, Mapping) or _clean(payload.get("service")) != "Kyre Sports API":
        return {}
    out: dict[str, dict[str, Any]] = {}
    for game in payload.get("games") or []:
        if isinstance(game, Mapping) and _game_id(game) and isinstance(game.get("team_identity"), Mapping):
            out[_game_id(game)] = dict(game["team_identity"])
    return out


def _capture_payload(game_date: str = "", game_id: str = "") -> dict[str, Any]:
    global _CONTEXT_GAMES, _CONTEXT_IDENTITIES, _CONTEXT_SELECTED_DAY
    payload = _ORIGINAL_LOAD_PAGE_PAYLOAD(game_date, game_id)
    selected_day = _clean(payload.get("selected_date"))
    _CONTEXT_SELECTED_DAY = selected_day
    _CONTEXT_GAMES = [dict(row) for row in payload.get("games") or [] if isinstance(row, Mapping)]
    _CONTEXT_IDENTITIES = _load_identity_map(selected_day)
    return payload


def _rail_html(games: list[Mapping[str, Any]], selected: Mapping[str, Any], selected_day: date, identities: Mapping[str, Any]) -> str:
    selected_id = _game_id(selected)
    chips: list[str] = []
    for game in games:
        href = _rail_href(game, selected_day)
        if not href:
            continue
        active = " selected" if _game_id(game) == selected_id else ""
        away_abbr = _abbr(game, identities, "away")
        home_abbr = _abbr(game, identities, "home")
        kickoff = _kickoff_time(game)
        label = f'{_clean(game.get("away_team"))} at {_clean(game.get("home_team"))}, {kickoff}'
        chips.append(f'<a class="cfbml8-chip{active}" href="{escape(href, quote=True)}" target="_self" aria-label="{escape(label, quote=True)}"><span class="cfbml8-match">{_logo(game, identities, "away")}<span class="cfbml8-abbr">{escape(away_abbr)}</span><span class="cfbml8-at"> @ </span><span class="cfbml8-abbr">{escape(home_abbr)}</span>{_logo(game, identities, "home")}</span><span class="cfbml8-time">{escape(kickoff)}</span></a>')
    return '<div class="cfbml8-rail">' + "".join(chips) + "</div>"


def _segmented_control(label, *, options, format_func=None, default=None, selection_mode="single", label_visibility="visible", key=None, **kwargs):
    del label, format_func, selection_mode, label_visibility, key, kwargs
    option_ids = [_clean(value) for value in options if _clean(value)]
    chosen = _requested_game()
    if chosen not in option_ids:
        chosen = _clean(default) if _clean(default) in option_ids else (option_ids[0] if option_ids else "")
    selected = next((game for game in _CONTEXT_GAMES if _game_id(game) == chosen), None)
    if selected is not None and _CONTEXT_SELECTED_DAY:
        st.markdown(_CSS, unsafe_allow_html=True)
        st.markdown(_rail_html(_CONTEXT_GAMES, selected, date.fromisoformat(_CONTEXT_SELECTED_DAY), _CONTEXT_IDENTITIES), unsafe_allow_html=True)
    return chosen or None


def render_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    original_segmented = prior.st.segmented_control
    original_loader = prior._load_page_payload
    original_prior_api_base = prior._api_base
    prior.st.segmented_control = _segmented_control
    prior._load_page_payload = _capture_payload
    prior._api_base = _api_base
    try:
        return prior.render_moneyline_hub(section_header, status_info, team_logo, h)
    finally:
        prior.st.segmented_control = original_segmented
        prior._load_page_payload = original_loader
        prior._api_base = original_prior_api_base


def render_cfb_hub(market_id: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if _clean(market_id).lower() == "moneyline":
        return render_moneyline_hub(section_header, status_info, team_logo, h)
    return prior.render_cfb_hub(market_id, section_header, status_info, team_logo, h)


__all__ = ["MODEL_VERSION", "FROZEN_MONEYLINE_OWNER", "FROZEN_RAW_MODEL", "FROZEN_FINAL_MODEL", "SPORTSBOOK_PROJECTION_INFLUENCE", "MAY_MODIFY_PROJECTION", "MAY_MODIFY_PROBABILITY", "MAY_MODIFY_RANKING", "MAY_MODIFY_SELECTION", "render_moneyline_hub", "render_cfb_hub"]
