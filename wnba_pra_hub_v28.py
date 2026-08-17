"""WNBA PRA V2.8 — Step 5 projected minutes + role/usage modeling.

Keeps verified Steps 1-4. Step 5 is the first layer that intentionally changes
player P/R/A projections: availability can set minutes to zero, missing minutes
are reallocated across the active roster, explicit starters receive a small
minutes priority, and official Advanced USG% is used when available. Opponent
player-defense and sportsbook line grading remain later steps.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import streamlit as st

import wnba_pra_hub_v27 as v27
import wnba_role_v28 as role

MODEL_VERSION = "PRA V2.8"

ROLE_CSS = r"""
<style>
.w28-panel{border:1px solid #34627e;background:radial-gradient(circle at 5% 0%,rgba(34,211,238,.08),transparent 30%),linear-gradient(145deg,#0d1928,#08121e);border-radius:18px;padding:14px 15px;margin:12px 0 14px}.w28-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}.w28-head b{font-size:1rem;color:#fff}.w28-head span{color:#62ddff;font-size:.5rem;font-weight:950;text-transform:uppercase;letter-spacing:.1em}.w28-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.w28-metric{border:1px solid #2a405c;background:#091523;border-radius:12px;padding:9px}.w28-metric span{display:block;color:#6f84a1;font-size:.44rem;font-weight:950;text-transform:uppercase;letter-spacing:.07em}.w28-metric b{display:block;color:#fff;font-size:.84rem;margin-top:4px}.w28-metric.good b{color:#73efb7}.w28-metric.warn b{color:#ffe083}.w28-note{border-left:3px solid #45d9ff;background:#091d2c;padding:9px 11px;border-radius:0 11px 11px 0;color:#9db2ca;font-size:.61rem;line-height:1.5;margin-top:9px}.w28-role{border:1px solid #31516e;background:linear-gradient(145deg,#0b1726,#08131f);border-radius:16px;padding:11px;margin:12px 0}.w28-role-title{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:9px}.w28-role-title b{color:#fff;font-size:.82rem}.w28-role-title span{color:#70dcff;font-size:.47rem;font-weight:950;text-transform:uppercase}.w28-teamgrid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.w28-team{border:1px solid #273c57;background:#07131f;border-radius:13px;padding:9px}.w28-teamhead{display:flex;justify-content:space-between;gap:8px;align-items:center;border-bottom:1px solid #1d3148;padding-bottom:7px;margin-bottom:3px}.w28-teamhead b{color:#fff;font-size:.72rem}.w28-teamhead span{color:#758da9;font-size:.48rem}.w28-row{display:grid;grid-template-columns:1.45fr .5fr .62fr .52fr .52fr .52fr .58fr;gap:5px;align-items:center;padding:6px 0;border-bottom:1px solid #14263a;font-size:.52rem}.w28-row:last-child{border-bottom:0}.w28-row b{color:#eef5ff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.w28-row span{color:#98aac0;text-align:right}.w28-row.head b,.w28-row.head span{color:#607997;font-size:.4rem;text-transform:uppercase}.w28-player{display:flex;flex-direction:column;min-width:0}.w28-player small{font-size:.4rem;color:#778da7;margin-top:2px}.w28-badge{display:inline-flex;align-items:center;width:max-content;border-radius:999px;padding:1px 5px;font-size:.38rem;font-weight:950;margin-top:2px;border:1px solid #32506a;color:#a9bdd2}.w28-badge.out{border-color:#7c3746;background:#2a1118;color:#ff9daa}.w28-badge.warn{border-color:#745f22;background:#28210c;color:#ffe083}.w28-badge.start{border-color:#246b52;background:#092a20;color:#78efba}.w28-delta-up{color:#77efba!important}.w28-delta-down{color:#ff9daa!important}.w28-topgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:12px}.w28-pick{border:1px solid #304663;background:#091624;border-radius:14px;padding:10px}.w28-pick.first{border-color:#ff72ac;box-shadow:inset 3px 0 0 #ff72ac}.w28-rank{font-size:.47rem;color:#63ddff;font-weight:950}.w28-name{font-size:.76rem;color:#fff;font-weight:950;margin-top:4px}.w28-meta{font-size:.5rem;color:#8195ae;margin-top:3px;line-height:1.4}.w28-pra{font-size:1.35rem;color:#79efba;font-weight:1000;margin-top:7px}.w28-pra span{font-size:.43rem;color:#7489a4;text-transform:uppercase}.w28-split{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-top:7px}.w28-split div{border:1px solid #233850;border-radius:8px;padding:5px}.w28-split span{display:block;color:#6c839e;font-size:.38rem;text-transform:uppercase}.w28-split b{display:block;color:#fff;font-size:.62rem;margin-top:1px}
@media(max-width:900px){.w28-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.w28-teamgrid{grid-template-columns:1fr}.w28-topgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.w28-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.w28-head{align-items:flex-start;flex-direction:column}.w28-row{grid-template-columns:1.4fr .58fr .58fr .62fr}.w28-row .hide-mobile{display:none}.w28-topgrid{grid-template-columns:1fr}}
</style>
"""


def _e(v):
    return v27._e(v)


def _fmt(v, digits=1, fallback="—"):
    try:
        x = float(v)
        if math.isnan(x):
            return fallback
        return f"{x:.{digits}f}"
    except Exception:
        return fallback


def _attach_usage_with_name(pool: pd.DataFrame, usage: pd.DataFrame):
    """WNBA Stats IDs and ESPN roster IDs differ; match team + normalized name too."""
    out = pool.copy()
    for c in ("USG_PCT", "L10_USG_PCT", "L5_USG_PCT"):
        out[c] = np.nan
    if usage is None or usage.empty:
        return out
    by_id, by_name = {}, {}
    for _, r in usage.iterrows():
        tid = int(r.get("TEAM_ID") or 0)
        if pd.notna(r.get("PLAYER_ID")):
            by_id[(tid, int(float(r.get("PLAYER_ID"))))] = r
        name = role.availability._norm_name(r.get("PLAYER_NAME"))
        if name:
            by_name[(tid, name)] = r
    for idx, p in out.iterrows():
        tid = int(p.get("TEAM_ID") or 0)
        r = None
        pid = p.get("PLAYER_ID")
        if pd.notna(pid):
            r = by_id.get((tid, int(float(pid))))
        if r is None:
            r = by_name.get((tid, role.availability._norm_name(p.get("PLAYER_NAME"))))
        if r is not None:
            for c in ("USG_PCT", "L10_USG_PCT", "L5_USG_PCT"):
                out.at[idx, c] = role._num(r.get(c), np.nan)
    return out


# Runtime patch improves official-usage joins without changing the verified roster IDs.
role._attach_usage = _attach_usage_with_name


def _data_health(schedule, stats):
    health = v27._data_health(schedule, stats)
    try:
        diag = role.role_diagnostics(st.session_state.get("wnba_pra_v2_date"))
    except Exception:
        diag = {}
    health["Minutes + role"] = "CONNECTED" if diag.get("state") == "VERIFIED" else "CHECK"
    return health


def _role_panel(day):
    with st.spinner("🧠 Building conditional minutes + role/usage projections…"):
        diag = role.role_diagnostics(day)
    state = str(diag.get("state") or "CHECK")
    cls = "good" if state == "VERIFIED" else "warn"
    usage_connected = int(diag.get("usage_players") or 0) > 0
    st.markdown(
        '<div class="w28-panel">'
        '<div class="w28-head"><b>🧠 V2.8 Minutes + Role Verification</b><span>Step 5 • first projection adjustment</span></div>'
        '<div class="w28-grid">'
        f'<div class="w28-metric {cls}"><span>Verification</span><b>{_e(state)}</b></div>'
        f'<div class="w28-metric good"><span>Current players</span><b>{diag.get("players",0)}</b></div>'
        f'<div class="w28-metric good"><span>Team-minute checks</span><b>{diag.get("team_minutes_ok",0)}/{diag.get("teams",0)}</b></div>'
        f'<div class="w28-metric"><span>OUT applied</span><b>{diag.get("out_applied",0)}</b></div>'
        f'<div class="w28-metric warn"><span>Status uncertain</span><b>{diag.get("uncertain",0)}</b></div>'
        f'<div class="w28-metric {"good" if usage_connected else "warn"}"><span>Official USG rows</span><b>{diag.get("usage_players",0)}</b></div>'
        '</div>'
        f'<div class="w28-note"><b>Usage source:</b> {_e(diag.get("usage_source") or "unavailable")}. Team minutes are balanced to 200 conditional on QUESTIONABLE/DAY-TO-DAY players playing. OUT/INACTIVE/DOUBTFUL players are set to 0. Points, rebounds and assists are projected separately; opponent-defense adjustments are still off.</div>'
        '</div>', unsafe_allow_html=True,
    )
    if st.button("🔄 RECHECK MINUTES + ROLE", use_container_width=True, key=f"wnba_v28_role_{diag.get('selected_date')}"):
        role.clear_role_cache()
        st.rerun()


def _designation_badge(row):
    status = str(row.get("DESIGNATION") or "NO DESIGNATION").upper()
    if status in role.OUT_STATUSES:
        return f'<span class="w28-badge out">{_e(status)}</span>'
    if status in role.UNCERTAIN_STATUSES:
        return f'<span class="w28-badge warn">{_e(status)}</span>'
    if bool(row.get("STARTER_CONFIRMED")):
        return '<span class="w28-badge start">STARTER</span>'
    return '<span class="w28-badge">ACTIVE</span>'


def _role_table(frame: pd.DataFrame, limit=10):
    if frame is None or frame.empty:
        return '<div class="w2-empty">No Step 5 player projections available.</div>'
    rows = ['<div class="w28-row head"><b>Player</b><span>Min</span><span>USG</span><span>PTS</span><span class="hide-mobile">REB</span><span class="hide-mobile">AST</span><span>PRA</span></div>']
    for _, p in frame.head(limit).iterrows():
        min_delta = float(p.get("MIN_DELTA") or 0.0)
        min_cls = "w28-delta-up" if min_delta > .5 else "w28-delta-down" if min_delta < -.5 else ""
        usg = _fmt(p.get("PROJ_USG"), 1)
        usg_delta = _fmt(p.get("ROLE_DELTA_PCT"), 1, "0.0")
        rows.append(
            '<div class="w28-row">'
            f'<div class="w28-player"><b>{_e(p.get("PLAYER_NAME") or "Player")}</b>{_designation_badge(p)}</div>'
            f'<span class="{min_cls}">{_fmt(p.get("PROJ_MIN"),1)}</span>'
            f'<span>{usg}{(" +"+usg_delta if usg!="—" and float(p.get("ROLE_DELTA_PCT") or 0)>0.05 else "")}</span>'
            f'<span>{_fmt(p.get("PROJ_PTS"),1)}</span>'
            f'<span class="hide-mobile">{_fmt(p.get("PROJ_REB"),1)}</span>'
            f'<span class="hide-mobile">{_fmt(p.get("PROJ_AST"),1)}</span>'
            f'<span><b>{_fmt(p.get("PROJ_PRA"),1)}</b></span>'
            '</div>'
        )
    return ''.join(rows)


def _role_game_section(row, stats):
    result = role.role_projection_for_game(row, stats)
    away_id = int(row.get("away_team_id") or 0)
    home_id = int(row.get("home_team_id") or 0)
    away = result.get("teams", {}).get(away_id, pd.DataFrame())
    home = result.get("teams", {}).get(home_id, pd.DataFrame())
    away_name = str(row.get("away_team") or "Away")
    home_name = str(row.get("home_team") or "Home")
    return (
        '<div class="w28-role">'
        '<div class="w28-role-title"><b>🧠 Step 5 • Projected minutes + role</b><span>P / R / A adjusted separately</span></div>'
        '<div class="w28-teamgrid">'
        f'<div class="w28-team"><div class="w28-teamhead"><b>{_e(away_name)}</b><span>Σ MIN {_fmt(away.get("PROJ_MIN",pd.Series(dtype=float)).sum(),1)}</span></div>{_role_table(away)}</div>'
        f'<div class="w28-team"><div class="w28-teamhead"><b>{_e(home_name)}</b><span>Σ MIN {_fmt(home.get("PROJ_MIN",pd.Series(dtype=float)).sum(),1)}</span></div>{_role_table(home)}</div>'
        '</div>'
        f'<div class="w27-source">Usage source: {_e(result.get("usage_source") or "unavailable")} • Availability source: {_e(result.get("availability_source") or "—")}</div>'
        '</div>'
    )


def _game_card(row, stats, roster_counts=None):
    away_id, home_id = int(row.get("away_team_id") or 0), int(row.get("home_team_id") or 0)
    away_name, home_name = str(row.get("away_team") or "Away"), str(row.get("home_team") or "Home")
    ctx = v27.context.game_context(row)
    away_ctx, home_ctx, h2h = ctx.get("away", {}), ctx.get("home", {}), ctx.get("h2h", {})
    av = role.availability_for_game(row, stats)
    av_frame = av.get("players") if isinstance(av, dict) else pd.DataFrame()
    feed_ok = bool(av.get("summary_connected")) or int(av.get("team_feeds_connected") or 0) > 0
    status = str(row.get("status") or row.get("status_text") or "Scheduled")
    tip = str(row.get("first_tip_et") or "—")
    venue = str(row.get("venue") or "Venue TBD")
    away_count = len(role.team_player_pool(stats, away_id))
    home_count = len(role.team_player_pool(stats, home_id))
    st.markdown(
        '<div class="w2-game">'
        f'<div class="w2-game-top"><span>{_e(status)}</span><span>{_e(tip)}</span></div>'
        '<div class="w2-match">'
        f'<div class="w2-team"><img src="{role.logo_url(away_id)}"><b>{_e(away_name)}</b><span>{away_count} current players • {v27._record(away_ctx)}</span></div>'
        '<div class="w2-at">@</div>'
        f'<div class="w2-team"><img src="{role.logo_url(home_id)}"><b>{_e(home_name)}</b><span>{home_count} current players • {v27._record(home_ctx)}</span></div>'
        '</div>'
        f'<div class="w2-venue">📍 {_e(venue)} • {_e(status)}</div>'
        '<div class="w27-context">'
        f'{v27._team_box(away_name,away_ctx)}{v27._team_box(home_name,home_ctx)}{v27._h2h_box(away_name,home_name,h2h)}'
        '</div>'
        '<div class="w27-avail"><div class="w27-avail-title"><b>🏥 Availability + confirmed starters</b><span>explicit provider status only</span></div>'
        '<div class="w27-avgrid">'
        f'{v27._availability_team(away_name,away_id,av_frame,feed_ok)}{v27._availability_team(home_name,home_id,av_frame,feed_ok)}'
        f'</div><div class="w27-source">Source: {_e(av.get("source") or "—")} • Starters remain pending unless an explicit provider flag is returned.</div></div>'
        f'{_role_game_section(row,stats)}'
        '<div class="w27-note"><b>Step 5 is active:</b> availability now changes projected minutes and therefore PTS/REB/AST. Official USG% can add a conservative role adjustment when teammates are unavailable. <b>Opponent defense, pace matchup and sportsbook lines are not applied yet.</b></div>'
        '</div>', unsafe_allow_html=True,
    )


def _adjusted_top5(schedule, stats):
    rows = []
    if schedule is None or schedule.empty:
        return rows
    for _, game in schedule.iterrows():
        result = role.role_projection_for_game(game, stats)
        for tid, frame in result.get("teams", {}).items():
            if frame is None or frame.empty:
                continue
            for _, p in frame.iterrows():
                status = str(p.get("DESIGNATION") or "NO DESIGNATION").upper()
                if status in role.OUT_STATUSES or float(p.get("PROJ_MIN") or 0) < 15:
                    continue
                opponent = game.get("home_team") if int(tid) == int(game.get("away_team_id") or 0) else game.get("away_team")
                rows.append({
                    "name": str(p.get("PLAYER_NAME") or "Player"), "team": str(p.get("TEAM_ABBREVIATION") or p.get("TEAM_NAME") or ""),
                    "opponent": str(opponent or "—"), "min": float(p.get("PROJ_MIN") or 0), "usg": p.get("PROJ_USG"),
                    "p": float(p.get("PROJ_PTS") or 0), "r": float(p.get("PROJ_REB") or 0), "a": float(p.get("PROJ_AST") or 0), "pra": float(p.get("PROJ_PRA") or 0),
                    "status": status, "starter": bool(p.get("STARTER_CONFIRMED")),
                })
    return sorted(rows, key=lambda x: x["pra"], reverse=True)[:5]


def _render_top5(picks):
    if not picks:
        st.markdown('<div class="w2-empty">No eligible Step 5 projections are available.</div>', unsafe_allow_html=True)
        return
    cards = []
    for i, p in enumerate(picks, 1):
        first = " first" if i == 1 else ""
        status = "STARTER" if p["starter"] else p["status"] if p["status"] != "NO DESIGNATION" else "ACTIVE"
        cards.append(
            f'<div class="w28-pick{first}"><div class="w28-rank">#{i} STEP-5 PRA</div><div class="w28-name">{_e(p["name"])}</div>'
            f'<div class="w28-meta">{_e(p["team"])} vs {_e(p["opponent"])} • {_e(status)} • {p["min"]:.1f} MIN</div>'
            f'<div class="w28-pra">{p["pra"]:.1f} <span>Projected PRA</span></div>'
            '<div class="w28-split">'
            f'<div><span>PTS</span><b>{p["p"]:.1f}</b></div><div><span>REB</span><b>{p["r"]:.1f}</b></div><div><span>AST</span><b>{p["a"]:.1f}</b></div><div><span>USG</span><b>{_fmt(p["usg"],1)}</b></div>'
            '</div></div>'
        )
    st.markdown(
        '<div class="w23-summary"><div class="w23-title">🏆 V2.8 Minutes + Role PRA — Top 5</div>'
        '<div class="w23-sub">First adjusted ranking: current availability, projected team minutes and role/USG changes are active. Opponent defensive matchup and sportsbook line grading remain off.</div>'
        f'<div class="w28-topgrid">{"".join(cards)}</div></div>', unsafe_allow_html=True,
    )


def _slate_tab(day, schedule, stats):
    st.markdown('<div class="w2-note blue"><b>V2.8 Step 5:</b> schedule, rosters, team context and availability are verified. Projected minutes and role/usage now intentionally move PTS, REB and AST separately. Matchup defense and betting lines are still excluded.</div>', unsafe_allow_html=True)
    pool = role.slate_player_pool(schedule, stats)
    teams = len(set(schedule.away_team_id.tolist() + schedule.home_team_id.tolist())) if schedule is not None and not schedule.empty else 0
    v27.v25.v24.v23.hub._metrics([
        ("Games", len(schedule), "cyan"), ("Teams", teams, "pink"), ("Current player pool", len(pool), "good"), ("Step 5", "MIN + ROLE", "good")
    ])
    if schedule is None or schedule.empty:
        st.markdown('<div class="w2-empty">No verified WNBA games were returned for this date.</div>', unsafe_allow_html=True)
        return
    _render_top5(_adjusted_top5(schedule, stats))
    st.markdown("### 🗓️ Selected WNBA Games")
    for _, row in schedule.iterrows():
        _game_card(row, stats, {})


def _hero(day):
    st.markdown(
        '<div class="w2-hero"><div class="w2-kicker">KYRE SPORTS AI • WNBA PRA INTELLIGENCE</div>'
        '<div class="w2-title">🏀 WNBA PRA Command Center — V2.8</div>'
        '<div class="w2-sub">Steps 1–4 verify the slate, current player pool, matchup history and availability. Step 5 now projects conditional minutes, reallocates minutes from unavailable players and uses official Advanced USG% when accessible to adjust Points, Rebounds and Assists separately. No opponent-defense or sportsbook-line adjustment yet.</div>'
        '<div class="w2-pills">'
        f'<div class="w2-pill">📅 Slate <b>{_e(day)}</b></div><div class="w2-pill">🧠 <b>PRA V2.8</b></div><div class="w2-pill">⏱️ <b>Projected minutes</b></div><div class="w2-pill">📈 <b>Role / USG</b></div><div class="w2-pill">🎯 <b>P / R / A separate</b></div>'
        '</div></div>', unsafe_allow_html=True,
    )
    v27.v25.v24._schedule_panel(day)
    v27._player_panel(day)
    v27._context_panel(day)
    v27._availability_panel(day)
    _role_panel(day)


# Wire V2.8 into the existing PRA shell.
for module in (v27.v25.v24.v23.hub, v27.v25.v24.v23):
    module.current_season = role.current_season
    module.data_health = _data_health
    module.empirical_profile = role.empirical_profile
    module.game_for_team = role.game_for_team
    module.logo_url = role.logo_url
    module.official_roster = role.official_roster
    module.player_form_table = role.player_form_table
    module.player_game_log = role.player_game_log
    module.schedule_for_date = role.schedule_for_date
    module.slate_player_pool = role.slate_player_pool
    module.team_player_pool = role.team_player_pool

v27.v25.v24.v23.hub.MODEL_VERSION = MODEL_VERSION
v27.v25.v24.v23.hub._hero = _hero
v27.v25.v24.v23.hub._game_card = _game_card
v27.v25.v24.v23.hub._slate_tab = _slate_tab
v27.v25.v24.v23._game_card = _game_card
v27.v25.v24.v23._slate_tab = _slate_tab


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(v27.v25.v24.v23.EXTRA_CSS + v27.v25.v24.SCHEDULE_CSS + v27.v25.PLAYER_CSS + v27.CONTEXT_CSS + ROLE_CSS, unsafe_allow_html=True)
    st.caption("🔒 WNBA league isolation active • PRA V2.8 • Step 5 projected minutes + role/usage")
    return v27.v25.v24.v23.hub.render_wnba_pra_hub(section_header, status_info, team_logo, h)
