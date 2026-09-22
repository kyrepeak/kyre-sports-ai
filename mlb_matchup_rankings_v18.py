"""MLB Daily Rankings V1.8 — Step 2-5 matchup intelligence for 1+ Hit.

Preserves V1.6 fast/deep workflow. For 1+ Hit only, applies the same conservative,
reliability-gated matchup calibration used by the Matchup Explorer player page.
Fast board uses BvP/platoon/starter form; deep board adds cached Statcast pitch mix.
Other ranking markets remain unchanged.
"""
from __future__ import annotations
import math
import streamlit as st

import mlb_matchup_rankings_v16 as base
import mlb_matchup_rankings_v17 as fastfeeds
import mlb_matchup_rankings_v14 as scbase
import mlb_matchup_player_v18 as intel
import mlb_matchup_player_v19 as verdictmod

VERSION="MLB Daily Rankings V1.8"

def _clamp(x,lo,hi): return max(lo,min(hi,x))
def _finite(v,d=0.0):
    try:
        x=float(v); return x if math.isfinite(x) else d
    except Exception:return d

def _is_hit_market(market):
    s=str(market or "").lower().replace(" ","")
    return ("1+hit" in s or s in {"hit","hits"}) and "hr" not in s and "run" not in s and "rbi" not in s

def _install_fast_feed():
    # Make V1.6's deep pass use the short-timeout shared Statcast cache.
    base.feeds=fastfeeds
    scbase._statcast_rows=fastfeeds._statcast_rows
    try: base.scbase._statcast_rows=fastfeeds._statcast_rows
    except Exception: pass

def _starter_for_row(gm,r):
    try:
        g=gm.get(int(r.get("game_pk") or 0),{})
        is_away=str(r.get("team") or "")==str(g.get("away_team") or "")
        return g.get("home_pitcher_id") if is_away else g.get("away_pitcher_id")
    except Exception:return None

def _player_obj(r,spid):
    return {"id":r.get("player_id") or r.get("id"),"name":r.get("player") or r.get("name") or "Hitter","opponent_pitcher_id":spid,"opponent_pitcher":r.get("opponent_pitcher") or r.get("starter") or "Starter"}

def _verdict_for_row(r,spid,season,deep=False):
    p=_player_obj(r,spid)
    try:
        pid,spid2,hand,r5,_,hs,ps=intel._fast_payload(p,season)
        bvp,bvp_rel,bvp_info=verdictmod._bvp_component(p,season)
        platoon,h_ab,p_bf=intel._platoon_component(hs,ps)
        form=intel._form_component(r5)
        split_rel=min(1.0,max(h_ab/120.0,p_bf/160.0)) if (h_ab or p_bf) else 0.0
        form_rel=min(1.0,float(r5.get("n") or 0)/5.0) if r5.get("status")=="VERIFIED" else 0.0
        pitch=0.0; pitch_rel=0.0; pitch_score=None; pitch_label="NOT LOADED"
        if deep and pid and spid2:
            pc=intel.v16._pitch_context(pid,spid2,season,hand)
            if pc.get("status")=="VERIFIED":
                pitch,pitch_rel=intel._pitch_component(pc)
                pitch_score,pitch_label,_,_,_,_,_=intel._matchup_score(r5,hs,ps,pc)
        weighted=denom=0.0
        for val,w,rel in ((bvp,.15,bvp_rel),(platoon,.30,split_rel),(form,.25,form_rel),(pitch,.30,pitch_rel if deep else 0.0)):
            ew=w*_clamp(rel,0,1)
            if ew>0: weighted+=val*ew;denom+=ew
        combined=weighted/denom if denom else 0.0
        score=int(round(_clamp(50.0+22.0*combined,25,75)))
        label=verdictmod._verdict_label(score)
        reliability=int(round(100*_clamp(denom,0,1)))
        return {"score":score,"label":label,"reliability":reliability,"deep_loaded":bool(deep and pitch_rel>0),"pitch_score":pitch_score,"pitch_label":pitch_label,"bvp_info":bvp_info,"platoon":platoon,"form":form,"pitch":pitch,"pitch_rel":pitch_rel}
    except Exception:
        return {"score":50,"label":"NEUTRAL","reliability":0,"deep_loaded":False}

def _delta(v):
    score=float(v.get("score") or 50); rel=_clamp(float(v.get("reliability") or 0)/100,0,1)
    centered=_clamp((score-50)/25,-1,1); gate=_clamp((rel-.25)/.55,0,1)
    cap=.025 if v.get("deep_loaded") else .0125
    return _clamp(centered*cap*gate,-cap,cap)

def _apply_matchup(games_df,rows,market,deep=False):
    if not _is_hit_market(market): return [dict(r) for r in (rows or [])]
    gm=base._starter_map(games_df)
    season=int(str(games_df.iloc[0].get("game_date"))[:4]) if games_df is not None and not games_df.empty else 2026
    out=[]
    for r0 in rows or []:
        r=dict(r0); spid=_starter_for_row(gm,r); v=_verdict_for_row(r,spid,season,deep=deep)
        d=_delta(v); pre=float(r.get("p") or 0); r["pre_matchup_p"]=pre; r["p"]=_clamp(pre+d,.001,.999)
        r["matchup_score"]=v.get("score");r["matchup_label"]=v.get("label");r["matchup_reliability"]=v.get("reliability");r["matchup_adj"]=d;r["matchup_deep"]=bool(v.get("deep_loaded"));r["matchup_pitch_score"]=v.get("pitch_score")
        out.append(r)
    out.sort(key=lambda x:(float(x.get("p") or 0),float(x.get("reliability") or 0),1 if x.get("confirmed") else 0),reverse=True)
    return out

def fast_scan(games_df,market,sims=20_000,include_live=False):
    _install_fast_feed(); rows,diag=base.fast_scan(games_df,market,sims,include_live); rows=_apply_matchup(games_df,rows,market,deep=False)
    diag=dict(diag or {});diag.update({"matchup_stage":"FAST","ranking_version":"V1.8"});return rows,diag

def deep_calibrate(games_df,rows,market):
    _install_fast_feed(); deep_rows,diag=base.deep_calibrate(games_df,rows,market);deep_rows=_apply_matchup(games_df,deep_rows,market,deep=True)
    diag=dict(diag or {});diag.update({"matchup_stage":"DEEP","ranking_version":"V1.8"});return deep_rows,diag

def _audit(rows,market):
    if not _is_hit_market(market) or not rows:return
    st.markdown("#### 🧠 Top 5 Matchup Intelligence Audit")
    for i,r in enumerate(rows[:5],1):
        adj=float(r.get("matchup_adj") or 0)*100; pre=float(r.get("pre_matchup_p") or r.get("p") or 0)*100; final=float(r.get("p") or 0)*100
        state="DEEP" if r.get("matchup_deep") else "FAST"
        st.caption(f"#{i} {r.get('player')} • {r.get('matchup_score',50)}/100 {r.get('matchup_label','NEUTRAL')} • reliability {r.get('matchup_reliability',0)}% • {state} • {pre:.1f}% → {final:.1f}% ({adj:+.1f} pts)")

def render_daily_rankings(games_df):
    _install_fast_feed();base.core.base.base.base._css()
    st.markdown('<div class="rk-wrap"><div class="rk-head"><div><div class="rk-title">🏆 Daily Slate Rankings — Player Intelligence</div><div class="rk-sub">Fast core + Step 2-5 matchup calibration; optional cached Statcast deep pass for Top-8</div></div><div class="rk-sub">V1.8</div></div></div>',unsafe_allow_html=True)
    if games_df is None or games_df.empty:st.info("No verified MLB slate is available for rankings.");return
    market=st.selectbox("RANKING MARKET",base.core.base.base.base.MARKETS,key="mx_rank_market_v18")
    c1,c2=st.columns([2,1])
    with c1:depth=st.selectbox("SCAN DEPTH",[20_000,50_000,100_000],index=1,format_func=lambda n:f"{n//1000}K simulations / hitter",key="mx_rank_depth_v18")
    with c2:include_live=st.checkbox("Include live games",value=False,key="mx_rank_live_v18")
    day=str(games_df.iloc[0].get("game_date"))[:10];fast_key=f"mx_rank_fast_v18::{day}::{market}::{depth}::{int(include_live)}";deep_key=f"mx_rank_deep_v18::{day}::{market}::{depth}::{int(include_live)}"
    if st.button(f"⚡ BUILD FAST TOP 5 — {market.upper()}",use_container_width=True,key="mx_rank_fast_btn_v18"):
        with st.spinner(f"Building fast {market} board with matchup intelligence..."):
            rows,diag=fast_scan(games_df,market,depth,include_live);st.session_state[fast_key]={"rows":rows,"diag":diag};st.session_state.pop(deep_key,None)
    fast=st.session_state.get(fast_key)
    if fast:
        d=fast["diag"];st.success(f"⚡ FAST BOARD READY • {d.get('modeled',len(fast['rows']))}/{d.get('pool',len(fast['rows']))} hitters modeled • matchup intelligence applied")
        scbase._render_top5(fast["rows"],market,depth);_audit(fast["rows"],market)
        if st.button("🎯 DEEP CALIBRATE TOP 5 — STATCAST TOP-8 ONLY",use_container_width=True,key="mx_rank_deep_btn_v18"):
            with st.spinner("Deep-calibrating Top-8 with shared cached Statcast + player intelligence..."):
                rows,diag=deep_calibrate(games_df,fast["rows"],market);st.session_state[deep_key]={"rows":rows,"diag":diag}
    deep=st.session_state.get(deep_key)
    if deep:
        d=deep["diag"];st.success(f"🎯 DEEP BOARD READY • {d.get('statcast_contenders',0)} hitters checked • player-intelligence calibration synchronized")
        scbase._render_top5(deep["rows"],market,depth);_audit(deep["rows"],market)
        st.caption(f"{VERSION} • 1+ Hit uses Step 2-5 matchup calibration • deep Statcast profiles shared/cached • other ranking markets unchanged")
    elif not fast:st.info("Start with ⚡ FAST TOP 5. Deep Statcast is optional for the final 1+ Hit board.")