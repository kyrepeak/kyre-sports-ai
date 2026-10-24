"""CFB Game Total Page 1 A-tier V5 — premium compact logo matchup rail."""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_page1_atier_v1 as base
import cfb_game_total_page1_atier_v3 as card
import cfb_game_total_page1_atier_v4 as prior

MODEL_VERSION = "CFB GAME TOTAL PAGE1 A-TIER V5 • PREMIUM LOGO MATCHUP RAIL R1"
MARKET = "Game Total"
PAGE1_ENDPOINT = prior.PAGE1_ENDPOINT
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False

_CSS = card._CSS + r"""
<style>
.cfbgt5-shell{margin:2px 0 8px}.cfbgt5-eyebrow{font-size:.53rem;letter-spacing:.14em;font-weight:950;color:#68d9ff;text-transform:uppercase}.cfbgt5-title{font-size:1.55rem;line-height:1.02;font-weight:1000;color:#f7fbff;margin:4px 0}.cfbgt5-sub{font-size:.58rem;color:#8299aa;max-width:700px;line-height:1.45}.cfbgt5-date{display:inline-flex;align-items:center;min-height:31px;border:1px solid rgba(95,190,233,.20);background:#081925;border-radius:10px;padding:0 10px;font-size:.38rem;font-weight:850;color:#b8d7e6;white-space:nowrap}.cfbgt5-board{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 10px;border:1px solid rgba(87,193,238,.20);border-radius:12px;background:linear-gradient(145deg,#071923,#081d2a);margin:8px 0}.cfbgt5-board b{font-size:.40rem;color:#7ddfff;letter-spacing:.07em;text-transform:uppercase}.cfbgt5-board span{font-size:.31rem;color:#7897a8;text-align:right}.cfbgt5-rail{display:flex;flex-wrap:nowrap;gap:8px;overflow-x:auto;overflow-y:hidden;white-space:nowrap;padding:3px 22px 10px 1px;scrollbar-width:thin;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch}.cfbgt5-chip{display:inline-flex;flex:0 0 176px;width:176px;height:78px;box-sizing:border-box;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:9px 10px;border:1px solid rgba(94,160,193,.22);border-radius:14px;background:linear-gradient(145deg,#071722,#081b27);color:#d7edf6!important;text-decoration:none!important;scroll-snap-align:start;box-shadow:0 8px 18px rgba(0,0,0,.14);transition:border-color .16s ease,background .16s ease,transform .16s ease}.cfbgt5-chip:hover{border-color:rgba(89,206,255,.48);background:#092130;transform:translateY(-1px)}.cfbgt5-chip.selected{border-color:#68d9ff;background:linear-gradient(145deg,#0a2434,#0b2b40);box-shadow:0 0 0 1px rgba(104,217,255,.12),0 8px 22px rgba(0,0,0,.20)}.cfbgt5-matchrow{display:flex;align-items:center;justify-content:center;gap:6px;width:100%;min-width:0}.cfbgt5-team-logo{position:relative;width:25px;height:25px;flex:0 0 25px;border-radius:50%;display:grid;place-items:center;background:#0a2332;border:1px solid rgba(103,197,238,.24);overflow:hidden;color:#7ddfff;font-size:.26rem;font-weight:1000}.cfbgt5-team-logo img{position:absolute;inset:1px;width:23px;height:23px;object-fit:contain;border-radius:50%;background:#07141f}.cfbgt5-abbr{font-size:.43rem;line-height:1;font-weight:1000;color:#f7fbff;letter-spacing:.02em;overflow:hidden;text-overflow:ellipsis;max-width:42px}.cfbgt5-at{font-size:.34rem;font-weight:900;color:#66889a}.cfbgt5-time{font-size:.30rem;line-height:1;font-weight:850;color:#86a7b7;letter-spacing:.025em}.cfbgt5-selected-label{margin:2px 0 0;font-size:.31rem;letter-spacing:.08em;text-transform:uppercase;color:#6f8fa2;font-weight:950}.cfbgt5-empty{padding:15px;border:1px solid rgba(130,153,168,.22);border-radius:14px;background:#0a151c;color:#aec1cb;font-size:.45rem}
@media(max-width:620px){.cfbgt5-title{font-size:1.31rem}.cfbgt5-sub{font-size:.53rem}.cfbgt5-date{width:100%;box-sizing:border-box}.cfbgt5-board{align-items:flex-start;flex-direction:column}.cfbgt5-board span{text-align:left}.cfbgt5-rail{padding-right:28px}.cfbgt5-chip{flex-basis:176px;width:176px;height:78px}.cfbgt5-team-logo{width:24px;height:24px;flex-basis:24px}.cfbgt5-team-logo img{width:22px;height:22px}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _identity(game: Mapping[str, Any], side: str) -> Mapping[str, Any]:
    identities = game.get("team_identity") if isinstance(game.get("team_identity"), Mapping) else {}
    value = identities.get(side) if isinstance(identities.get(side), Mapping) else {}
    return value


def _abbr(game: Mapping[str, Any], side: str) -> str:
    for key in (
        f"{side}_team_abbreviation",
        f"{side}_abbreviation",
        f"{side}_team_abbr",
        f"{side}_abbr",
    ):
        value = _clean(game.get(key))
        if value:
            return value.upper()[:6]
    identity = _identity(game, side)
    fallback = _clean(identity.get("fallback_monogram"))
    if fallback:
        return fallback.upper()[:6]
    name = base._name(game, side)
    initials = "".join(part[:1] for part in name.replace("-", " ").split()[:4]).upper()
    return initials or side[:1].upper()


def _team_logo(game: Mapping[str, Any], side: str) -> str:
    identity = _identity(game, side)
    team_name = base._name(game, side)
    fallback = _abbr(game, side)
    url = _clean(identity.get("logo_url"))
    img = (
        f'<img src="{escape(url, quote=True)}" alt="{escape(team_name, quote=True)} logo" '
        'loading="lazy" onerror="this.style.display=\'none\'">'
        if url else ""
    )
    return f'<span class="cfbgt5-team-logo"><span>{escape(fallback)}</span>{img}</span>'


def _kickoff_time(game: Mapping[str, Any]) -> str:
    text = _clean(game.get("kickoff_iso") or game.get("start_time_utc"))
    if not text:
        return "Time TBD"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return "Time TBD"
        return parsed.astimezone(base._PHOENIX).strftime("%-I:%M %p")
    except (TypeError, ValueError):
        return "Time TBD"


def _rail_html(games: list[Mapping[str, Any]], selected: Mapping[str, Any], selected_day) -> str:
    selected_id = prior._game_id(selected)
    chips: list[str] = []
    for game in games:
        href = prior._rail_href(game, selected_day)
        if not href:
            continue
        away = base._name(game, "away")
        home = base._name(game, "home")
        away_abbr = _abbr(game, "away")
        home_abbr = _abbr(game, "home")
        kickoff = _kickoff_time(game)
        active = " selected" if prior._game_id(game) == selected_id else ""
        label = f"{away} at {home}, {kickoff}"
        chips.append(
            f'<a class="cfbgt5-chip{active}" href="{escape(href, quote=True)}" target="_self" '
            f'aria-label="{escape(label, quote=True)}" title="{escape(label, quote=True)}">'
            '<span class="cfbgt5-matchrow">'
            f'{_team_logo(game, "away")}<span class="cfbgt5-abbr">{escape(away_abbr)}</span>'
            '<span class="cfbgt5-at"> @ </span>'
            f'<span class="cfbgt5-abbr">{escape(home_abbr)}</span>{_team_logo(game, "home")}'
            '</span>'
            f'<span class="cfbgt5-time">{escape(kickoff)}</span>'
            '</a>'
        )
    return '<div class="cfbgt5-rail">' + "".join(chips) + "</div>"


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
        '<div class="cfbgt5-shell"><div class="cfbgt5-eyebrow">KYRE SPORTS AI • CFB GAME TOTALS</div>'
        '<div class="cfbgt5-title">Game Total Intelligence</div>'
        '<div class="cfbgt5-sub">Upcoming games only. Swipe the matchup rail, choose a game, then use the full card below for the actual analytics.</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="cfbgt5-date">📅 {escape(selected_day.strftime("%A • %B %d, %Y"))} • Phoenix</div>',
        unsafe_allow_html=True,
    )
    picked = st.date_input("Slate date", value=selected_day, key="cfbgt5_date", label_visibility="collapsed")
    if picked != selected_day:
        st.query_params["date"] = picked.isoformat()
        st.query_params["ks_cfb_game_total_date"] = picked.isoformat()
        st.query_params.pop("cfbgt_game", None)
        st.rerun()

    st.markdown(
        '<div class="cfbgt5-board"><b>UPCOMING MATCHUPS</b>'
        f'<span>{len(games)} actionable games • started/final hidden • refreshed {escape(generated)}</span></div>',
        unsafe_allow_html=True,
    )
    if not games:
        st.markdown(
            '<div class="cfbgt5-empty">No upcoming CFB games remain on this slate. Started and completed games are hidden automatically.</div>',
            unsafe_allow_html=True,
        )
        return

    selected = prior._select_game(games, prior._requested_game())
    if selected is None:
        return
    st.markdown(_rail_html(games, selected, selected_day), unsafe_allow_html=True)
    st.markdown('<div class="cfbgt5-selected-label">Selected matchup</div>', unsafe_allow_html=True)
    card._render_card(selected, 1, selected_day)


def render_cfb_hub(market: str, *args, **kwargs) -> None:
    del args, kwargs
    if market != MARKET:
        raise ValueError(f"CFB Game Total A-tier V5 cannot render market={market!r}")
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
