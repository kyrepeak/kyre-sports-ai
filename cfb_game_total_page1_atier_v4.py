"""CFB Game Total Page 1 A-tier V4 — upcoming matchup rail Step 1."""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Any, Mapping
from urllib.parse import urlencode

import streamlit as st

import cfb_game_total_page1_atier_v1 as base
import cfb_game_total_page1_atier_v3 as prior

MODEL_VERSION = "CFB GAME TOTAL PAGE1 A-TIER V4 • UPCOMING MATCHUP RAIL STEP1"
MARKET = "Game Total"
PAGE1_ENDPOINT = prior.PAGE1_ENDPOINT
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False

_CSS = prior._CSS + r"""
<style>
.cfbgt4-shell{margin:2px 0 8px}.cfbgt4-eyebrow{font-size:.53rem;letter-spacing:.14em;font-weight:950;color:#68d9ff;text-transform:uppercase}.cfbgt4-title{font-size:1.55rem;line-height:1.02;font-weight:1000;color:#f7fbff;margin:4px 0}.cfbgt4-sub{font-size:.58rem;color:#8299aa;max-width:700px;line-height:1.45}.cfbgt4-date{display:inline-flex;align-items:center;min-height:31px;border:1px solid rgba(95,190,233,.20);background:#081925;border-radius:10px;padding:0 10px;font-size:.38rem;font-weight:850;color:#b8d7e6;white-space:nowrap}.cfbgt4-board{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 10px;border:1px solid rgba(87,193,238,.20);border-radius:12px;background:linear-gradient(145deg,#071923,#081d2a);margin:8px 0}.cfbgt4-board b{font-size:.40rem;color:#7ddfff;letter-spacing:.07em;text-transform:uppercase}.cfbgt4-board span{font-size:.31rem;color:#7897a8;text-align:right}.cfbgt4-rail{display:flex;gap:8px;overflow-x:auto;white-space:nowrap;padding:3px 1px 9px;scrollbar-width:thin;scroll-snap-type:x proximity}.cfbgt4-chip{display:inline-flex;flex:0 0 auto;min-width:168px;max-width:220px;flex-direction:column;gap:4px;padding:9px 10px;border:1px solid rgba(94,160,193,.22);border-radius:12px;background:#071722;color:#c8dbe5!important;text-decoration:none!important;scroll-snap-align:start}.cfbgt4-chip:hover{border-color:rgba(89,206,255,.45);background:#092130}.cfbgt4-chip.selected{border-color:#68d9ff;background:linear-gradient(145deg,#0a2434,#0b2b40);box-shadow:inset 0 0 0 1px rgba(104,217,255,.10)}.cfbgt4-match{font-size:.42rem;font-weight:950;overflow:hidden;text-overflow:ellipsis;color:#eff9fd}.cfbgt4-meta{display:flex;align-items:center;justify-content:space-between;gap:9px;font-size:.29rem;color:#7695a6}.cfbgt4-total{font-weight:950;color:#7fe3ff}.cfbgt4-selected-label{margin:2px 0 0;font-size:.31rem;letter-spacing:.08em;text-transform:uppercase;color:#6f8fa2;font-weight:950}.cfbgt4-empty{padding:15px;border:1px solid rgba(130,153,168,.22);border-radius:14px;background:#0a151c;color:#aec1cb;font-size:.45rem}
@media(max-width:620px){.cfbgt4-title{font-size:1.31rem}.cfbgt4-sub{font-size:.53rem}.cfbgt4-date{width:100%;box-sizing:border-box}.cfbgt4-board{align-items:flex-start;flex-direction:column}.cfbgt4-board span{text-align:left}.cfbgt4-chip{min-width:154px;padding:8px 9px}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _game_id(game: Mapping[str, Any]) -> str:
    return _clean(game.get("game_id") or game.get("identity_key"))


def _requested_game() -> str:
    return base._scalar(st.query_params.get("cfbgt_game"))


def _select_game(games: list[Mapping[str, Any]], requested_id: str) -> Mapping[str, Any] | None:
    wanted = _clean(requested_id)
    if wanted:
        for game in games:
            if _game_id(game) == wanted:
                return game
    return games[0] if games else None


def _rail_href(game: Mapping[str, Any], selected_day: date) -> str:
    event_id = _game_id(game)
    if not event_id:
        return ""
    day = selected_day.isoformat()
    return "?" + urlencode(
        {
            "sport": "cfb",
            "market": "game-total",
            "date": day,
            "ks_sport": "College Football",
            "ks_cfb_market": "Game Total",
            "ks_cfb_game_total_date": day,
            "cfbgt_game": event_id,
        }
    )


def _rail_total(game: Mapping[str, Any]) -> str:
    quote = base._quote(game)
    value = quote.get("total_line")
    if value is None or value == "":
        return "O/U pending"
    return f"O/U {base._line(value)}"


def _rail_html(games: list[Mapping[str, Any]], selected: Mapping[str, Any], selected_day: date) -> str:
    selected_id = _game_id(selected)
    chips: list[str] = []
    for game in games:
        href = _rail_href(game, selected_day)
        if not href:
            continue
        away = base._name(game, "away")
        home = base._name(game, "home")
        active = " selected" if _game_id(game) == selected_id else ""
        chips.append(
            f'<a class="cfbgt4-chip{active}" href="{escape(href, quote=True)}" target="_self">'
            f'<span class="cfbgt4-match">{escape(away)} @ {escape(home)}</span>'
            f'<span class="cfbgt4-meta"><span class="cfbgt4-total">{escape(_rail_total(game))}</span>'
            f'<span>{escape(base._kickoff(game))}</span></span></a>'
        )
    return '<div class="cfbgt4-rail">' + "".join(chips) + "</div>"


def render_game_total_page1() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    requested = base._requested_date()
    try:
        payload = base._load_payload(requested)
    except Exception as exc:
        st.error(f"Kyre Sports API could not load the Game Total board: {type(exc).__name__}")
        return

    selected_day = base._selected_date(payload)
    games = [row for row in payload.get("games") or [] if isinstance(row, Mapping)]
    generated = _clean(payload.get("generated_at_utc")) or "Freshness pending"

    st.markdown(
        '<div class="cfbgt4-shell"><div class="cfbgt4-eyebrow">KYRE SPORTS AI • CFB GAME TOTALS</div>'
        '<div class="cfbgt4-title">Game Total Intelligence</div>'
        '<div class="cfbgt4-sub">Upcoming games only. Choose a matchup, read the market, then open the deeper analysis only when you need it.</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="cfbgt4-date">📅 {escape(selected_day.strftime("%A • %B %d, %Y"))} • Phoenix</div>',
        unsafe_allow_html=True,
    )
    picked = st.date_input("Slate date", value=selected_day, key="cfbgt4_date", label_visibility="collapsed")
    if picked != selected_day:
        st.query_params["date"] = picked.isoformat()
        st.query_params["ks_cfb_game_total_date"] = picked.isoformat()
        st.query_params.pop("cfbgt_game", None)
        st.rerun()

    st.markdown(
        '<div class="cfbgt4-board"><b>UPCOMING MATCHUPS</b>'
        f'<span>{len(games)} actionable games • started/final hidden • refreshed {escape(generated)}</span></div>',
        unsafe_allow_html=True,
    )
    if not games:
        st.markdown(
            '<div class="cfbgt4-empty">No upcoming CFB games remain on this slate. Started and completed games are hidden automatically.</div>',
            unsafe_allow_html=True,
        )
        return

    selected = _select_game(games, _requested_game())
    if selected is None:
        return
    st.markdown(_rail_html(games, selected, selected_day), unsafe_allow_html=True)
    st.markdown('<div class="cfbgt4-selected-label">Selected matchup</div>', unsafe_allow_html=True)
    prior._render_card(selected, 1, selected_day)


def render_cfb_hub(market: str, *args, **kwargs) -> None:
    del args, kwargs
    if market != MARKET:
        raise ValueError(f"CFB Game Total A-tier V4 cannot render market={market!r}")
    render_game_total_page1()


__all__ = [
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
