"""NFL Spread V2 — matchup-board presentation over frozen V1 transport.

Step 6 is presentation-only. Frozen Spread V1 continues to own the verified NFL
slate join, exact ESPN event identity, Kyre Sports API transport, fail-closed
market validation, and sportsbook-context semantics. V2 only reorganizes those
already-certified outputs into a matchup-first board inspired by the certified
Moneyline, Rushing Yards, and Receiving Yards surfaces.

No cover probability, projection model, Monte Carlo, edge, grading, rankings,
stake sizing, or wager actions are introduced here.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_spread_hub_v1 as frozen

MODEL_VERSION = "NFL SPREAD V2 • MATCHUP BOARD PRESENTATION • V1 TRANSPORT FROZEN"
FROZEN_TRANSPORT = "nfl_spread_hub_v1"
PRESENTATION_ONLY = True
MATCHUP_BOARD_FIRST = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = False
MONTE_CARLO_ENABLED = False
RANKINGS_ENABLED = False
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def _safe(value: Any, default: str = "") -> str:
    return frozen._safe(value, default)


def _num(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _market_role(value: Any) -> str:
    line = _num(value)
    if not math.isfinite(line):
        return "LINE UNAVAILABLE"
    if line < 0:
        return "MARKET FAVORITE"
    if line > 0:
        return "UNDERDOG"
    return "PICK'EM"


def _role_class(value: Any) -> str:
    role = _market_role(value)
    if role == "MARKET FAVORITE":
        return "favorite"
    if role == "UNDERDOG":
        return "underdog"
    if role == "PICK'EM":
        return "pickem"
    return "off"


def _team_panel(game: dict[str, Any], side: str, book: dict[str, Any], ready: bool) -> str:
    team = _safe(game.get(f"{side}_team"), side.title())
    abbr = _safe(game.get(f"{side}_abbr"), "NFL").upper()
    record = _safe(game.get(f"{side}_record"), "—")
    line_value = book.get(f"{side}_spread") if ready else None
    price_value = book.get(f"{side}_price") if ready else None
    line = frozen.market_api.fmt_spread(line_value) if ready else "—"
    price = frozen.market_api.fmt_american(price_value) if ready else "—"
    sportsbook = _safe(book.get("sportsbook"), "FanDuel") if ready else "—"
    role = _market_role(line_value) if ready else "LINE UNAVAILABLE"
    role_class = _role_class(line_value) if ready else "off"
    logo = frozen._logo(game.get(f"{side}_logo"), abbr, team)

    return f'''
    <section class="ksp2-team-panel ksp2-{escape(side)}">
      <div class="ksp2-team-head">
        <div class="ksp2-team-id">
          {logo}
          <div><b>{escape(team)}</b><span>{escape(abbr)} • {escape(record)}</span></div>
        </div>
        <span class="ksp2-role {role_class}">{escape(role)}</span>
      </div>
      <div class="ksp2-line-hero">
        <span>FANDUEL SPREAD</span>
        <div><b>{escape(line)}</b><em>{escape(price)}</em></div>
      </div>
      <div class="ksp2-mini-grid">
        <div><span>SPORTSBOOK</span><b>{escape(sportsbook)}</b></div>
        <div><span>MARKET ROLE</span><b>{escape(role.replace('MARKET ', ''))}</b></div>
      </div>
    </section>
    '''


def _matchup_card(game: dict[str, Any], market: dict[str, Any]) -> str:
    event_id = _safe(game.get("game_id"))
    state = _safe(game.get("state"), "pre").lower()
    ready = state == "pre" and bool(market.get("ready"))
    books = market.get("books") or [] if ready else []
    book = books[0] if books else {}

    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    phase = _safe(game.get("season_type"), "NFL")
    tip = _safe(game.get("tip_et"), "TBD")
    venue = _safe(game.get("venue"), "Venue TBD")
    broadcast = _safe(game.get("broadcast"), "—")

    if state != "pre":
        market_label = "PREGAME ONLY"
        market_class = "off"
        context = "Spread transport is intentionally disabled after kickoff."
        freshness = ""
    elif ready:
        market_label = "MARKET READY"
        market_class = "good"
        sportsbook = _safe(book.get("sportsbook"), "FanDuel")
        freshness = frozen._age_text(book.get("age_seconds"))
        context = f"{sportsbook} • active • {freshness}"
    else:
        market_label = "MARKET UNAVAILABLE"
        market_class = "bad"
        freshness = ""
        context = _safe(market.get("reason"), "Certified pregame Spread market is unavailable.")

    return f'''
    <article class="ksp2-matchup-card" data-event-id="{escape(event_id, quote=True)}">
      <div class="ksp2-matchup-top">
        <div class="ksp2-matchup-copy">
          <span class="ksp2-phase">{escape(phase)}</span>
          <b>{escape(away)} <em>@</em> {escape(home)}</b>
          <small>🕒 {escape(tip)} &nbsp; • &nbsp; 🏟️ {escape(venue)} &nbsp; • &nbsp; 📺 {escape(broadcast)}</small>
        </div>
        <div class="ksp2-health">
          <span class="{market_class}">{escape(market_label)}</span>
          <span class="good">EXACT ID</span>
          <span class="neutral">MODEL OFF</span>
          <span class="neutral">MC OFF</span>
        </div>
      </div>
      <div class="ksp2-team-grid">
        {_team_panel(game, 'away', book, ready)}
        <div class="ksp2-vs">VS</div>
        {_team_panel(game, 'home', book, ready)}
      </div>
      <div class="ksp2-market-footer {market_class}">
        <div><span>CERTIFIED MARKET CONTEXT</span><b>{escape(context)}</b></div>
        <small>ESPN event {escape(event_id)} • sportsbook projection influence 0.0% • no recommendation math in V2</small>
      </div>
    </article>
    '''


def _summary_html(*, games: int, upcoming: int, available: int) -> str:
    if upcoming > 0 and available == upcoming:
        market = "READY"
        market_class = "good"
    elif available > 0:
        market = f"{available}/{upcoming} READY"
        market_class = "watch"
    else:
        market = "UNAVAILABLE" if upcoming else "NO PREGAME"
        market_class = "bad" if upcoming else "neutral"

    return f'''
    <div class="ksp2-summary">
      <div><span>GAMES</span><b>{games}</b><small>{upcoming} pregame</small></div>
      <div><span>MARKET</span><b class="{market_class}">{escape(market)}</b><small>{available}/{upcoming} certified</small></div>
      <div><span>MODEL</span><b>OFF</b><small>Step 7</small></div>
      <div><span>MONTE CARLO</span><b>OFF</b><small>Step 7</small></div>
    </div>
    '''


_CSS = r'''
<style>
.ksp2-page{max-width:1180px;margin:0 auto}.ksp2-hero{border:1px solid rgba(56,189,248,.32);border-radius:20px;background:radial-gradient(circle at 88% 12%,rgba(45,212,191,.12),transparent 32%),linear-gradient(145deg,#0d1b2a,#08121d 64%);padding:17px 18px;margin:7px 0 14px;overflow:hidden;box-shadow:0 12px 34px rgba(0,0,0,.14)}.ksp2-eyebrow{font-size:.57rem;font-weight:950;letter-spacing:.12em;color:#7dd3fc;text-transform:uppercase}.ksp2-title{font-size:1.42rem;font-weight:950;color:#f8fafc;letter-spacing:-.02em;margin-top:3px}.ksp2-title span{color:#7ff2c2}.ksp2-sub{font-size:.72rem;line-height:1.5;color:#91a6ba;margin-top:5px;max-width:880px}.ksp2-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.ksp2-chip,.ksp2-health span,.ksp2-role{border:1px solid #284c67;background:#091a29;color:#9ddcf6;border-radius:999px;padding:4px 7px;font-size:.51rem;font-weight:900;white-space:nowrap}.ksp2-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0 13px}.ksp2-summary>div{border:1px solid #203c52;border-radius:12px;background:linear-gradient(180deg,#0a1724,#08131e);padding:10px 11px;min-width:0}.ksp2-summary span,.ksp2-line-hero>span,.ksp2-mini-grid span,.ksp2-market-footer span{display:block;color:#7089a0;font-size:.49rem;font-weight:950;letter-spacing:.07em}.ksp2-summary b{display:block;color:#f5f9fd;font-size:.92rem;margin-top:3px}.ksp2-summary small{display:block;color:#61798f;font-size:.52rem;margin-top:2px}.ksp2-summary b.good,.ksp2-health .good,.ksp2-market-footer.good b{color:#79efbd}.ksp2-summary b.watch,.ksp2-health .watch{color:#f2d77b}.ksp2-summary b.bad,.ksp2-health .bad,.ksp2-market-footer.bad b{color:#f5a0ac}.ksp2-health .neutral{color:#9fb3c6}.ksp2-matchup-card{border:1px solid #2b5574;border-radius:19px;background:linear-gradient(180deg,#091724,#07111b);padding:13px;margin:12px 0;box-shadow:0 10px 28px rgba(0,0,0,.16);overflow:hidden}.ksp2-matchup-top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;border-bottom:1px solid #17324a;padding-bottom:10px}.ksp2-matchup-copy{display:flex;flex-direction:column;min-width:0}.ksp2-phase{color:#7ff2c2;font-size:.51rem;font-weight:950;text-transform:uppercase}.ksp2-matchup-copy>b{color:#f7fbff;font-size:1.03rem;margin-top:3px}.ksp2-matchup-copy em{font-style:normal;color:#68859e;font-size:.72rem}.ksp2-matchup-copy small{color:#748da4;font-size:.54rem;margin-top:4px;white-space:normal}.ksp2-health{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}.ksp2-team-grid{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:9px;align-items:stretch;margin-top:10px}.ksp2-team-panel{border:1px solid #203f59;border-radius:15px;background:linear-gradient(180deg,#0b1a29,#091522);padding:12px;min-width:0}.ksp2-team-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.ksp2-team-id{display:flex;align-items:center;gap:9px;min-width:0}.ksp2-team-id .kspread-logo,.ksp2-team-id .kspread-logo-fallback{width:48px;height:48px;flex:0 0 48px}.ksp2-team-id>div{display:flex;flex-direction:column;min-width:0}.ksp2-team-id b{color:#f8fafc;font-size:.88rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ksp2-team-id span{color:#71899f;font-size:.56rem;margin-top:2px}.ksp2-role{align-self:flex-start}.ksp2-role.favorite{border-color:#397d68;color:#79efbd}.ksp2-role.underdog{border-color:#806d2e;color:#f2d77b}.ksp2-role.pickem{border-color:#365d7a;color:#9ddcf6}.ksp2-role.off{border-color:#5b4650;color:#c9a3ad}.ksp2-line-hero{border:1px solid #274b65;border-radius:12px;background:rgba(6,20,33,.72);padding:10px 11px;margin-top:11px}.ksp2-line-hero>div{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-top:3px}.ksp2-line-hero b{color:#7dd3fc;font-size:1.72rem;line-height:1;font-weight:950}.ksp2-line-hero em{font-style:normal;color:#d7e4ef;font-size:.78rem;font-weight:900}.ksp2-mini-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:8px}.ksp2-mini-grid>div{border:1px solid #19354c;border-radius:10px;padding:7px 8px;background:#081521;min-width:0}.ksp2-mini-grid b{display:block;color:#dae6f0;font-size:.65rem;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ksp2-vs{align-self:center;color:#5f7b94;border:1px solid #29455c;background:#07131e;border-radius:999px;width:34px;height:34px;display:flex;align-items:center;justify-content:center;font-size:.52rem;font-weight:950}.ksp2-market-footer{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;border-top:1px solid #17324a;margin-top:10px;padding-top:9px}.ksp2-market-footer>div{min-width:0}.ksp2-market-footer b{display:block;color:#dce8f2;font-size:.66rem;margin-top:3px;white-space:normal}.ksp2-market-footer small{color:#607a91;font-size:.51rem;text-align:right;max-width:48%}.ksp2-market-footer.off b{color:#b7c4d0}.ksp2-market-footer.bad b{color:#f5a0ac}
@media(max-width:760px){.ksp2-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.ksp2-matchup-top{flex-direction:column}.ksp2-health{justify-content:flex-start}.ksp2-team-grid{grid-template-columns:1fr}.ksp2-vs{margin:0 auto}.ksp2-market-footer{align-items:flex-start;flex-direction:column}.ksp2-market-footer small{text-align:left;max-width:none}.ksp2-title{font-size:1.28rem}}
</style>
'''


def render_nfl_hub(market: str = "Spread") -> None:
    if str(market or "") != "Spread":
        raise RuntimeError("NFL Spread V2 only owns the Spread route.")

    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="ksp2-page"><section class="ksp2-hero">'
        '<div class="ksp2-eyebrow">NFL • certified spread market</div>'
        '<div class="ksp2-title">🎯 NFL Spread <span>Matchup Board</span></div>'
        '<div class="ksp2-sub">Pregame matchup cards • verified ESPN identity • certified FanDuel spreads • market-only context. Projection model, Monte Carlo, rankings, staking and wager actions remain OFF until the next certified build step.</div>'
        '<div class="ksp2-chips">'
        '<span class="ksp2-chip">PREGAME ONLY</span>'
        '<span class="ksp2-chip">KYRE SPORTS API</span>'
        '<span class="ksp2-chip">FANDUEL</span>'
        '<span class="ksp2-chip">EXACT ESPN ID</span>'
        '<span class="ksp2-chip">V1 TRANSPORT FROZEN</span>'
        '<span class="ksp2-chip">MODEL OFF</span>'
        '</div></section></div>',
        unsafe_allow_html=True,
    )

    if "nfl_v1_date" not in st.session_state:
        st.session_state["nfl_v1_date"] = datetime.now(frozen.base.ET).date()
    selected = st.date_input(
        "📅 NFL Spread date",
        value=st.session_state["nfl_v1_date"],
        key="nfl_spread_v2_date_input",
    )
    st.session_state["nfl_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Verifying NFL slate…"):
        games, diag = frozen.base.load_nfl_slate(day_str)

    if not diag.get("request_ok"):
        st.error(
            "NFL schedule provider did not return a usable slate. Spread stays fail-closed and no fake games or lines are created. "
            f"Provider: {diag.get('provider')} • HTTP: {diag.get('http') or '—'}"
        )
        return

    with st.spinner("🔌 Loading certified NFL Spread markets…"):
        markets = frozen._fetch_markets(games)

    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0
    available = sum(1 for item in markets.values() if item.get("ready"))

    st.markdown(
        _summary_html(games=int(len(games)), upcoming=upcoming, available=available),
        unsafe_allow_html=True,
    )
    st.caption(
        f"✅ Verified NFL schedule • {day_str} • {diag.get('provider')} • {len(games)} game(s) • "
        f"{available}/{upcoming} pregame Spread market(s) certified • sportsbook projection influence 0.0%"
    )

    try:
        st.session_state["nfl_spread_v2_last"] = {
            "version": MODEL_VERSION,
            "date": day_str,
            "games": int(len(games)),
            "pregame_games": upcoming,
            "market_ready": available,
            "frozen_transport": FROZEN_TRANSPORT,
            "presentation_only": True,
            "projection_model_enabled": False,
            "monte_carlo_enabled": False,
            "sportsbook_projection_influence": 0.0,
            "stake_sizing_enabled": False,
            "wager_actions_enabled": False,
        }
    except Exception:
        pass

    if games.empty:
        st.info("No verified NFL games were returned for this date.")
        return

    cards: list[str] = []
    for _, row in games.iterrows():
        game = row.to_dict()
        event_id = _safe(game.get("game_id"))
        market_state = markets.get(event_id) or {
            "ready": False,
            "reason": "Pregame Spread market was not requested for this game state.",
            "books": [],
            "projection_weight": 0.0,
        }
        cards.append(_matchup_card(game, market_state))

    st.markdown('<div class="ksp2-page">' + "".join(cards) + "</div>", unsafe_allow_html=True)

    with st.expander("🔒 Spread V2 presentation contract", expanded=False):
        st.write(
            {
                "page_version": MODEL_VERSION,
                "frozen_transport": FROZEN_TRANSPORT,
                "verified_slate_owner": frozen.FROZEN_SLATE_OWNER,
                "market_owner": frozen.MARKET_OWNER,
                "official_event_identity": "ESPN game_id only",
                "fuzzy_matching": False,
                "synthetic_event_ids": False,
                "sportsbook_projection_influence": 0.0,
                "presentation_only": True,
                "projection_model": "OFF",
                "monte_carlo": "OFF",
                "rankings_recommendations": "OFF",
                "stake_sizing": "OFF",
                "wager_actions": "OFF",
            }
        )


__all__ = [
    "FROZEN_TRANSPORT",
    "MATCHUP_BOARD_FIRST",
    "MODEL_VERSION",
    "MONTE_CARLO_ENABLED",
    "PRESENTATION_ONLY",
    "PROJECTION_MODEL_ENABLED",
    "RANKINGS_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_market_role",
    "_matchup_card",
    "_role_class",
    "_summary_html",
    "_team_panel",
    "render_nfl_hub",
]
