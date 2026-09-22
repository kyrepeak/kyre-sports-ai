"""MLB Daily Game Picks V1.8 — Step 4D Pitcher Strikeouts connector.

Preserves V1.7 connectors and adds the existing Pitcher K V1.0.x production
workload/opponent-K/Monte-Carlo engine. The connector is manual and cached by
slate date. It never invents a K line: only verified posted market lines become
scored Daily Game Picks candidates.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import streamlit as st
import mlb_daily_game_picks_v17 as base
import mlb_pitcher_k_hub_v106 as pkmod

engine = pkmod.engine
VERSION="MLB Daily Game Picks V1.8 • STEP 4D PITCHER K CONNECTOR"
_ACTIVE_GAMES=None
_orig_candidates=base._production_candidates


def _day(games):
    if games is None or games.empty:return ""
    return str(games.iloc[0].get("game_date") or "")[:10]


def _key(games):return f"dgp_prod_pitcherk_v18::{_day(games)}"


def _data_quality(r):
    try: rel=float(r.get("reliability") or 0)
    except Exception: rel=0.0
    try: opp=float(r.get("opp_sample") or 0)
    except Exception: opp=0.0
    opp_rel=max(0.0,min(1.0,opp/1200.0))
    # Both components are direct production evidence: model reliability and opponent sample coverage.
    return max(0.0,min(1.0,.75*rel+.25*opp_rel))


def _pk_candidates(row):
    games=_ACTIVE_GAMES
    if games is None or games.empty:return []
    pack=st.session_state.get(_key(games),{})
    gpk=str(base.base.base.base._gamepk(row));out=[]
    for r in pack.get("rows",[]):
        if str(r.get("game_pk") or "")!=gpk:continue
        grade=r.get("grade") or {}
        try:p=float(grade.get("win_prob"))
        except Exception:continue
        try:rel=float(r.get("reliability") or 0)
        except Exception:rel=0.0
        dq=_data_quality(r)
        norm=base.base.base.base.base.normalize_candidate(
            market="Pitcher Strikeouts",probability=p,reliability=rel,data_quality=dq,
            confirmed=bool(r.get("opp_lineup_confirmed")),uncertainty=None,stale=False)
        if norm.get("status")!="SCORED":continue
        side=str(grade.get("side") or "")
        line=grade.get("line")
        out.append({
            "market":"Pitcher Strikeouts","name":str(r.get("player_name") or "Pitcher"),
            "side":f"{side} {line:g}" if line is not None else side,"line":line,
            "probability":p,"reliability":rel,"data_quality":dq,"score":norm["score"],
            "source":"Pitcher K V1.0.x production model","normalization":norm,
            "team":r.get("team"),"confidence":r.get("confidence"),
            "expected_k":(r.get("sim") or {}).get("mean"),
            "projected_ip":r.get("projected_ip"),"opp_k_rate":r.get("opp_k_rate"),
            "push_probability":grade.get("p_push"),"fair_odds":grade.get("fair_odds")})
    return sorted(out,key=lambda x:x["score"],reverse=True)


def _production_candidates(row,market):
    if market=="Pitcher Strikeouts":return _pk_candidates(row)
    return _orig_candidates(row,market)

base._production_candidates=_production_candidates


def _active_rows(games):
    rows=[]
    for _,row in games.iterrows():
        status=str(row.get("status") or "").lower()
        if any(x in status for x in ("final","completed","cancel","postpon","suspended","in progress","live","delayed")):
            continue
        rows.append(row)
    return rows


def _build(games):
    active=_active_rows(games)
    try: ctx=engine.build_slate_player_context(games)
    except Exception: ctx={}
    candidates=[]
    for row in active:
        for side in ("away","home"):
            try:c=engine._build_pitcher_candidate(row,side,ctx)
            except Exception:c=None
            if c:candidates.append(c)

    projected=[];errors=[]
    if candidates:
        bar=st.progress(0,text="Building pitcher workload + opponent K profiles...")
        with ThreadPoolExecutor(max_workers=min(8,len(candidates))) as pool:
            futs={pool.submit(engine._project_pitcher,c):c for c in candidates}
            done=0
            for fut in as_completed(futs):
                done+=1
                try:
                    r=fut.result()
                    if r:projected.append(r)
                except Exception as exc:errors.append(f"{futs[fut].get('player_name')}: {exc}")
                bar.progress(done/max(len(candidates),1),text=f"Pitcher profiles {done}/{len(candidates)}")
        bar.empty()

    try:market_lines,market_meta=engine._fetch_market_lines(games,projected)
    except Exception as exc:market_lines,market_meta={}, {"connected":False,"error":str(exc)}

    graded=[];unposted=0
    projected.sort(key=lambda x:x.get("projected_k",0),reverse=True)
    if projected:
        bar=st.progress(0,text="Running 250K pitcher K distributions...")
        for i,r in enumerate(projected,1):
            seed=281000+int(r["game_pk"])%100000+int(r["player_id"])%10000
            try:r["sim"]=engine._simulate_distribution(r,250_000,seed)
            except Exception:
                bar.progress(i/max(len(projected),1));continue
            market=market_lines.get((int(r["game_pk"]),engine._norm_name(r.get("player_name"))))
            r["market"]=market
            line=(market or {}).get("line")
            if line is None:
                unposted+=1
            else:
                g=engine._grade_line(r["sim"],line)
                if g:
                    rr=dict(r);rr["grade"]=g;graded.append(rr)
            bar.progress(i/max(len(projected),1),text=f"Pitcher K simulations {i}/{len(projected)}")
        bar.empty()
    return {"rows":graded,"projected_count":len(projected),"unposted_count":unposted,"market_meta":dict(market_meta or {}),"errors":errors,"sim_depth":250_000}


def render_daily_game_picks(games_df,section_header=None,status_info=None,team_logo=None,h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES=games_df
    # Synchronize active-game pointers through the connector inheritance chain.
    base._ACTIVE_GAMES=games_df
    base.base._ACTIVE_GAMES=games_df
    base.base.base._ACTIVE_GAMES=games_df
    base.base.base.base._ACTIVE_GAMES=games_df
    day=_day(games_df);key=_key(games_df);pack=st.session_state.get(key)

    c1,c2=st.columns([4,1])
    with c1:
        if pack and (pack.get("projected_count") or pack.get("rows")):
            st.success(f"🔥 Pitcher K production connector ready • {pack.get('projected_count',0)} starters modeled • {len(pack.get('rows',[]))} posted K lines graded • 250K sims each • {day}")
        else:
            st.info("🔥 Pitcher Strikeouts connector is ready to build. It will run only when requested.")
    with c2:
        label="↻ REFRESH PITCHER K" if pack and (pack.get("projected_count") or pack.get("rows")) else "🔥 CONNECT PITCHER K"
        if st.button(label,use_container_width=True,key=f"dgp_pitcherk_connect_v18::{day}"):
            with st.spinner("Building Pitcher K production projections and grading verified posted lines..."):
                try:st.session_state[key]=_build(games_df)
                except Exception as exc:st.session_state[key]={"rows":[],"projected_count":0,"errors":[f"{type(exc).__name__}: {exc}"]}
            st.rerun()

    if pack and pack.get("unposted_count"):
        st.caption(f"🎯 {pack['unposted_count']} modeled starter(s) have no verified posted K line, so they remain projection-only and are not promoted into cross-market scoring.")
    st.caption("🔌 Step 4D: Pitcher Strikeouts uses the existing workload + opponent-K + Monte Carlo production engine. Only real posted K lines are graded; no threshold is fabricated.")
    return base.render_daily_game_picks(games_df,section_header,status_info,team_logo,h)
