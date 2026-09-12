"""NFL Rushing Yards V1 — UI cleanup foundation.

Additive, presentation-only Rushing Yards workspace. It reuses the verified NFL
slate/date layer from nfl_hub_v1 and intentionally does not enable projection,
sportsbook grading, probability, EV, Monte Carlo, ranking or recommendation
logic.

The certified NFL Passing Yards chain is not imported or modified here.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from nfl_hub_v1 import ET, load_nfl_slate

MODEL_VERSION = "NFL RUSHING YARDS V1 • UI CLEANUP FOUNDATION • MODEL OFF"

_RUSH_CSS = r'''
<style>
.krush-hero{
  position:relative;overflow:hidden;border:1px solid #31563f;border-radius:22px;
  background:linear-gradient(145deg,#0d1c16 0%,#0b1712 55%,#101912 100%);
  padding:20px 20px 18px;margin:8px 0 14px;box-shadow:0 16px 42px rgba(0,0,0,.18)
}
.krush-hero:after{
  content:"";position:absolute;right:-32px;bottom:-76px;width:220px;height:220px;
  border:2px solid rgba(139,226,172,.08);border-radius:50%;box-shadow:0 0 0 24px rgba(139,226,172,.025),0 0 0 48px rgba(139,226,172,.018)
}
.krush-kicker{color:#8be2ac;font-size:.63rem;font-weight:950;letter-spacing:.12em;text-transform:uppercase}
.krush-title{color:#f7fbf8;font-size:1.72rem;font-weight:950;letter-spacing:-.035em;line-height:1.08;margin-top:5px}
.krush-title span{color:#8be2ac}.krush-sub{max-width:760px;color:#9bafa2;font-size:.78rem;line-height:1.55;margin-top:8px}
.krush-chiprow{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px;position:relative;z-index:1}
.krush-chip{border:1px solid #315b42;background:#10251a;border-radius:999px;padding:5px 9px;color:#a8e9bf;font-size:.60rem;font-weight:900}
.krush-chip.lock{border-color:#3e5367;background:#111d27;color:#a9bacb}
.krush-board{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:10px 0 14px}
.krush-tool{border:1px solid #283d31;border-radius:14px;background:#0c1712;padding:11px;min-height:82px}
.krush-tool .icon{font-size:1.15rem}.krush-tool b{display:block;color:#edf6f0;font-size:.72rem;margin-top:4px}.krush-tool span{display:block;color:#70877a;font-size:.57rem;line-height:1.35;margin-top:3px}
.krush-progress{border:1px solid #273a30;border-radius:15px;background:#0b1511;padding:11px 12px;margin-bottom:14px}
.krush-progress-top{display:flex;justify-content:space-between;gap:10px;align-items:center}.krush-progress-top b{color:#eaf4ed;font-size:.70rem}.krush-progress-top span{color:#8be2ac;font-size:.58rem;font-weight:900}
.krush-track{height:6px;background:#17251d;border-radius:999px;margin-top:8px;overflow:hidden}.krush-fill{width:25%;height:100%;background:linear-gradient(90deg,#59c27e,#94e7b1);border-radius:999px}
.krush-stage-row{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.krush-stage{font-size:.53rem;font-weight:900;color:#6d8275;border:1px solid #22342a;border-radius:999px;padding:4px 7px}.krush-stage.on{color:#9ae3b4;border-color:#315940;background:#102119}
.krush-section{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:16px 0 8px}.krush-section h3{margin:0;color:#f0f7f2;font-size:1rem}.krush-section span{color:#73887a;font-size:.56rem;font-weight:800}
.krush-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.krush-game{border:1px solid #263c30;background:#0b1611;border-radius:16px;padding:12px;min-width:0}
.krush-game-top{display:flex;justify-content:space-between;gap:8px;color:#6f8577;font-size:.54rem;font-weight:900;text-transform:uppercase}.krush-status{color:#99b5a2}.krush-status.live{color:#8be2ac}
.krush-team{display:flex;align-items:center;gap:9px;margin-top:10px}.krush-logo{width:42px;height:42px;object-fit:contain;flex:0 0 42px}.krush-fallback{width:42px;height:42px;border:1px solid #31513d;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#94ad9b;font-size:.54rem;font-weight:950;flex:0 0 42px}
.krush-team-copy{min-width:0;flex:1}.krush-team-copy b{display:block;color:#f2f7f4;font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krush-team-copy span{display:block;color:#708477;font-size:.55rem;margin-top:2px}.krush-score{color:#8be2ac;font-size:1.28rem}.krush-at{margin:2px 0 0 51px;color:#51685a;font-size:.45rem;font-weight:950}
.krush-meta{display:grid;gap:3px;border-top:1px solid #1d3025;margin-top:10px;padding-top:8px;color:#718679;font-size:.54rem}
.krush-empty{border:1px dashed #34503e;border-radius:14px;padding:16px;color:#8fa295;background:#0b1511}
.krush-guard{border-left:3px solid #6a88a7;background:#101922;border-radius:8px;padding:9px 11px;color:#92a7ba;font-size:.61rem;line-height:1.45;margin-top:12px}
@media(max-width:760px){.krush-board{grid-template-columns:repeat(2,minmax(0,1fr))}.krush-grid{grid-template-columns:1fr}.krush-title{font-size:1.45rem}.krush-hero{padding:16px}}
</style>
'''


def _safe(value, default="—") -> str:
    text = str(value or "").strip()
    return text or default


def _logo_html(url: str, abbr: str, name: str) -> str:
    url = _safe(url, "")
    if url:
        return (
            f'<img class="krush-logo" src="{escape(url, quote=True)}" '
            f'alt="{escape(name, quote=True)} logo">'
        )
    return f'<div class="krush-fallback">{escape(_safe(abbr, "NFL")[:4])}</div>'


def _score(row, side: str) -> str:
    state = _safe(row.get("state"), "pre").lower()
    if state not in {"in", "post"}:
        return ""
    return _safe(row.get(f"{side}_score"), "0")


def _game_card(row) -> str:
    state = _safe(row.get("state"), "pre").lower()
    status_class = "live" if state == "in" else ""
    away_name = _safe(row.get("away_team"), "Away")
    home_name = _safe(row.get("home_team"), "Home")
    return f'''
    <article class="krush-game">
      <div class="krush-game-top">
        <span>{escape(_safe(row.get('season_type'), 'NFL'))}</span>
        <span class="krush-status {status_class}">{escape(_safe(row.get('status'), 'Scheduled'))}</span>
      </div>
      <div class="krush-team">
        {_logo_html(row.get('away_logo'), row.get('away_abbr'), away_name)}
        <div class="krush-team-copy"><b>{escape(away_name)}</b><span>{escape(_safe(row.get('away_record')))}</span></div>
        <strong class="krush-score">{escape(_score(row, 'away'))}</strong>
      </div>
      <div class="krush-at">AT</div>
      <div class="krush-team">
        {_logo_html(row.get('home_logo'), row.get('home_abbr'), home_name)}
        <div class="krush-team-copy"><b>{escape(home_name)}</b><span>{escape(_safe(row.get('home_record')))}</span></div>
        <strong class="krush-score">{escape(_score(row, 'home'))}</strong>
      </div>
      <div class="krush-meta">
        <span>🕒 {escape(_safe(row.get('tip_et'), 'TBD'))}</span>
        <span>🏟️ {escape(_safe(row.get('venue'), 'Venue TBD'))}</span>
        <span>📺 {escape(_safe(row.get('broadcast')))}</span>
      </div>
    </article>
    '''


def render_nfl_rushing_yards_hub() -> None:
    """Render the Rushing Yards cleanup shell with verified schedule context only."""
    st.markdown(_RUSH_CSS, unsafe_allow_html=True)
    st.markdown(
        '''
        <section class="krush-hero">
          <div class="krush-kicker">NFL • Rushing Yards</div>
          <div class="krush-title">🏃 Ground Game <span>Lab</span></div>
          <div class="krush-sub">A cleaner home for running-back research. For this first pass we are fixing the experience before we touch the engine: verified game identity and schedule context are live, while player projections and market math stay intentionally OFF.</div>
          <div class="krush-chiprow">
            <span class="krush-chip">✅ UI CLEANUP V1</span>
            <span class="krush-chip">🏈 VERIFIED NFL SLATE</span>
            <span class="krush-chip lock">🧊 PASSING YARDS FROZEN</span>
            <span class="krush-chip lock">🔒 MODEL OFF</span>
          </div>
        </section>
        <div class="krush-board">
          <div class="krush-tool"><div class="icon">🏃</div><b>Workhorse Volume</b><span>Carries, snap share and role stability will live here.</span></div>
          <div class="krush-tool"><div class="icon">🧱</div><b>Run Front</b><span>Opponent rush defense and trench matchup will live here.</span></div>
          <div class="krush-tool"><div class="icon">⚡</div><b>Explosiveness</b><span>Efficiency and big-play profile will live here.</span></div>
          <div class="krush-tool"><div class="icon">🎯</div><b>Market Edge</b><span>Verified line, probability and grade come later.</span></div>
        </div>
        <div class="krush-progress">
          <div class="krush-progress-top"><b>Rushing Yards build board</b><span>1 OF 4 • FOUNDATION</span></div>
          <div class="krush-track"><div class="krush-fill"></div></div>
          <div class="krush-stage-row">
            <span class="krush-stage on">1 • CLEAN UI ✅</span>
            <span class="krush-stage">2 • PLAYER + MATCHUP DATA</span>
            <span class="krush-stage">3 • PROJECTION ENGINE</span>
            <span class="krush-stage">4 • LIVE MARKET + FINAL GRADE</span>
          </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    if "nfl_rushing_yards_v1_date" not in st.session_state:
        st.session_state["nfl_rushing_yards_v1_date"] = datetime.now(ET).date()

    selected_day = st.date_input(
        "📅 Choose NFL slate date",
        value=st.session_state["nfl_rushing_yards_v1_date"],
        key="nfl_rushing_yards_v1_date_input",
    )
    st.session_state["nfl_rushing_yards_v1_date"] = selected_day
    day_str = pd.to_datetime(selected_day).strftime("%Y-%m-%d")

    with st.spinner("🏈 Loading verified NFL matchups…"):
        games, diag = load_nfl_slate(day_str)

    c1, c2, c3, c4 = st.columns(4)
    states = games.get("state", pd.Series(dtype=str)).astype(str) if not games.empty else pd.Series(dtype=str)
    c1.metric("Games", int(len(games)))
    c2.metric("Upcoming", int((states == "pre").sum()))
    c3.metric("Live", int((states == "in").sum()))
    c4.metric("Final", int((states == "post").sum()))

    st.markdown(
        '<div class="krush-section"><h3>🏟️ Today\'s Ground Game Board</h3><span>VERIFIED SCHEDULE CONTEXT</span></div>',
        unsafe_allow_html=True,
    )

    if not diag.get("request_ok"):
        st.error(
            "The NFL schedule source did not return a usable slate, so this page is staying fail-closed instead of inventing games. "
            f"Provider: {diag.get('provider') or '—'} • HTTP: {diag.get('http') or '—'}"
        )
        if diag.get("error"):
            st.caption(f"Provider detail: {diag.get('error')}")
    elif games.empty:
        st.markdown(
            '<div class="krush-empty">No verified NFL games were returned for this date. Pick another slate date above.</div>',
            unsafe_allow_html=True,
        )
    else:
        cards = "".join(_game_card(row) for _, row in games.iterrows())
        st.markdown(f'<div class="krush-grid">{cards}</div>', unsafe_allow_html=True)
        st.caption(
            f"✅ {len(games)} verified NFL game{'s' if len(games) != 1 else ''} • "
            f"source: {diag.get('provider') or 'NFL schedule'} • selected date: {day_str}"
        )

    st.markdown(
        '<div class="krush-guard">🧊 <b>Frozen-line guard:</b> this cleanup page does not alter the certified Passing Yards chain, projection math, probability logic, FanDuel transport, grading, freshness rules, or any CFB surface.</div>',
        unsafe_allow_html=True,
    )


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    """Router-compatible entrypoint."""
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V1 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = ["MODEL_VERSION", "render_nfl_hub", "render_nfl_rushing_yards_hub"]
