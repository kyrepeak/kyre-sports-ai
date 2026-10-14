"""NBA Spread Page 1 — Step 6 verified market spread context.

Preserves frozen Steps 1–5, then adds one fail-closed sportsbook spread market
layer with consensus and best-available context. Injury, projection, probability,
and ranking layers remain deferred.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from nba_spread_most_bet_v1 import load_most_bet_feature
from nba_spread_schedule_v1 import load_verified_nba_schedule
from nba_spread_sharp_money_v1 import SHARP_MONEY_LABEL, load_sharp_money_feature
from nba_spread_market_lines_v1 import MARKET_SECTION_LABEL, load_spread_market_features

MODEL_VERSION = "NBA_SPREAD_PAGE_V1_STEP6_MARKET_LINES"
PAGE_HEARTBEAT = "NBA_SPREAD_STEP4_MOST_BET_FEATURE_ACTIVE"
STEP3_HEARTBEAT = "NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_ACTIVE"
STEP5_HEARTBEAT = "NBA_SPREAD_STEP5_SHARP_MONEY_ACTIVE"
STEP6_HEARTBEAT = "NBA_SPREAD_STEP6_MARKET_LINES_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False


@st.cache_data(ttl=90, show_spinner=False)
def _load_verified_schedule() -> dict:
    return load_verified_nba_schedule()


@st.cache_data(ttl=300, show_spinner=False)
def _load_most_bet(games: list[dict]) -> dict:
    return load_most_bet_feature(games)


@st.cache_data(ttl=300, show_spinner=False)
def _load_sharp_money(games: list[dict]) -> dict:
    return load_sharp_money_feature(games)


@st.cache_data(ttl=90, show_spinner=False)
def _load_market_lines(games: list[dict]) -> dict:
    return load_spread_market_features(games)


def _game_card(game: dict) -> str:
    away = escape(str(game.get("away_tricode") or "—"))
    home = escape(str(game.get("home_tricode") or "—"))
    away_name = escape(str(game.get("away_name") or away))
    home_name = escape(str(game.get("home_name") or home))
    tip = escape(str(game.get("tip_phoenix") or "Time unavailable"))
    date = escape(str(game.get("game_date_phoenix") or "Date unavailable"))
    status = escape(str(game.get("status") or "UPCOMING"))
    venue = escape(str(game.get("venue") or ""))
    venue_line = f'<div style="font-size:.72rem;color:#70849a;margin-top:5px">{venue}</div>' if venue else ""
    return f"""
<div data-testid="nba-spread-step3-game-card" style="border:1px solid rgba(103,216,255,.18);border-radius:18px;
background:linear-gradient(145deg,#0a121e,#0e1b2b);padding:15px 16px;margin:0 0 10px">
  <div style="display:flex;justify-content:space-between;gap:12px;align-items:center">
    <div>
      <div style="font-size:.7rem;font-weight:900;letter-spacing:.1em;color:#67d8ff">{status}</div>
      <div style="font-size:1rem;font-weight:900;color:#f8fafc;margin-top:4px">{away} @ {home}</div>
      <div style="font-size:.76rem;color:#91a4b8;margin-top:3px">{away_name} at {home_name}</div>
      {venue_line}
    </div>
    <div style="text-align:right;white-space:nowrap">
      <div style="font-size:.88rem;font-weight:900;color:#f8fafc">{tip}</div>
      <div style="font-size:.7rem;color:#7f93a8;margin-top:3px">{date} • Phoenix</div>
    </div>
  </div>
  <div style="font-size:.68rem;color:#688197;margin-top:10px">Verified: NBA Official + ESPN NBA</div>
</div>
"""


def _most_bet_card(feature: dict) -> str:
    away = escape(str(feature.get("away_tricode") or "—"))
    home = escape(str(feature.get("home_tricode") or "—"))
    away_name = escape(str(feature.get("away_name") or away))
    home_name = escape(str(feature.get("home_name") or home))
    tip = escape(str(feature.get("tip_phoenix") or "Time unavailable"))
    date = escape(str(feature.get("game_date_phoenix") or "Date unavailable"))
    bet_count = int(feature.get("bet_count") or 0)
    away_bets = int(feature.get("away_bet_pct") or 0)
    home_bets = int(feature.get("home_bet_pct") or 0)
    away_money = int(feature.get("away_money_pct") or 0)
    home_money = int(feature.get("home_money_pct") or 0)
    return f"""
<div data-testid="nba-spread-step4-most-bet-card" style="border:1px solid rgba(103,216,255,.42);border-radius:22px;
background:linear-gradient(140deg,rgba(8,18,31,.99),rgba(12,42,67,.97));padding:18px 18px 16px;margin:14px 0 12px;
box-shadow:0 14px 34px rgba(0,0,0,.22)">
  <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
    <div>
      <div style="font-size:.72rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase;color:#67d8ff">🔥 Most Bet Game</div>
      <div style="font-size:1.25rem;font-weight:950;color:#f8fafc;margin-top:6px">{away} @ {home}</div>
      <div style="font-size:.77rem;color:#91a4b8;margin-top:3px">{away_name} at {home_name}</div>
    </div>
    <div style="text-align:right;white-space:nowrap">
      <div style="font-size:.9rem;font-weight:900;color:#f8fafc">{tip}</div>
      <div style="font-size:.69rem;color:#7f93a8;margin-top:3px">{date} • Phoenix</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px">
    <div style="border:1px solid rgba(148,163,184,.14);border-radius:13px;padding:10px;background:rgba(5,12,20,.45)">
      <div style="font-size:.62rem;color:#7890a5;text-transform:uppercase;font-weight:900">Tracked Bets</div>
      <div style="font-size:1.02rem;color:#f8fafc;font-weight:950;margin-top:3px">{bet_count:,}</div>
    </div>
    <div style="border:1px solid rgba(148,163,184,.14);border-radius:13px;padding:10px;background:rgba(5,12,20,.45)">
      <div style="font-size:.62rem;color:#7890a5;text-transform:uppercase;font-weight:900">% of Bets</div>
      <div style="font-size:.82rem;color:#f8fafc;font-weight:900;margin-top:3px">{away} {away_bets}% • {home} {home_bets}%</div>
    </div>
    <div style="border:1px solid rgba(148,163,184,.14);border-radius:13px;padding:10px;background:rgba(5,12,20,.45)">
      <div style="font-size:.62rem;color:#7890a5;text-transform:uppercase;font-weight:900">% of Money</div>
      <div style="font-size:.82rem;color:#f8fafc;font-weight:900;margin-top:3px">{away} {away_money}% • {home} {home_money}%</div>
    </div>
  </div>
  <div style="font-size:.66rem;color:#688197;margin-top:11px">Volume/splits: Action Network • Matchup/time: verified Step-3 NBA schedule</div>
</div>
"""


def _sharp_money_card(feature: dict) -> str:
    away = escape(str(feature.get("away_tricode") or "—"))
    home = escape(str(feature.get("home_tricode") or "—"))
    tip = escape(str(feature.get("tip_phoenix") or "Time unavailable"))
    date = escape(str(feature.get("game_date_phoenix") or "Date unavailable"))
    sharp_side = escape(str(feature.get("sharp_side_tricode") or "—"))
    sharp_name = escape(str(feature.get("sharp_side_name") or sharp_side))
    sharp_bets = int(feature.get("sharp_bet_pct") or 0)
    sharp_money = int(feature.get("sharp_money_pct") or 0)
    sharp_gap = int(feature.get("sharp_gap_pct") or 0)
    bet_count = int(feature.get("bet_count") or 0)
    return f"""
<div data-testid="nba-spread-step5-sharp-money-card" style="border:1px solid rgba(103,216,255,.34);border-radius:22px;
background:linear-gradient(140deg,rgba(8,18,31,.99),rgba(9,34,52,.97));padding:18px 18px 16px;margin:12px 0;
box-shadow:0 14px 34px rgba(0,0,0,.2)">
  <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
    <div>
      <div style="font-size:.72rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase;color:#67d8ff">{SHARP_MONEY_LABEL}</div>
      <div style="font-size:1.16rem;font-weight:950;color:#f8fafc;margin-top:6px">{away} @ {home}</div>
      <div style="font-size:.76rem;color:#91a4b8;margin-top:3px">Signal side: {sharp_name} ({sharp_side})</div>
    </div>
    <div style="text-align:right;white-space:nowrap">
      <div style="font-size:.9rem;font-weight:900;color:#f8fafc">{tip}</div>
      <div style="font-size:.69rem;color:#7f93a8;margin-top:3px">{date} • Phoenix</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px">
    <div style="border:1px solid rgba(148,163,184,.14);border-radius:13px;padding:10px;background:rgba(5,12,20,.45)">
      <div style="font-size:.62rem;color:#7890a5;text-transform:uppercase;font-weight:900">Bets → Money</div>
      <div style="font-size:.9rem;color:#f8fafc;font-weight:950;margin-top:3px">{sharp_bets}% → {sharp_money}%</div>
    </div>
    <div style="border:1px solid rgba(148,163,184,.14);border-radius:13px;padding:10px;background:rgba(5,12,20,.45)">
      <div style="font-size:.62rem;color:#7890a5;text-transform:uppercase;font-weight:900">Divergence</div>
      <div style="font-size:1.02rem;color:#f8fafc;font-weight:950;margin-top:3px">+{sharp_gap} pts</div>
    </div>
    <div style="border:1px solid rgba(148,163,184,.14);border-radius:13px;padding:10px;background:rgba(5,12,20,.45)">
      <div style="font-size:.62rem;color:#7890a5;text-transform:uppercase;font-weight:900">Tracked Bets</div>
      <div style="font-size:1.02rem;color:#f8fafc;font-weight:950;margin-top:3px">{bet_count:,}</div>
    </div>
  </div>
</div>
"""


def _market_lines_card(feature: dict) -> str:
    away = escape(str(feature.get("away_tricode") or "—"))
    home = escape(str(feature.get("home_tricode") or "—"))
    tip = escape(str(feature.get("tip_phoenix") or "Time unavailable"))
    date = escape(str(feature.get("game_date_phoenix") or "Date unavailable"))
    ca = float(feature.get("consensus_away_spread") or 0.0)
    ch = float(feature.get("consensus_home_spread") or 0.0)
    ba = dict(feature.get("best_away") or {})
    bh = dict(feature.get("best_home") or {})
    books = int(feature.get("sportsbook_count") or 0)
    return f"""
<div data-testid="nba-spread-step6-market-lines-card" style="border:1px solid rgba(103,216,255,.30);border-radius:22px;
background:linear-gradient(140deg,rgba(8,18,31,.99),rgba(10,31,49,.97));padding:18px;margin:12px 0">
  <div style="display:flex;justify-content:space-between;gap:12px">
    <div>
      <div style="font-size:.72rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase;color:#67d8ff">{MARKET_SECTION_LABEL}</div>
      <div style="font-size:1.16rem;font-weight:950;color:#f8fafc;margin-top:6px">{away} @ {home}</div>
    </div>
    <div style="text-align:right"><div style="font-size:.9rem;font-weight:900;color:#f8fafc">{tip}</div><div style="font-size:.69rem;color:#7f93a8">{date} • Phoenix</div></div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:14px">
    <div style="border:1px solid rgba(148,163,184,.14);border-radius:13px;padding:10px;background:rgba(5,12,20,.45)">
      <div style="font-size:.62rem;color:#7890a5;text-transform:uppercase;font-weight:900">Consensus Spread</div>
      <div style="font-size:.86rem;color:#f8fafc;font-weight:950;margin-top:3px">{away} {ca:+g} • {home} {ch:+g}</div>
      <div style="font-size:.62rem;color:#688197;margin-top:3px">{books} independent books</div>
    </div>
    <div style="border:1px solid rgba(148,163,184,.14);border-radius:13px;padding:10px;background:rgba(5,12,20,.45)">
      <div style="font-size:.62rem;color:#7890a5;text-transform:uppercase;font-weight:900">Best Available</div>
      <div style="font-size:.78rem;color:#f8fafc;font-weight:900;margin-top:3px">{away} {float(ba.get('spread') or 0.0):+g} • {escape(str(ba.get('sportsbook') or '—'))}</div>
      <div style="font-size:.78rem;color:#f8fafc;font-weight:900;margin-top:2px">{home} {float(bh.get('spread') or 0.0):+g} • {escape(str(bh.get('sportsbook') or '—'))}</div>
    </div>
  </div>
</div>
"""


def _render_most_bet(feature: dict) -> None:
    if feature.get("verification") == "VERIFIED":
        st.markdown(_most_bet_card(feature), unsafe_allow_html=True)
        return
    diagnostic = escape(str(feature.get("diagnostic_state") or "SOURCE_UNAVAILABLE"))
    st.markdown(
        f"""
<div data-testid="nba-spread-step4-most-bet-unavailable" style="border:1px dashed rgba(103,216,255,.22);border-radius:16px;
padding:13px 15px;background:#09131f;margin:14px 0 12px">
  <div style="font-size:.78rem;font-weight:900;color:#b9dceb">🔥 Most Bet Game data unavailable</div>
  <div style="font-size:.72rem;color:#7890a5;margin-top:4px">No matchup is promoted unless tracked volume and both betting splits match a verified Step-3 game.</div>
  <div style="font-size:.64rem;color:#61778b;margin-top:6px">{diagnostic}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_sharp_money(feature: dict) -> None:
    if feature.get("verification") == "VERIFIED":
        st.markdown(_sharp_money_card(feature), unsafe_allow_html=True)
        return
    diagnostic = escape(str(feature.get("diagnostic_state") or "SOURCE_UNAVAILABLE"))
    st.markdown(
        f"""
<div data-testid="nba-spread-step5-sharp-money-unavailable" style="border:1px dashed rgba(103,216,255,.22);border-radius:16px;
padding:13px 15px;background:#09131f;margin:12px 0">
  <div style="font-size:.78rem;font-weight:900;color:#b9dceb">{SHARP_MONEY_LABEL} data unavailable</div>
  <div style="font-size:.72rem;color:#7890a5;margin-top:4px">No matchup is promoted unless ticket share, money share, positive authoritative volume, and the verified Step-3 matchup all pass.</div>
  <div style="font-size:.64rem;color:#61778b;margin-top:6px">{diagnostic}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_market_lines(feature: dict) -> None:
    if feature.get("verification") == "VERIFIED":
        st.markdown(_market_lines_card(feature), unsafe_allow_html=True)
        return
    diagnostic = escape(str(feature.get("diagnostic_state") or "SOURCE_UNAVAILABLE"))
    st.markdown(
        f"""
<div data-testid="nba-spread-step6-market-lines-unavailable" style="border:1px dashed rgba(103,216,255,.22);border-radius:16px;
padding:13px 15px;background:#09131f;margin:12px 0">
  <div style="font-size:.78rem;font-weight:900;color:#b9dceb">{MARKET_SECTION_LABEL} data unavailable</div>
  <div style="font-size:.72rem;color:#7890a5;margin-top:4px">Consensus Spread and Best Available require exact verified sportsbook observations from at least two independent books. Nothing is guessed.</div>
  <div style="font-size:.64rem;color:#61778b;margin-top:6px">{diagnostic}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_game_group(title: str, games: list[dict], empty_text: str) -> None:
    st.markdown(
        f'<div style="font-size:.78rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;'
        f'color:#cbd5e1;margin:18px 0 9px">{escape(title)}</div>',
        unsafe_allow_html=True,
    )
    if not games:
        st.markdown(
            f'<div style="border:1px dashed rgba(148,163,184,.18);border-radius:15px;padding:13px 15px;'
            f'color:#7f93a8;font-size:.78rem">{escape(empty_text)}</div>',
            unsafe_allow_html=True,
        )
        return
    for game in games:
        st.markdown(_game_card(game), unsafe_allow_html=True)


def render_nba_spread_page() -> None:
    st.markdown(
        '<div data-testid="nba-spread-step2-active" style="display:none!important"></div>'
        f'<div data-testid="nba-spread-step3-schedule-active" data-heartbeat="{STEP3_HEARTBEAT}" style="display:none!important"></div>'
        f'<div data-testid="nba-spread-step4-most-bet-active" data-heartbeat="{PAGE_HEARTBEAT}" style="display:none!important"></div>'
        f'<div data-testid="nba-spread-step5-sharp-money-active" data-heartbeat="{STEP5_HEARTBEAT}" style="display:none!important"></div>'
        f'<div data-testid="nba-spread-step6-market-lines-active" data-heartbeat="{STEP6_HEARTBEAT}" style="display:none!important"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div style="border:1px solid rgba(56,189,248,.32);border-radius:24px;padding:22px 24px;
background:linear-gradient(135deg,rgba(8,13,22,.98),rgba(15,36,60,.96));margin:8px 0 16px">
  <div style="font-size:.72rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#67d8ff">KYRE SPORTS AI • NBA</div>
  <div style="font-size:clamp(2rem,6vw,3.1rem);font-weight:950;letter-spacing:-.045em;color:#f8fafc;margin-top:5px">🏀 NBA Spread</div>
  <div style="font-size:.88rem;color:#a9b8c8;margin-top:7px">Rolling 7-day schedule • Phoenix, Arizona time</div>
</div>
""",
        unsafe_allow_html=True,
    )

    schedule = _load_verified_schedule()
    if schedule.get("verification") != "VERIFIED":
        diagnostic = escape(str(schedule.get("diagnostic_state") or "SOURCE_UNAVAILABLE"))
        st.markdown(
            f"""
<div data-testid="nba-spread-step3-schedule-unavailable" style="border:1px solid rgba(248,113,113,.28);
border-radius:18px;padding:16px 18px;background:#160e14">
  <div style="font-weight:900;color:#fecaca">Schedule verification unavailable</div>
  <div style="font-size:.78rem;color:#b9a1aa;margin-top:5px">NBA Official and ESPN NBA must agree before this page publishes a slate. Nothing is guessed.</div>
  <div style="font-size:.68rem;color:#846b75;margin-top:8px">{diagnostic}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        return

    games = list(schedule.get("games") or [])
    upcoming = [game for game in games if game.get("status") in {"UPCOMING", "DELAYED"}]
    live_final = [game for game in games if game.get("status") in {"LIVE", "FINAL", "CANCELLED"}]

    window = list(schedule.get("window_dates") or [])
    window_text = " → ".join((window[0], window[-1])) if window else "Rolling Phoenix window"
    st.markdown(
        f"""
<div style="display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid rgba(148,163,184,.13);
border-radius:16px;padding:11px 14px;background:#0a1320">
  <div style="font-size:.76rem;font-weight:850;color:#d7e2ec">Verified 7-Day NBA Slate</div>
  <div style="font-size:.68rem;color:#71869a">{escape(window_text)}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    _render_most_bet(_load_most_bet(games))
    _render_sharp_money(_load_sharp_money(games))
    _render_market_lines(_load_market_lines(games))
    _render_game_group("Upcoming", upcoming, "No verified upcoming NBA games in this Phoenix-time window.")
    _render_game_group("Live / Final", live_final, "No verified live or completed NBA games in this window yet.")


__all__ = [
    "MODEL_VERSION",
    "PAGE_HEARTBEAT",
    "STEP3_HEARTBEAT",
    "STEP5_HEARTBEAT",
    "STEP6_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "render_nba_spread_page",
]
