"""CFB Game Total Page 1 presentation polish R4.

Presentation-only successor over the frozen Daily Slate data engine. R3 retains
schedule/fallback ownership; this module owns compact navigation and card UX.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

import requests
import streamlit as st

import cfb_game_total_page1_daily_slate_v1 as base
from cfb_game_total_page1_daily_slate_market_v1 import build_game_market_context

MODEL_VERSION = "CFB GAME TOTAL PAGE1 POLISH R4"
ACTIVE_MARKER = "CFB_GAME_TOTAL_PAGE1_POLISH_R4_ACTIVE"
MARKET = base.MARKET
PHOENIX = base.PHOENIX
DATE_QUERY_KEY = base.DATE_QUERY_KEY
EVENT_QUERY_KEY = base.EVENT_QUERY_KEY
SELECTOR_SYNC_QUERY_KEY = base.SELECTOR_SYNC_QUERY_KEY
ROUTE_QUERY_SPORT = base.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = base.ROUTE_QUERY_MARKET
FILTER_OPTIONS = base.FILTER_OPTIONS
DEFAULT_FILTER = base.DEFAULT_FILTER
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False
NETWORK_CALLS_ADDED = 0

_clean = base._clean
_parse_phoenix = base._parse_phoenix
_status_state = base._status_state
_team = base._team
_quote_value = base._quote_value
_american = base._american
_query_day = base._query_day
_set_day = base._set_day
_load_day = base._load_day
_load_slate_cached_20 = base._load_slate_cached_20
_conference_options = base._conference_options
_team_title = base._team_title
_status_line = base._status_line
resolve_effective_slate_date = base.resolve_effective_slate_date
filter_slate_games = base.filter_slate_games
group_slate_games = base.group_slate_games
next_upcoming_window = base.next_upcoming_window
view_game_href = base.view_game_href

PAGE_CSS = "<style id=\"cfb-game-total-page1-polish-r4\">\n" + (
    Path(__file__).with_name("cfb_game_total_page1_polish_r4.css").read_text(encoding="utf-8")
) + "\n</style>"


def card_view_model(game: Mapping[str, Any]) -> dict[str, Any]:
    game_id = _clean(game.get("event_id"))
    away = _team(game, "away")
    home = _team(game, "home")
    market = build_game_market_context(game_id, list(game.get("market_observations") or []))
    current = market["current"]
    opening = market["opening"]
    total_value = _quote_value(current["game_total"])
    opening_total_value = _quote_value(opening["game_total"])
    spread_value = _quote_value(current["spread"])
    home_ml = _quote_value(current["moneyline_home"])
    away_ml = _quote_value(current["moneyline_away"])
    away_moneyline = _american(away_ml)
    home_moneyline = _american(home_ml)
    spread = "Unavailable" if spread_value is None else f"{spread_value:+g}"
    total = "Unavailable" if total_value is None else f"O/U {total_value:g}"
    opening_total = "Unavailable" if opening_total_value is None else f"{opening_total_value:g}"
    total_move = "Unavailable"
    if opening_total_value is not None and total_value is not None:
        total_move = f"{total_value - opening_total_value:+.1f}"

    weather = game.get("weather") if isinstance(game.get("weather"), Mapping) else {}
    bits: list[str] = []
    if weather:
        temp = weather.get("temperature_f")
        if temp is not None:
            try: bits.append(f"{float(temp):g}°")
            except (TypeError, ValueError): pass
        if _clean(weather.get("summary")): bits.append(_clean(weather.get("summary")))
        wind = weather.get("wind_mph")
        if wind is not None:
            try: bits.append(f"Wind {float(wind):g} mph")
            except (TypeError, ValueError): pass
    weather_text = " • ".join(bits) or "—"
    availability = game.get("availability") if isinstance(game.get("availability"), Mapping) else {}
    availability_text = _clean(availability.get("summary")) if availability.get("verified") is True and _clean(availability.get("summary")) else "Unavailable"
    return {
        "event_id": game_id,
        "away_id": _clean(away.get("id")) or "Unavailable",
        "home_id": _clean(home.get("id")) or "Unavailable",
        "away_logo": _clean(away.get("logo")), "home_logo": _clean(home.get("logo")),
        "away_conference": _clean(away.get("conference")), "home_conference": _clean(home.get("conference")),
        "broadcast": _clean(game.get("broadcast")) or "—", "weather": weather_text,
        "venue": _clean(game.get("venue")) or "Unavailable", "city": _clean(game.get("city")) or "—",
        "away_moneyline": away_moneyline, "home_moneyline": home_moneyline,
        "spread": spread, "total": total, "opening_total": opening_total, "total_move": total_move,
        "availability": availability_text,
        "market_confidence": current["game_total"].get("confidence") or "Unavailable",
    }


def date_nav_days(selected_day: date) -> list[date]:
    return [selected_day + timedelta(days=offset) for offset in range(-3, 4)]


def date_nav_href(day: date) -> str:
    return "?" + urlencode({ROUTE_QUERY_SPORT: "College Football", ROUTE_QUERY_MARKET: MARKET, DATE_QUERY_KEY: day.isoformat()})


def _render_date_navigation(selected_day: date) -> None:
    today = datetime.now(PHOENIX).date()
    pills: list[str] = []
    for nav_day in date_nav_days(selected_day):
        active = " active" if nav_day == selected_day else ""
        tag = "TODAY" if nav_day == today else ("SELECTED" if nav_day == selected_day else "")
        pills.append(
            f'<a class="cfbgt-date-pill{active}" href="{escape(date_nav_href(nav_day), quote=True)}" target="_self">'
            f'<span class="dow">{escape(nav_day.strftime("%a"))}</span><span class="day">{nav_day.day}</span>'
            f'<span class="tag">{tag or "&nbsp;"}</span></a>'
        )
    st.markdown('<div class="cfbgt-date-strip">' + "".join(pills) + '</div>', unsafe_allow_html=True)
    holder = st.popover("📅 Jump to date", use_container_width=True) if hasattr(st, "popover") else st.expander("📅 Jump to date", expanded=False)
    with holder:
        jump_day = st.date_input("Jump to date", value=selected_day, key=f"cfbgt_jump_{selected_day.isoformat()}")
        if jump_day != selected_day:
            _set_day(jump_day); st.rerun()


def _render_game_card(game: Mapping[str, Any], selected_day: date) -> None:
    away, home = _team(game, "away"), _team(game, "home")
    card = card_view_model(game)
    status = _status_state(game)
    score = ""
    if status in {"Live", "Halftime", "Final"}:
        score = f" • {escape(_clean(away.get('score')) or '—')}–{escape(_clean(home.get('score')) or '—')}"
    away_logo = f'<img class="cfbgt-team-logo" src="{escape(card["away_logo"], quote=True)}" alt="" loading="lazy">' if card["away_logo"] else '<span></span>'
    home_logo = f'<img class="cfbgt-team-logo" src="{escape(card["home_logo"], quote=True)}" alt="" loading="lazy">' if card["home_logo"] else '<span></span>'
    away_sub = " • ".join(x for x in (card["away_conference"], _clean(away.get("record"))) if x) or "College Football"
    home_sub = " • ".join(x for x in (card["home_conference"], _clean(home.get("record"))) if x) or "College Football"
    move_display = "No verified move" if card["total_move"] == "Unavailable" else f'{card["total_move"]} pts'
    with st.container(border=True):
        st.markdown(
            '<div class="cfbgt-matchup"><div class="cfbgt-team-row">'
            f'{away_logo}<div><div class="cfbgt-team-name">{escape(_team_title(away))}</div><div class="cfbgt-team-sub">{escape(away_sub)}</div></div><span class="cfbgt-team-id">ID {escape(card["away_id"])}</span></div>'
            '<div class="cfbgt-at">at</div><div class="cfbgt-team-row">'
            f'{home_logo}<div><div class="cfbgt-team-name">{escape(_team_title(home))}</div><div class="cfbgt-team-sub">{escape(home_sub)}</div></div><span class="cfbgt-team-id">ID {escape(card["home_id"])}</span></div></div>'
            f'<div class="cfbgt-card-meta"><strong>{escape(_status_line(game))}</strong>{score} &nbsp;•&nbsp; 📺 {escape(card["broadcast"])}</div>'
            f'<div class="cfbgt-detail-row"><span>🏟️ {escape(card["venue"])} • {escape(card["city"])}</span><span>🌤️ {escape(card["weather"])}</span></div>'
            f'<div class="cfbgt-total-focus"><div><div class="cfbgt-total-label">Game Total</div><div class="cfbgt-total-number">{escape(card["total"])}</div></div><div class="cfbgt-total-move">Open <strong>{escape(card["opening_total"])}</strong><br>Move <strong>{escape(move_display)}</strong></div></div>'
            '<div class="cfbgt-market-grid">'
            f'<div class="cfbgt-market-cell"><span class="label">Away ML</span><span class="value">{escape(card["away_moneyline"])}</span></div>'
            f'<div class="cfbgt-market-cell"><span class="label">Home ML</span><span class="value">{escape(card["home_moneyline"])}</span></div>'
            f'<div class="cfbgt-market-cell"><span class="label">Home Spread</span><span class="value">{escape(card["spread"])}</span></div></div>', unsafe_allow_html=True)
        with st.expander("More ↓", expanded=False):
            st.markdown(f"**Event ID:** {card['event_id'] or 'Unavailable'}")
            st.markdown(f"**Team IDs:** Away {card['away_id']} • Home {card['home_id']}")
            st.markdown(f"**Venue:** {card['venue']} • {card['city']}")
            st.markdown(f"**Weather:** {card['weather']}")
            st.markdown(f"**Broadcast:** {card['broadcast']}")
            st.markdown(f"**Subdivision:** {', '.join(game.get('subdivisions') or []) or '—'}")
            st.markdown(f"**Availability:** {card['availability']}")
            st.markdown(f"**Game Total:** Opening {card['opening_total']} • Current {card['total']} • Move {move_display}")
            st.markdown(f"**Market confidence:** {card['market_confidence']}")
        href = view_game_href(game, selected_day)
        if href: st.markdown(f'<div class="cfbgt-view"><a href="{escape(href, quote=True)}" target="_self">View Game →</a></div>', unsafe_allow_html=True)
        else: st.caption("View Game unavailable — exact game identity is missing")


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    del section_header, status_info, team_logo, h
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    requested_day = _query_day()
    effective_day, payload = resolve_effective_slate_date(requested_day, _load_day)
    if effective_day != requested_day: _set_day(effective_day)
    games = list(payload.get("games") or [])
    if any(_status_state(g) in {"Live", "Halftime"} for g in games if isinstance(g, Mapping)):
        try:
            live_payload = dict(_load_slate_cached_20(effective_day.isoformat()))
            if live_payload.get("games"): games = list(live_payload["games"])
        except (requests.RequestException, ValueError, TypeError): pass
    live_count = sum(_status_state(g) in {"Live", "Halftime"} for g in games if isinstance(g, Mapping))
    ranked_count = sum(any(_team(g, s).get("rank") not in (None, "") for s in ("away", "home")) for g in games if isinstance(g, Mapping))
    slate_label = "Saturday Slate" if effective_day.weekday() == 5 else f"{effective_day.strftime('%A')} Slate"
    st.markdown('<div class="cfbgt-hero"><div class="cfbgt-hero-kicker">🏈 College Football • Totals Board</div><h2>CFB GAME TOTALS</h2>'
                f'<div class="cfbgt-hero-sub">{escape(slate_label)} • {escape(effective_day.strftime("%B %d, %Y"))} • Phoenix Time</div><div class="cfbgt-hero-stats">'
                f'<span class="cfbgt-stat"><strong>{len(games)}</strong> Games</span><span class="cfbgt-stat"><strong>{ranked_count}</strong> Ranked Matchups</span><span class="cfbgt-stat"><strong>{live_count}</strong> Live</span><span class="cfbgt-stat">FBS + FCS</span></div></div>', unsafe_allow_html=True)
    _render_date_navigation(effective_day)
    st.markdown(f'<div class="cfbgt-date-chip">{escape(effective_day.strftime("%A • %B %d, %Y"))}</div>', unsafe_allow_html=True)
    if payload.get("auto_advanced"): st.caption(f"No games on {requested_day.isoformat()}; showing the next Phoenix date with games.")
    search = st.text_input("Search team", key="cfbgt_daily_search", placeholder="Search team")
    if hasattr(st, "segmented_control"):
        selected_filter = st.segmented_control("Slate Filter", FILTER_OPTIONS, default=DEFAULT_FILTER, key="cfbgt_daily_filter") or DEFAULT_FILTER
    else:
        selected_filter = st.radio("Slate Filter", FILTER_OPTIONS, index=0, horizontal=True, key="cfbgt_daily_filter")
    conference = ""
    if selected_filter == "Conference":
        choice = st.selectbox("Conference", _conference_options(games), key="cfbgt_daily_conference")
        conference = "" if choice == "Select conference" else choice
    visible = filter_slate_games(games, search=search, filter_name=selected_filter, conference=conference)
    if not games and payload.get("auto_advance_exhausted"): st.info("No upcoming games found"); return
    if not visible: st.info("No games match the current Page 1 filters."); return
    groups = group_slate_games(visible, now_phoenix=datetime.now(PHOENIX)); next_window = next_upcoming_window(groups)
    for section_name, section_games in groups.items():
        if not section_games: continue
        label = f"{section_name} • Next Up" if section_name == next_window else section_name
        with st.expander(label, expanded=(section_name == "Live Games" or section_name == next_window)):
            for game in section_games: _render_game_card(game, effective_day)


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET: raise ValueError(f"R4 Page 1 received unsupported market: {market}")
    render_game_total_hub(section_header, status_info, team_logo, h)

__all__ = ["ACTIVE_MARKER", "MARKET", "MODEL_VERSION", "PAGE_CSS", "SPORTSBOOK_PROJECTION_INFLUENCE", "card_view_model", "date_nav_days", "date_nav_href", "render_cfb_hub", "render_game_total_hub"]

_MISSING = object()
_PRESENTATION_ATTRS = (
    "PAGE_CSS", "card_view_model", "date_nav_days", "date_nav_href",
    "_render_date_navigation", "_render_game_card", "render_game_total_hub", "render_cfb_hub",
)
_HELPER_ATTRS = (
    "_clean", "_parse_phoenix", "_status_state", "_team", "_quote_value", "_american",
    "_query_day", "_set_day", "_load_day", "_load_slate_cached_20", "_conference_options",
    "_team_title", "_status_line", "resolve_effective_slate_date", "filter_slate_games",
    "group_slate_games", "next_upcoming_window", "view_game_href",
)


def install_into(target):
    """Install R4 presentation onto one current/fresh R3 Daily Slate module."""
    global_vars = globals()
    for name in _HELPER_ATTRS:
        global_vars[name] = getattr(target, name)
    originals = {name: getattr(target, name, _MISSING) for name in _PRESENTATION_ATTRS}
    for name in _PRESENTATION_ATTRS:
        setattr(target, name, global_vars[name])
    return originals


def restore_from(target, originals) -> None:
    for name, value in originals.items():
        if value is _MISSING:
            if hasattr(target, name):
                delattr(target, name)
        else:
            setattr(target, name, value)
