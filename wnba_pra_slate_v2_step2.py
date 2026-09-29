"""WNBA Navigation V2 — Step 2 lightweight Slate page.

Page 1 owns schedule presentation only. It performs one cached GET against the
certified Kyre Sports API schedule endpoint and deliberately avoids loading the
legacy PRA analysis stack, players, markets, projections, rankings, H2H, or
Monte Carlo work.

Selecting a matchup writes only the frozen Step-1 game navigation state. Page 2
content is intentionally deferred to Step 3.
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape
from time import perf_counter
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

from wnba_api_client_v1 import KyreWNBAAPIClient, SUPPORTED_SEASON
import wnba_pra_navigation_v2_step1 as navigation


MODEL_VERSION = "WNBA PRA NAVIGATION V2 • STEP 2 LIGHTWEIGHT SLATE"
API_SOURCE = "Kyre Sports API"
CACHE_TTL_SECONDS = 60
API_TIMEOUT_SECONDS = 5.0
API_ATTEMPTS = 1
EASTERN = ZoneInfo("America/New_York")

DATE_KEY = "ks_wnba_pra_nav_v2_slate_date"
PERF_KEY = "ks_wnba_pra_nav_v2_step2_perf"
SESSION_SELECTED_GAME = "ks_wnba_pra_nav_v2_selected_game"
SESSION_SLATE_META = "ks_wnba_pra_nav_v2_slate_meta"

SLATE_CONTRACT = {
    "project": "WNBA Navigation V2",
    "step": "2/7",
    "page": "slate",
    "source": API_SOURCE,
    "endpoint": "/api/v1/wnba/games",
    "api_timeout_seconds": API_TIMEOUT_SECONDS,
    "api_attempts": API_ATTEMPTS,
    "cache_ttl_seconds": CACHE_TTL_SECONDS,
    "schedule_payloads_per_uncached_render": 1,
    "players_loaded": False,
    "markets_loaded": False,
    "projections_loaded": False,
    "rankings_loaded": False,
    "qualification_loaded": False,
    "h2h_loaded": False,
    "monte_carlo_loaded": False,
    "page2_prefetched": False,
    "page3_prefetched": False,
    "api_ownership_changed": False,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
}


class WNBASlateLoadError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _team_name(team: Mapping[str, Any]) -> str:
    full = _text(team.get("full_name"))
    if full:
        return full
    city = _text(team.get("team_city"))
    name = _text(team.get("team_name"))
    return " ".join(part for part in (city, name) if part).strip() or "WNBA Team"


def _team_logo_url(team_id: Any) -> str:
    try:
        tid = int(team_id)
    except (TypeError, ValueError):
        return ""
    return f"https://cdn.nba.com/logos/wnba/{tid}/global/L/logo.svg"


def _time_label(value: Any) -> str:
    text = _text(value)
    if not text:
        return "TBD"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone(EASTERN).strftime("%I:%M %p").lstrip("0") + " ET"
    except Exception:
        return text


def _status_parts(game: Mapping[str, Any]) -> tuple[str, str]:
    raw = game.get("status") if isinstance(game.get("status"), Mapping) else {}
    category = _text(raw.get("category")).upper() or "UNKNOWN"
    text = _text(raw.get("text"))
    if not text:
        text = category.title()
    return category, text


def _normalize_game(raw: Mapping[str, Any], day_str: str) -> dict[str, Any] | None:
    away = raw.get("away") if isinstance(raw.get("away"), Mapping) else {}
    home = raw.get("home") if isinstance(raw.get("home"), Mapping) else {}
    gid = _text(raw.get("game_id"))
    away_id = away.get("official_team_id")
    home_id = home.get("official_team_id")
    if not gid or away_id in (None, "") or home_id in (None, ""):
        return None

    category, status_text = _status_parts(raw)
    venue = raw.get("venue") if isinstance(raw.get("venue"), Mapping) else {}
    return {
        "game_id": gid,
        "game_date": _text(raw.get("official_schedule_date")) or day_str,
        "game_datetime_eastern": _text(raw.get("game_datetime_eastern")),
        "time_label": _time_label(raw.get("game_datetime_eastern")),
        "status_category": category,
        "status_text": status_text,
        "away_team_id": int(away_id),
        "away_team": _team_name(away),
        "away_tricode": _text(away.get("team_tricode")),
        "away_logo": _team_logo_url(away_id),
        "home_team_id": int(home_id),
        "home_team": _team_name(home),
        "home_tricode": _text(home.get("team_tricode")),
        "home_logo": _team_logo_url(home_id),
        "venue": _text(venue.get("name")) or _text(venue.get("city")) or "Venue TBD",
    }


def _validated_slate_payload(payload: Mapping[str, Any], day_str: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise WNBASlateLoadError("Schedule response was not an object.")
    if int(payload.get("season") or 0) != int(SUPPORTED_SEASON):
        raise WNBASlateLoadError("Schedule response season did not match the certified WNBA season.")
    raw_games = payload.get("games")
    if not isinstance(raw_games, list):
        raise WNBASlateLoadError("Schedule response did not contain a games list.")

    games: list[dict[str, Any]] = []
    rejected = 0
    for raw in raw_games:
        if not isinstance(raw, Mapping):
            rejected += 1
            continue
        game = _normalize_game(raw, day_str)
        if game is None:
            rejected += 1
            continue
        games.append(game)

    games.sort(key=lambda row: (row.get("game_datetime_eastern") or "9999", row["game_id"]))
    return {
        "selected_date": day_str,
        "season": int(SUPPORTED_SEASON),
        "state": "CONNECTED" if games else "OFF_DAY",
        "source": API_SOURCE,
        "source_variant": _text(payload.get("source_variant")),
        "games": games,
        "games_received": len(raw_games),
        "games_valid": len(games),
        "games_rejected": rejected,
    }


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_slate(day_str: str) -> dict[str, Any]:
    """Load exactly one schedule payload from the certified hosted API."""
    client = KyreWNBAAPIClient(
        timeout_seconds=API_TIMEOUT_SECONDS,
        attempts=API_ATTEMPTS,
    )
    payload = client.games_for_date(day_str, SUPPORTED_SEASON)
    return _validated_slate_payload(payload, day_str)


def _css() -> None:
    st.markdown(
        """
<style>
.wn2-hero{border:1px solid rgba(56,189,248,.24);border-radius:22px;padding:18px 20px;margin:.2rem 0 1rem;background:linear-gradient(135deg,rgba(14,116,144,.18),rgba(15,23,42,.96))}
.wn2-kicker{font-size:.72rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:#7dd3fc}
.wn2-title{font-size:clamp(1.55rem,4vw,2.2rem);font-weight:950;color:#f8fafc;letter-spacing:-.035em;margin:.18rem 0}
.wn2-sub{font-size:.82rem;color:#94a3b8}
.wn2-health{display:flex;gap:.55rem;flex-wrap:wrap;margin:.55rem 0 1rem}
.wn2-chip{border:1px solid rgba(148,163,184,.22);border-radius:999px;padding:.32rem .62rem;font-size:.72rem;font-weight:800;color:#cbd5e1;background:rgba(15,23,42,.78)}
.wn2-chip.ok{color:#86efac;border-color:rgba(34,197,94,.34)}
.wn2-card{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:1rem;border:1px solid rgba(148,163,184,.18);border-radius:20px;padding:16px 18px;margin:10px 0 5px;background:linear-gradient(145deg,rgba(15,23,42,.97),rgba(15,23,42,.84));box-shadow:0 14px 34px rgba(0,0,0,.14)}
.wn2-team{display:flex;align-items:center;gap:.7rem;min-width:0}.wn2-team.home{justify-content:flex-end;text-align:right}.wn2-logo{width:48px;height:48px;object-fit:contain;flex:0 0 auto}
.wn2-name{font-weight:900;color:#f8fafc;line-height:1.08}.wn2-code{font-size:.7rem;color:#94a3b8;font-weight:800;margin-top:.18rem}
.wn2-mid{text-align:center;min-width:128px}.wn2-time{font-size:.9rem;color:#f8fafc;font-weight:900}.wn2-status{font-size:.68rem;color:#7dd3fc;font-weight:900;text-transform:uppercase;letter-spacing:.07em;margin-top:.18rem}.wn2-venue{font-size:.66rem;color:#64748b;margin-top:.22rem}
@media(max-width:640px){.wn2-card{grid-template-columns:1fr;text-align:center}.wn2-team,.wn2-team.home{justify-content:center;text-align:center}.wn2-mid{order:3}.wn2-logo{width:44px;height:44px}}
</style>
""",
        unsafe_allow_html=True,
    )


def _logo_markup(url: str, team: str) -> str:
    if not url:
        return ""
    return f'<img class="wn2-logo" src="{escape(url)}" alt="{escape(team)} logo" loading="lazy">'


def _game_card(game: Mapping[str, Any]) -> None:
    gid = _text(game.get("game_id"))
    away = _text(game.get("away_team"))
    home = _text(game.get("home_team"))
    away_code = _text(game.get("away_tricode"))
    home_code = _text(game.get("home_tricode"))
    st.markdown(
        '<div class="wn2-card">'
        '<div class="wn2-team">'
        f'{_logo_markup(_text(game.get("away_logo")), away)}'
        f'<div><div class="wn2-name">{escape(away)}</div><div class="wn2-code">{escape(away_code)} • AWAY</div></div>'
        '</div>'
        '<div class="wn2-mid">'
        f'<div class="wn2-time">{escape(_text(game.get("time_label")) or "TBD")}</div>'
        f'<div class="wn2-status">{escape(_text(game.get("status_text")) or _text(game.get("status_category")))}</div>'
        f'<div class="wn2-venue">{escape(_text(game.get("venue")))}</div>'
        '</div>'
        '<div class="wn2-team home">'
        f'<div><div class="wn2-name">{escape(home)}</div><div class="wn2-code">{escape(home_code)} • HOME</div></div>'
        f'{_logo_markup(_text(game.get("home_logo")), home)}'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button(
        "Open Game Center →",
        key=f"wnba_nav_v2_step2_open_{gid}",
        use_container_width=True,
    ):
        st.session_state[SESSION_SELECTED_GAME] = dict(game)
        navigation.go_to_game(gid)
        st.rerun()


def _default_day() -> date:
    return datetime.now(EASTERN).date()


def render_slate_page() -> dict[str, Any]:
    _css()
    st.markdown(
        '<div class="wn2-hero">'
        '<div class="wn2-kicker">Kyre Sports AI • WNBA</div>'
        '<div class="wn2-title">🏀 WNBA Slate</div>'
        '<div class="wn2-sub">Choose a matchup first. Player and PRA intelligence load only after you drill down.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    selected = st.date_input("📅 Slate date", value=_default_day(), key=DATE_KEY)
    day_str = selected.isoformat() if hasattr(selected, "isoformat") else str(selected)[:10]

    started = perf_counter()
    try:
        slate = load_slate(day_str)
        error_type = ""
    except Exception as exc:
        slate = {
            "selected_date": day_str,
            "state": "API_ERROR",
            "source": API_SOURCE,
            "games": [],
            "games_valid": 0,
            "games_rejected": 0,
        }
        error_type = type(exc).__name__

    elapsed_ms = (perf_counter() - started) * 1000.0
    st.session_state[SESSION_SLATE_META] = {
        "selected_date": day_str,
        "state": slate.get("state"),
        "games": int(len(slate.get("games") or [])),
        "source": API_SOURCE,
    }
    st.session_state[PERF_KEY] = {
        "page": navigation.PAGE_SLATE,
        "schedule_requests_this_render": 1,
        "page2_prefetches": 0,
        "page3_prefetches": 0,
        "player_requests": 0,
        "market_requests": 0,
        "model_requests": 0,
        "load_call_ms": elapsed_ms,
        "api_error_type": error_type,
    }

    state = _text(slate.get("state"))
    games = list(slate.get("games") or [])
    health_class = "ok" if state in {"CONNECTED", "OFF_DAY"} else ""
    st.markdown(
        '<div class="wn2-health">'
        f'<span class="wn2-chip {health_class}">● {escape(state.replace("_", " ") or "UNKNOWN")}</span>'
        f'<span class="wn2-chip">{len(games)} game{"s" if len(games) != 1 else ""}</span>'
        f'<span class="wn2-chip">⚡ {escape(API_SOURCE)}</span>'
        '<span class="wn2-chip">No player/model prefetch</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    if state == "API_ERROR":
        st.error("WNBA schedule is temporarily unavailable. No fallback analytics were loaded.")
        if st.button("Retry schedule", key="wnba_nav_v2_step2_retry", use_container_width=True):
            try:
                load_slate.clear()
            except Exception:
                st.cache_data.clear()
            st.rerun()
        return slate

    if not games:
        st.info("No WNBA games are scheduled for this date.")
        return slate

    for game in games:
        _game_card(game)

    st.caption("Detailed PRA edges stay asleep on this page for faster loading.")
    return slate


def _render_deeper_placeholder(state: navigation.NavigationState) -> dict[str, Any]:
    _css()
    if st.button("← Back to WNBA Slate", key="wnba_nav_v2_step2_back", use_container_width=True):
        navigation.go_to_slate()
        st.rerun()

    snapshot = st.session_state.get(SESSION_SELECTED_GAME)
    if not isinstance(snapshot, Mapping):
        snapshot = {}

    if state.page == navigation.PAGE_GAME:
        away = _text(snapshot.get("away_team"))
        home = _text(snapshot.get("home_team"))
        title = f"{away} @ {home}".strip(" @") or f"Game {state.game_id}"
        st.markdown("## 🏀 Game Center")
        st.markdown(f"### {escape(title)}")
        st.info("Game Center player cards are intentionally deferred to Step 3. Nothing heavy was prefetched.")
    else:
        st.markdown("## 🎯 Player PRA Intelligence")
        st.info("Player intelligence is intentionally deferred to Step 4. Nothing heavy was prefetched.")

    st.session_state[PERF_KEY] = {
        "page": state.page,
        "schedule_requests_this_render": 0,
        "page2_prefetches": 0,
        "page3_prefetches": 0,
        "player_requests": 0,
        "market_requests": 0,
        "model_requests": 0,
    }
    return {"page": state.page, "game_id": state.game_id, "player_id": state.player_id}


def render_step2_route() -> dict[str, Any]:
    state = navigation.current_state()
    if state.page == navigation.PAGE_SLATE:
        return render_slate_page()
    return _render_deeper_placeholder(state)


__all__ = [
    "API_ATTEMPTS",
    "API_SOURCE",
    "API_TIMEOUT_SECONDS",
    "CACHE_TTL_SECONDS",
    "DATE_KEY",
    "MODEL_VERSION",
    "PERF_KEY",
    "SESSION_SELECTED_GAME",
    "SESSION_SLATE_META",
    "SLATE_CONTRACT",
    "WNBASlateLoadError",
    "_normalize_game",
    "_validated_slate_payload",
    "load_slate",
    "render_slate_page",
    "render_step2_route",
]
