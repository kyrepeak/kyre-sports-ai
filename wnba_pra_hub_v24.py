"""WNBA PRA V2.4 — Step 1 verified schedule + diagnostics.

Only the schedule layer changes here. Player production, roster and PRA model
layers remain exactly where V2.3.2 left them.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_pra_hub_v23 as v23
import wnba_data_v232 as player_transport
from wnba_schedule_v24 import (
    clear_schedule_cache,
    current_season,
    data_health,
    empirical_profile,
    game_for_team,
    logo_url,
    official_roster,
    player_form_table,
    player_game_log,
    schedule_diagnostics,
    schedule_for_date,
    slate_player_pool,
    team_player_pool,
)

MODEL_VERSION = "PRA V2.4"

SCHEDULE_CSS = r"""
<style>
.w24-panel{border:1px solid #315a79;background:linear-gradient(145deg,#0d1a2a,#09121e);border-radius:18px;padding:14px 15px;margin:12px 0 14px}
.w24-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.w24-head b{color:#fff;font-size:1rem}.w24-head span{font-size:.53rem;color:#71cfff;text-transform:uppercase;letter-spacing:.1em;font-weight:950}
.w24-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.w24-metric{background:#0b1625;border:1px solid #293f59;border-radius:12px;padding:9px 10px}.w24-metric span{display:block;color:#71849f;font-size:.48rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.w24-metric b{display:block;color:#fff;font-size:.9rem;margin-top:4px}.w24-metric.good b{color:#78efbb}.w24-metric.warn b{color:#ffe181}.w24-metric.bad b{color:#ff929e}
.w24-providers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}.w24-provider{border:1px solid #2c405c;background:#091422;border-radius:12px;padding:9px}.w24-provider b{display:block;color:#f5f7fb;font-size:.64rem}.w24-provider span{display:block;color:#7f93ae;font-size:.52rem;line-height:1.5;margin-top:3px}.w24-provider.pass{border-color:#22674d;background:#09281f}.w24-provider.pass b{color:#7af0ba}.w24-provider.fail{border-color:#6a3038;background:#281116}.w24-provider.fail b{color:#ff9aa5}.w24-provider.empty{border-color:#665827;background:#29230d}.w24-provider.empty b{color:#ffe187}
.w24-banner{margin-top:9px;border-radius:11px;padding:8px 10px;font-size:.64rem;line-height:1.5}.w24-banner.good{background:#0a2b21;border:1px solid #246a50;color:#85efbf}.w24-banner.warn{background:#2a230d;border:1px solid #715f22;color:#f3df8a}.w24-banner.bad{background:#2b1117;border:1px solid #773440;color:#ffabb4}
@media(max-width:760px){.w24-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.w24-providers{grid-template-columns:1fr}.w24-head{align-items:flex-start;flex-direction:column}}
</style>
"""


def _e(v):
    return v23._e(v)


def _state_class(state):
    return "good" if state == "VERIFIED" else "warn" if state == "VERIFIED_OFF_DAY" else "bad"


def _provider_card(meta):
    request_ok = bool(meta.get("request_ok"))
    selected = int(meta.get("selected_games") or 0)
    valid = int(meta.get("valid_games") or 0)
    if not request_ok:
        cls, label = "fail", "FAILED"
    elif selected:
        cls, label = "pass", f"PASS • {selected} selected"
    elif valid:
        cls, label = "empty", "PASS • no selected games"
    else:
        cls, label = "empty", "EMPTY"
    http = meta.get("http") if meta.get("http") is not None else "—"
    json_state = "yes" if meta.get("json") else "no"
    elapsed = f"{meta.get('elapsed_ms')} ms" if meta.get("elapsed_ms") is not None else "—"
    return (
        f'<div class="w24-provider {cls}"><b>{_e(meta.get("provider"))} • {label}</b>'
        f'<span>HTTP {http} • JSON {json_state} • valid {valid} • rejected {int(meta.get("rejected_games") or 0)} • {elapsed}</span></div>'
    )


def _schedule_panel(day):
    diag = schedule_diagnostics(day)
    state = str(diag.get("state") or "PROVIDER_FAILURE")
    cls = _state_class(state)
    source = diag.get("chosen_source") or "none"
    confirming = diag.get("confirming_sources") or []
    provider_html = "".join(_provider_card(x) for x in diag.get("attempts", []))
    if state == "VERIFIED":
        banner = f'✅ Selected slate verified: <b>{diag.get("games",0)} WNBA game(s)</b>. Using <b>{_e(source)}</b>. Confirmed by {max(1,len(confirming))} schedule path(s).'
    elif state == "VERIFIED_OFF_DAY":
        banner = '🟡 Schedule providers returned valid whole-season WNBA data and the selected date is absent. This is being treated as a verified WNBA off-day — not a feed error.'
    else:
        banner = '🔴 Schedule could not be verified. The app will show 0 games, but it is explicitly marked PROVIDER FAILURE rather than pretending the selected date is an off-day.'
    st.markdown(
        '<div class="w24-panel">'
        '<div class="w24-head"><b>📅 V2.4 WNBA Slate Verification</b><span>Step 1 • schedule only</span></div>'
        '<div class="w24-grid">'
        f'<div class="w24-metric"><span>Selected date</span><b>{_e(diag.get("selected_date"))}</b></div>'
        f'<div class="w24-metric {cls}"><span>Verification</span><b>{_e(state.replace("_"," "))}</b></div>'
        f'<div class="w24-metric good"><span>Games found</span><b>{diag.get("games",0)}</b></div>'
        f'<div class="w24-metric"><span>WNBA teams validated</span><b>{diag.get("teams",0)}</b></div>'
        '</div>'
        f'<div class="w24-providers">{provider_html}</div>'
        f'<div class="w24-banner {cls}">{banner}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("🔄 RECHECK WNBA SCHEDULE FEEDS", use_container_width=True, key=f"wnba_v24_recheck_{diag.get('selected_date')}"):
        clear_schedule_cache()
        st.rerun()
    errors = [x for x in diag.get("attempts", []) if x.get("error")]
    if errors:
        with st.expander("🧪 Schedule feed diagnostics"):
            for item in errors:
                st.caption(f"{item.get('provider')}: {item.get('error')}")
    schedule = schedule_for_date(day)
    if schedule is not None and not schedule.empty:
        show_cols = [c for c in ["away_team", "home_team", "first_tip_et", "venue", "status", "source"] if c in schedule.columns]
        preview = schedule[show_cols].copy().rename(columns={
            "away_team":"Away", "home_team":"Home", "first_tip_et":"Tip (ET)",
            "venue":"Venue", "status":"Status", "source":"Verified Source",
        })
        with st.expander(f"✅ Verified WNBA games • {len(preview)}", expanded=True):
            st.dataframe(preview, use_container_width=True, hide_index=True)


# Wire only V2.4 schedule verification into the existing V2.3 command center.
v23.hub.current_season = current_season
v23.hub.data_health = data_health
v23.hub.empirical_profile = empirical_profile
v23.hub.game_for_team = game_for_team
v23.hub.logo_url = logo_url
v23.hub.official_roster = official_roster
v23.hub.player_form_table = player_form_table
v23.hub.player_game_log = player_game_log
v23.hub.schedule_for_date = schedule_for_date
v23.hub.slate_player_pool = slate_player_pool
v23.hub.team_player_pool = team_player_pool
v23.hub.MODEL_VERSION = MODEL_VERSION

v23.current_season = current_season
v23.data_health = data_health
v23.empirical_profile = empirical_profile
v23.game_for_team = game_for_team
v23.logo_url = logo_url
v23.official_roster = official_roster
v23.player_form_table = player_form_table
v23.player_game_log = player_game_log
v23.schedule_for_date = schedule_for_date
v23.slate_player_pool = slate_player_pool
v23.team_player_pool = team_player_pool


def _hero_v24(day):
    st.markdown(
        '<div class="w2-hero">'
        '<div class="w2-kicker">KYRE SPORTS AI • WNBA PRA INTELLIGENCE</div>'
        '<div class="w2-title">🏀 WNBA PRA Command Center — V2.4</div>'
        '<div class="w2-sub">Step 1 is dedicated to slate accuracy. V2.4 verifies the selected WNBA date across multiple schedule paths, validates WNBA team IDs and separates a real off-day from a provider failure. Player/model upgrades are intentionally unchanged in this step.</div>'
        '<div class="w2-pills">'
        f'<div class="w2-pill">📅 Slate <b>{_e(day)}</b></div>'
        '<div class="w2-pill">🧠 <b>PRA V2.4</b></div>'
        '<div class="w2-pill">✅ <b>Schedule verification</b></div>'
        '<div class="w2-pill">🔒 <b>WNBA-only IDs</b></div>'
        '</div></div>', unsafe_allow_html=True,
    )
    _schedule_panel(day)


v23.hub._hero = _hero_v24
v23.hub._game_card = v23._game_card
v23.hub._slate_tab = v23._slate_tab


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(v23.EXTRA_CSS + SCHEDULE_CSS, unsafe_allow_html=True)
    st.caption("🔒 WNBA league isolation active • PRA V2.4 • Step 1 verified slate engine")
    return v23.hub.render_wnba_pra_hub(section_header, status_info, team_logo, h)
