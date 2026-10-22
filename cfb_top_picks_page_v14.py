"""CFB Top Picks V14 — simple Page 1 decision board."""
from __future__ import annotations

from datetime import datetime
from html import escape
import json
import os
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st

MODEL_VERSION = "CFB TOP PICKS V14 • SIMPLE TOP 10 + PROP TOP 10"
PAGE_MARKER = "CFB_TOP_PICKS_V14_SIMPLE_PAGE1_ACTIVE"
PAGE1_ENDPOINT = "/api/v3/cfb/top-picks/page1"
KYRE_SPORTS_API_BASE_URL = os.getenv(
    "KYRE_SPORTS_API_BASE_URL", "https://kyre-sports-api.vercel.app"
).rstrip("/")
PHOENIX = ZoneInfo("America/Phoenix")

CSS = r"""
<style id="cfb-top-picks-v14-css">
:root{--bg:#050b12;--panel:#081522;--line:rgba(93,195,255,.17);--blue:#2bb7ff;--text:#eef8ff;--muted:#7892a5;--green:#71e6b0;--gold:#ffd278}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 65% -10%,rgba(24,139,212,.12),transparent 35%),#050a10}
[data-testid="cfb-top-picks-v14-root"]{max-width:1100px;margin:0 auto;padding:10px 3px 44px;color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.tp14-shell{border:1px solid var(--line);border-radius:22px;background:linear-gradient(150deg,rgba(8,26,41,.98),rgba(4,12,21,.99));overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.25)}
.tp14-head{padding:22px 24px;border-bottom:1px solid rgba(255,255,255,.055)}.tp14-brand{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:17px}.tp14-brand b{font-size:.72rem;letter-spacing:.16em}.tp14-live{font-size:.58rem;color:#9ab4c6;font-weight:850}.tp14-live:before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);margin-right:7px;box-shadow:0 0 12px rgba(113,230,176,.65)}
.tp14-title{display:flex;justify-content:space-between;align-items:end;gap:18px}.tp14-title h1{margin:0;font-size:2.2rem;letter-spacing:-.055em;font-weight:950}.tp14-title h1 span{color:var(--blue)}.tp14-title p{margin:7px 0 0;color:#8ca4b5;font-size:.76rem}.tp14-date{border:1px solid rgba(77,190,255,.21);border-radius:11px;padding:8px 11px;background:rgba(5,19,31,.68);font-size:.65rem;font-weight:900;white-space:nowrap}
.tp14-section{padding:18px 24px 6px}.tp14-section+.tp14-section{padding-top:23px}.tp14-section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:10px}.tp14-section-head h2{margin:0;font-size:.9rem;letter-spacing:.02em}.tp14-section-head h2 span{color:var(--blue)}.tp14-section-head p{margin:0;color:#687f91;font-size:.52rem}.tp14-list{display:grid;gap:8px}
.tp14-pick{display:grid;grid-template-columns:42px minmax(175px,1.35fr) minmax(150px,1fr) 108px 115px;gap:10px;align-items:center;padding:12px 13px;border:1px solid rgba(87,184,241,.13);border-radius:13px;background:linear-gradient(135deg,rgba(7,24,38,.92),rgba(5,16,27,.96));text-decoration:none;color:inherit}.tp14-pick:hover{border-color:rgba(48,180,255,.42);background:linear-gradient(135deg,rgba(9,33,51,.96),rgba(5,18,30,.98))}
.tp14-rank{width:31px;height:31px;border:1.5px solid rgba(49,183,255,.75);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.66rem;font-weight:950}.tp14-identity{min-width:0}.tp14-match{display:flex;align-items:center;gap:7px;min-width:0}.team-logo{width:24px;height:24px;border-radius:50%;object-fit:contain;background:rgba(255,255,255,.05);flex:0 0 auto}.team-logo.fallback{display:flex;align-items:center;justify-content:center;border:1px solid rgba(87,184,241,.19);font-size:.48rem;font-weight:950;color:#9fdfff}.tp14-teamnames{min-width:0}.tp14-teamnames b{display:block;font-size:.65rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp14-teamnames small{display:block;margin-top:3px;color:#69869a;font-size:.48rem}.tp14-selection{min-width:0}.tp14-badge{display:inline-block;border:1px solid rgba(45,182,255,.4);border-radius:6px;padding:2px 6px;color:#88dcff;font-size:.42rem;font-weight:950;letter-spacing:.07em}.tp14-selection strong{display:block;margin-top:5px;font-size:.72rem}.tp14-selection small{display:block;margin-top:3px;color:#7f9aac;font-size:.49rem}.tp14-prob{text-align:center}.tp14-prob b{display:block;font-size:1.02rem;color:#fff}.tp14-prob span,.tp14-meta span{display:block;color:#668195;font-size:.40rem;font-weight:900;letter-spacing:.055em}.tp14-meta{text-align:right}.tp14-meta b{display:block;font-size:.62rem;margin-top:2px}.tp14-tap{display:block;margin-top:4px;color:#66cfff;font-size:.43rem;font-weight:850}
.tp14-prop{grid-template-columns:42px minmax(190px,1.35fr) minmax(150px,1fr) 108px 115px}.tp14-player{display:flex;gap:8px;align-items:center}.player-id{width:34px;height:34px;border-radius:10px;border:1px solid rgba(77,190,255,.2);background:rgba(18,65,92,.23);display:flex;align-items:center;justify-content:center;font-size:.50rem;font-weight:950;color:#8cddff;flex:0 0 auto}.tp14-player-copy{min-width:0}.tp14-player-copy b{display:block;font-size:.68rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp14-player-copy small{display:block;color:#688599;font-size:.45rem;margin-top:3px}.tp14-player-logos{display:flex;gap:4px;margin-top:5px}
.tp14-empty{padding:15px;border:1px solid rgba(255,210,120,.23);border-radius:12px;background:rgba(105,73,18,.10);color:#e9c67c;font-size:.63rem;line-height:1.45}.tp14-foot{padding:11px 24px 19px;color:#5f788a;font-size:.49rem;text-align:center}
@media(max-width:760px){.tp14-head,.tp14-section{padding-left:13px;padding-right:13px}.tp14-title{align-items:flex-start;flex-direction:column}.tp14-title h1{font-size:1.9rem}.tp14-section-head{align-items:flex-start;flex-direction:column}.tp14-pick,.tp14-prop{grid-template-columns:36px minmax(0,1fr) 86px;gap:8px}.tp14-selection{grid-column:2/4}.tp14-meta{grid-column:2/4;display:flex;align-items:center;justify-content:space-between;text-align:left;border-top:1px solid rgba(255,255,255,.045);padding-top:7px}.tp14-meta span,.tp14-meta b,.tp14-tap{display:inline-block;margin:0}.tp14-prob{text-align:right}}
</style>
"""


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
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _prob(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "—"
    if 0 <= number <= 1:
        number *= 100.0
    return f"{number:.0f}%"


def _initials(team: str) -> str:
    words = [word for word in _clean(team).replace("-", " ").split() if word]
    if not words:
        return "CFB"
    return "".join(word[0].upper() for word in words[:3])


def _logo(url: Any, team: str) -> str:
    src = _clean(url)
    if src.startswith("https://"):
        return f'<img class="team-logo" src="{escape(src)}" alt="{escape(team)} logo">'
    return f'<span class="team-logo fallback" aria-label="{escape(team)} team mark">{escape(_initials(team))}</span>'


def _game_time(value: Any) -> str:
    text = _clean(value)
    if not text:
        return "Time pending"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return text
        local = parsed.astimezone(PHOENIX)
        return local.strftime("%-I:%M %p AZ")
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
        raise RuntimeError("Top Picks V3 returned an invalid gateway contract")
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
        query["top_pick_player_id"] = _clean(row.get("player_id"))
        query["top_pick_line"] = _clean(row.get("line"))
    return "?" + urlencode({key: value for key, value in query.items() if value})


def _game_card(row: Mapping[str, Any]) -> str:
    rank = int(row.get("rank") or 0)
    away = _clean(row.get("away_team")) or "Away"
    home = _clean(row.get("home_team")) or "Home"
    market = _clean(row.get("market_type")).upper()
    badge = "ML" if market == "MONEYLINE" else market
    selection = _clean(row.get("selection")) or "Selection pending"
    book = _clean(row.get("sportsbook")) or "Book pending"
    odds = _money(row.get("american_odds"))
    probability = _prob(row.get("probability"))
    away_record = _clean(row.get("away_record")) or "—"
    home_record = _clean(row.get("home_record")) or "—"
    time = _game_time(row.get("kickoff_iso"))
    return f"""
    <a class="tp14-pick" href="{escape(_handoff(row, 'game'))}" data-testid="top-game-pick-{rank}">
      <div class="tp14-rank">{rank}</div>
      <div class="tp14-identity">
        <div class="tp14-match">{_logo(row.get('away_logo'), away)}<div class="tp14-teamnames"><b>{escape(away)} @ {escape(home)}</b><small>RECORD • {escape(away_record)} vs {escape(home_record)}</small></div>{_logo(row.get('home_logo'), home)}</div>
      </div>
      <div class="tp14-selection"><span class="tp14-badge">{escape(badge)}</span><strong>{escape(selection)}</strong><small>ODDS • {escape(odds)} • {escape(book)}</small></div>
      <div class="tp14-prob"><b>{escape(probability)}</b><span>HIT PROBABILITY</span></div>
      <div class="tp14-meta"><span>GAME TIME</span><b>{escape(time)}</b><small class="tp14-tap">Tap for full analysis →</small></div>
    </a>
    """


def _prop_card(row: Mapping[str, Any]) -> str:
    rank = int(row.get("rank") or 0)
    player = _clean(row.get("player_name")) or "Player"
    player_id = _clean(row.get("player_id_display")) or "ID not reported"
    away = _clean(row.get("away_team")) or "Away"
    home = _clean(row.get("home_team")) or "Home"
    market = _clean(row.get("market_label")) or "Player Prop"
    side = _clean(row.get("side")).upper()
    line = _number(row.get("line"))
    selection = f"{side.title()} {line:g}" if line is not None else side.title()
    book = _clean(row.get("sportsbook")) or "Book pending"
    odds = _money(row.get("american_odds"))
    probability = _prob(row.get("probability"))
    away_record = _clean(row.get("away_record")) or "—"
    home_record = _clean(row.get("home_record")) or "—"
    time = _game_time(row.get("kickoff_iso"))
    short_id = player_id if len(player_id) <= 11 else player_id[:8] + "…"
    return f"""
    <a class="tp14-pick tp14-prop" href="{escape(_handoff(row, 'player-prop'))}" data-testid="top-player-prop-{rank}">
      <div class="tp14-rank">{rank}</div>
      <div class="tp14-player">
        <div class="player-id">ID</div>
        <div class="tp14-player-copy"><b>{escape(player)}</b><small>PLAYER ID • {escape(short_id)}</small><div class="tp14-player-logos">{_logo(row.get('away_logo'), away)}{_logo(row.get('home_logo'), home)}</div></div>
      </div>
      <div class="tp14-selection"><span class="tp14-badge">PROP</span><strong>{escape(market)} • {escape(selection)}</strong><small>ODDS • {escape(odds)} • {escape(book)} • RECORD {escape(away_record)} vs {escape(home_record)}</small></div>
      <div class="tp14-prob"><b>{escape(probability)}</b><span>HIT PROBABILITY</span></div>
      <div class="tp14-meta"><span>GAME TIME</span><b>{escape(time)}</b><small class="tp14-tap">Tap for full analysis →</small></div>
    </a>
    """


def _page_html(payload: Mapping[str, Any]) -> str:
    game_picks = [dict(row) for row in list(payload.get("game_picks") or []) if isinstance(row, Mapping)]
    props = [dict(row) for row in list(payload.get("player_props") or []) if isinstance(row, Mapping)]
    diag = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), Mapping) else {}
    selected = _clean(payload.get("selected_date")) or "Verified slate"
    game_cards = "".join(_game_card(row) for row in game_picks)
    prop_cards = "".join(_prop_card(row) for row in props)
    game_empty = '<div class="tp14-empty">Verified inventory is below 10. Approved fallbacks were exhausted; no fake game selection was inserted.</div>'
    prop_empty = '<div class="tp14-empty">Verified inventory is below 10. Approved fallbacks were exhausted; no fake player prop was inserted.</div>'
    return f"""
    <section data-testid="cfb-top-picks-v14-root" data-page-marker="{PAGE_MARKER}">
      <div class="tp14-shell">
        <header class="tp14-head">
          <div class="tp14-brand"><b>KYRE SPORTS AI</b><span class="tp14-live">KYRE SPORTS API LIVE</span></div>
          <div class="tp14-title"><div><h1>Top <span>Picks</span></h1><p>Fast decisions only. Tap any selection for the full breakdown.</p></div><div class="tp14-date">{escape(selected)}</div></div>
        </header>
        <section class="tp14-section">
          <div class="tp14-section-head"><h2>TOP 10 <span>GAME PICKS</span></h2><p>ML + SPREAD + TOTAL • best verified selections compete together</p></div>
          <div class="tp14-list">{game_cards if game_cards else game_empty}</div>
          {'' if diag.get('game_picks_10_of_10') else game_empty if game_cards else ''}
        </section>
        <section class="tp14-section">
          <div class="tp14-section-head"><h2>TOP 10 <span>PLAYER PROPS</span></h2><p>Best verified Over/Under player selections</p></div>
          <div class="tp14-list">{prop_cards if prop_cards else prop_empty}</div>
          {'' if diag.get('player_props_10_of_10') else prop_empty if prop_cards else ''}
        </section>
        <div class="tp14-foot">Exact sportsbook prices • verified records • no invented slot fillers</div>
      </div>
    </section>
    """


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        with st.spinner("Loading verified CFB Top Picks from Kyre Sports API..."):
            payload = _load_page_payload(_query_date())
    except Exception as exc:
        st.error(
            f"Kyre Sports API Top Picks V3 is temporarily unavailable ({type(exc).__name__}). "
            "No substitute data was inserted."
        )
        return
    st.markdown(_page_html(payload), unsafe_allow_html=True)


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if _clean(market) != "Top Picks":
        raise RuntimeError("CFB Top Picks V14 owns only the Top Picks route")
    render_top_picks_page()


__all__ = [
    "KYRE_SPORTS_API_BASE_URL",
    "MODEL_VERSION",
    "PAGE1_ENDPOINT",
    "PAGE_MARKER",
    "render_cfb_hub",
    "render_top_picks_page",
]
