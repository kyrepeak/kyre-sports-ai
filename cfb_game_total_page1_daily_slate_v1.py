"""CFB Game Total Page 1 — mobile-first Daily Slate V1.

All verified FBS + FCS games for one America/Phoenix calendar date, organized
for fast scanning with truthful missing-data states and explicit selected-game
handoff. This presentation layer does not modify any sports model behavior.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
import os
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
import streamlit as st

from cfb_game_total_page1_daily_slate_market_v1 import build_game_market_context

MODEL_VERSION = "CFB GAME TOTAL PAGE1 DAILY SLATE V1"
MARKET = "Game Total"
ACTIVE_MARKER = "CFB_GAME_TOTAL_PAGE1_DAILY_SLATE_V1_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False

PHOENIX = ZoneInfo("America/Phoenix")
MAX_FORWARD_SEARCH_DAYS = 21
DEFAULT_FILTER = "All Games"
FILTER_OPTIONS = ("All Games", "Live", "Upcoming", "Ranked", "FBS", "FCS", "Conference")
WINDOW_ORDER = ("Early Games", "Afternoon Games", "Evening Games", "Late Games")

API_BASE_ENV = "KYRE_SPORTS_API_BASE_URL"
API_BASE_DEFAULT = "https://kyre-sports-api.onrender.com"
DAILY_SLATE_ENDPOINT = "/api/v1/cfb/daily-slate"
DATE_QUERY_KEY = "ks_cfb_game_total_date"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
SELECTOR_SYNC_QUERY_KEY = "ks_cfb_game_total_selector_sync"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"

PAGE_CSS = r"""
<style id="cfb-game-total-page1-daily-slate-v1">
.cfbgt-daily-head{max-width:900px;margin:6px auto 12px;padding:16px 18px;border:1px solid rgba(84,190,255,.30);border-radius:18px;background:linear-gradient(145deg,#071a27,#07131f)}
.cfbgt-daily-head h2{margin:0;color:#f7fbff;font-size:24px;line-height:1.15}.cfbgt-daily-head p{margin:6px 0 0;color:#91aabd;font-size:12px;font-weight:700}
.cfbgt-date-chip{max-width:900px;margin:0 auto 10px;text-align:center;color:#86dcff;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}
.cfbgt-card-top{font-size:15px;font-weight:950;color:#f5fbff;line-height:1.35}.cfbgt-card-meta{margin-top:5px;color:#a7bdcc;font-size:11px;line-height:1.45}.cfbgt-market{margin-top:8px;padding:8px 10px;border-radius:10px;background:rgba(55,139,184,.10);font-size:11px;color:#d5e6f1}.cfbgt-status-live{color:#63f2b4;font-weight:950}.cfbgt-status-final{color:#9daeba;font-weight:900}.cfbgt-unavailable{color:#7f929f}.cfbgt-view a{display:block;text-align:center;padding:9px 12px;margin-top:7px;border:1px solid rgba(89,199,255,.45);border-radius:11px;color:#74dcff!important;text-decoration:none!important;font-weight:950;font-size:12px}.cfbgt-view a:hover{background:rgba(67,185,244,.10)}
@media(max-width:640px){.cfbgt-daily-head{padding:13px 14px;border-radius:15px;margin-top:4px}.cfbgt-daily-head h2{font-size:20px}.cfbgt-daily-head p{font-size:10px}.cfbgt-card-top{font-size:14px}.cfbgt-card-meta,.cfbgt-market{font-size:10px}.cfbgt-view a{min-height:42px;display:flex;align-items:center;justify-content:center}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _parse_phoenix(value: Any) -> datetime:
    text = _clean(value)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=PHOENIX)
    return parsed.astimezone(PHOENIX)


def resolve_effective_slate_date(
    requested_day: date,
    loader: Callable[[date], Mapping[str, Any]],
    *,
    max_forward_days: int = MAX_FORWARD_SEARCH_DAYS,
) -> tuple[date, dict[str, Any]]:
    initial = dict(loader(requested_day) or {})
    if int(initial.get("game_count") or len(initial.get("games") or [])) > 0:
        initial["auto_advanced"] = False
        return requested_day, initial

    for offset in range(1, max(0, int(max_forward_days)) + 1):
        candidate = requested_day + timedelta(days=offset)
        payload = dict(loader(candidate) or {})
        if int(payload.get("game_count") or len(payload.get("games") or [])) > 0:
            payload["auto_advanced"] = True
            payload["auto_advanced_from"] = requested_day.isoformat()
            return candidate, payload

    initial["auto_advanced"] = False
    initial["auto_advance_exhausted"] = True
    return requested_day, initial


def _status_state(game: Mapping[str, Any]) -> str:
    status = game.get("status") if isinstance(game.get("status"), Mapping) else {}
    return _clean(status.get("state") or "Scheduled")


def _team(game: Mapping[str, Any], side: str) -> Mapping[str, Any]:
    value = game.get(side)
    return value if isinstance(value, Mapping) else {}


def filter_slate_games(
    games: Sequence[Mapping[str, Any]],
    *,
    search: str = "",
    filter_name: str = DEFAULT_FILTER,
    conference: str = "",
) -> list[dict[str, Any]]:
    search_key = _clean(search).casefold()
    filter_key = _clean(filter_name) or DEFAULT_FILTER
    conference_key = _clean(conference).casefold()
    visible: list[dict[str, Any]] = []

    for raw in games:
        if not isinstance(raw, Mapping):
            continue
        game = dict(raw)
        away = _team(game, "away")
        home = _team(game, "home")
        names = f"{_clean(away.get('name'))} {_clean(home.get('name'))}".casefold()
        if search_key and search_key not in names:
            continue

        state = _status_state(game)
        subdivisions = {_clean(item).upper() for item in (game.get("subdivisions") or [])}
        ranked = any(
            side.get("rank") not in (None, "")
            for side in (away, home)
        )
        conferences = {_clean(away.get("conference")).casefold(), _clean(home.get("conference")).casefold()}

        keep = True
        if filter_key == "Live":
            keep = state in {"Live", "Halftime"}
        elif filter_key == "Upcoming":
            keep = state not in {"Live", "Halftime", "Final"}
        elif filter_key == "Ranked":
            keep = ranked
        elif filter_key == "FBS":
            keep = "FBS" in subdivisions
        elif filter_key == "FCS":
            keep = "FCS" in subdivisions
        elif filter_key == "Conference":
            keep = bool(conference_key) and conference_key in conferences
        if keep:
            visible.append(game)
    return visible


def kickoff_window(game: Mapping[str, Any]) -> str:
    local = _parse_phoenix(game.get("kickoff_phoenix"))
    hour = local.hour
    if hour < 12:
        return "Early"
    if hour < 17:
        return "Afternoon"
    if hour < 21:
        return "Evening"
    return "Late"


def group_slate_games(
    games: Sequence[Mapping[str, Any]], *, now_phoenix: datetime
) -> dict[str, list[dict[str, Any]]]:
    del now_phoenix  # State is authoritative; time is retained for stable future extension.
    groups: dict[str, list[dict[str, Any]]] = {
        "Live Games": [],
        "Early Games": [],
        "Afternoon Games": [],
        "Evening Games": [],
        "Late Games": [],
        "Completed Games": [],
    }
    ordered = sorted(
        (dict(game) for game in games if isinstance(game, Mapping)),
        key=lambda game: (_parse_phoenix(game.get("kickoff_phoenix")), _clean(game.get("event_id"))),
    )
    for game in ordered:
        state = _status_state(game)
        if state == "Final":
            groups["Completed Games"].append(game)
        elif state in {"Live", "Halftime"}:
            groups["Live Games"].append(game)
        else:
            groups[f"{kickoff_window(game)} Games"].append(game)
    return groups


def next_upcoming_window(groups: Mapping[str, Sequence[Mapping[str, Any]]]) -> str | None:
    for name in WINDOW_ORDER:
        if groups.get(name):
            return name
    return None


def view_game_href(game: Mapping[str, Any], selected_day: date) -> str:
    event_id = _clean(game.get("event_id"))
    if not event_id:
        return ""
    params = {
        ROUTE_QUERY_SPORT: "College Football",
        ROUTE_QUERY_MARKET: MARKET,
        DATE_QUERY_KEY: selected_day.isoformat(),
        EVENT_QUERY_KEY: event_id,
        SELECTOR_SYNC_QUERY_KEY: event_id,
    }
    return "?" + urlencode(params)


def _quote_value(result: Mapping[str, Any]) -> float | None:
    selected = result.get("selected_quote") if isinstance(result.get("selected_quote"), Mapping) else {}
    value = selected.get("value")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _american(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    number = int(value) if float(value).is_integer() else value
    return f"+{number}" if value > 0 else str(number)


def card_view_model(game: Mapping[str, Any]) -> dict[str, Any]:
    game_id = _clean(game.get("event_id"))
    market = build_game_market_context(game_id, list(game.get("market_observations") or []))
    current = market["current"]
    total_value = _quote_value(current["game_total"])
    spread_value = _quote_value(current["spread"])
    home_ml = _quote_value(current["moneyline_home"])
    away_ml = _quote_value(current["moneyline_away"])

    if home_ml is None and away_ml is None:
        moneyline = "Unavailable"
    else:
        moneyline = f"A {_american(away_ml)} • H {_american(home_ml)}"
    spread = "Unavailable" if spread_value is None else f"{spread_value:+g}"
    total = "Unavailable" if total_value is None else f"O/U {total_value:g}"

    weather = game.get("weather") if isinstance(game.get("weather"), Mapping) else {}
    if weather:
        bits: list[str] = []
        temp = weather.get("temperature_f")
        if temp is not None:
            try:
                bits.append(f"{float(temp):g}°")
            except (TypeError, ValueError):
                pass
        if _clean(weather.get("summary")):
            bits.append(_clean(weather.get("summary")))
        wind = weather.get("wind_mph")
        if wind is not None:
            try:
                bits.append(f"Wind {float(wind):g} mph")
            except (TypeError, ValueError):
                pass
        weather_text = " • ".join(bits) or "—"
    else:
        weather_text = "—"

    availability = game.get("availability") if isinstance(game.get("availability"), Mapping) else {}
    availability_text = (
        _clean(availability.get("summary"))
        if availability.get("verified") is True and _clean(availability.get("summary"))
        else "Unavailable"
    )
    return {
        "broadcast": _clean(game.get("broadcast")) or "—",
        "weather": weather_text,
        "venue": _clean(game.get("venue")) or "Unavailable",
        "city": _clean(game.get("city")) or "—",
        "moneyline": moneyline,
        "spread": spread,
        "total": total,
        "availability": availability_text,
        "market_confidence": current["game_total"].get("confidence") or "Unavailable",
        "market_context": market,
    }


def _api_base() -> str:
    return _clean(os.environ.get(API_BASE_ENV)) or API_BASE_DEFAULT


@st.cache_data(ttl=60, show_spinner=False)
def _load_slate_cached_60(day_iso: str) -> dict[str, Any]:
    response = requests.get(
        f"{_api_base().rstrip('/')}{DAILY_SLATE_ENDPOINT}",
        params={"game_date": day_iso},
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Daily Slate API returned a non-object payload")
    return payload


@st.cache_data(ttl=20, show_spinner=False)
def _load_slate_cached_20(day_iso: str) -> dict[str, Any]:
    response = requests.get(
        f"{_api_base().rstrip('/')}{DAILY_SLATE_ENDPOINT}",
        params={"game_date": day_iso},
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Daily Slate API returned a non-object payload")
    return payload


def _load_day(day: date) -> dict[str, Any]:
    try:
        return dict(_load_slate_cached_60(day.isoformat()))
    except (requests.RequestException, ValueError, TypeError):
        return {"requested_phoenix_date": day.isoformat(), "game_count": 0, "games": [], "api_unavailable": True}


def _query_day() -> date:
    raw: Any = None
    try:
        raw = st.query_params.get(DATE_QUERY_KEY)
    except Exception:
        pass
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else None
    try:
        return date.fromisoformat(_clean(raw)) if raw else datetime.now(PHOENIX).date()
    except ValueError:
        return datetime.now(PHOENIX).date()


def _set_day(day: date) -> None:
    try:
        st.query_params[DATE_QUERY_KEY] = day.isoformat()
    except Exception:
        pass


def _conference_options(games: Sequence[Mapping[str, Any]]) -> list[str]:
    values: set[str] = set()
    for game in games:
        for side in ("away", "home"):
            conference = _clean(_team(game, side).get("conference"))
            if conference:
                values.add(conference)
    return ["Select conference"] + sorted(values, key=str.casefold)


def _team_title(team: Mapping[str, Any]) -> str:
    rank = team.get("rank")
    prefix = f"#{rank} " if rank not in (None, "") else ""
    record = f" ({_clean(team.get('record'))})" if _clean(team.get("record")) else ""
    return f"{prefix}{_clean(team.get('name')) or 'Team'}{record}"


def _status_line(game: Mapping[str, Any]) -> str:
    status = game.get("status") if isinstance(game.get("status"), Mapping) else {}
    state = _clean(status.get("state") or "Scheduled")
    if state == "Live":
        period = status.get("period")
        clock = _clean(status.get("clock"))
        parts = ["LIVE"]
        if period:
            parts.append(f"Q{period}")
        if clock:
            parts.append(clock)
        return " • ".join(parts)
    if state == "Halftime":
        return "HALFTIME"
    if state == "Final":
        return "FINAL"
    try:
        return _parse_phoenix(game.get("kickoff_phoenix")).strftime("%-I:%M %p MST")
    except Exception:
        return "TBD"


def _render_game_card(game: Mapping[str, Any], selected_day: date) -> None:
    away = _team(game, "away")
    home = _team(game, "home")
    card = card_view_model(game)
    status = _status_state(game)
    score = ""
    if status in {"Live", "Halftime", "Final"}:
        away_score = _clean(away.get("score")) or "—"
        home_score = _clean(home.get("score")) or "—"
        score = f" • {escape(away_score)}–{escape(home_score)}"

    with st.container(border=True):
        st.markdown(
            '<div class="cfbgt-card-top">'
            f'{escape(_team_title(away))} &nbsp; @ &nbsp; {escape(_team_title(home))}'
            '</div>'
            '<div class="cfbgt-card-meta">'
            f'{escape(_status_line(game))}{score} &nbsp;•&nbsp; 📺 {escape(card["broadcast"])}'
            f' &nbsp;•&nbsp; 🌤 {escape(card["weather"])}'
            '</div>'
            '<div class="cfbgt-market">'
            f'ML: {escape(card["moneyline"])} &nbsp;•&nbsp; Spread: {escape(card["spread"])}'
            f' &nbsp;•&nbsp; Total: {escape(card["total"])}'
            '</div>',
            unsafe_allow_html=True,
        )
        with st.expander("More ↓", expanded=False):
            st.markdown(f"**Venue:** {card['venue']} • {card['city']}")
            st.markdown(f"**Weather:** {card['weather']}")
            st.markdown(f"**Broadcast:** {card['broadcast']}")
            st.markdown(f"**Subdivision:** {', '.join(game.get('subdivisions') or []) or '—'}")
            st.markdown(f"**Availability:** {card['availability']}")
            opening = card["market_context"]["opening"]["game_total"]
            current = card["market_context"]["current"]["game_total"]
            opening_value = _quote_value(opening)
            current_value = _quote_value(current)
            st.markdown(
                "**Game Total:** "
                f"Opening {('Unavailable' if opening_value is None else f'{opening_value:g}')} • "
                f"Current {('Unavailable' if current_value is None else f'{current_value:g}')} • "
                f"{current.get('confidence') or 'Unavailable'}"
            )
        href = view_game_href(game, selected_day)
        if href:
            st.markdown(
                f'<div class="cfbgt-view"><a href="{escape(href, quote=True)}" target="_self">View Game →</a></div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("View Game unavailable — exact game identity is missing")


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    del section_header, status_info, team_logo, h
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="cfbgt-daily-head">'
        '<h2>CFB Game Total</h2>'
        '<p>All FBS + FCS games • Phoenix Time • Daily market snapshot</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    requested_day = _query_day()
    nav_left, nav_today, nav_right = st.columns(3)
    if nav_left.button("← Previous", use_container_width=True, key="cfbgt_daily_prev"):
        _set_day(requested_day - timedelta(days=1))
        st.rerun()
    if nav_today.button("Today", use_container_width=True, key="cfbgt_daily_today"):
        _set_day(datetime.now(PHOENIX).date())
        st.rerun()
    if nav_right.button("Next →", use_container_width=True, key="cfbgt_daily_next"):
        _set_day(requested_day + timedelta(days=1))
        st.rerun()

    effective_day, payload = resolve_effective_slate_date(requested_day, _load_day)
    if effective_day != requested_day:
        _set_day(effective_day)
    st.markdown(
        f'<div class="cfbgt-date-chip">{escape(effective_day.strftime("%A • %B %d, %Y"))}</div>',
        unsafe_allow_html=True,
    )
    if payload.get("auto_advanced"):
        st.caption(f"No games on {requested_day.isoformat()}; showing the next Phoenix date with games.")

    games = list(payload.get("games") or [])
    if any(_status_state(game) in {"Live", "Halftime"} for game in games if isinstance(game, Mapping)):
        try:
            live_payload = dict(_load_slate_cached_20(effective_day.isoformat()))
            if live_payload.get("games"):
                games = list(live_payload["games"])
        except (requests.RequestException, ValueError, TypeError):
            pass

    search = st.text_input("Search team", key="cfbgt_daily_search", placeholder="Search team")
    if hasattr(st, "segmented_control"):
        selected_filter = st.segmented_control(
            "Slate Filter",
            FILTER_OPTIONS,
            default=DEFAULT_FILTER,
            key="cfbgt_daily_filter",
        ) or DEFAULT_FILTER
    else:
        selected_filter = st.radio(
            "Slate Filter",
            FILTER_OPTIONS,
            index=0,
            horizontal=True,
            key="cfbgt_daily_filter",
        )
    conference = ""
    if selected_filter == "Conference":
        conference_choice = st.selectbox(
            "Conference",
            _conference_options(games),
            key="cfbgt_daily_conference",
        )
        conference = "" if conference_choice == "Select conference" else conference_choice

    visible = filter_slate_games(
        games,
        search=search,
        filter_name=selected_filter,
        conference=conference,
    )
    if not games and payload.get("auto_advance_exhausted"):
        st.info("No upcoming games found")
        return
    if not visible:
        st.info("No games match the current Page 1 filters.")
        return

    groups = group_slate_games(visible, now_phoenix=datetime.now(PHOENIX))
    next_window = next_upcoming_window(groups)
    for section_name, section_games in groups.items():
        if not section_games:
            continue
        expanded = section_name == "Live Games" or section_name == next_window
        label = section_name
        if section_name == next_window:
            label = f"{section_name} • Next Up"
        with st.expander(label, expanded=expanded):
            for game in section_games:
                _render_game_card(game, effective_day)


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Daily Slate Page 1 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "DEFAULT_FILTER",
    "FILTER_OPTIONS",
    "MARKET",
    "MAX_FORWARD_SEARCH_DAYS",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "PAGE_CSS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "WINDOW_ORDER",
    "card_view_model",
    "filter_slate_games",
    "group_slate_games",
    "kickoff_window",
    "next_upcoming_window",
    "render_cfb_hub",
    "render_game_total_hub",
    "resolve_effective_slate_date",
    "view_game_href",
]
