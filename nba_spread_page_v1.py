"""NBA Spread Page 1 — Step 4 Most Bet Game featured card.

Step 4 preserves the verified Step-3 Phoenix schedule and adds one fail-closed
featured game selected by the highest tracked NBA spread bet count. Injury,
model, probability, edge, ranking, and later decision layers remain deferred.
"""
from __future__ import annotations

from html import escape
import json

import streamlit as st

from nba_spread_most_bet_v1 import MostBetUnavailable, load_most_bet_game
from nba_spread_schedule_v1 import load_verified_nba_schedule

MODEL_VERSION = "NBA_SPREAD_PAGE_V1_STEP4_MOST_BET_GAME"
PAGE_HEARTBEAT = "NBA_SPREAD_STEP4_MOST_BET_GAME_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False


@st.cache_data(ttl=90, show_spinner=False)
def _load_verified_schedule() -> dict:
    return load_verified_nba_schedule()


@st.cache_data(ttl=120, show_spinner=False)
def _load_featured_most_bet(games_json: str) -> dict:
    games = json.loads(games_json)
    return load_most_bet_game(games)


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


def _most_bet_card(featured: dict) -> str:
    away = escape(str(featured.get("away_tricode") or "—"))
    home = escape(str(featured.get("home_tricode") or "—"))
    tip = escape(str(featured.get("tip_phoenix") or "Time unavailable"))
    date = escape(str(featured.get("game_date_phoenix") or "Date unavailable"))
    tracked = int(featured.get("tracked_bets") or 0)
    bet_pct = list(featured.get("bet_pct") or [0, 0])
    money_pct = list(featured.get("money_pct") or [0, 0])
    return f"""
<div data-testid="nba-spread-step4-most-bet-card" style="border:1px solid rgba(103,216,255,.42);border-radius:22px;
background:linear-gradient(145deg,#07111d,#102842);padding:18px 19px;margin:0 0 16px;box-shadow:0 16px 36px rgba(0,0,0,.22)">
  <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap">
    <div>
      <div style="font-size:.7rem;font-weight:950;letter-spacing:.12em;color:#67d8ff;text-transform:uppercase">🔥 Most Bet Game</div>
      <div style="font-size:1.28rem;font-weight:950;color:#f8fafc;margin-top:5px">{away} @ {home}</div>
      <div style="font-size:.76rem;color:#91a4b8;margin-top:4px">{tip} • {date} • Phoenix</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:1.22rem;font-weight:950;color:#f8fafc">{tracked:,}</div>
      <div style="font-size:.66rem;color:#7f93a8">tracked bets</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:14px">
    <div style="border:1px solid rgba(148,163,184,.13);border-radius:14px;padding:10px 11px;background:rgba(5,12,20,.48)">
      <div style="font-size:.63rem;color:#71869a;text-transform:uppercase;letter-spacing:.08em">Bets</div>
      <div style="font-size:.8rem;font-weight:900;color:#e7f4ff;margin-top:4px">{away} {bet_pct[0]}% • {home} {bet_pct[1]}%</div>
    </div>
    <div style="border:1px solid rgba(148,163,184,.13);border-radius:14px;padding:10px 11px;background:rgba(5,12,20,.48)">
      <div style="font-size:.63rem;color:#71869a;text-transform:uppercase;letter-spacing:.08em">Money</div>
      <div style="font-size:.8rem;font-weight:900;color:#e7f4ff;margin-top:4px">{away} {money_pct[0]}% • {home} {money_pct[1]}%</div>
    </div>
  </div>
  <div style="font-size:.65rem;color:#688197;margin-top:11px">Action Network • matched to verified NBA schedule</div>
</div>
"""


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
        f'<div data-testid="nba-spread-step2-active" style="display:none!important"></div>'
        f'<div data-testid="nba-spread-step3-schedule-active" style="display:none!important"></div>'
        f'<div data-testid="nba-spread-step4-most-bet-active" data-heartbeat="{PAGE_HEARTBEAT}" style="display:none!important"></div>',
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
<div data-testid="nba-spread-step3-schedule-unavailable" style="border:1px solid rgba(248,113,113,.28);border-radius:18px;padding:16px 18px;background:#160e14">
  <div style="font-weight:900;color:#fecaca">Schedule verification unavailable</div>
  <div style="font-size:.78rem;color:#b9a1aa;margin-top:5px">NBA Official and ESPN NBA must agree before this page publishes a slate. Nothing is guessed.</div>
  <div style="font-size:.68rem;color:#846b75;margin-top:8px">{diagnostic}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        return

    games = list(schedule.get("games") or [])
    try:
        featured = _load_featured_most_bet(json.dumps(games, sort_keys=True, separators=(",", ":")))
    except MostBetUnavailable as exc:
        diagnostic = escape(str(exc))
        st.markdown(
            f'<div data-testid="nba-spread-step4-most-bet-unavailable" style="border:1px dashed rgba(148,163,184,.18);border-radius:16px;padding:12px 14px;color:#7f93a8;font-size:.75rem">Most Bet Game unavailable • {diagnostic}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(_most_bet_card(featured), unsafe_allow_html=True)

    upcoming = [game for game in games if game.get("status") in {"UPCOMING", "DELAYED"}]
    live_final = [game for game in games if game.get("status") in {"LIVE", "FINAL", "CANCELLED"}]
    window = list(schedule.get("window_dates") or [])
    window_text = " → ".join((window[0], window[-1])) if window else "Rolling Phoenix window"
    st.markdown(
        f"""
<div style="display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid rgba(148,163,184,.13);border-radius:16px;padding:11px 14px;background:#0a1320">
  <div style="font-size:.76rem;font-weight:850;color:#d7e2ec">Verified 7-Day NBA Slate</div>
  <div style="font-size:.68rem;color:#71869a">{escape(window_text)}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    _render_game_group("Upcoming", upcoming, "No verified upcoming NBA games in this Phoenix-time window.")
    _render_game_group("Live / Final", live_final, "No verified live or completed NBA games in this window yet.")


__all__ = [
    "MODEL_VERSION", "PAGE_HEARTBEAT", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL", "MAY_MODIFY_PROJECTION", "MAY_MODIFY_PROBABILITY",
    "render_nba_spread_page",
]
