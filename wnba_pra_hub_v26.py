"""WNBA PRA V2.6 — Step 3 team history + matchup context UI.

Keeps Step 1 schedule verification and Step 2 player pool intact. Adds verified
team record, L10/L5, H2H and recent scoring/pace/efficiency context to each WNBA
game card. V2.6 does not feed these values into the PRA projection yet.
"""
from __future__ import annotations

import math
import pandas as pd
import streamlit as st

import wnba_pra_hub_v25 as v25
import wnba_context_v26 as context

MODEL_VERSION = "PRA V2.6"

CONTEXT_CSS = r"""
<style>
.w26-panel{border:1px solid #345875;background:radial-gradient(circle at 95% 0%,rgba(80,205,255,.08),transparent 34%),linear-gradient(145deg,#0d1928,#09121e);border-radius:18px;padding:14px 15px;margin:12px 0 14px}
.w26-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.w26-head b{color:#fff;font-size:1rem}.w26-head span{color:#68d8ff;font-size:.52rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase}.w26-health{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.w26-health div{background:#0a1523;border:1px solid #2c405b;border-radius:12px;padding:9px 10px}.w26-health span{display:block;color:#71849f;font-size:.46rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.w26-health b{display:block;color:#fff;font-size:.86rem;margin-top:4px}.w26-health .good b{color:#75efba}.w26-health .warn b{color:#ffe083}.w26-banner{margin-top:9px;border-radius:11px;padding:8px 10px;background:#0a2a22;border:1px solid #246b53;color:#90f1c8;font-size:.64rem;line-height:1.5}.w26-banner.warn{background:#29230e;border-color:#6f5e24;color:#eedb90}
.w26-context{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:12px 0}.w26-box{border:1px solid #2b4261;background:#091625;border-radius:14px;padding:10px}.w26-box.h2h{border-color:#5b4774;background:#171326}.w26-label{color:#6f88a6;font-size:.47rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.w26-main{color:#fff;font-size:.82rem;font-weight:950;margin-top:4px}.w26-sub{color:#8da0ba;font-size:.55rem;line-height:1.5;margin-top:4px}.w26-adv{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:8px}.w26-adv div{border:1px solid #203650;background:#08131f;border-radius:9px;padding:6px}.w26-adv span{display:block;color:#617b9b;font-size:.4rem;text-transform:uppercase;font-weight:900}.w26-adv b{display:block;color:#dbeafe;font-size:.64rem;margin-top:2px}.w26-tag{display:inline-flex;align-items:center;border:1px solid #2b526a;border-radius:999px;padding:3px 7px;color:#70dcff;font-size:.46rem;font-weight:900;margin-top:6px}.w26-note{border-left:3px solid #61d7ff;background:#0a1b2a;border-radius:0 11px 11px 0;padding:9px 11px;color:#9db1c9;font-size:.61rem;line-height:1.55;margin:10px 0}.w26-note b{color:#e8f6ff}
@media(max-width:900px){.w26-health{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:700px){.w26-context{grid-template-columns:1fr}.w26-health{grid-template-columns:repeat(2,minmax(0,1fr))}.w26-head{align-items:flex-start;flex-direction:column}}
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


def _context_panel(day):
    with st.spinner("🏀 Verifying WNBA team form + H2H + recent pace environment…"):
        diag = context.context_diagnostics(day)
    state = str(diag.get("state") or "PARTIAL")
    cls = "good" if state == "VERIFIED" else "warn"
    if state == "VERIFIED":
        banner = (
            f'✅ Step 3 context connected for <b>{diag.get("records_verified",0)}/{diag.get("teams",0)} slate teams</b>. '
            'Team history is visible on the game cards, but remains descriptive and does not alter player PRA yet.'
        )
    else:
        banner = '🟡 Team context is partially available. Missing values stay blank and are not manufactured or used as PRA adjustments.'
    st.markdown(
        '<div class="w26-panel">'
        '<div class="w26-head"><b>🧭 V2.6 WNBA Matchup Context Verification</b><span>Step 3 • team context only</span></div>'
        '<div class="w26-health">'
        f'<div class="{cls}"><span>Verification</span><b>{_e(state)}</b></div>'
        f'<div class="good"><span>Team records</span><b>{diag.get("records_verified",0)}/{diag.get("teams",0)}</b></div>'
        f'<div><span>Slate games</span><b>{diag.get("games",0)}</b></div>'
        f'<div class="good"><span>Advanced teams</span><b>{diag.get("advanced_teams",0)}/{diag.get("teams",0)}</b></div>'
        f'<div><span>Advanced samples</span><b>{diag.get("advanced_games",0)}</b></div>'
        f'<div><span>H2H samples</span><b>{diag.get("h2h_samples",0)}</b></div>'
        '</div>'
        f'<div class="w26-banner {"" if state=="VERIFIED" else "warn"}">{banner}<br><b>Source:</b> {_e(diag.get("source") or "—")}</div>'
        '</div>', unsafe_allow_html=True,
    )
    if st.button("🔄 RECHECK WNBA MATCHUP CONTEXT", use_container_width=True, key=f"wnba_v26_recheck_{diag.get('selected_date')}"):
        context.clear_context_cache()
        st.rerun()


def _team_box(name, obj, side):
    return (
        '<div class="w26-box">'
        f'<div class="w26-label">{_e(name)} • team form</div>'
        f'<div class="w26-main">{_record(obj)} • L10 {_record(obj,"L10")} • L5 {_record(obj,"L5")}</div>'
        f'<div class="w26-sub">Season {_fmt(obj.get("PF"))} PF / {_fmt(obj.get("PA"))} PA • Diff {_fmt(obj.get("DIFF"))}<br>'
        f'L10 {_fmt(obj.get("L10_PF"))} PF / {_fmt(obj.get("L10_PA"))} PA • Diff {_fmt(obj.get("L10_DIFF"))}</div>'
        '<div class="w26-adv">'
        f'<div><span>Pace L10*</span><b>{_fmt(obj.get("PACE_L10"))}</b></div>'
        f'<div><span>OffRtg L10*</span><b>{_fmt(obj.get("ORTG_L10"))}</b></div>'
        f'<div><span>DefRtg L10*</span><b>{_fmt(obj.get("DRTG_L10"))}</b></div>'
        '</div>'
        f'<div class="w26-tag">{int(obj.get("ADV_GAMES",0) or 0)} advanced game samples</div>'
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
        '<div class="w26-box h2h">'
        '<div class="w26-label">Head-to-head • last 10 available</div>'
        f'<div class="w26-main">{main}</div><div class="w26-sub">{sub}</div>'
        '<div class="w26-tag">small context layer • not a projection input yet</div>'
        '</div>'
    )


def _game_card_v26(row, stats, roster_counts=None):
    away_id, home_id = int(row.get("away_team_id") or 0), int(row.get("home_team_id") or 0)
    away_name, home_name = str(row.get("away_team") or "Away"), str(row.get("home_team") or "Home")
    away_pool = context.team_player_pool(stats, away_id)
    home_pool = context.team_player_pool(stats, home_id)
    ctx = context.game_context(row)
    away_ctx, home_ctx, h2h = ctx.get("away", {}), ctx.get("home", {}), ctx.get("h2h", {})
    status = str(row.get("status") or row.get("status_text") or "Scheduled")
    tip = str(row.get("first_tip_et") or "—")
    venue = str(row.get("venue") or "Venue TBD")
    away_count = roster_counts.get(away_id) if roster_counts else None
    home_count = roster_counts.get(home_id) if roster_counts else None
    away_meta = f"{len(away_pool)} stat rows" + (f" • roster {away_count}" if away_count is not None else "")
    home_meta = f"{len(home_pool)} stat rows" + (f" • roster {home_count}" if home_count is not None else "")
    player_table = v25.v24.v23._player_table
    st.markdown(
        '<div class="w2-game">'
        f'<div class="w2-game-top"><span>{_e(status)}</span><span>{_e(tip)}</span></div>'
        '<div class="w2-match">'
        f'<div class="w2-team"><img src="{context.logo_url(away_id)}"><b>{_e(away_name)}</b><span>{_e(away_meta)} • {_record(away_ctx)}</span></div>'
        '<div class="w2-at">@</div>'
        f'<div class="w2-team"><img src="{context.logo_url(home_id)}"><b>{_e(home_name)}</b><span>{_e(home_meta)} • {_record(home_ctx)}</span></div>'
        '</div>'
        f'<div class="w2-venue">📍 {_e(venue)} • {_e(status)}</div>'
        '<div class="w26-context">'
        f'{_team_box(away_name, away_ctx, "away")}{_team_box(home_name, home_ctx, "home")}{_h2h_box(away_name, home_name, h2h)}'
        '</div>'
        '<div class="w23-teamgrid">'
        f'<div class="w23-teamcard"><div class="w23-teamhead"><b>{_e(away_name)}</b><span>season / L10 / L5</span></div>{player_table(away_pool)}</div>'
        f'<div class="w23-teamcard"><div class="w23-teamhead"><b>{_e(home_name)}</b><span>season / L10 / L5</span></div>{player_table(home_pool)}</div>'
        '</div>'
        '<div class="w26-note"><b>Step 3 context only:</b> records, recent scoring, H2H and *approximate possession-based Pace/OffRtg/DefRtg are verified for display. They are <b>not applied to PRA projections yet</b>. Injuries, confirmed starters and usage/role changes remain later steps.</div>'
        '</div>', unsafe_allow_html=True,
    )


# Keep all Step 1/2 data dependencies, then add the Step 3 presentation layer.
for module in (v25.v24.v23.hub, v25.v24.v23):
    module.current_season = context.current_season
    module.data_health = context.data_health
    module.empirical_profile = context.empirical_profile
    module.game_for_team = context.game_for_team
    module.logo_url = context.logo_url
    module.official_roster = context.official_roster
    module.player_form_table = context.player_form_table
    module.player_game_log = context.player_game_log
    module.schedule_for_date = context.schedule_for_date
    module.slate_player_pool = context.slate_player_pool
    module.team_player_pool = context.team_player_pool

v25.v24.v23.hub.MODEL_VERSION = MODEL_VERSION


def _hero_v26(day):
    st.markdown(
        '<div class="w2-hero">'
        '<div class="w2-kicker">KYRE SPORTS AI • WNBA PRA INTELLIGENCE</div>'
        '<div class="w2-title">🏀 WNBA PRA Command Center — V2.6</div>'
        '<div class="w2-sub">Step 1 verifies the slate. Step 2 verifies current players and P/R/A production. Step 3 now verifies team history and matchup context: season record, Last 10, Last 5, head-to-head, scoring environment and approximate recent pace/efficiency. These new layers remain display-only until the PRA model is explicitly upgraded later.</div>'
        '<div class="w2-pills">'
        f'<div class="w2-pill">📅 Slate <b>{_e(day)}</b></div>'
        '<div class="w2-pill">🧠 <b>PRA V2.6</b></div>'
        '<div class="w2-pill">✅ <b>Schedule + players</b></div>'
        '<div class="w2-pill">🧭 <b>Team context</b></div>'
        '<div class="w2-pill">🔒 <b>No PRA adjustment yet</b></div>'
        '</div></div>', unsafe_allow_html=True,
    )
    v25.v24._schedule_panel(day)
    v25._player_panel(day)
    _context_panel(day)


v25.v24.v23.hub._hero = _hero_v26
v25.v24.v23._game_card = _game_card_v26
v25.v24.v23.hub._game_card = _game_card_v26
v25.v24.v23.hub._slate_tab = v25.v24.v23._slate_tab


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(v25.v24.v23.EXTRA_CSS + v25.v24.SCHEDULE_CSS + v25.PLAYER_CSS + CONTEXT_CSS, unsafe_allow_html=True)
    st.caption("🔒 WNBA league isolation active • PRA V2.6 • Step 1 schedule + Step 2 players + Step 3 matchup context")
    return v25.v24.v23.hub.render_wnba_pra_hub(section_header, status_info, team_logo, h)
