"""NFL Game Totals V1 — Page Step 1 verified slate foundation.

Additive NFL Game Totals / Over-Under workspace modeled after the certified
Rushing Yards, Receiving Yards, and Moneyline presentation language. Step 1
owns only the fun page shell, connected 10-step build rail, verified ESPN NFL
slate, exact game identity, Phoenix kickoff display, and compact matchup cards.

Live FanDuel totals, offense/defense analysis, pace, explosiveness, red-zone
context, environment adjustments, projection math, market comparison, final
read, probability, EV, ranking, recommendations, staking, and wager actions
remain intentionally OFF. Exact ESPN event identity is the foundation for all
future layers. Sportsbook projection influence remains exactly 0.0%.
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

MODEL_VERSION = "NFL GAME TOTALS V1 • PAGE STEP 1 VERIFIED SLATE FOUNDATION"
PAGE_BUILD_STEP = 1
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = False
LIVE_MARKET_ENABLED = False
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False
PHOENIX_TZ_NAME = "America/Phoenix"
PHOENIX_TZ_LABEL = "MST"

_PHOENIX = ZoneInfo(PHOENIX_TZ_NAME)

_GAME_TOTALS_CSS = r'''
<style>
.kgt-page{max-width:1180px;margin:0 auto}
.kgt-hero{position:relative;overflow:hidden;border:1px solid #5d4328;border-radius:22px;background:linear-gradient(145deg,#18130f 0%,#111820 48%,#0b151c 100%);padding:20px 20px 18px;margin:8px 0 13px;box-shadow:0 16px 42px rgba(0,0,0,.20)}
.kgt-hero:before{content:"";position:absolute;right:-45px;top:-70px;width:235px;height:235px;border:2px solid rgba(255,173,84,.09);border-radius:50%;box-shadow:0 0 0 26px rgba(127,242,194,.025),0 0 0 52px rgba(255,173,84,.018)}
.kgt-kicker{color:#ffb56b;font-size:.63rem;font-weight:950;letter-spacing:.12em;text-transform:uppercase}
.kgt-title{color:#f9fbfd;font-size:1.72rem;font-weight:950;letter-spacing:-.035em;line-height:1.08;margin-top:5px}.kgt-title .over{color:#ffb56b}.kgt-title .under{color:#7ff2c2}
.kgt-sub{max-width:800px;color:#9aaaba;font-size:.78rem;line-height:1.55;margin-top:8px;position:relative;z-index:1}
.kgt-chiprow{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px;position:relative;z-index:1}.kgt-chip{border:1px solid #625037;background:#201911;border-radius:999px;padding:5px 9px;color:#ffc58d;font-size:.60rem;font-weight:900}.kgt-chip.teal{border-color:#2d5c56;background:#0d201e;color:#93ead0}.kgt-chip.lock{border-color:#3a4d5d;background:#111a22;color:#a7b6c3}
.kgt-toolboard{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:10px 0 12px}.kgt-tool{border:1px solid #293b49;border-radius:14px;background:#0b141b;padding:11px;min-height:84px}.kgt-tool .icon{font-size:1.15rem}.kgt-tool b{display:block;color:#edf4f8;font-size:.72rem;margin-top:4px}.kgt-tool span{display:block;color:#718493;font-size:.57rem;line-height:1.35;margin-top:3px}.kgt-tool.live{border-color:#755132;background:#1a1410}.kgt-tool.live span{color:#c29c78}
.kgt-progress{border:1px solid #2d3d49;border-radius:16px;background:#091218;padding:12px;margin:0 0 14px;overflow:hidden}.kgt-progress-top{display:flex;justify-content:space-between;gap:10px;align-items:center}.kgt-progress-top b{color:#edf4f8;font-size:.70rem}.kgt-progress-top span{color:#ffb56b;font-size:.58rem;font-weight:950}.kgt-track{height:6px;background:#17242d;border-radius:999px;margin-top:8px;overflow:hidden}.kgt-fill{width:10%;height:100%;background:linear-gradient(90deg,#ff9f43,#ffc27d);border-radius:999px}
.kgt-rail-wrap{overflow-x:auto;margin-top:10px;padding:1px 1px 4px}.kgt-rail{display:flex;align-items:stretch;min-width:1040px}.kgt-stage{position:relative;flex:1;min-width:96px;text-align:center;padding:22px 5px 5px;color:#657887;font-size:.46rem;font-weight:950;letter-spacing:.02em}.kgt-stage:before{content:"";position:absolute;top:7px;left:50%;width:11px;height:11px;border:2px solid #3a4d59;background:#0a141b;border-radius:50%;transform:translateX(-50%);z-index:2}.kgt-stage:not(:last-child):after{content:"";position:absolute;top:12px;left:calc(50% + 7px);width:calc(100% - 14px);height:2px;background:#2a3944;z-index:1}.kgt-stage.on{color:#ffc58d}.kgt-stage.on:before{border-color:#ffad59;background:#ff9f43;box-shadow:0 0 0 4px rgba(255,159,67,.10)}.kgt-stage.on:after{background:linear-gradient(90deg,#ff9f43,#4b4650)}
.kgt-banner{border:1px solid #34495a;border-radius:13px;background:#0b1720;padding:10px 12px;margin:10px 0;color:#9eb0be;font-size:.62rem;line-height:1.5}.kgt-banner strong{color:#f2f7fa}.kgt-banner .orange{color:#ffbd79}.kgt-banner .teal{color:#8ce4ca}
.kgt-section{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:16px 0 8px}.kgt-section h3{margin:0;color:#f0f5f8;font-size:1rem}.kgt-section span{color:#758796;font-size:.56rem;font-weight:850}
.kgt-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.kgt-game{border:1px solid #2b4354;background:linear-gradient(180deg,#0b1720,#091219);border-radius:17px;padding:12px;min-width:0;box-shadow:0 7px 20px rgba(0,0,0,.13)}.kgt-game-top{display:flex;justify-content:space-between;gap:8px;color:#778b99;font-size:.54rem;font-weight:900;text-transform:uppercase}.kgt-status{color:#a3b1bc}.kgt-status.live{color:#7ff2c2}.kgt-id{color:#9a7b5c}
.kgt-team{display:flex;align-items:center;gap:9px;margin-top:10px}.kgt-logo{width:43px;height:43px;object-fit:contain;flex:0 0 43px}.kgt-fallback{width:43px;height:43px;border:1px solid #3a5364;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#9fb0bc;font-size:.54rem;font-weight:950;flex:0 0 43px}.kgt-team-copy{min-width:0;flex:1}.kgt-team-copy b{display:block;color:#f3f7fa;font-size:.79rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kgt-team-copy span{display:block;color:#718594;font-size:.55rem;margin-top:2px}.kgt-score{color:#7ff2c2;font-size:1.28rem}.kgt-at{margin:2px 0 0 52px;color:#526a79;font-size:.45rem;font-weight:950}.kgt-meta{display:grid;gap:3px;border-top:1px solid #1f3442;margin-top:10px;padding-top:8px;color:#748895;font-size:.54rem}
.kgt-reserved{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:9px}.kgt-reserved>div{border:1px dashed #3b4b58;border-radius:10px;background:#0a131a;padding:8px 9px}.kgt-reserved b{display:block;color:#9eb0bd;font-size:.57rem}.kgt-reserved span{display:block;color:#657987;font-size:.50rem;margin-top:2px}.kgt-reserved .market b{color:#ffc180}.kgt-reserved .projection b{color:#8de3ca}
.kgt-empty{border:1px dashed #3b5060;border-radius:14px;padding:17px;color:#93a5b1;background:#0a141b}
@media(max-width:760px){.kgt-toolboard{grid-template-columns:repeat(2,minmax(0,1fr))}.kgt-grid{grid-template-columns:1fr}.kgt-title{font-size:1.45rem}.kgt-hero{padding:16px}.kgt-reserved{grid-template-columns:1fr}.kgt-progress{padding:10px}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _logo_html(url: str, abbr: str, name: str) -> str:
    url = _safe(url, "")
    if url:
        return (
            f'<img class="kgt-logo" src="{escape(url, quote=True)}" '
            f'alt="{escape(name, quote=True)} logo">'
        )
    return f'<div class="kgt-fallback">{escape(_safe(abbr, "NFL")[:4])}</div>'


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
        "clock": f"{label} • Phoenix",
        "status": f"{phoenix.month}/{phoenix.day} - {label}",
    }


def _game_card(row: Any) -> str:
    state = _safe(row.get("state"), "pre").lower()
    status_class = "live" if state == "in" else ""
    away_name = _safe(row.get("away_team"), "Away")
    home_name = _safe(row.get("home_team"), "Home")
    labels = _phoenix_kickoff(row)
    clock = labels["clock"] if labels else _safe(row.get("tip_et"), "TBD")
    status = _safe(row.get("status"), "Scheduled")
    if state == "pre" and labels:
        status = labels["status"]
    event_id = _safe(row.get("game_id"), "UNVERIFIED")

    html = f'''
    <article class="kgt-game" data-espn-event-id="{escape(event_id, quote=True)}">
      <div class="kgt-game-top">
        <span>{escape(_safe(row.get('season_type'), 'NFL'))} • <span class="kgt-id">ESPN {escape(event_id)}</span></span>
        <span class="kgt-status {status_class}">{escape(status)}</span>
      </div>
      <div class="kgt-team">
        {_logo_html(row.get('away_logo'), row.get('away_abbr'), away_name)}
        <div class="kgt-team-copy"><b>{escape(away_name)}</b><span>{escape(_safe(row.get('away_record')))}</span></div>
        <strong class="kgt-score">{escape(_score(row, 'away'))}</strong>
      </div>
      <div class="kgt-at">AT</div>
      <div class="kgt-team">
        {_logo_html(row.get('home_logo'), row.get('home_abbr'), home_name)}
        <div class="kgt-team-copy"><b>{escape(home_name)}</b><span>{escape(_safe(row.get('home_record')))}</span></div>
        <strong class="kgt-score">{escape(_score(row, 'home'))}</strong>
      </div>
      <div class="kgt-meta">
        <span>🕒 {escape(clock)}</span>
        <span>🏟️ {escape(_safe(row.get('venue'), 'Venue TBD'))}</span>
        <span>📺 {escape(_safe(row.get('broadcast')))}</span>
      </div>
      <div class="kgt-reserved">
        <div class="market"><b>🎰 LIVE MARKET • STEP 2</b><span>Total / Over / Under prices connect next.</span></div>
        <div class="projection"><b>🧠 PROJECTION • STEP 8</b><span>Market-blind total projection remains OFF.</span></div>
      </div>
    </article>
    '''
    return dedent(html).strip()


def _progress_html() -> str:
    stages = (
        ("1", "VERIFIED SLATE", True),
        ("2", "LIVE TOTAL", False),
        ("3", "OFFENSE VS DEFENSE", False),
        ("4", "PACE + POSSESSION", False),
        ("5", "EXPLOSIVE SCORING", False),
        ("6", "RED ZONE + DRIVES", False),
        ("7", "GAME ENVIRONMENT", False),
        ("8", "TOTAL PROJECTION", False),
        ("9", "MARKET + FINAL READ", False),
        ("10", "FINAL CERTIFICATION", False),
    )
    stage_html = "".join(
        f'<div class="kgt-stage{" on" if active else ""}">{number} • {label}</div>'
        for number, label, active in stages
    )
    return (
        '<div class="kgt-progress">'
        '<div class="kgt-progress-top"><b>🏟️ Game Totals connected page build</b><span>STEP 1 OF 10 • CONNECTED BUILD</span></div>'
        '<div class="kgt-track"><div class="kgt-fill"></div></div>'
        f'<div class="kgt-rail-wrap"><div class="kgt-rail">{stage_html}</div></div>'
        '</div>'
    )


def _render_hero() -> None:
    st.markdown(
        _GAME_TOTALS_CSS
        + '<div class="kgt-page"><div class="kgt-hero">'
        + '<div class="kgt-kicker">NFL GAME TOTALS • MONSTER BUILD</div>'
        + '<div class="kgt-title">🏟️ Game Totals <span class="over">Over</span> / <span class="under">Under Lab</span></div>'
        + '<div class="kgt-sub">A matchup-first totals workspace with the same fun, compact feel as our Rushing Yards, Receiving Yards, and Moneyline pages. Step 1 locks the verified NFL slate and Exact ESPN event identity before any live total, analysis, or projection is allowed in.</div>'
        + '<div class="kgt-chiprow">'
        + '<span class="kgt-chip">EXACT ESPN GAME IDs</span>'
        + '<span class="kgt-chip teal">PHOENIX GAME TIMES</span>'
        + '<span class="kgt-chip lock">LIVE MARKET OFF • STEP 2</span>'
        + '<span class="kgt-chip lock">SPORTSBOOK INFLUENCE 0.0%</span>'
        + '</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kgt-toolboard">'
        '<div class="kgt-tool live"><div class="icon">🏈</div><b>Verified Slate</b><span>Exact ESPN game identity, teams, records and schedule are live.</span></div>'
        '<div class="kgt-tool"><div class="icon">🎰</div><b>Live Total</b><span>FanDuel Total + Over/Under prices arrive in Step 2.</span></div>'
        '<div class="kgt-tool"><div class="icon">⚔️</div><b>Matchup Layers</b><span>Offense/defense, pace, explosiveness and drives build next.</span></div>'
        '<div class="kgt-tool"><div class="icon">🧠</div><b>Total Projection</b><span>Market-blind projection stays OFF until Step 8 is certified.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_progress_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-banner"><strong>Step 1 firewall:</strong> only verified schedule/identity presentation is active. '
        '<span class="orange">No FanDuel total is displayed yet.</span> '
        '<span class="teal">No total projection is calculated yet.</span> '
        'Future layers must attach to the exact ESPN event ID already shown on each card.</div>',
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
            "NFL schedule provider did not return a usable slate. Game Totals fails closed and no fake games are created. "
            f"Provider: {diag.get('provider')} • HTTP: {diag.get('http') or '—'}"
        )
        if diag.get("error"):
            st.caption(f"Provider detail: {diag.get('error')}")
        return

    st.caption(
        f"✅ Verified NFL schedule • {day_str} • ESPN NFL scoreboard • {len(games)} game(s) • "
        "schedule identity interpreted in America/New_York • kickoff clocks displayed in Phoenix MST"
    )
    st.markdown(
        '<div class="kgt-section"><h3>🏟️ Verified Matchups</h3><span>STEP 1 • EXACT ESPN EVENT IDENTITY</span></div>',
        unsafe_allow_html=True,
    )
    if games.empty:
        st.markdown('<div class="kgt-empty">No verified NFL games were returned for this date.</div>', unsafe_allow_html=True)
        return

    cards = "".join(_game_card(row) for _, row in games.iterrows())
    st.markdown(f'<div class="kgt-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_game_totals_hub() -> None:
    _render_hero()

    if "nfl_game_totals_v1_date" not in st.session_state:
        st.session_state["nfl_game_totals_v1_date"] = st.session_state.get("nfl_v1_date", datetime.now(ET).date())

    selected = st.date_input(
        "📅 NFL Game Totals slate date",
        value=st.session_state["nfl_game_totals_v1_date"],
        key="nfl_game_totals_v1_date_input",
    )
    st.session_state["nfl_game_totals_v1_date"] = selected
    st.session_state["nfl_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = load_nfl_slate(day_str)

    _render_schedule(games, day_str, diag)
    st.caption(
        f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • "
        "projection OFF • live market OFF • wager actions OFF"
    )


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V1 only renders the Game Total market.")
    return render_nfl_game_totals_hub()


__all__ = [
    "LIVE_MARKET_ENABLED",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "PHOENIX_TZ_LABEL",
    "PHOENIX_TZ_NAME",
    "PROJECTION_MODEL_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_game_card",
    "_phoenix_kickoff",
    "_progress_html",
    "render_nfl_game_totals_hub",
    "render_nfl_hub",
]
