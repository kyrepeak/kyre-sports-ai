"""WNBA PRA V2.5 — Step 2 verified current player pool.

Keeps V2.4 schedule verification unchanged. Step 2 adds current roster gating and
season/L10/L5 P/R/A player production for only the teams on the verified slate.
No injury, starter, usage, pace or opponent-defense modeling is added here.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v24 as v24
import wnba_players_v25 as players

MODEL_VERSION = "PRA V2.5"

PLAYER_CSS = r"""
<style>
.w25-panel{border:1px solid #5a3d78;background:radial-gradient(circle at 8% 0%,rgba(244,114,182,.08),transparent 35%),linear-gradient(145deg,#121525,#0b111d);border-radius:18px;padding:14px 15px;margin:12px 0 14px}
.w25-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.w25-head b{color:#fff;font-size:1rem}.w25-head span{font-size:.53rem;color:#f08bc0;text-transform:uppercase;letter-spacing:.1em;font-weight:950}
.w25-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.w25-metric{background:#0b1523;border:1px solid #303b58;border-radius:12px;padding:9px 10px}.w25-metric span{display:block;color:#7586a0;font-size:.46rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.w25-metric b{display:block;color:#fff;font-size:.86rem;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.w25-metric.good b{color:#75efba}.w25-metric.warn b{color:#ffe083}.w25-metric.bad b{color:#ff929e}.w25-source{margin-top:9px;border-radius:11px;padding:9px 10px;background:#0b1d2b;border:1px solid #2d526c;color:#9fc7dc;font-size:.62rem;line-height:1.5}.w25-source b{color:#fff}.w25-banner{margin-top:8px;border-radius:11px;padding:8px 10px;font-size:.64rem;line-height:1.5}.w25-banner.good{background:#0a2b21;border:1px solid #246a50;color:#85efbf}.w25-banner.warn{background:#2a230d;border:1px solid #715f22;color:#f3df8a}.w25-banner.bad{background:#2b1117;border:1px solid #773440;color:#ffabb4}
@media(max-width:900px){.w25-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:620px){.w25-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.w25-head{align-items:flex-start;flex-direction:column}}
</style>
"""


def _e(v):
    return v24._e(v)


def _player_panel(day):
    diag = players.player_diagnostics(day)
    state = str(diag.get("state") or "PROVIDER_FAILURE")
    cls = "good" if state == "VERIFIED" else "warn" if state in ("NO_GAMES", "PARTIAL") else "bad"
    source = str(diag.get("source") or "none")
    roster_source = str(diag.get("roster_source") or "unavailable")
    if state == "VERIFIED":
        banner = (
            f'✅ Step 2 player pool connected: <b>{diag.get("stat_rows",0)} current slate players</b> '
            f'across <b>{diag.get("teams",0)} teams</b>. Current roster gate is active before players enter the PRA pool.'
        )
    elif state == "NO_GAMES":
        banner = '🟡 No verified WNBA games exist on this selected date, so there is no slate player pool to construct.'
    else:
        banner = '🔴 The selected games are verified, but current roster/player production could not be completed. The app will not manufacture player rows.'
    st.markdown(
        '<div class="w25-panel">'
        '<div class="w25-head"><b>👥 V2.5 WNBA Player Pool Verification</b><span>Step 2 • rosters + P/R/A only</span></div>'
        '<div class="w25-grid">'
        f'<div class="w25-metric {cls}"><span>Verification</span><b>{_e(state.replace("_"," "))}</b></div>'
        f'<div class="w25-metric"><span>Slate teams</span><b>{diag.get("teams",0)}</b></div>'
        f'<div class="w25-metric good"><span>Rosters connected</span><b>{diag.get("rosters_connected",0)}/{diag.get("teams",0)}</b></div>'
        f'<div class="w25-metric good"><span>Roster players</span><b>{diag.get("roster_players",0)}</b></div>'
        f'<div class="w25-metric good"><span>Player stat rows</span><b>{diag.get("stat_rows",0)}</b></div>'
        f'<div class="w25-metric"><span>Completed games used</span><b>{diag.get("completed_games_used",0)}</b></div>'
        '</div>'
        f'<div class="w25-source"><b>Production source:</b> {_e(source)}<br><b>Roster source:</b> {_e(roster_source)}<br>Season MIN / PTS / REB / AST / PRA plus Last 10 and Last 5 are built before any later matchup adjustments.</div>'
        f'<div class="w25-banner {cls}">{banner}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("🔄 RECHECK WNBA PLAYER POOL", use_container_width=True, key=f"wnba_v25_recheck_{diag.get('selected_date')}"):
        players.clear_player_cache()
        st.rerun()


# Wire Step 2 data into the existing V2.3/V2.4 presentation tree.
for module in (v24.v23.hub, v24.v23):
    module.current_season = players.current_season
    module.data_health = players.data_health
    module.empirical_profile = players.empirical_profile
    module.game_for_team = players.game_for_team
    module.logo_url = players.logo_url
    module.official_roster = players.official_roster
    module.player_form_table = players.player_form_table
    module.player_game_log = players.player_game_log
    module.schedule_for_date = players.schedule_for_date
    module.slate_player_pool = players.slate_player_pool
    module.team_player_pool = players.team_player_pool

v24.v23.hub.MODEL_VERSION = MODEL_VERSION


def _hero_v25(day):
    st.markdown(
        '<div class="w2-hero">'
        '<div class="w2-kicker">KYRE SPORTS AI • WNBA PRA INTELLIGENCE</div>'
        '<div class="w2-title">🏀 WNBA PRA Command Center — V2.5</div>'
        '<div class="w2-sub">Step 1 verifies the WNBA slate. Step 2 now verifies the current player pool: current rosters, team mapping, season minutes/points/rebounds/assists/PRA, Last 10 and Last 5. Non-current team rows are gated out before they reach the slate. Injuries, confirmed starters, usage, pace and matchup adjustments remain intentionally untouched.</div>'
        '<div class="w2-pills">'
        f'<div class="w2-pill">📅 Slate <b>{_e(day)}</b></div>'
        '<div class="w2-pill">🧠 <b>PRA V2.5</b></div>'
        '<div class="w2-pill">✅ <b>Schedule verified</b></div>'
        '<div class="w2-pill">👥 <b>Current player pool</b></div>'
        '<div class="w2-pill">🎯 <b>P / R / A separate</b></div>'
        '</div></div>', unsafe_allow_html=True,
    )
    v24._schedule_panel(day)
    _player_panel(day)


v24.v23.hub._hero = _hero_v25
v24.v23.hub._game_card = v24.v23._game_card
v24.v23.hub._slate_tab = v24.v23._slate_tab


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(v24.v23.EXTRA_CSS + v24.SCHEDULE_CSS + PLAYER_CSS, unsafe_allow_html=True)
    st.caption("🔒 WNBA league isolation active • PRA V2.5 • Step 1 verified schedule + Step 2 verified player pool")
    return v24.v23.hub.render_wnba_pra_hub(section_header, status_info, team_logo, h)
