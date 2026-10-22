"""CFB Top Picks V15 — polished simple Page 1 decision board."""
from __future__ import annotations

from datetime import datetime
from html import escape
import json
import os
from textwrap import dedent
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st

MODEL_VERSION = "CFB TOP PICKS V15 • CLEAN SIMPLE DECISION BOARD"
PAGE_MARKER = "CFB_TOP_PICKS_V15_CLEAN_PAGE1_ACTIVE"
PAGE1_ENDPOINT = "/api/v4/cfb/top-picks/page1"
KYRE_SPORTS_API_BASE_URL = os.getenv("KYRE_SPORTS_API_BASE_URL", "https://kyre-sports-api.vercel.app").rstrip("/")
PHOENIX = ZoneInfo("America/Phoenix")

CSS = r"""
<style id="cfb-top-picks-v15-css">
:root{--bg:#050b12;--panel:#081522;--line:rgba(93,195,255,.18);--blue:#30baff;--text:#f3f9fd;--muted:#7f98aa;--green:#6be3ad;--gold:#ffd278}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 60% -10%,rgba(33,151,222,.13),transparent 36%),#050a10}
[data-testid="cfb-top-picks-v15-root"]{max-width:1120px;margin:0 auto;padding:8px 2px 44px;color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.tp15-shell{border:1px solid var(--line);border-radius:22px;background:linear-gradient(150deg,rgba(8,26,41,.99),rgba(4,12,21,.995));overflow:hidden;box-shadow:0 24px 72px rgba(0,0,0,.28)}
.tp15-head{padding:22px 24px 19px;border-bottom:1px solid rgba(255,255,255,.06)}.tp15-brand{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:16px}.tp15-brand b{font-size:.72rem;letter-spacing:.16em}.tp15-live{font-size:.6rem;color:#a2b7c5;font-weight:850}.tp15-live:before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);margin-right:7px;box-shadow:0 0 12px rgba(107,227,173,.65)}
.tp15-title{display:flex;justify-content:space-between;align-items:end;gap:18px}.tp15-title h1{margin:0;font-size:2.12rem;letter-spacing:-.05em;font-weight:950}.tp15-title p{margin:5px 0 0;color:#8ba2b2;font-size:.72rem}.tp15-date{border:1px solid rgba(82,190,255,.24);border-radius:10px;padding:7px 10px;color:#9fcce8;font-size:.62rem;font-weight:850;white-space:nowrap;background:rgba(17,79,113,.15)}
.tp15-section{padding:18px 24px 5px}.tp15-section+.tp15-section{padding-top:25px}.tp15-section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:10px}.tp15-section-head h2{margin:0;font-size:.92rem;letter-spacing:.02em}.tp15-section-head h2 span{color:var(--blue)}.tp15-section-head p{margin:0;color:#71899b;font-size:.55rem}.tp15-list{display:grid;gap:8px}
.tp15-card{display:grid;grid-template-columns:42px minmax(240px,1.18fr) minmax(210px,1fr) 108px 115px;gap:12px;align-items:center;text-decoration:none!important;color:inherit!important;padding:11px 12px;border:1px solid rgba(82,178,232,.14);border-radius:13px;background:linear-gradient(90deg,rgba(7,25,39,.96),rgba(7,19,31,.97));transition:.14s ease}.tp15-card:hover{transform:translateY(-1px);border-color:rgba(76,194,255,.35);background:linear-gradient(90deg,rgba(8,31,49,.98),rgba(7,21,34,.98))}
.tp15-rank{width:32px;height:32px;display:grid;place-items:center;border-radius:9px;background:rgba(42,178,244,.12);color:#69cfff;font-weight:950;font-size:.72rem}.tp15-rank:before{content:"#";font-size:.52rem;margin-right:1px;color:#548aa8}
.tp15-matchup,.tp15-player{display:flex;align-items:center;gap:10px;min-width:0}.tp15-logo{width:36px;height:36px;border-radius:9px;object-fit:contain;background:rgba(255,255,255,.035);padding:3px;border:1px solid rgba(255,255,255,.07)}.tp15-logo.fallback{display:grid;place-items:center;color:#d9eaf3;font-size:.58rem;font-weight:900}.tp15-vs{font-size:.52rem;color:#668094;font-weight:900}.tp15-teamcopy{min-width:0}.tp15-teamcopy b,.tp15-player-copy b{display:block;color:#f7fbfe;font-size:.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp15-teamcopy small,.tp15-player-copy small{display:block;color:#8198a9;font-size:.58rem;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp15-records{color:#88a1b2!important}
.tp15-avatar{width:44px;height:44px;border-radius:12px;object-fit:cover;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08)}.tp15-player-team{width:26px;height:26px;border-radius:7px;object-fit:contain;background:rgba(255,255,255,.04);padding:2px;margin-left:-18px;margin-top:26px;border:1px solid rgba(255,255,255,.1)}
.tp15-selection{min-width:0}.tp15-badge{display:inline-block;border-radius:6px;padding:3px 6px;background:rgba(45,185,255,.11);color:#58caff;font-size:.5rem;font-weight:950;letter-spacing:.05em;margin-bottom:4px}.tp15-selection strong{display:block;color:#f5fbff;font-size:.84rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tp15-selection small{display:block;color:#849aab;font-size:.58rem;margin-top:4px}.tp15-book{color:#a9c4d5!important}.tp15-prob{text-align:right}.tp15-prob b{display:block;color:#f8fbfd;font-size:1.08rem}.tp15-prob span{display:block;color:#698295;font-size:.49rem;font-weight:900;margin-top:2px}.tp15-meta{text-align:right}.tp15-meta .slate{display:inline-block;border:1px solid rgba(255,210,120,.24);border-radius:6px;padding:2px 5px;color:var(--gold);font-size:.48rem;font-weight:950;margin-bottom:4px}.tp15-meta b{display:block;color:#cfe2ed;font-size:.66rem}.tp15-tap{display:block;color:#5cbef1!important;font-size:.5rem!important;margin-top:4px}.tp15-empty{padding:13px;border:1px solid rgba(255,207,94,.18);border-radius:11px;background:rgba(92,64,14,.11);color:#e6c66e;font-size:.65rem}.tp15-foot{padding:15px 24px 18px;color:#567285;font-size:.52rem;text-align:center}
@media(max-width:900px){.tp15-card{grid-template-columns:38px minmax(0,1fr) 96px}.tp15-selection{grid-column:2/4}.tp15-meta{grid-column:2/4;display:flex;justify-content:space-between;align-items:center;text-align:left;border-top:1px solid rgba(255,255,255,.05);padding-top:7px}.tp15-meta b,.tp15-meta .slate,.tp15-tap{display:inline-block;margin:0}.tp15-prob{text-align:right}}
@media(max-width:600px){.tp15-head,.tp15-section{padding-left:13px;padding-right:13px}.tp15-title,.tp15-section-head{align-items:flex-start;flex-direction:column}.tp15-title h1{font-size:1.8rem}.tp15-card{grid-template-columns:34px minmax(0,1fr) 82px;gap:8px;padding:10px 9px}.tp15-logo{width:32px;height:32px}.tp15-matchup{gap:7px}.tp15-teamcopy b,.tp15-player-copy b{font-size:.72rem}.tp15-selection strong{font-size:.76rem}.tp15-prob b{font-size:.96rem}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_html(value: str) -> str:
    return dedent(value).strip()


def _initials(name: str) -> str:
    return "".join(part[:1].upper() for part in _clean(name).split()[:2]) or "—"


def _logo(url: Any, name: str, *, cls: str = "tp15-logo") -> str:
    value = _clean(url)
    label = escape(name or "team")
    if value.startswith("https://"):
        return f'<img class="{cls}" src="{escape(value, quote=True)}" alt="{label} logo" loading="lazy">'
    return f'<span class="{cls} fallback" aria-label="{label} logo unavailable">{escape(_initials(name))}</span>'


def _record(value: Any) -> str:
    text = _clean(value)
    return "Record unavailable" if not text or text in {"NOT_AVAILABLE", "DATA_UNAVAILABLE"} else text


def _odds(value: Any) -> str:
    try:
        number = int(value)
        return f"+{number}" if number > 0 else str(number)
    except Exception:
        return "Unavailable"


def _prob(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "—"


def _game_time(value: Any) -> str:
    text = _clean(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return text
        return parsed.astimezone(PHOENIX).strftime("%-I:%M %p AZ")
    except Exception:
        return text or "Time unavailable"


def _slate_badge(value: Any) -> str:
    text = _clean(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(PHOENIX)
        today = datetime.now(PHOENIX).date()
        if parsed.date() == today:
            return "TODAY"
        if (parsed.date() - today).days == 1:
            return "TOMORROW"
        return parsed.strftime("%a %b %-d").upper()
    except Exception:
        return "VERIFIED SLATE"


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
        query["top_pick_player_id"] = _clean(row.get("player_id"))
        query["top_pick_line"] = _clean(row.get("line"))
    return "?" + urlencode({key: value for key, value in query.items() if value})


def _game_card(row: Mapping[str, Any]) -> str:
    rank = int(row.get("rank") or 0)
    away, home = _clean(row.get("away_team")) or "Away", _clean(row.get("home_team")) or "Home"
    market = _clean(row.get("market_type")).upper()
    badge = "ML" if market == "MONEYLINE" else market
    return _safe_html(f"""
    <a class="tp15-card" href="{escape(_handoff(row, 'game-pick'))}" data-testid="top-game-pick-{rank}">
      <div class="tp15-rank">{rank}</div>
      <div class="tp15-matchup">
        {_logo(row.get('away_logo'), away)}
        <div class="tp15-teamcopy"><b>{escape(away)}</b><small class="tp15-records">{escape(_record(row.get('away_record')))}</small></div>
        <span class="tp15-vs">@</span>
        {_logo(row.get('home_logo'), home)}
        <div class="tp15-teamcopy"><b>{escape(home)}</b><small class="tp15-records">{escape(_record(row.get('home_record')))}</small></div>
      </div>
      <div class="tp15-selection"><span class="tp15-badge">{escape(badge)}</span><strong>{escape(_clean(row.get('selection')))}</strong><small class="tp15-book">{escape(_clean(row.get('sportsbook')))} • {escape(_odds(row.get('american_odds')))}</small></div>
      <div class="tp15-prob"><b>{escape(_prob(row.get('probability')))}</b><span>HIT PROBABILITY</span></div>
      <div class="tp15-meta"><span class="slate">{escape(_slate_badge(row.get('kickoff_iso')))}</span><b>{escape(_game_time(row.get('kickoff_iso')))}</b><small class="tp15-tap">Tap for full analysis →</small></div>
    </a>
    """)


def _prop_card(row: Mapping[str, Any]) -> str:
    rank = int(row.get("rank") or 0)
    player = _clean(row.get("player_name")) or "Player"
    team = _clean(row.get("player_team")) or "Team unavailable"
    opponent = _clean(row.get("opponent"))
    position, jersey = _clean(row.get("position")), _clean(row.get("jersey_number"))
    player_id = _clean(row.get("player_id"))
    identity_parts = [part for part in (position, f"#{jersey}" if jersey else "", team) if part]
    if player_id:
        identity_parts.append(f"ID {player_id}")
    identity = " • ".join(identity_parts) if identity_parts else "Official roster data unavailable"
    avatar = _clean(row.get("player_headshot")) or _clean(row.get("player_team_logo"))
    avatar_html = _logo(avatar, player, cls="tp15-avatar")
    team_logo = _logo(row.get("player_team_logo"), team, cls="tp15-player-team")
    line = row.get("line")
    try:
        selection = f"{_clean(row.get('side')).upper()} {float(line):g}"
    except Exception:
        selection = _clean(row.get("side")).upper()
    market = _clean(row.get("market_label") or row.get("market_key")).replace("_", " ").title()
    matchup = f"vs {opponent}" if opponent else "Opponent unavailable"
    return _safe_html(f"""
    <a class="tp15-card" href="{escape(_handoff(row, 'player-prop'))}" data-testid="top-player-prop-{rank}">
      <div class="tp15-rank">{rank}</div>
      <div class="tp15-player">
        {avatar_html}{team_logo}
        <div class="tp15-player-copy"><b>{escape(player)}</b><small>{escape(identity)}</small><small class="tp15-records">{escape(matchup)}</small></div>
      </div>
      <div class="tp15-selection"><span class="tp15-badge">PROP</span><strong>{escape(market)} • {escape(selection)}</strong><small class="tp15-book">{escape(_clean(row.get('sportsbook')))} • {escape(_odds(row.get('american_odds')))}</small></div>
      <div class="tp15-prob"><b>{escape(_prob(row.get('probability')))}</b><span>HIT PROBABILITY</span></div>
      <div class="tp15-meta"><span class="slate">{escape(_slate_badge(row.get('kickoff_iso')))}</span><b>{escape(_game_time(row.get('kickoff_iso')))}</b><small class="tp15-tap">Tap for full analysis →</small></div>
    </a>
    """)


def _page_html(payload: Mapping[str, Any]) -> str:
    game_picks = [dict(row) for row in payload.get("game_picks") or [] if isinstance(row, Mapping)]
    props = [dict(row) for row in payload.get("player_props") or [] if isinstance(row, Mapping)]
    selected = _clean(payload.get("selected_date")) or "Verified slate"
    game_cards = "".join(_game_card(row) for row in game_picks)
    prop_cards = "".join(_prop_card(row) for row in props)
    game_empty = '<div class="tp15-empty">Verified inventory is below 10 after approved fallbacks; no fake game selection was inserted.</div>'
    prop_empty = '<div class="tp15-empty">Verified inventory is below 10 after approved fallbacks; no fake player prop was inserted.</div>'
    return _safe_html(f"""
    <section data-testid="cfb-top-picks-v15-root" data-page-marker="{PAGE_MARKER}">
      <div class="tp15-shell">
        <header class="tp15-head">
          <div class="tp15-brand"><b>KYRE SPORTS • CFB</b><span class="tp15-live">KYRE SPORTS API LIVE</span></div>
          <div class="tp15-title"><div><h1>TOP PICKS</h1><p>Today's best verified CFB bets. Tap any pick for the full analytics lab.</p></div><span class="tp15-date">{escape(selected)}</span></div>
        </header>
        <section class="tp15-section">
          <div class="tp15-section-head"><h2>TOP 10 <span>GAME PICKS</span></h2><p>Moneyline + spread + totals compete together</p></div>
          <div class="tp15-list">{game_cards or game_empty}</div>
        </section>
        <section class="tp15-section">
          <div class="tp15-section-head"><h2>TOP 10 <span>PLAYER PROPS</span></h2><p>Verified player identity + sportsbook-specific price</p></div>
          <div class="tp15-list">{prop_cards or prop_empty}</div>
        </section>
        <footer class="tp15-foot">Kyre Sports API • verified CFB identity • sportsbook-specific lines • no fabricated fields</footer>
      </div>
    </section>
    """)


def render_cfb_hub(_market_name: str = "Top Picks") -> None:
    st.markdown(_safe_html(CSS), unsafe_allow_html=True)
    try:
        payload = _load_page_payload(_query_date())
    except Exception as exc:
        st.error(f"Top Picks data is temporarily unavailable ({type(exc).__name__}).")
        return
    st.markdown(_page_html(payload), unsafe_allow_html=True)


__all__ = ["MODEL_VERSION", "PAGE1_ENDPOINT", "PAGE_MARKER", "_game_card", "_page_html", "_prop_card", "render_cfb_hub"]
