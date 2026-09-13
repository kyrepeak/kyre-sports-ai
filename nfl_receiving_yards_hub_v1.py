"""NFL Receiving Yards V1 — Step 1 verified slate foundation.

Additive Receiving Yards workspace modeled after the certified Rushing Yards
page structure. Step 1 owns only the verified NFL slate, page shell, Phoenix
kickoff display, and build-state presentation.

Player/roster context, injuries/depth chart, receiving projection math,
FanDuel markets, probabilities, EV, Monte Carlo, ranking, recommendations,
staking, and wager actions remain OFF. The certified Passing Yards and Rushing
Yards chains are not imported or modified here. Sportsbook projection influence
is exactly 0.0%.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import re
from textwrap import dedent
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from nfl_hub_v1 import ET, load_nfl_slate

MODEL_VERSION = "NFL RECEIVING YARDS V1 • STEP 1 VERIFIED SLATE FOUNDATION"
RECEIVING_YARDS_MARKET = "Receiving Yards"
SYSTEM_STEP = 1
SYSTEM_TOTAL = 4
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PHOENIX_TZ_NAME = "America/Phoenix"
PHOENIX_TZ_LABEL = "MST"

_PHOENIX = ZoneInfo(PHOENIX_TZ_NAME)

_RECV_CSS = r'''
<style>
.krecv-hero{position:relative;overflow:hidden;border:1px solid #31563f;border-radius:22px;background:linear-gradient(145deg,#0d1c16 0%,#0b1712 55%,#101912 100%);padding:20px 20px 18px;margin:8px 0 14px;box-shadow:0 16px 42px rgba(0,0,0,.18)}
.krecv-hero:after{content:"";position:absolute;right:-32px;bottom:-76px;width:220px;height:220px;border:2px solid rgba(139,226,172,.08);border-radius:50%;box-shadow:0 0 0 24px rgba(139,226,172,.025),0 0 0 48px rgba(139,226,172,.018)}
.krecv-kicker{color:#8be2ac;font-size:.63rem;font-weight:950;letter-spacing:.12em;text-transform:uppercase}.krecv-title{color:#f7fbf8;font-size:1.72rem;font-weight:950;letter-spacing:-.035em;line-height:1.08;margin-top:5px}.krecv-title span{color:#8be2ac}.krecv-sub{max-width:780px;color:#9bafa2;font-size:.78rem;line-height:1.55;margin-top:8px}
.krecv-chiprow{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px;position:relative;z-index:1}.krecv-chip{border:1px solid #315b42;background:#10251a;border-radius:999px;padding:5px 9px;color:#a8e9bf;font-size:.60rem;font-weight:900}.krecv-chip.lock{border-color:#3e5367;background:#111d27;color:#a9bacb}
.krecv-board{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:10px 0 14px}.krecv-tool{border:1px solid #283d31;border-radius:14px;background:#0c1712;padding:11px;min-height:82px}.krecv-tool .icon{font-size:1.15rem}.krecv-tool b{display:block;color:#edf6f0;font-size:.72rem;margin-top:4px}.krecv-tool span{display:block;color:#70877a;font-size:.57rem;line-height:1.35;margin-top:3px}.krecv-tool.live{border-color:#3d6c4d;background:#0f1d16}.krecv-tool.live span{color:#91ad9a}
.krecv-progress{border:1px solid #273a30;border-radius:15px;background:#0b1511;padding:11px 12px;margin-bottom:14px}.krecv-progress-top{display:flex;justify-content:space-between;gap:10px;align-items:center}.krecv-progress-top b{color:#eaf4ed;font-size:.70rem}.krecv-progress-top span{color:#8be2ac;font-size:.58rem;font-weight:900}.krecv-track{height:6px;background:#17251d;border-radius:999px;margin-top:8px;overflow:hidden}.krecv-fill{width:25%;height:100%;background:linear-gradient(90deg,#59c27e,#94e7b1);border-radius:999px}.krecv-stage-row{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.krecv-stage{font-size:.53rem;font-weight:900;color:#6d8275;border:1px solid #22342a;border-radius:999px;padding:4px 7px}.krecv-stage.on{color:#9ae3b4;border-color:#315940;background:#102119}
.krecv-section{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:16px 0 8px}.krecv-section h3{margin:0;color:#f0f7f2;font-size:1rem}.krecv-section span{color:#73887a;font-size:.56rem;font-weight:800}.krecv-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.krecv-game{border:1px solid #263c30;background:#0b1611;border-radius:16px;padding:12px;min-width:0}.krecv-game-top{display:flex;justify-content:space-between;gap:8px;color:#6f8577;font-size:.54rem;font-weight:900;text-transform:uppercase}.krecv-status{color:#99b5a2}.krecv-status.live{color:#8be2ac}.krecv-team{display:flex;align-items:center;gap:9px;margin-top:10px}.krecv-logo{width:42px;height:42px;object-fit:contain;flex:0 0 42px}.krecv-fallback{width:42px;height:42px;border:1px solid #31513d;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#94ad9b;font-size:.54rem;font-weight:950;flex:0 0 42px}.krecv-team-copy{min-width:0;flex:1}.krecv-team-copy b{display:block;color:#f2f7f4;font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv-team-copy span{display:block;color:#708477;font-size:.55rem;margin-top:2px}.krecv-score{color:#8be2ac;font-size:1.28rem}.krecv-at{margin:2px 0 0 51px;color:#51685a;font-size:.45rem;font-weight:950}.krecv-meta{display:grid;gap:3px;border-top:1px solid #1d3025;margin-top:10px;padding-top:8px;color:#718679;font-size:.54rem}.krecv-guard{border-left:3px solid #6a88a7;background:#101922;border-radius:8px;padding:9px 11px;color:#92a7ba;font-size:.61rem;line-height:1.45;margin-top:12px}
@media(max-width:760px){.krecv-board{grid-template-columns:repeat(2,minmax(0,1fr))}.krecv-grid{grid-template-columns:1fr}.krecv-title{font-size:1.45rem}.krecv-hero{padding:16px}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _logo_html(url: str, abbr: str, name: str) -> str:
    url = _safe(url, "")
    if url:
        return (
            f'<img class="krecv-logo" src="{escape(url, quote=True)}" '
            f'alt="{escape(name, quote=True)} logo">'
        )
    return f'<div class="krecv-fallback">{escape(_safe(abbr, "NFL")[:4])}</div>'


def _score(row: Any, side: str) -> str:
    state = _safe(row.get("state"), "pre").lower()
    if state not in {"in", "post"}:
        return ""
    return _safe(row.get(f"{side}_score"), "0")


def _clock_label(value: datetime) -> str:
    hour = value.strftime("%I").lstrip("0") or "0"
    return f"{hour}:{value.strftime('%M')} {value.strftime('%p')} {PHOENIX_TZ_LABEL}"


def _phoenix_kickoff(row: Any) -> dict[str, str] | None:
    try:
        game_date = _safe(row.get("game_date"), "")
        tip_et = _safe(row.get("tip_et"), "")
    except Exception:
        return None
    if not game_date or not tip_et or tip_et.upper().startswith("TBD"):
        return None
    clock = re.sub(r"\s+(?:ET|EST|EDT)\s*$", "", tip_et, flags=re.IGNORECASE).strip()
    try:
        eastern = datetime.strptime(f"{game_date} {clock}", "%Y-%m-%d %I:%M %p").replace(tzinfo=ET)
        phoenix = eastern.astimezone(_PHOENIX)
    except Exception:
        return None
    label = _clock_label(phoenix)
    return {
        "clock": label,
        "clock_with_location": f"{label} • Phoenix",
        "status": f"{phoenix.month}/{phoenix.day} - {label}",
    }


def _game_card(row: Any) -> str:
    state = _safe(row.get("state"), "pre").lower()
    status_class = "live" if state == "in" else ""
    away_name = _safe(row.get("away_team"), "Away")
    home_name = _safe(row.get("home_team"), "Home")
    labels = _phoenix_kickoff(row)
    clock = labels["clock_with_location"] if labels else _safe(row.get("tip_et"), "TBD")
    status = _safe(row.get("status"), "Scheduled")
    if state == "pre" and labels:
        status = labels["status"]
    html = f'''
    <article class="krecv-game">
      <div class="krecv-game-top">
        <span>{escape(_safe(row.get('season_type'), 'NFL'))}</span>
        <span class="krecv-status {status_class}">{escape(status)}</span>
      </div>
      <div class="krecv-team">
        {_logo_html(row.get('away_logo'), row.get('away_abbr'), away_name)}
        <div class="krecv-team-copy"><b>{escape(away_name)}</b><span>{escape(_safe(row.get('away_record')))}</span></div>
        <strong class="krecv-score">{escape(_score(row, 'away'))}</strong>
      </div>
      <div class="krecv-at">AT</div>
      <div class="krecv-team">
        {_logo_html(row.get('home_logo'), row.get('home_abbr'), home_name)}
        <div class="krecv-team-copy"><b>{escape(home_name)}</b><span>{escape(_safe(row.get('home_record')))}</span></div>
        <strong class="krecv-score">{escape(_score(row, 'home'))}</strong>
      </div>
      <div class="krecv-meta">
        <span>🕒 {escape(clock)}</span>
        <span>🏟️ {escape(_safe(row.get('venue'), 'Venue TBD'))}</span>
        <span>📺 {escape(_safe(row.get('broadcast')))}</span>
      </div>
    </article>
    '''
    return dedent(html).strip()


def _render_hero() -> None:
    st.markdown(
        _RECV_CSS
        + '<div class="krecv-hero">'
        + '<div class="krecv-kicker">NFL RECEIVING YARDS • MONSTER BUILD</div>'
        + '<div class="krecv-title">🎯 Receiving Yards <span>Receiver Lab</span></div>'
        + '<div class="krecv-sub">Built on the same visual foundation as the certified Rushing Yards page. Step 1 locks the verified NFL slate and game identity before receiver usage, matchup context, projection math, or sportsbook markets are allowed in.</div>'
        + '<div class="krecv-chiprow">'
        + '<span class="krecv-chip">EXACT ESPN GAME IDs</span>'
        + '<span class="krecv-chip">PHOENIX GAME TIMES</span>'
        + '<span class="krecv-chip lock">PROJECTION OFF</span>'
        + '<span class="krecv-chip lock">SPORTSBOOK INFLUENCE 0.0%</span>'
        + '</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="krecv-board">'
        '<div class="krecv-tool live"><div class="icon">🏈</div><b>Verified Slate</b><span>Exact ESPN event/team identity and schedule are live.</span></div>'
        '<div class="krecv-tool"><div class="icon">👤</div><b>Receiver Context</b><span>Targets, catches, routes/usage and exact athlete identity come next.</span></div>'
        '<div class="krecv-tool"><div class="icon">🧠</div><b>Projection Engine</b><span>Market-blind receiving-yards projection stays OFF until certified.</span></div>'
        '<div class="krecv-tool"><div class="icon">📈</div><b>FanDuel Market</b><span>Live line/price layer stays OFF until exact-ID model work is locked.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="krecv-progress">'
        '<div class="krecv-progress-top"><b>Receiving Yards core build</b><span>STEP 1 OF 4 • ACTIVE</span></div>'
        '<div class="krecv-track"><div class="krecv-fill"></div></div>'
        '<div class="krecv-stage-row">'
        '<span class="krecv-stage on">1 • VERIFIED SLATE</span>'
        '<span class="krecv-stage">2 • RECEIVER + MATCHUP DATA</span>'
        '<span class="krecv-stage">3 • PROJECTION</span>'
        '<span class="krecv-stage">4 • LIVE MARKET</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _render_schedule(games: pd.DataFrame, day_str: str, diag: dict[str, Any]) -> None:
    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    final = int((games.get("state", pd.Series(dtype=str)).astype(str) == "post").sum()) if not games.empty else 0
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", len(games))
    c2.metric("Upcoming", upcoming)
    c3.metric("Live", live)
    c4.metric("Final", final)

    if not diag.get("request_ok"):
        st.error(
            "NFL schedule provider did not return a usable slate. Receiving Yards fails closed and no fake games are created. "
            f"Provider: {diag.get('provider')} • HTTP: {diag.get('http') or '—'}"
        )
        if diag.get("error"):
            st.caption(f"Provider detail: {diag.get('error')}")
        return

    st.caption(
        f"✅ Verified NFL schedule • {day_str} • ESPN NFL scoreboard • {len(games)} game(s) • "
        "slate identity interpreted in America/New_York • kickoff clocks displayed in Phoenix MST"
    )
    st.markdown(
        '<div class="krecv-section"><h3>🏟️ Verified Matchups</h3><span>STEP 1 • EXACT GAME IDENTITY</span></div>',
        unsafe_allow_html=True,
    )
    if games.empty:
        st.info("No verified NFL games were returned for this date.")
        return

    cards = "\n".join(_game_card(row) for _, row in games.iterrows())
    st.markdown(f'<div class="krecv-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_receiving_yards_hub() -> None:
    _render_hero()

    if "nfl_receiving_yards_v1_date" not in st.session_state:
        st.session_state["nfl_receiving_yards_v1_date"] = datetime.now(ET).date()
    day = st.date_input(
        "📅 NFL slate date",
        value=st.session_state["nfl_receiving_yards_v1_date"],
        key="nfl_receiving_yards_v1_date_input",
    )
    st.session_state["nfl_receiving_yards_v1_date"] = day
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")

    with st.spinner("🎯 Verifying Receiving Yards NFL slate…"):
        games, diag = load_nfl_slate(day_str)
    _render_schedule(games, day_str, diag)

    st.markdown(
        '<div class="krecv-guard"><strong>Step 1 safety lock:</strong> player/roster data, injuries/depth chart, receiving projection math, live sportsbook markets, probability, EV, Monte Carlo, rankings, recommendations, staking and wager actions are OFF. No sportsbook input can alter a projection because no Receiving Yards projection exists yet. Sportsbook projection influence: <strong>0.0%</strong>.</div>',
        unsafe_allow_html=True,
    )


def render_nfl_hub(market: str = RECEIVING_YARDS_MARKET) -> None:
    if str(market or RECEIVING_YARDS_MARKET) != RECEIVING_YARDS_MARKET:
        raise ValueError("NFL Receiving Yards V1 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "MODEL_VERSION",
    "PHOENIX_TZ_LABEL",
    "PHOENIX_TZ_NAME",
    "RECEIVING_YARDS_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SYSTEM_STEP",
    "SYSTEM_TOTAL",
    "_game_card",
    "_phoenix_kickoff",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
