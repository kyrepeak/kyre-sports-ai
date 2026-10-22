"""CFB Top Picks V15 — clean Page 1 decision board."""
from __future__ import annotations

from datetime import datetime
from html import escape
import json
import os
import re
from textwrap import dedent
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st

MODEL_VERSION = "CFB TOP PICKS V15 • CLEAN SIMPLE DECISION BOARD"
PAGE_MARKER = "CFB_TOP_PICKS_V15_CLEAN_PAGE1_ACTIVE"
PAGE1_ENDPOINT = "/api/v4/cfb/top-picks/page1"
KYRE_SPORTS_API_BASE_URL = os.getenv(
    "KYRE_SPORTS_API_BASE_URL", "https://kyre-sports-api.vercel.app"
).rstrip("/")
PHOENIX = ZoneInfo("America/Phoenix")

CSS = r"""
<style id="cfb-top-picks-v15-css">
:root{--tp15-bg:#050b12;--tp15-panel:#071522;--tp15-line:rgba(74,184,248,.18);--tp15-blue:#36bfff;--tp15-text:#edf8ff;--tp15-muted:#7892a5;--tp15-green:#70e8b2;--tp15-gold:#ffd278}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 65% -10%,rgba(24,139,212,.12),transparent 35%),#050a10}
[data-testid="cfb-top-picks-v15-root"]{max-width:1120px;margin:0 auto;padding:10px 3px 44px;color:var(--tp15-text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.tp15-shell{border:1px solid var(--tp15-line);border-radius:22px;background:linear-gradient(150deg,rgba(8,26,41,.98),rgba(4,12,21,.99));overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.25)}
.tp15-head{padding:22px 25px;border-bottom:1px solid rgba(255,255,255,.055)}.tp15-brand{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:18px}.tp15-brand b{font-size:.76rem;letter-spacing:.16em}.tp15-live{font-size:.60rem;color:#a3b8c8;font-weight:850}.tp15-live:before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--tp15-green);margin-right:7px;box-shadow:0 0 12px rgba(113,230,176,.65)}
.tp15-title{display:flex;justify-content:space-between;align-items:end;gap:18px}.tp15-title h1{margin:0;font-size:2.25rem;letter-spacing:-.055em;font-weight:950}.tp15-title h1 span{color:var(--tp15-blue)}.tp15-title p{margin:7px 0 0;color:#91a8b9;font-size:.79rem}.tp15-date{border:1px solid rgba(77,190,255,.24);border-radius:11px;padding:9px 12px;background:rgba(5,19,31,.72);font-size:.68rem;font-weight:900;white-space:nowrap}
.tp15-section{padding:20px 25px 7px}.tp15-section+.tp15-section{padding-top:27px}.tp15-section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:11px}.tp15-section-head h2{margin:0;font-size:.94rem;letter-spacing:.02em}.tp15-section-head h2 span{color:var(--tp15-blue)}.tp15-section-head p{margin:0;color:#71899b;font-size:.57rem}.tp15-list{display:grid;gap:9px}
.tp15-pick{display:grid;grid-template-columns:42px minmax(225px,1.45fr) minmax(180px,1.05fr) 112px 128px;gap:12px;align-items:center;padding:13px 14px;border:1px solid rgba(87,184,241,.15);border-radius:14px;background:linear-gradient(135deg,rgba(7,24,38,.94),rgba(5,16,27,.97));text-decoration:none!important;color:inherit!important;transition:border-color .14s ease,transform .14s ease}.tp15-pick:hover{border-color:rgba(48,180,255,.48);transform:translateY(-1px)}
.tp15-rank{width:32px;height:32px;border:1.5px solid rgba(49,183,255,.82);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.69rem;font-weight:950}.tp15-identity{min-width:0}.tp15-match{display:grid;grid-template-columns:34px minmax(0,1fr) 34px;gap:8px;align-items:center}.team-logo{width:32px;height:32px;object-fit:contain;display:block}.team-logo.fallback{border:1px solid rgba(87,184,241,.24);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.48rem;font-weight:950;color:#9fdfff;background:rgba(255,255,255,.035)}.tp15-teamnames{min-width:0}.tp15-teamnames b{display:block;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp15-teamnames small{display:block;margin-top:4px;color:#7893a6;font-size:.54rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tp15-selection{min-width:0}.tp15-badge{display:inline-block;border:1px solid rgba(45,182,255,.45);border-radius:6px;padding:3px 7px;color:#90dfff;font-size:.44rem;font-weight:950;letter-spacing:.08em}.tp15-selection strong{display:block;margin-top:6px;font-size:.78rem;color:#f3faff}.tp15-selection small{display:block;margin-top:4px;color:#89a2b3;font-size:.55rem}.tp15-prob{text-align:center}.tp15-prob b{display:block;font-size:1.12rem;color:#fff}.tp15-prob span,.tp15-meta span{display:block;color:#6e899b;font-size:.42rem;font-weight:900;letter-spacing:.065em}.tp15-meta{text-align:right}.tp15-meta .date-pill{display:inline-block;border:1px solid rgba(66,188,255,.24);border-radius:6px;padding:2px 6px;color:#8ddcff;font-size:.43rem;font-weight:950;letter-spacing:.04em}.tp15-meta b{display:block;font-size:.68rem;margin-top:5px}.tp15-tap{display:block;margin-top:5px;color:#6dd2ff;font-size:.46rem;font-weight:850}
.tp15-player{display:grid;grid-template-columns:44px 32px minmax(0,1fr);gap:8px;align-items:center;min-width:0}.player-photo{width:44px;height:44px;border-radius:50%;object-fit:cover;background:#0c2231;border:1px solid rgba(91,194,250,.24)}.player-photo.fallback{display:flex;align-items:center;justify-content:center;font-size:.54rem;font-weight:950;color:#a5e2ff}.tp15-player-team-logo{width:30px;height:30px;object-fit:contain}.tp15-player-copy{min-width:0}.tp15-player-copy b{display:block;font-size:.73rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp15-player-copy small{display:block;color:#7d98ab;font-size:.50rem;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp15-player-copy .opponent{color:#66869b;font-size:.47rem;margin-top:3px}
.tp15-empty{padding:15px;border:1px solid rgba(255,210,120,.23);border-radius:12px;background:rgba(105,73,18,.10);color:#e9c67c;font-size:.64rem;line-height:1.45}.tp15-foot{padding:14px 24px 20px;color:#688194;font-size:.53rem;text-align:center}
@media(max-width:800px){.tp15-head,.tp15-section{padding-left:14px;padding-right:14px}.tp15-title{align-items:flex-start;flex-direction:column}.tp15-title h1{font-size:1.95rem}.tp15-section-head{align-items:flex-start;flex-direction:column}.tp15-pick{grid-template-columns:36px minmax(0,1fr) 90px;gap:9px}.tp15-selection{grid-column:2/4}.tp15-meta{grid-column:2/4;display:grid;grid-template-columns:auto auto 1fr;gap:8px;align-items:center;text-align:left;border-top:1px solid rgba(255,255,255,.05);padding-top:8px}.tp15-tap{text-align:right;margin:0}.tp15-meta b{margin:0}.tp15-prob{text-align:right}}
@media(max-width:540px){.tp15-player{grid-template-columns:40px 27px minmax(0,1fr)}.player-photo{width:40px;height:40px}.tp15-player-team-logo{width:26px;height:26px}.tp15-teamnames b{font-size:.67rem}.tp15-selection strong{font-size:.72rem}}
</style>
"""


def _clean_html(value: str) -> str:
    """Remove Markdown code-block indentation from HTML boundaries."""
    text = dedent(value or "").strip()
    return re.sub(r"\n[ \t]+", "", text)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return out if out == out else None


def _money(value: Any) -> str:
    number = _number(value)
    if number is None or number == 0:
        return "NOT_AVAILABLE"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _prob(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "NOT_AVAILABLE"
    if 0 <= number <= 1:
        number *= 100.0
    return f"{number:.0f}%"


def _initials(value: str) -> str:
    words = [word for word in _clean(value).replace("-", " ").split() if word]
    return "".join(word[0].upper() for word in words[:3]) if words else "CFB"


def _logo(url: Any, team: str, *, css_class: str = "team-logo") -> str:
    src = _clean(url)
    if src.startswith("https://"):
        return f'<img class="{css_class}" src="{escape(src)}" alt="{escape(team)} logo">'
    return f'<span class="{css_class} fallback" aria-label="{escape(team)} logo unavailable">{escape(_initials(team))}</span>'


def _player_photo(url: Any, player: str) -> str:
    src = _clean(url)
    if src.startswith("https://"):
        return f'<img class="player-photo" src="{escape(src)}" alt="{escape(player)} headshot">'
    return f'<span class="player-photo fallback" aria-label="{escape(player)} headshot unavailable">{escape(_initials(player))}</span>'


def _record(value: Any) -> str:
    text = _clean(value)
    return text if text and text.casefold() not in {"none", "null", "unknown", "unavailable"} else "NOT_AVAILABLE"


def _game_time(value: Any) -> str:
    text = _clean(value)
    if not text:
        return "TIME NOT_AVAILABLE"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return text
        return parsed.astimezone(PHOENIX).strftime("%-I:%M %p AZ")
    except Exception:
        return text


def _query_date() -> str | None:
    try:
        raw = st.query_params.get("top_pick_date")
    except Exception:
        raw = None
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    return _clean(raw) or None


@st.cache_data(ttl=45, show_spinner=False)
def _load_page_payload(game_date: str | None = None) -> dict[str, Any]:
    query = {"limit": "10"}
    if game_date:
        query["game_date"] = game_date
    url = f"{KYRE_SPORTS_API_BASE_URL}{PAGE1_ENDPOINT}?{urlencode(query)}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "KyreSportsAI/1.0"})
    with urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if _clean(payload.get("service")) != "Kyre Sports API":
        raise RuntimeError("Top Picks V4 returned an invalid gateway contract")
    return dict(payload)


def _handoff(row: Mapping[str, Any], kind: str) -> str:
    query = {
        "top_pick_kind": kind,
        "top_pick_event": _clean(row.get("event_id")),
        "top_pick_market": _clean(row.get("market_type") or row.get("market_key")),
        "top_pick_selection": _clean(row.get("selection") or row.get("side")),
    }
    if kind == "player-prop":
        query["top_pick_player"] = _clean(row.get("player_name"))
        query["top_pick_player_id"] = _clean(row.get("official_roster_id") or row.get("player_id"))
        query["top_pick_line"] = _clean(row.get("line"))
    return "?" + urlencode({key: value for key, value in query.items() if value})


def _game_card(row: Mapping[str, Any]) -> str:
    rank = int(row.get("rank") or 0)
    away = _clean(row.get("away_team")) or "Away"
    home = _clean(row.get("home_team")) or "Home"
    market = _clean(row.get("market_type")).upper()
    badge = "ML" if market == "MONEYLINE" else market or "MARKET"
    selection = _clean(row.get("selection")) or "SELECTION NOT_AVAILABLE"
    book = _clean(row.get("sportsbook")) or "BOOK NOT_AVAILABLE"
    odds = _money(row.get("american_odds"))
    probability = _prob(row.get("probability"))
    away_record = _record(row.get("away_record"))
    home_record = _record(row.get("home_record"))
    date_label = _clean(row.get("date_label")) or "DATE NOT_AVAILABLE"
    time = _game_time(row.get("kickoff_iso"))
    return _clean_html(f"""
    <a class="tp15-pick" href="{escape(_handoff(row, 'game'))}" data-testid="top-game-pick-{rank}">
      <div class="tp15-rank">{rank}</div>
      <div class="tp15-identity"><div class="tp15-match">{_logo(row.get('away_logo'), away)}<div class="tp15-teamnames"><b>{escape(away)} @ {escape(home)}</b><small>{escape(away)} {escape(away_record)} • {escape(home)} {escape(home_record)}</small></div>{_logo(row.get('home_logo'), home)}</div></div>
      <div class="tp15-selection"><span class="tp15-badge">{escape(badge)}</span><strong>{escape(selection)}</strong><small>{escape(book)} • {escape(odds)}</small></div>
      <div class="tp15-prob"><b>{escape(probability)}</b><span>HIT PROBABILITY</span></div>
      <div class="tp15-meta"><span class="date-pill">{escape(date_label)}</span><b>{escape(time)}</b><small class="tp15-tap">Tap for full analysis →</small></div>
    </a>
    """)


def _player_identity_line(row: Mapping[str, Any]) -> str:
    position = _clean(row.get("position")) or "POS NOT_AVAILABLE"
    jersey = _clean(row.get("jersey_number"))
    player_id = _clean(row.get("player_id_display")) or "ID unavailable"
    bits = [position]
    bits.append(f"#{jersey}" if jersey else "# NOT_AVAILABLE")
    bits.append(f"ID {player_id}" if player_id != "ID unavailable" else "ID NOT_AVAILABLE")
    return " • ".join(bits)


def _prop_card(row: Mapping[str, Any]) -> str:
    rank = int(row.get("rank") or 0)
    player = _clean(row.get("player_name")) or "PLAYER NOT_AVAILABLE"
    team = _clean(row.get("player_team")) or "TEAM NOT_AVAILABLE"
    opponent = _clean(row.get("opponent")) or "OPPONENT NOT_AVAILABLE"
    market = _clean(row.get("market_label")) or "PLAYER PROP"
    side = _clean(row.get("side")).upper() or "SIDE NOT_AVAILABLE"
    line = _number(row.get("line"))
    selection = f"{side.title()} {line:g}" if line is not None else side.title()
    book = _clean(row.get("sportsbook")) or "BOOK NOT_AVAILABLE"
    odds = _money(row.get("american_odds"))
    probability = _prob(row.get("probability"))
    date_label = _clean(row.get("date_label")) or "DATE NOT_AVAILABLE"
    time = _game_time(row.get("kickoff_iso"))
    return _clean_html(f"""
    <a class="tp15-pick" href="{escape(_handoff(row, 'player-prop'))}" data-testid="top-player-prop-{rank}">
      <div class="tp15-rank">{rank}</div>
      <div class="tp15-player">{_player_photo(row.get('player_headshot'), player)}{_logo(row.get('team_logo'), team, css_class='tp15-player-team-logo')}<div class="tp15-player-copy"><b>{escape(player)}</b><small>{escape(_player_identity_line(row))}</small><div class="opponent">{escape(team)} vs {escape(opponent)}</div></div></div>
      <div class="tp15-selection"><span class="tp15-badge">PROP</span><strong>{escape(market)} • {escape(selection)}</strong><small>{escape(book)} • {escape(odds)}</small></div>
      <div class="tp15-prob"><b>{escape(probability)}</b><span>HIT PROBABILITY</span></div>
      <div class="tp15-meta"><span class="date-pill">{escape(date_label)}</span><b>{escape(time)}</b><small class="tp15-tap">Tap for full analysis →</small></div>
    </a>
    """)


def _page_html(payload: Mapping[str, Any]) -> str:
    game_picks = [dict(row) for row in list(payload.get("game_picks") or []) if isinstance(row, Mapping)]
    props = [dict(row) for row in list(payload.get("player_props") or []) if isinstance(row, Mapping)]
    selected = _clean(payload.get("selected_date")) or "DATE NOT_AVAILABLE"
    game_cards = "".join(_game_card(row) for row in game_picks)
    prop_cards = "".join(_prop_card(row) for row in props)
    game_empty = '<div class="tp15-empty">Verified inventory is below 10. Approved fallbacks were exhausted; no fake game selection was inserted.</div>'
    prop_empty = '<div class="tp15-empty">Verified inventory is below 10. Approved fallbacks were exhausted; no fake player prop was inserted.</div>'
    return _clean_html(f"""
    <section data-testid="cfb-top-picks-v15-root" data-page-marker="{PAGE_MARKER}">
      <div class="tp15-shell">
        <header class="tp15-head"><div class="tp15-brand"><b>KYRE SPORTS AI</b><span class="tp15-live">KYRE SPORTS API LIVE</span></div><div class="tp15-title"><div><h1><span>Top Picks</span></h1><p>Fast decisions only. Tap any selection for the full breakdown.</p></div><div class="tp15-date">{escape(selected)}</div></div></header>
        <section class="tp15-section"><div class="tp15-section-head"><h2>TOP 10 <span>GAME PICKS</span></h2><p>Moneyline + spread + total • one combined board</p></div><div class="tp15-list">{game_cards if len(game_picks) == 10 else game_cards + game_empty}</div></section>
        <section class="tp15-section"><div class="tp15-section-head"><h2>TOP 10 <span>PLAYER PROPS</span></h2><p>Verified player identity • exact sportsbook price</p></div><div class="tp15-list">{prop_cards if len(props) == 10 else prop_cards + prop_empty}</div></section>
        <div class="tp15-foot">Exact sportsbook prices • verified NCAA team identity • current official roster identity • no invented slots</div>
      </div>
    </section>
    """)


def render() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        payload = _load_page_payload(_query_date())
    except Exception as exc:
        st.error(f"Top Picks data unavailable: {type(exc).__name__}")
        return
    st.markdown(_page_html(payload), unsafe_allow_html=True)


__all__ = [
    "MODEL_VERSION",
    "PAGE1_ENDPOINT",
    "PAGE_MARKER",
    "_clean_html",
    "_game_card",
    "_page_html",
    "_prop_card",
    "render",
]
