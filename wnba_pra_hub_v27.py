"""WNBA PRA V2.7 — Step 4 availability + confirmed starters.

Keeps V2.4 schedule verification, V2.5 current player pool and V2.6 matchup
context. Step 4 adds provider-reported injury/status designations and explicit
starter confirmations. Starters are never guessed; until an explicit lineup is
published the page says PENDING. These fields remain display-only and do not yet
change PRA projections.
"""
from __future__ import annotations

import math
import pandas as pd
import streamlit as st

import wnba_pra_hub_v25 as v25
import wnba_context_v26 as context
import wnba_availability_v27 as availability

MODEL_VERSION = "PRA V2.7"

CONTEXT_CSS = r"""
<style>
.w27-panel{border:1px solid #345875;background:radial-gradient(circle at 95% 0%,rgba(80,205,255,.08),transparent 34%),linear-gradient(145deg,#0d1928,#09121e);border-radius:18px;padding:14px 15px;margin:12px 0 14px}
.w27-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.w27-head b{color:#fff;font-size:1rem}.w27-head span{color:#68d8ff;font-size:.52rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase}
.w27-health{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.w27-health div{background:#0a1523;border:1px solid #2c405b;border-radius:12px;padding:9px 10px}.w27-health span{display:block;color:#71849f;font-size:.46rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.w27-health b{display:block;color:#fff;font-size:.86rem;margin-top:4px}.w27-health .good b{color:#75efba}.w27-health .warn b{color:#ffe083}.w27-health .bad b{color:#ff929e}.w27-banner{margin-top:9px;border-radius:11px;padding:8px 10px;background:#0a2a22;border:1px solid #246b53;color:#90f1c8;font-size:.64rem;line-height:1.5}.w27-banner.warn{background:#29230e;border-color:#6f5e24;color:#eedb90}
.w27-context{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:12px 0}.w27-box{border:1px solid #2b4261;background:#091625;border-radius:14px;padding:10px}.w27-box.h2h{border-color:#5b4774;background:#171326}.w27-label{color:#6f88a6;font-size:.47rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.w27-main{color:#fff;font-size:.82rem;font-weight:950;margin-top:4px}.w27-sub{color:#8da0ba;font-size:.55rem;line-height:1.5;margin-top:4px}.w27-adv{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:8px}.w27-adv div{border:1px solid #203650;background:#08131f;border-radius:9px;padding:6px}.w27-adv span{display:block;color:#617b9b;font-size:.4rem;text-transform:uppercase;font-weight:900}.w27-adv b{display:block;color:#dbeafe;font-size:.64rem;margin-top:2px}.w27-tag{display:inline-flex;align-items:center;border:1px solid #2b526a;border-radius:999px;padding:3px 7px;color:#70dcff;font-size:.46rem;font-weight:900;margin-top:6px}.w27-note{border-left:3px solid #61d7ff;background:#0a1b2a;border-radius:0 11px 11px 0;padding:9px 11px;color:#9db1c9;font-size:.61rem;line-height:1.55;margin:10px 0}.w27-note b{color:#e8f6ff}
.w27-avail{border:1px solid #533d69;background:linear-gradient(145deg,#151326,#0b1220);border-radius:16px;padding:11px;margin:11px 0}.w27-avail-title{display:flex;justify-content:space-between;gap:8px;align-items:center}.w27-avail-title b{color:#fff;font-size:.8rem}.w27-avail-title span{color:#f29ac5;font-size:.48rem;font-weight:950;text-transform:uppercase;letter-spacing:.08em}.w27-avgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:9px}.w27-avteam{border:1px solid #303d58;background:#091523;border-radius:13px;padding:9px}.w27-avteam h4{color:#fff;font-size:.69rem;margin:0 0 6px}.w27-line{color:#9fb0c5;font-size:.55rem;line-height:1.55;margin:3px 0}.w27-line b{color:#eef5ff}.w27-pill{display:inline-flex;border-radius:999px;padding:2px 6px;margin:2px 3px 2px 0;font-size:.46rem;font-weight:950;border:1px solid #36506a;color:#b8c9db}.w27-pill.good{border-color:#246c52;color:#78efba;background:#0a2b21}.w27-pill.warn{border-color:#765f20;color:#ffe083;background:#28210c}.w27-pill.bad{border-color:#7c3746;color:#ff9daa;background:#2a1118}.w27-pill.info{border-color:#315a74;color:#78ddff;background:#0a1e2b}.w27-source{color:#7186a2;font-size:.49rem;margin-top:7px;line-height:1.45}
.w27-topgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:12px}
@media(max-width:900px){.w27-health{grid-template-columns:repeat(3,minmax(0,1fr))}.w27-topgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:700px){.w27-context,.w27-avgrid{grid-template-columns:1fr}.w27-health{grid-template-columns:repeat(2,minmax(0,1fr))}.w27-head{align-items:flex-start;flex-direction:column}.w27-topgrid{grid-template-columns:1fr}}
</style>
"""


def _e(v):
    return v25._e(v)


def _fmt(v, digits=1, fallback="—"):
    try:
        x = float(v)
        if math.isnan(x):
            return fallback
        return f"{x:.{digits}f}"
    except Exception:
        return fallback


def _record(obj, prefix=""):
    if prefix == "L10":
        return f"{int(obj.get('L10_W',0))}-{int(obj.get('L10_L',0))}"
    if prefix == "L5":
        return f"{int(obj.get('L5_W',0))}-{int(obj.get('L5_L',0))}"
    return f"{int(obj.get('W',0))}-{int(obj.get('L',0))}"


def _data_health(schedule, stats):
    health = context.data_health(schedule, stats)
    try:
        diag = availability.availability_diagnostics(st.session_state.get("wnba_pra_v2_date"))
    except Exception:
        diag = {}
    if stats is not None and not stats.empty:
        health["WNBA player stats"] = "CONNECTED"
        health["Official rosters"] = "CONNECTED"
    health["Injury status"] = "CONNECTED" if diag.get("state") == "CONNECTED" else "CHECK"
    teams = int(diag.get("teams") or 0)
    confirmed = int(diag.get("lineups_confirmed") or 0)
    health["Confirmed starters"] = "CONNECTED" if teams and confirmed >= teams else "PENDING"
    return health


def _player_panel(day):
    diag = availability.player_pool_diagnostics(day)
    state = str(diag.get("state") or "CHECK")
    cls = "good" if state == "VERIFIED" else "warn"
    st.markdown(
        '<div class="w27-panel">'
        '<div class="w27-head"><b>👥 V2.7 Current Player Pool Check</b><span>current roster gate</span></div>'
        '<div class="w27-health">'
        f'<div class="{cls}"><span>Verification</span><b>{_e(state)}</b></div>'
        f'<div><span>Slate teams</span><b>{diag.get("teams",0)}</b></div>'
        f'<div class="good"><span>Roster players</span><b>{diag.get("roster_players",0)}</b></div>'
        f'<div class="good"><span>Eligible pool</span><b>{diag.get("players",0)}</b></div>'
        f'<div><span>Raw stat rows</span><b>{diag.get("raw_rows",0)}</b></div>'
        '<div class="good"><span>Roster gate</span><b>ACTIVE</b></div>'
        '</div>'
        '<div class="w27-banner">✅ The slate pool is now counted from current rosters, not historical stat rows. Team/name matching prevents old or traded rows from inflating the active pool.</div>'
        '</div>', unsafe_allow_html=True,
    )


def _context_panel(day):
    with st.spinner("🏀 Verifying WNBA team form + H2H + recent pace environment…"):
        diag = context.context_diagnostics(day)
    state = str(diag.get("state") or "PARTIAL")
    cls = "good" if state == "VERIFIED" else "warn"
    banner = (
        f'✅ Step 3 context connected for <b>{diag.get("records_verified",0)}/{diag.get("teams",0)} slate teams</b>. Team history remains descriptive and does not alter player PRA yet.'
        if state == "VERIFIED" else
        '🟡 Team context is partially available. Missing values stay blank and are not manufactured or used as PRA adjustments.'
    )
    st.markdown(
        '<div class="w27-panel">'
        '<div class="w27-head"><b>🧭 V2.7 Matchup Context Check</b><span>Step 3 retained</span></div>'
        '<div class="w27-health">'
        f'<div class="{cls}"><span>Verification</span><b>{_e(state)}</b></div>'
        f'<div class="good"><span>Team records</span><b>{diag.get("records_verified",0)}/{diag.get("teams",0)}</b></div>'
        f'<div><span>Slate games</span><b>{diag.get("games",0)}</b></div>'
        f'<div class="good"><span>Advanced teams</span><b>{diag.get("advanced_teams",0)}/{diag.get("teams",0)}</b></div>'
        f'<div><span>Advanced samples</span><b>{diag.get("advanced_games",0)}</b></div>'
        f'<div><span>H2H samples</span><b>{diag.get("h2h_samples",0)}</b></div>'
        '</div>'
        f'<div class="w27-banner {"" if state=="VERIFIED" else "warn"}">{banner}</div>'
        '</div>', unsafe_allow_html=True,
    )


def _availability_panel(day):
    with st.spinner("🏥 Checking WNBA injury designations + explicit starter flags…"):
        diag = availability.availability_diagnostics(day)
    state = str(diag.get("state") or "CHECK")
    cls = "good" if state == "CONNECTED" else "warn"
    teams = int(diag.get("teams") or 0)
    confirmed_teams = int(diag.get("lineups_confirmed") or 0)
    st.markdown(
        '<div class="w27-panel">'
        '<div class="w27-head"><b>🏥 V2.7 Availability + Starter Verification</b><span>Step 4 • status only</span></div>'
        '<div class="w27-health">'
        f'<div class="{cls}"><span>Availability feed</span><b>{_e(state)}</b></div>'
        f'<div class="good"><span>Current players</span><b>{diag.get("players",0)}</b></div>'
        f'<div><span>Injury designations</span><b>{diag.get("injury_designations",0)}</b></div>'
        f'<div><span>Confirmed starters</span><b>{diag.get("confirmed_starters",0)}</b></div>'
        f'<div class="{("good" if teams and confirmed_teams>=teams else "warn")}"><span>Lineups confirmed</span><b>{confirmed_teams}/{teams}</b></div>'
        f'<div><span>Team injury feeds</span><b>{diag.get("team_injury_feeds",0)}/{teams}</b></div>'
        '</div>'
        '<div class="w27-banner warn">Starter status is <b>never inferred</b>. If the provider has not published an explicit starting five, V2.7 shows PENDING. Injury/status and starter fields are display-only and do not move PRA yet.</div>'
        '</div>', unsafe_allow_html=True,
    )
    if st.button("🔄 RECHECK WNBA AVAILABILITY", use_container_width=True, key=f"wnba_v27_avail_{diag.get('selected_date')}"):
        availability.clear_availability_cache()
        st.rerun()


def _team_box(name, obj):
    return (
        '<div class="w27-box">'
        f'<div class="w27-label">{_e(name)} • team form</div>'
        f'<div class="w27-main">{_record(obj)} • L10 {_record(obj,"L10")} • L5 {_record(obj,"L5")}</div>'
        f'<div class="w27-sub">Season {_fmt(obj.get("PF"))} PF / {_fmt(obj.get("PA"))} PA • Diff {_fmt(obj.get("DIFF"))}<br>'
        f'L10 {_fmt(obj.get("L10_PF"))} PF / {_fmt(obj.get("L10_PA"))} PA • Diff {_fmt(obj.get("L10_DIFF"))}</div>'
        '<div class="w27-adv">'
        f'<div><span>Pace L10*</span><b>{_fmt(obj.get("PACE_L10"))}</b></div>'
        f'<div><span>OffRtg L10*</span><b>{_fmt(obj.get("ORTG_L10"))}</b></div>'
        f'<div><span>DefRtg L10*</span><b>{_fmt(obj.get("DRTG_L10"))}</b></div>'
        '</div>'
        f'<div class="w27-tag">{int(obj.get("ADV_GAMES",0) or 0)} advanced game samples</div>'
        '</div>'
    )


def _h2h_box(away_name, home_name, h2h):
    g = int(h2h.get("GAMES",0) or 0)
    if g:
        main = f'{_e(away_name)} {int(h2h.get("AWAY_W",0))}-{int(h2h.get("HOME_W",0))}'
        sub = f'Last {g} • Avg total {_fmt(h2h.get("AVG_TOTAL"))} • {_e(away_name)} avg margin {_fmt(h2h.get("AWAY_MARGIN"))}<br>Current-season meetings {int(h2h.get("CURRENT_GAMES",0) or 0)}'
    else:
        main = 'No prior meetings found'
        sub = 'H2H is not forced when a verified historical sample is unavailable.'
    return (
        '<div class="w27-box h2h"><div class="w27-label">Head-to-head • last 10 available</div>'
        f'<div class="w27-main">{main}</div><div class="w27-sub">{sub}</div>'
        '<div class="w27-tag">small context layer • not a projection input yet</div></div>'
    )


def _designation_class(status):
    s = str(status or "").upper()
    if s in ("OUT","INACTIVE","DOUBTFUL"):
        return "bad"
    if s in ("QUESTIONABLE","DAY-TO-DAY","PROBABLE"):
        return "warn"
    if s in ("AVAILABLE",):
        return "good"
    return "info"


def _availability_team(name, team_id, frame, feed_ok):
    team = frame[frame["TEAM_ID"].astype(int).eq(int(team_id))] if frame is not None and not frame.empty else pd.DataFrame()
    starters = team[team["STARTER_CONFIRMED"].eq(True)] if not team.empty else pd.DataFrame()
    flagged = team[~team["DESIGNATION"].astype(str).eq("NO DESIGNATION")] if not team.empty else pd.DataFrame()
    if len(starters) >= 5:
        starter_text = " • ".join(starters["PLAYER_NAME"].astype(str).head(5).tolist())
        starter_html = f'<span class="w27-pill good">STARTERS CONFIRMED 5/5</span><div class="w27-line">{_e(starter_text)}</div>'
    elif len(starters):
        starter_text = " • ".join(starters["PLAYER_NAME"].astype(str).tolist())
        starter_html = f'<span class="w27-pill warn">PARTIAL STARTERS {len(starters)}/5</span><div class="w27-line">{_e(starter_text)}</div>'
    else:
        starter_html = '<span class="w27-pill warn">STARTERS PENDING</span><div class="w27-line">No explicit starting five has been published by the connected provider yet.</div>'
    if not feed_ok:
        injury_html = '<div class="w27-line"><b>Injuries:</b> feed unavailable — no status claimed.</div>'
    elif flagged.empty:
        injury_html = '<div class="w27-line"><b>Injuries:</b> no provider designation currently returned.</div>'
    else:
        bits = []
        for _, r in flagged.iterrows():
            status = str(r.get("DESIGNATION") or "STATUS")
            detail = str(r.get("DETAIL") or "")
            bits.append(f'<span class="w27-pill {_designation_class(status)}">{_e(status)} • {_e(r.get("PLAYER_NAME"))}</span>' + (f'<div class="w27-line">{_e(detail)}</div>' if detail else ''))
        injury_html = '<div class="w27-line"><b>Provider designations</b></div>' + ''.join(bits)
    return f'<div class="w27-avteam"><h4>{_e(name)}</h4>{starter_html}{injury_html}</div>'


def _game_card(row, stats, roster_counts=None):
    away_id, home_id = int(row.get("away_team_id") or 0), int(row.get("home_team_id") or 0)
    away_name, home_name = str(row.get("away_team") or "Away"), str(row.get("home_team") or "Home")
    away_pool = availability.team_player_pool(stats, away_id)
    home_pool = availability.team_player_pool(stats, home_id)
    ctx = context.game_context(row)
    away_ctx, home_ctx, h2h = ctx.get("away", {}), ctx.get("home", {}), ctx.get("h2h", {})
    av = availability.availability_for_game(row, stats)
    av_frame = av.get("players") if isinstance(av, dict) else pd.DataFrame()
    feed_ok = bool(av.get("summary_connected")) or int(av.get("team_feeds_connected") or 0) > 0
    status = str(row.get("status") or row.get("status_text") or "Scheduled")
    tip = str(row.get("first_tip_et") or "—")
    venue = str(row.get("venue") or "Venue TBD")
    player_table = v25.v24.v23._player_table
    st.markdown(
        '<div class="w2-game">'
        f'<div class="w2-game-top"><span>{_e(status)}</span><span>{_e(tip)}</span></div>'
        '<div class="w2-match">'
        f'<div class="w2-team"><img src="{availability.logo_url(away_id)}"><b>{_e(away_name)}</b><span>{len(away_pool)} current players • {_record(away_ctx)}</span></div>'
        '<div class="w2-at">@</div>'
        f'<div class="w2-team"><img src="{availability.logo_url(home_id)}"><b>{_e(home_name)}</b><span>{len(home_pool)} current players • {_record(home_ctx)}</span></div>'
        '</div>'
        f'<div class="w2-venue">📍 {_e(venue)} • {_e(status)}</div>'
        '<div class="w27-context">'
        f'{_team_box(away_name, away_ctx)}{_team_box(home_name, home_ctx)}{_h2h_box(away_name, home_name, h2h)}'
        '</div>'
        '<div class="w27-avail"><div class="w27-avail-title"><b>🏥 Availability + confirmed starters</b><span>explicit provider status only</span></div>'
        '<div class="w27-avgrid">'
        f'{_availability_team(away_name, away_id, av_frame, feed_ok)}{_availability_team(home_name, home_id, av_frame, feed_ok)}'
        '</div><div class="w27-source">Source: {_e(av.get("source") or "—")} • No starter is labeled confirmed unless the provider returns an explicit starter flag.</div></div>'
        '<div class="w23-teamgrid">'
        f'<div class="w23-teamcard"><div class="w23-teamhead"><b>{_e(away_name)}</b><span>season / L10 / L5</span></div>{player_table(away_pool)}</div>'
        f'<div class="w23-teamcard"><div class="w23-teamhead"><b>{_e(home_name)}</b><span>season / L10 / L5</span></div>{player_table(home_pool)}</div>'
        '</div>'
        '<div class="w27-note"><b>Step 4 status only:</b> schedule, current players, team context, injuries/status and explicit starter flags are verified for display. <b>None of the new availability fields modify PRA yet.</b> Minutes and usage/role changes are the next modeling layer.</div>'
        '</div>', unsafe_allow_html=True,
    )


def _render_top5(picks):
    if not picks:
        st.markdown('<div class="w2-empty">No eligible current WNBA players were found for the selected slate.</div>', unsafe_allow_html=True)
        return
    cards = []
    for i, p in enumerate(picks, 1):
        first = " first" if i == 1 else ""
        cards.append(
            f'<div class="w23-pick{first}"><div class="w23-rank">#{i} BASELINE</div>'
            f'<div class="w23-name">{_e(p["name"])}</div><div class="w23-meta">{_e(p["team"])} vs {_e(p["opponent"])} • {p["min"]:.1f} MIN</div>'
            f'<div class="w23-pra">{p["pra"]:.1f} <span>Expected PRA</span></div>'
            '<div class="w23-split">'
            f'<div><span>PTS</span><b>{p["p"]:.1f}</b></div><div><span>REB</span><b>{p["r"]:.1f}</b></div><div><span>AST</span><b>{p["a"]:.1f}</b></div>'
            f'</div><div class="w23-meta">L10 {p["l10"]:.1f} • L5 {p["l5"]:.1f}</div></div>'
        )
    st.markdown(
        '<div class="w23-summary"><div class="w23-title">🏆 V2.7 Current-Roster PRA Baseline — Top 5</div>'
        '<div class="w23-sub">Still a descriptive P/R/A baseline only. Current-roster gating is active, but injury/starter status does not alter projections yet.</div>'
        f'<div class="w27-topgrid">{"".join(cards)}</div></div>', unsafe_allow_html=True,
    )


def _slate_tab(day, schedule, stats):
    st.markdown('<div class="w2-note blue"><b>V2.7 foundation:</b> schedule, current roster/player production, team matchup context and availability/starter status are connected. The PRA numbers remain descriptive until minutes/usage and matchup adjustments are intentionally activated.</div>', unsafe_allow_html=True)
    pool = availability.slate_player_pool(schedule, stats)
    teams = len(set(schedule.away_team_id.tolist() + schedule.home_team_id.tolist())) if schedule is not None and not schedule.empty else 0
    v25.v24.v23.hub._metrics([
        ("Games", len(schedule), "cyan"),
        ("Teams", teams, "pink"),
        ("Current player pool", len(pool), "good"),
        ("League guard", "WNBA ONLY", "warn"),
    ])
    if schedule is None or schedule.empty:
        st.markdown('<div class="w2-empty">No verified WNBA games were returned for this date.</div>', unsafe_allow_html=True)
        return
    _render_top5(v25.v24.v23._top5_baseline(schedule, stats))
    st.markdown("### 🗓️ Selected WNBA Games")
    for _, row in schedule.iterrows():
        _game_card(row, stats, {})


# Wire current-roster-safe data into the entire PRA presentation tree.
for module in (v25.v24.v23.hub, v25.v24.v23):
    module.current_season = availability.current_season
    module.data_health = _data_health
    module.empirical_profile = availability.empirical_profile
    module.game_for_team = availability.game_for_team
    module.logo_url = availability.logo_url
    module.official_roster = availability.official_roster
    module.player_form_table = availability.player_form_table
    module.player_game_log = availability.player_game_log
    module.schedule_for_date = availability.schedule_for_date
    module.slate_player_pool = availability.slate_player_pool
    module.team_player_pool = availability.team_player_pool

v25.v24.v23.hub.MODEL_VERSION = MODEL_VERSION


def _hero(day):
    st.markdown(
        '<div class="w2-hero">'
        '<div class="w2-kicker">KYRE SPORTS AI • WNBA PRA INTELLIGENCE</div>'
        '<div class="w2-title">🏀 WNBA PRA Command Center — V2.7</div>'
        '<div class="w2-sub">Step 1 schedule verification + Step 2 current roster/player production + Step 3 team history/matchup context + Step 4 provider-reported injury/status and explicit confirmed starters. Starter status is never guessed. Availability remains display-only until the next minutes/usage modeling step.</div>'
        '<div class="w2-pills">'
        f'<div class="w2-pill">📅 Slate <b>{_e(day)}</b></div>'
        '<div class="w2-pill">🧠 <b>PRA V2.7</b></div>'
        '<div class="w2-pill">👥 <b>Current rosters</b></div>'
        '<div class="w2-pill">🏥 <b>Availability</b></div>'
        '<div class="w2-pill">✅ <b>Explicit starters only</b></div>'
        '</div></div>', unsafe_allow_html=True,
    )
    v25.v24._schedule_panel(day)
    _player_panel(day)
    _context_panel(day)
    _availability_panel(day)


v25.v24.v23.hub._hero = _hero
v25.v24.v23.hub._game_card = _game_card
v25.v24.v23.hub._slate_tab = _slate_tab
v25.v24.v23._game_card = _game_card
v25.v24.v23._slate_tab = _slate_tab


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(v25.v24.v23.EXTRA_CSS + v25.v24.SCHEDULE_CSS + v25.PLAYER_CSS + CONTEXT_CSS, unsafe_allow_html=True)
    st.caption("🔒 WNBA league isolation active • PRA V2.7 • Step 4 availability + explicit starter verification")
    return v25.v24.v23.hub.render_wnba_pra_hub(section_header, status_info, team_logo, h)
