"""NFL Rushing Yards V1 — Ground Game Lab Steps 1-2.

Additive Rushing Yards workspace. Step 1 provides the verified NFL slate and
presentation foundation. Step 2 consumes the certified Kyre Sports API
``nfl_rushing_yards_context_v1`` contract for exact-ID current-roster rushing
workload and opponent run-front context.

Projection, sportsbook grading, probability, EV, Monte Carlo, ranking,
recommendation, and stake sizing remain intentionally OFF. The certified NFL
Passing Yards chain is not imported or modified here.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from nfl_hub_v1 import ET, load_nfl_slate
import nfl_rushing_yards_context_api_v1 as rushing_context_api

MODEL_VERSION = "NFL RUSHING YARDS V1 • STEP 2 PLAYER + MATCHUP DATA • MODEL OFF"

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
.krush-tool.live{border-color:#3d6c4d;background:#0f1d16}.krush-tool.live span{color:#91ad9a}
.krush-progress{border:1px solid #273a30;border-radius:15px;background:#0b1511;padding:11px 12px;margin-bottom:14px}
.krush-progress-top{display:flex;justify-content:space-between;gap:10px;align-items:center}.krush-progress-top b{color:#eaf4ed;font-size:.70rem}.krush-progress-top span{color:#8be2ac;font-size:.58rem;font-weight:900}
.krush-track{height:6px;background:#17251d;border-radius:999px;margin-top:8px;overflow:hidden}.krush-fill{width:50%;height:100%;background:linear-gradient(90deg,#59c27e,#94e7b1);border-radius:999px}
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
.krush-data-banner{border:1px solid #315940;border-radius:14px;background:#0e1b14;padding:10px 12px;margin:10px 0;color:#9ecfaf;font-size:.63rem;line-height:1.45}
.krush-player{border:1px solid #274234;border-radius:13px;background:#0b1711;padding:10px 11px;margin:7px 0}
.krush-player-top{display:flex;justify-content:space-between;gap:8px;align-items:center}.krush-player-name{color:#f0f7f2;font-weight:900;font-size:.76rem}.krush-player-pos{color:#8be2ac;font-size:.52rem;font-weight:900;border:1px solid #315940;border-radius:999px;padding:3px 6px}
.krush-player-meta{color:#718679;font-size:.54rem;margin-top:3px}.krush-player-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}.krush-stat{border-top:1px solid #1f3428;padding-top:6px}.krush-stat b{display:block;color:#dfeae2;font-size:.67rem}.krush-stat span{color:#64796d;font-size:.48rem;text-transform:uppercase;font-weight:900}
@media(max-width:760px){.krush-board{grid-template-columns:repeat(2,minmax(0,1fr))}.krush-grid{grid-template-columns:1fr}.krush-title{font-size:1.45rem}.krush-hero{padding:16px}.krush-player-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
'''


def _safe(value, default="—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value, digits: int = 1, suffix: str = "") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    rendered = f"{number:.{digits}f}"
    if digits > 0:
        rendered = rendered.rstrip("0").rstrip(".")
    return f"{rendered}{suffix}"


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


def _player_card(player: dict) -> str:
    baseline = _safe(player.get("baseline_season"), "—")
    sample = _safe(player.get("sample_games"), "0")
    return f'''
    <div class="krush-player">
      <div class="krush-player-top">
        <span class="krush-player-name">{escape(_safe(player.get('player_name'), 'Unknown rusher'))}</span>
        <span class="krush-player-pos">{escape(_safe(player.get('position'), '—'))}</span>
      </div>
      <div class="krush-player-meta">ESPN athlete ID {escape(_safe(player.get('official_athlete_id')))} • {escape(sample)} verified game{'s' if sample != '1' else ''} • {escape(baseline)} baseline</div>
      <div class="krush-player-stats">
        <div class="krush-stat"><b>{escape(_num(player.get('carries_per_game'), 1))}</b><span>Carries / Game</span></div>
        <div class="krush-stat"><b>{escape(_num(player.get('rushing_yards_per_game'), 1))}</b><span>Rush Yds / Game</span></div>
        <div class="krush-stat"><b>{escape(_num(player.get('yards_per_carry'), 2))}</b><span>Yards / Carry</span></div>
        <div class="krush-stat"><b>{escape(_num(player.get('rushing_touchdowns'), 0))}</b><span>Rush TD</span></div>
      </div>
    </div>
    '''


@st.cache_data(ttl=120, show_spinner=False)
def _load_rushing_context(event_id: str) -> dict:
    return rushing_context_api.fetch_event_context(str(event_id))


def _render_team_context(team: dict) -> None:
    team_name = _safe(team.get("team_name"), _safe(team.get("team_abbreviation"), "NFL Team"))
    abbr = _safe(team.get("team_abbreviation"), "NFL")
    side = _safe(team.get("home_away"), "team").upper()
    baseline = _safe(team.get("player_baseline_season"), "—")
    sample = _safe(team.get("player_sample_games"), "0")

    st.markdown(f"#### 🏃 {escape(abbr)} • {escape(team_name)}")
    st.caption(
        f"{side} • ESPN team ID {_safe(team.get('official_team_id'))} • "
        f"player baseline {baseline} • {sample} verified game{'s' if sample != '1' else ''}"
    )

    front = team.get("opponent_run_front") or {}
    st.markdown("**🧱 Opponent Run Front**")
    if front.get("data_available") is True:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rush Yds Allowed/G", _num(front.get("rush_yards_allowed_per_game"), 1))
        c2.metric("YPC Allowed", _num(front.get("yards_per_carry_allowed"), 2))
        c3.metric("Rush Att Allowed/G", _num(front.get("rush_attempts_allowed_per_game"), 1))
        c4.metric("Rush TD Allowed/G", _num(front.get("rushing_touchdowns_allowed_per_game"), 2))
        st.caption(
            f"Opponent ESPN team ID {_safe(front.get('official_team_id'))} • "
            f"{_safe(front.get('baseline_season'))} baseline • {_safe(front.get('sample_games'), '0')} verified games"
        )
    else:
        st.info("Verified opponent run-front sample is not available yet. No defensive values were invented.")

    st.markdown("**🏃 Verified Rusher Workload**")
    players = team.get("players") or []
    if not players:
        st.info("No current-roster rusher survived the exact-ID workload contract for this matchup yet.")
        return
    for player in players[:5]:
        st.markdown(_player_card(player), unsafe_allow_html=True)


def _render_context_board(games: pd.DataFrame) -> None:
    st.markdown(
        '<div class="krush-section"><h3>🔬 Step 2 • Player + Matchup Data</h3><span>KYRE SPORTS API • EXACT ESPN IDs</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="krush-data-banner">✅ The production Rushing Yards API is now the source of truth for this section. Select one verified matchup to load current-roster rushing workload plus opponent run-front context. Projection and sportsbook logic remain OFF.</div>',
        unsafe_allow_html=True,
    )

    verified = games.copy()
    if "game_id" not in verified.columns:
        st.warning("Verified slate did not expose an official ESPN event ID, so Step 2 is staying fail-closed.")
        return
    verified["game_id"] = verified["game_id"].astype(str).str.strip()
    verified = verified[verified["game_id"].str.fullmatch(r"\d+")].copy()
    if verified.empty:
        st.warning("No exact numeric ESPN event IDs survived the slate contract, so Step 2 is staying fail-closed.")
        return

    labels: dict[str, str] = {}
    for _, row in verified.iterrows():
        event_id = _safe(row.get("game_id"), "")
        labels[event_id] = (
            f"{_safe(row.get('away_abbr'), 'AWY')} @ {_safe(row.get('home_abbr'), 'HME')}"
            f" • {_safe(row.get('tip_et'), 'TBD')} • ESPN {event_id}"
        )

    event_ids = list(labels)
    selected_event_id = st.selectbox(
        "🏈 Matchup research board",
        options=event_ids,
        format_func=lambda value: labels.get(value, value),
        key="nfl_rushing_yards_step2_event",
    )

    with st.spinner("🏃 Loading exact-ID rushing workload + run-front context…"):
        context = _load_rushing_context(selected_event_id)

    if not context.get("ready"):
        st.warning(
            "Rushing Yards context failed closed. No player or matchup values were guessed. "
            f"Reason: {context.get('reason') or 'production API unavailable'}"
        )
        return
    if not context.get("data_available"):
        st.info(
            "The event identity and API contract are verified, but no current-roster rushing workload is available yet. "
            "The page is intentionally showing no synthetic fallback."
        )
        return

    teams = context.get("teams") or []
    teams = sorted(teams, key=lambda item: 0 if _safe(item.get("home_away"), "").lower() == "away" else 1)
    tab_labels = [f"{_safe(team.get('team_abbreviation'), 'NFL')} {_safe(team.get('home_away'), '').upper()}" for team in teams]
    tabs = st.tabs(tab_labels)
    for tab, team in zip(tabs, teams):
        with tab:
            _render_team_context(team)

    stamp = _safe(context.get("captured_at_utc"), "—")
    attempts = _safe(context.get("request_attempts"), "—")
    st.caption(
        f"✅ Schema {rushing_context_api.SCHEMA_VERSION} • official ESPN event {selected_event_id} • "
        f"captured {stamp} • request attempts {attempts} • sportsbook influence 0.0%"
    )
    if context.get("source_note"):
        st.caption(f"Source note: {context.get('source_note')}")


def render_nfl_rushing_yards_hub() -> None:
    """Render Ground Game Lab Steps 1-2 with exact-ID production context."""
    st.markdown(_RUSH_CSS, unsafe_allow_html=True)
    st.markdown(
        '''
        <section class="krush-hero">
          <div class="krush-kicker">NFL • Rushing Yards</div>
          <div class="krush-title">🏃 Ground Game <span>Lab</span></div>
          <div class="krush-sub">A cleaner home for running-back research. Step 2 now adds verified current-roster rushing workload and opponent run-front context from the Kyre Sports API. Projection and market math remain intentionally OFF until later certified steps.</div>
          <div class="krush-chiprow">
            <span class="krush-chip">✅ CLEAN UI</span>
            <span class="krush-chip">✅ PLAYER + MATCHUP DATA</span>
            <span class="krush-chip">🏈 EXACT ESPN IDs</span>
            <span class="krush-chip lock">🧊 PASSING YARDS FROZEN</span>
            <span class="krush-chip lock">🔒 MODEL OFF</span>
          </div>
        </section>
        <div class="krush-board">
          <div class="krush-tool live"><div class="icon">🏃</div><b>Workhorse Volume ✅</b><span>Verified carries, yards, efficiency, touchdowns and role sample.</span></div>
          <div class="krush-tool live"><div class="icon">🧱</div><b>Run Front ✅</b><span>Opponent rush attempts, yards, YPC and touchdowns allowed.</span></div>
          <div class="krush-tool"><div class="icon">⚡</div><b>Explosiveness</b><span>Advanced efficiency and big-play profile come next.</span></div>
          <div class="krush-tool"><div class="icon">🎯</div><b>Market Edge</b><span>Verified line, probability and grade come later.</span></div>
        </div>
        <div class="krush-progress">
          <div class="krush-progress-top"><b>Rushing Yards build board</b><span>2 OF 4 • DATA LIVE</span></div>
          <div class="krush-track"><div class="krush-fill"></div></div>
          <div class="krush-stage-row">
            <span class="krush-stage on">1 • CLEAN UI ✅</span>
            <span class="krush-stage on">2 • PLAYER + MATCHUP DATA ✅</span>
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
        _render_context_board(games)

    st.markdown(
        '<div class="krush-guard">🧊 <b>Frozen-line guard:</b> Step 2 adds read-only exact-ID player and matchup context only. It does not alter the certified Passing Yards chain, projection math, probability logic, FanDuel transport, grading, freshness rules, or any CFB surface. Rushing Yards model/market logic remains OFF and sportsbook projection influence remains 0.0%.</div>',
        unsafe_allow_html=True,
    )


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    """Router-compatible entrypoint."""
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V1 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = ["MODEL_VERSION", "render_nfl_hub", "render_nfl_rushing_yards_hub"]
