"""MLB Matchup Explorer Daily Rankings V1.0.

On-demand, one-market-at-a-time slate rankings that reuse the frozen production
engines already embedded in Matchup Explorer. The scanner never uses sportsbook
price as a model input. It applies the V1.3 sample-reliability shrinkage layer
before ranking and keeps projected-lineup players visibly labeled.
"""
from __future__ import annotations

import math
import pandas as pd
import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v13 as cal
import mlb_hit_hub_v133 as hit133
import hit_hub_v131 as hitcore
import mlb_hr_hub_v11 as hrcore
import mlb_hrrbi_hub_v10 as hrrcore
import mlb_batter_components_v10 as components
from engine import odds

VERSION = "MLB Daily Rankings V1.0"
MARKETS = ["1+ Hit", "Home Run", "Total Bases", "RBIs", "Runs", "H+R+RBI"]
PRIORS = {
    "1+ Hit": .655,
    "Home Run": .095,
    "Total Bases": .690,
    "RBIs": .340,
    "Runs": .355,
    "H+R+RBI": .555,
}


def _finite(v, default=0.0):
    try:
        x=float(v); return x if math.isfinite(x) else default
    except Exception:
        return default


def _season_sample(player_id, year):
    try:
        s=ui._season_hitting(int(player_id), int(year))
        pa=_finite(s.get("plateAppearances"),0)
        if pa>0: return pa,"PA"
        g=_finite(s.get("gamesPlayed"),0)
        if g>0: return g,"G"
    except Exception:
        pass
    return 0.0,"G"


def _confidence_label(rel, base_conf=None, confirmed=False):
    raw=str(base_conf or "").upper()
    if rel >= .60 and confirmed and raw in ("HIGH","MEDIUM-HIGH","MEDIUM HIGH"): return "HIGH"
    if rel >= .42: return "MEDIUM-HIGH"
    if rel >= .25: return "MEDIUM"
    return "LOW"


def _candidate_meta(c):
    return {
        "player":str(c.get("player_name") or "Unknown"),
        "player_id":c.get("player_id"),
        "team":str(c.get("team") or c.get("team_name") or ""),
        "opponent":str(c.get("opponent") or c.get("opponent_name") or ""),
        "game_pk":c.get("game_pk"),
        "bat_spot":c.get("position"),
        "confirmed":bool(c.get("lineup_confirmed")),
        "starter":str(c.get("opponent_pitcher") or c.get("pitcher_name") or "TBD"),
        "time":str(c.get("first_pitch_et") or ""),
    }


def _model_one(c, market, sims):
    c=dict(c); meta=_candidate_meta(c)
    if market=="1+ Hit":
        r=hit133._downgrade_projected(hitcore.deep_scan(c,int(sims)))
        s=r.get("sim") or {}
        return {**meta,"raw_p":_finite(s.get("p_one_plus")),"support":f"xH {_finite(s.get('expected_hits')):.2f} • 2+ {_finite(s.get('p_two_plus'))*100:.1f}%","base_conf":r.get("confidence"),"data":f"{int(r.get('data_score',0) or 0)}/8"}
    if market=="Home Run":
        r=hrcore._model_candidate(c,deep=True,sims=int(sims)) or {}
        return {**meta,"raw_p":_finite(r.get("p_hr")),"support":f"2+ HR {_finite(r.get('p_2hr'))*100:.1f}% • Season HR {r.get('season_hr','—')}","base_conf":r.get("confidence"),"data":str(r.get("data_score") or "—")}
    if market=="H+R+RBI":
        r=hrrcore._profile_candidate(c)
        if not r: raise ValueError("No H+R+RBI profile")
        s=hrrcore._simulate(r,int(sims))
        return {**meta,"raw_p":_finite(s.get("p2")),"support":f"xCombined {_finite(s.get('expected_total')):.2f} • 3+ {_finite(s.get('p3'))*100:.1f}%","base_conf":r.get("confidence"),"data":str(r.get("data_score") or "—")}
    if market=="Total Bases":
        r=components.project_total_bases(c,int(sims))
        if r.get("error"): raise ValueError(r["error"])
        return {**meta,"raw_p":_finite(r.get("p1")),"support":f"xTB {_finite(r.get('expected')):.2f} • 2+ {_finite(r.get('p2'))*100:.1f}%","base_conf":r.get("confidence"),"data":"component"}
    if market=="RBIs":
        r=components.project_rbis(c,int(sims))
        if r.get("error"): raise ValueError(r["error"])
        return {**meta,"raw_p":_finite(r.get("p1")),"support":f"xRBI {_finite(r.get('expected')):.2f} • 2+ {_finite(r.get('p2'))*100:.1f}%","base_conf":r.get("confidence"),"data":"component"}
    if market=="Runs":
        r=components.project_runs(c,int(sims))
        if r.get("error"): raise ValueError(r["error"])
        return {**meta,"raw_p":_finite(r.get("p1")),"support":f"xRuns {_finite(r.get('expected')):.2f} • 2+ {_finite(r.get('p2'))*100:.1f}%","base_conf":r.get("confidence"),"data":"component"}
    raise ValueError("Unsupported market")


def scan_market(games_df, market, sims=20_000, include_live=False):
    pool, info=hit133._candidate_pool(games_df,include_live=bool(include_live))
    year=int(str(games_df.iloc[0].get("game_date"))[:4]) if games_df is not None and not games_df.empty else pd.Timestamp.now().year
    rows=[]; errors=0
    for c in pool:
        try:
            r=_model_one(c,market,sims)
            sample,unit=_season_sample(r["player_id"],year)
            rel=cal._reliability(sample,unit)
            p=cal._shrink(r["raw_p"],sample,PRIORS[market],unit)
            r.update({"p":p,"sample":sample,"sample_unit":unit,"reliability":rel,"confidence":_confidence_label(rel,r.get("base_conf"),r.get("confirmed"))})
            rows.append(r)
        except Exception:
            errors+=1
    rows.sort(key=lambda x:(x["p"],x["reliability"],1 if x["confirmed"] else 0),reverse=True)
    return rows,{"pool":len(pool),"modeled":len(rows),"errors":errors,"pool_info":info}


def _css():
    st.markdown("""
    <style>
    .rk-wrap{border:1px solid #284a67;border-radius:20px;background:#071522;padding:15px;margin:12px 0}.rk-head{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}.rk-title{font-size:1.25rem;font-weight:950;color:#fff}.rk-sub{font-size:.7rem;color:#87a0b7}.rk-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px}.rk-card{border:1px solid #294760;border-radius:16px;background:#0a1928;padding:13px}.rk-card.first{border:2px solid #d9b300}.rk-rank{font-size:.58rem;font-weight:950;color:#5bdcff;letter-spacing:.08em}.rk-name{font-size:1.05rem;color:#fff;font-weight:950;margin-top:5px}.rk-match{font-size:.67rem;color:#8da3b8;margin-top:3px}.rk-p{font-size:2.15rem;font-weight:1000;color:#fff;margin-top:12px}.rk-label{font-size:.58rem;color:#8298ab;font-weight:900;text-transform:uppercase}.rk-details{font-size:.68rem;color:#b9cad8;margin-top:9px}.rk-badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.rk-pill{border:1px solid #31516e;border-radius:999px;padding:4px 7px;font-size:.55rem;font-weight:900;color:#c6d5e1}.rk-pill.good{border-color:#176949;color:#6ff0b4;background:#082d22}
    @media(max-width:700px){.rk-grid{grid-template-columns:1fr}.rk-p{font-size:1.95rem}}
    </style>
    """,unsafe_allow_html=True)


def _render_top5(rows,market,sims):
    top=rows[:5]
    if not top:
        st.warning("No eligible hitters were successfully modeled for this market."); return
    cards=[]
    for i,r in enumerate(top,1):
        status="✅ CONFIRMED" if r["confirmed"] else "🕒 PROJECTED"
        fair=odds(r["p"])
        cards.append(f'''<div class="rk-card {'first' if i==1 else ''}"><div class="rk-rank">{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '•'} RANK {i} • {status}</div><div class="rk-name">{ui._esc(r['player'])}</div><div class="rk-match">{ui._esc(r['team'])} vs {ui._esc(r['opponent'])} • Bat #{ui._esc(r.get('bat_spot'))}</div><div class="rk-p">{r['p']*100:.1f}%</div><div class="rk-label">{ui._esc(market)} probability • Fair {ui._esc(fair)}</div><div class="rk-details">{ui._esc(r['support'])}</div><div class="rk-badges"><span class="rk-pill good">{ui._esc(r['confidence'])}</span><span class="rk-pill">Reliability {r['reliability']*100:.0f}%</span><span class="rk-pill">{r['sample']:.0f} {ui._esc(r['sample_unit'])}</span></div></div>''')
    st.markdown(f'<div class="rk-grid">{"".join(cards)}</div>',unsafe_allow_html=True)
    st.caption(f"Ranking scan completed with {int(sims):,} simulations per eligible hitter for {market}. Probabilities are sample-calibrated; sportsbook prices are not model inputs.")


def render_daily_rankings(games_df):
    _css()
    st.markdown('<div class="rk-wrap"><div class="rk-head"><div><div class="rk-title">🏆 Daily Slate Rankings</div><div class="rk-sub">Full-slate Top 5 boards • one market at a time • frozen production engines + V1.3 calibration</div></div><div class="rk-sub">V1.0</div></div></div>',unsafe_allow_html=True)
    if games_df is None or games_df.empty:
        st.info("No verified MLB slate is available for rankings."); return
    market=st.selectbox("RANKING MARKET",MARKETS,key="mx_rank_market")
    c1,c2=st.columns([2,1])
    with c1:
        depth=st.selectbox("SCAN DEPTH",[20_000,50_000,100_000],format_func=lambda n:f"{n//1000}K simulations / hitter",key="mx_rank_depth")
    with c2:
        include_live=st.checkbox("Include live games",value=False,key="mx_rank_live")
    day=str(games_df.iloc[0].get("game_date"))[:10]
    key=f"mx_rank_result::{day}::{market}::{depth}::{int(include_live)}"
    if st.button(f"🔥 BUILD TOP 5 — {market.upper()}",use_container_width=True,key="mx_rank_build"):
        with st.spinner(f"Scanning the full {market} slate..."):
            rows,diag=scan_market(games_df,market,depth,include_live)
            st.session_state[key]={"rows":rows,"diag":diag}
    result=st.session_state.get(key)
    if result:
        d=result["diag"]
        st.success(f"✅ {d['modeled']}/{d['pool']} eligible hitters modeled • {d['errors']} profile errors")
        _render_top5(result["rows"],market,depth)
    else:
        st.info("Choose a market and tap BUILD TOP 5. Rankings run only on demand so player browsing stays fast.")
