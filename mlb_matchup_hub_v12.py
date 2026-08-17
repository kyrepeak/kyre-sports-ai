"""MLB Matchup Explorer V1.2 — all hitter tabs modeled where approved.

Embedded read-only engines:
- Hits: 1+ Hit V13.3
- Home Runs: calibrated HR V1.1
- Total Bases: Batter Components V1.0
- RBIs: Batter Components V1.0
- Runs: Batter Components V1.0
- H+R+RBI: joint-event V1.0.1

Standalone production pages remain untouched.
"""
from __future__ import annotations

import math
import pandas as pd
import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_hit_hub_v133 as hit133
import hit_hub_v131 as hitcore
import mlb_hr_hub_v11 as hrcore
import mlb_hrrbi_hub_v10 as hrrcore
import mlb_batter_components_v10 as components
from engine import odds

VERSION = "MLB Matchup Hub V1.2"


def _finite(v, default=0.0):
    try:
        x=float(v); return x if math.isfinite(x) else default
    except Exception:
        return default


def _status_started(status):
    s=str(status or "").lower()
    return any(x in s for x in ("progress","live","final","completed","game over"))


def _selected_candidate(games_df,row,player_id):
    try: pool,_=hit133._candidate_pool(games_df,include_live=True)
    except Exception: pool=[]
    pk=int(row.get("game_pk")); pid=int(player_id)
    for c in pool:
        try:
            if int(c.get("game_pk"))==pk and int(c.get("player_id"))==pid: return c
        except Exception: pass
    return None


def _projection_css():
    st.markdown("""
    <style>
    .mx-proj{border:1px solid #31516e;border-radius:18px;background:linear-gradient(145deg,#0b1b2d,#08131f);padding:15px 16px;margin:12px 0 8px}
    .mx-top{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}.mx-engine{font-size:.62rem;color:#5bdcff;font-weight:950;letter-spacing:.1em;text-transform:uppercase}.mx-badge{border:1px solid #37536d;border-radius:999px;padding:4px 8px;color:#bdd0df;font-size:.56rem;font-weight:900}.mx-big{font-size:2.55rem;font-weight:1000;color:#fff;line-height:1;margin-top:10px}.mx-label{font-size:.63rem;color:#8ca2b8;text-transform:uppercase;font-weight:900;margin-top:3px}.mx-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:12px}.mx-cell{border:1px solid #253e57;background:#081522;border-radius:11px;padding:8px}.mx-cell span{display:block;color:#718aa3;font-size:.48rem;text-transform:uppercase;font-weight:900}.mx-cell b{display:block;color:#f5f8fc;font-size:.82rem;margin-top:3px}.mx-conf{display:inline-flex;margin-top:9px;border:1px solid #1d654b;background:#0a3326;color:#7beeb8;border-radius:999px;padding:4px 8px;font-size:.53rem;font-weight:950}.mx-warn{border-left:3px solid #f0b429;background:#261f0a;color:#efd889;padding:8px 10px;margin:8px 0;font-size:.65rem;border-radius:0 9px 9px 0}
    @media(max-width:700px){.mx-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.mx-big{font-size:2.2rem}}
    </style>
    """,unsafe_allow_html=True)


def _pregame_warn(started,label):
    if started:
        st.markdown(f'<div class="mx-warn">⚠️ Pregame-model view: this game has already started. This is not a live {label} projection.</div>',unsafe_allow_html=True)


def _hit_projection(c):
    try: return hit133._downgrade_projected(hitcore.deep_scan(dict(c),250_000))
    except Exception as exc: return {"error":f"{type(exc).__name__}: {exc}"}


def _hr_projection(c):
    try: return hrcore._model_candidate(dict(c),deep=True,sims=250_000) or {"error":"No calibrated HR profile returned."}
    except Exception as exc: return {"error":f"{type(exc).__name__}: {exc}"}


def _hrr_projection(c):
    try:
        r=hrrcore._profile_candidate(dict(c))
        if not r: return {"error":"No H+R+RBI profile returned."}
        r=dict(r); r["sim"]=hrrcore._simulate(r,250_000); return r
    except Exception as exc: return {"error":f"{type(exc).__name__}: {exc}"}


def _render_hit_card(r,started=False):
    if r.get("error"): st.warning(f"1+ Hit engine unavailable: {r['error']}"); return
    s=r.get("sim") or {}; p=_finite(s.get("p_one_plus")); _pregame_warn(started,"hit-prop")
    st.markdown(f'''<div class="mx-proj"><div class="mx-top"><div class="mx-engine">🎯 1+ Hit V13.3 deep model</div><div class="mx-badge">250K simulations</div></div><div class="mx-big">{p*100:.1f}%</div><div class="mx-label">1+ hit probability • Fair {odds(p)}</div><div class="mx-grid"><div class="mx-cell"><span>2+ Hits</span><b>{_finite(s.get('p_two_plus'))*100:.1f}%</b></div><div class="mx-cell"><span>Expected Hits</span><b>{_finite(s.get('expected_hits')):.2f}</b></div><div class="mx-cell"><span>Bat Spot</span><b>#{r.get('position','—')}</b></div><div class="mx-cell"><span>Data</span><b>{int(r.get('data_score',0) or 0)}/8</b></div></div><div class="mx-conf">{r.get('confidence','—')}</div></div>''',unsafe_allow_html=True)


def _render_hr_card(r,started=False):
    if r.get("error"): st.warning(f"Home Run engine unavailable: {r['error']}"); return
    p=_finite(r.get("p_hr")); sc=r.get("statcast") or {}; barrel=_finite(sc.get("barrel_rate"),-1); hr9=r.get("pitcher_hr9"); _pregame_warn(started,"home-run")
    barrel_txt='—' if barrel<0 else f'{barrel*100:.1f}%'; hr9_txt='—' if hr9 is None else f'{float(hr9):.2f}'
    st.markdown(f'''<div class="mx-proj"><div class="mx-top"><div class="mx-engine">💣 Home Run V1.1 calibrated model</div><div class="mx-badge">250K simulations</div></div><div class="mx-big">{p*100:.1f}%</div><div class="mx-label">1+ HR probability • Fair {odds(p)}</div><div class="mx-grid"><div class="mx-cell"><span>2+ HR</span><b>{_finite(r.get('p_2hr'))*100:.1f}%</b></div><div class="mx-cell"><span>Season HR</span><b>{r.get('season_hr','—')}</b></div><div class="mx-cell"><span>Barrel%</span><b>{barrel_txt}</b></div><div class="mx-cell"><span>Starter HR/9</span><b>{hr9_txt}</b></div></div><div class="mx-conf">{r.get('confidence','—')}</div></div>''',unsafe_allow_html=True)


def _render_component_card(r,started=False):
    if r.get("error"): st.warning(f"Component engine unavailable: {r['error']}"); return
    metric=r.get("metric","Stat"); p1=_finite(r.get("p1")); _pregame_warn(started,metric.lower())
    icon="🧱" if metric=="Total Bases" else "🏃" if metric=="Runs" else "🎯"
    extra=''
    if metric=="Total Bases": extra=f'<div class="mx-cell"><span>4+</span><b>{_finite(r.get("p4"))*100:.1f}%</b></div>'
    recent=r.get("recent10"); recent_txt='—' if recent is None else f'{float(recent):.2f}'
    st.markdown(f'''<div class="mx-proj"><div class="mx-top"><div class="mx-engine">{icon} {metric} V1.0 independent model</div><div class="mx-badge">250K simulations</div></div><div class="mx-big">{p1*100:.1f}%</div><div class="mx-label">1+ {metric} probability • Fair {odds(p1)}</div><div class="mx-grid"><div class="mx-cell"><span>Expected</span><b>{_finite(r.get('expected')):.2f}</b></div><div class="mx-cell"><span>2+</span><b>{_finite(r.get('p2'))*100:.1f}%</b></div><div class="mx-cell"><span>3+</span><b>{_finite(r.get('p3'))*100:.1f}%</b></div>{extra}<div class="mx-cell"><span>Median / Mode</span><b>{r.get('median','—')} / {r.get('mode','—')}</b></div><div class="mx-cell"><span>90% Range</span><b>{r.get('range90','—')}</b></div><div class="mx-cell"><span>Proj PA</span><b>{_finite(r.get('projected_pa')):.1f}</b></div><div class="mx-cell"><span>Recent 10</span><b>{recent_txt}</b></div></div><div class="mx-conf">{r.get('confidence','—')}</div></div>''',unsafe_allow_html=True)


def _render_hrr_card(r,started=False):
    if r.get("error"): st.warning(f"H+R+RBI engine unavailable: {r['error']}"); return
    s=r.get("sim") or {}; p2=_finite(s.get("p2")); _pregame_warn(started,"H+R+RBI")
    st.markdown(f'''<div class="mx-proj"><div class="mx-top"><div class="mx-engine">🔥 H+R+RBI V1.0.1 joint-event model</div><div class="mx-badge">250K simulations</div></div><div class="mx-big">{p2*100:.1f}%</div><div class="mx-label">2+ H+R+RBI probability • Fair {odds(p2)}</div><div class="mx-grid"><div class="mx-cell"><span>xH</span><b>{_finite(s.get('expected_h')):.2f}</b></div><div class="mx-cell"><span>xR</span><b>{_finite(s.get('expected_r')):.2f}</b></div><div class="mx-cell"><span>xRBI</span><b>{_finite(s.get('expected_rbi')):.2f}</b></div><div class="mx-cell"><span>xCombined</span><b>{_finite(s.get('expected_total')):.2f}</b></div><div class="mx-cell"><span>3+</span><b>{_finite(s.get('p3'))*100:.1f}%</b></div><div class="mx-cell"><span>4+</span><b>{_finite(s.get('p4'))*100:.1f}%</b></div><div class="mx-cell"><span>Median</span><b>{s.get('median','—')}</b></div><div class="mx-cell"><span>Mode</span><b>{s.get('mode','—')}</b></div></div><div class="mx-conf">{r.get('confidence','—')}</div></div>''',unsafe_allow_html=True)


def render_matchup_hub(games_df,section_header=None,status_info=None,team_logo=None,h=None):
    ui._css(); _projection_css()
    if games_df is None or games_df.empty: st.info("No verified MLB games are available for the selected date."); return
    day=ui._date_str(games_df.iloc[0]); season=pd.to_datetime(day).year
    st.markdown('<div class="mh-hero"><div class="mh-eyebrow">KYRE SPORTS AI • DAILY PLAYER MATCHUPS • V1.2</div><div class="mh-title">⚾ MLB Matchup Explorer</div><div class="mh-sub">Recent performance plus embedded Hits, HR, Total Bases, RBI, Runs and H+R+RBI projection engines.</div></div>',unsafe_allow_html=True)
    labels=[ui._game_label(r) for _,r in games_df.iterrows()]
    idx=st.selectbox("TODAY'S MATCHUPS",range(len(labels)),format_func=lambda i:labels[i],key="mh12_game"); row=games_df.iloc[int(idx)]
    st.markdown(f'<div class="mh-game"><div class="mh-teamrow"><div class="mh-team"><img src="{ui._logo(row.get("away_team_id"))}">{ui._esc(row.get("away_team"))}</div><div class="mh-at">@</div><div class="mh-team"><img src="{ui._logo(row.get("home_team_id"))}">{ui._esc(row.get("home_team"))}</div></div><div class="mh-meta">{ui._esc(row.get("first_pitch_et"))} ET • {ui._esc(row.get("venue_name"))} • {ui._esc(row.get("status"))}<br>{ui._esc(row.get("away_pitcher"))} vs {ui._esc(row.get("home_pitcher"))}</div></div>',unsafe_allow_html=True)
    players=ui._hitters_for_game(row)
    if not players: st.warning("No eligible hitters were returned for this matchup yet."); return
    pidx=st.selectbox("PLAYER",range(len(players)),format_func=lambda i:f"{players[i]['name']} • {players[i]['team']} • {players[i].get('source','')}",key="mh12_player"); p=players[int(pidx)]
    stat=ui._season_hitting(p["id"],season); logs=ui._game_logs(p["id"],season)
    games=int(ui._num(stat.get("gamesPlayed"))); avg=stat.get("avg") or ".000"; hr=int(ui._num(stat.get("homeRuns"))); rbi=int(ui._num(stat.get("rbi"))); ops=stat.get("ops") or ".000"
    st.markdown(f'<div class="mh-player"><div class="mh-small">{ui._esc(p.get("team"))} • {ui._esc(p.get("position"))} • {ui._esc(p.get("source"))}</div><div class="mh-name">{ui._esc(p.get("name"))}</div><div class="mh-season"><div class="mh-stat"><span>Games</span><b>{games}</b></div><div class="mh-stat"><span>AVG</span><b>{ui._esc(avg)}</b></div><div class="mh-stat"><span>HR</span><b>{hr}</b></div><div class="mh-stat"><span>RBI</span><b>{rbi}</b></div><div class="mh-stat"><span>OPS</span><b>{ui._esc(ops)}</b></div></div></div>',unsafe_allow_html=True)
    candidate=_selected_candidate(games_df,row,p["id"]); started=_status_started(row.get("status")); tabs=st.tabs(["Hits","Home Runs","Total Bases","RBIs","Runs","H+R+RBI","Game Log"])
    with tabs[0]:
        st.caption(f"{season} season AVG: {avg}"); ui._recent_chart(logs,"H")
        if candidate:
            with st.spinner("Running frozen 1+ Hit model..."): _render_hit_card(_hit_projection(candidate),started)
        else: st.info("Deep hit projection waits for this hitter to enter today's confirmed/projected batting order.")
    with tabs[1]:
        st.caption(f"{season} season Home Runs: {stat.get('homeRuns','—')}"); ui._recent_chart(logs,"HR")
        if candidate:
            with st.spinner("Running calibrated HR model..."): _render_hr_card(_hr_projection(candidate),started)
        else: st.info("Deep HR projection waits for this hitter to enter today's confirmed/projected batting order.")
    with tabs[2]:
        st.caption(f"{season} season Total Bases: {stat.get('totalBases','—')}"); ui._recent_chart(logs,"TB")
        if candidate:
            with st.spinner("Running Total Bases model..."): _render_component_card(components.project_total_bases(candidate,250_000),started)
        else: st.info("Total Bases projection waits for this hitter to enter today's confirmed/projected batting order.")
    with tabs[3]:
        st.caption(f"{season} season RBIs: {stat.get('rbi','—')}"); ui._recent_chart(logs,"RBI")
        if candidate:
            with st.spinner("Running RBI model..."): _render_component_card(components.project_rbis(candidate,250_000),started)
        else: st.info("RBI projection waits for this hitter to enter today's confirmed/projected batting order.")
    with tabs[4]:
        st.caption(f"{season} season Runs: {stat.get('runs','—')}"); ui._recent_chart(logs,"R")
        if candidate:
            with st.spinner("Running Runs model..."): _render_component_card(components.project_runs(candidate,250_000),started)
        else: st.info("Runs projection waits for this hitter to enter today's confirmed/projected batting order.")
    with tabs[5]:
        if logs: st.caption(f"Recent 10 H+R+RBI average: {sum(r['H+R+RBI'] for r in logs[:10])/len(logs[:10]):.2f}")
        ui._recent_chart(logs,"H+R+RBI")
        if candidate:
            with st.spinner("Running joint H+R+RBI model..."): _render_hrr_card(_hrr_projection(candidate),started)
        else: st.info("Deep H+R+RBI projection waits for this hitter to enter today's confirmed/projected batting order.")
    with tabs[6]:
        if not logs: st.info("No game log available.")
        else: st.dataframe(pd.DataFrame(logs[:20])[["date","opp","AB","H","HR","TB","RBI","R","H+R+RBI"]],hide_index=True,use_container_width=True)
    st.caption(f"{VERSION} • Official MLB data • embedded production/component engines • selected slate {day}")
