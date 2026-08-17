"""MLB Daily Rankings V2.1 — Top 5 team-logo presentation layer.

Preserves V2.0 ranking/calibration behavior exactly. This module only upgrades
Top-5 card rendering so each player's MLB team logo appears beside the name.
"""
from __future__ import annotations

import streamlit as st

import mlb_matchup_rankings_v20 as v20

VERSION = "MLB Daily Rankings V2.1"

# Official MLB team IDs used by mlbstatic team-logo assets.
TEAM_IDS = {
    "Arizona Diamondbacks": 109,
    "Atlanta Braves": 144,
    "Baltimore Orioles": 110,
    "Boston Red Sox": 111,
    "Chicago Cubs": 112,
    "Chicago White Sox": 145,
    "Cincinnati Reds": 113,
    "Cleveland Guardians": 114,
    "Colorado Rockies": 115,
    "Detroit Tigers": 116,
    "Houston Astros": 117,
    "Kansas City Royals": 118,
    "Los Angeles Angels": 108,
    "Los Angeles Dodgers": 119,
    "Miami Marlins": 146,
    "Milwaukee Brewers": 158,
    "Minnesota Twins": 142,
    "New York Mets": 121,
    "New York Yankees": 147,
    "Athletics": 133,
    "Oakland Athletics": 133,
    "Philadelphia Phillies": 143,
    "Pittsburgh Pirates": 134,
    "San Diego Padres": 135,
    "San Francisco Giants": 137,
    "Seattle Mariners": 136,
    "St. Louis Cardinals": 138,
    "Tampa Bay Rays": 139,
    "Texas Rangers": 140,
    "Toronto Blue Jays": 141,
    "Washington Nationals": 120,
}


def _logo_url(team):
    tid = TEAM_IDS.get(str(team or "").strip())
    return f"https://www.mlbstatic.com/team-logos/{tid}.svg" if tid else ""


def _fmt_pct(v):
    return "—" if v is None else f"{float(v)*100:.1f}%"


def _render_top5_with_logos(rows, market, sims):
    top=list(rows or [])[:5]
    if not top:
        st.warning("No eligible hitters were successfully modeled for this market.")
        return

    scbase=v20.v18.scbase
    ui=scbase.ui
    odds=scbase.odds

    st.markdown("""
    <style>
      .rk-player-row{display:flex;align-items:center;gap:12px;margin-top:8px;margin-bottom:2px}
      .rk-team-logo{width:38px;height:38px;object-fit:contain;flex:0 0 38px}
      .rk-player-row .rk-name{margin:0!important}
      @media (max-width:700px){.rk-team-logo{width:34px;height:34px;flex-basis:34px}.rk-player-row{gap:10px}}
    </style>
    """, unsafe_allow_html=True)

    cards=[]
    for i,r in enumerate(top,1):
        status="✅ CONFIRMED" if r.get("confirmed") else "🕒 PROJECTED"
        fair=odds(r["p"])
        starter=f"{r.get('starter','TBD')} ({r.get('starter_hand','—')})"
        sb=[]
        if r.get("starter_era") is not None: sb.append(f"ERA {r['starter_era']:.2f}")
        if r.get("starter_k9") is not None: sb.append(f"K/9 {r['starter_k9']:.1f}")
        ctx=float(r.get("applied_context_adj") or 0)*100
        env=float(r.get("applied_environment_adj") or 0)*100
        bp=float(r.get("applied_bullpen_adj") or 0)*100
        sc=float(r.get("applied_statcast_adj") or 0)*100

        if r.get("weather_status")=="VERIFIED":
            wx=[]
            if r.get("temp_f") is not None: wx.append(f"{r['temp_f']:.0f}°F")
            if r.get("wind_mph") is not None: wx.append(f"Wind {r['wind_mph']:.0f} mph")
            if r.get("precip_pct") is not None: wx.append(f"Precip {r['precip_pct']:.0f}%")
            wx_text=" • ".join(wx) or "verified"
        else:
            wx_text="pending"

        if r.get("bullpen_status")=="VERIFIED":
            bp_text=f"3G ERA {r.get('bp_era_3g',0):.2f} • Last {r.get('bp_last_ip',0):.1f} IP/{int(r.get('bp_last_relievers',0))} RP • Exposure {r.get('bullpen_exposure',0)*100:.0f}%"
        else:
            bp_text="pending"

        if r.get("statcast_status")=="VERIFIED":
            sc_bits=[]
            if r.get("statcast_ev") is not None: sc_bits.append(f"EV {r['statcast_ev']:.1f}")
            if r.get("statcast_hard_hit") is not None: sc_bits.append(f"HH {_fmt_pct(r['statcast_hard_hit'])}")
            if r.get("statcast_barrel") is not None: sc_bits.append(f"Barrel {_fmt_pct(r['statcast_barrel'])}")
            if r.get("statcast_contact_xba") is not None: sc_bits.append(f"c-xBA {r['statcast_contact_xba']:.3f}")
            sc_text=" • ".join(sc_bits) or "verified"
        else:
            sc_text="pending"

        mix=" / ".join(f"{pt} {share*100:.0f}%" for pt,share,_ in (r.get("pitch_mix") or [])[:3]) or "pending"
        logo=_logo_url(r.get("team"))
        logo_html=f'<img class="rk-team-logo" src="{ui._esc(logo)}" alt="{ui._esc(r.get("team") or "team")} logo">' if logo else ""
        medal='🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '•'

        cards.append(f'''<div class="rk-card {'first' if i==1 else ''}">
          <div class="rk-rank">{medal} RANK {i} • {status}</div>
          <div class="rk-player-row">{logo_html}<div class="rk-name">{ui._esc(r['player'])}</div></div>
          <div class="rk-match">{ui._esc(r['team'])} vs {ui._esc(r['opponent'])} • Bat #{ui._esc(r.get('bat_spot'))}</div>
          <div class="rk-p">{r['p']*100:.1f}%</div>
          <div class="rk-label">{ui._esc(market)} probability • Fair {ui._esc(fair)}</div>
          <div class="rk-details">{ui._esc(r['support'])}</div>
          <div class="rk-details">⚾ vs {ui._esc(starter)} • {' • '.join(sb) if sb else 'starter stats pending'} • Matchup {ctx:+.1f} pts</div>
          <div class="rk-details">🌦️ {ui._esc(r.get('venue_name') or r.get('venue') or 'Venue')} • {ui._esc(wx_text)} • Environment {env:+.1f} pts</div>
          <div class="rk-details">🧯 Opponent bullpen • {ui._esc(bp_text)} • Bullpen {bp:+.1f} pts</div>
          <div class="rk-details">📡 Statcast • {ui._esc(sc_text)} • Statcast/platoon/pitch {sc:+.1f} pts</div>
          <div class="rk-details">🎯 Starter arsenal • {ui._esc(mix)} • {ui._esc(r.get('platoon_note') or 'platoon pending')}</div>
          <div class="rk-badges"><span class="rk-pill good">{ui._esc(r['confidence'])}</span><span class="rk-pill">Reliability {r['reliability']*100:.0f}%</span><span class="rk-pill">{r['sample']:.0f} {ui._esc(r['sample_unit'])}</span></div>
        </div>''')

    st.markdown(f'<div class="rk-grid">{"".join(cards)}</div>',unsafe_allow_html=True)
    st.caption(f"{VERSION} • {int(sims):,} simulations/hitter • team-logo presentation layer • ranking/calibration math unchanged")


# V1.8 renderer calls this shared renderer at runtime. Swap presentation only.
v20.v18.scbase._render_top5=_render_top5_with_logos
render_daily_rankings=v20.render_daily_rankings
fast_scan=v20.fast_scan
deep_calibrate=v20.deep_calibrate
