"""MLB Daily Game Picks V1.8.1 — Pitcher K connector reliability hotfix.

Preserves V1.8 candidate/scoring behavior, but replaces the connector build path
with a bounded, visible workflow so a slow external profile/line request cannot
make the CONNECT button appear to do nothing.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import streamlit as st
import mlb_daily_game_picks_v18 as base

engine=base.engine
VERSION="MLB Daily Game Picks V1.8.1 • PITCHER K CONNECTOR HOTFIX"


def _build(games):
    active=base._active_rows(games)
    try:ctx=engine.build_slate_player_context(games)
    except Exception:ctx={}
    candidates=[]
    for row in active:
        for side in ("away","home"):
            try:c=engine._build_pitcher_candidate(row,side,ctx)
            except Exception:c=None
            if c:candidates.append(c)

    projected=[];errors=[]
    if candidates:
        bar=st.progress(0,text=f"Pitcher K: loading starter profiles 0/{len(candidates)}")
        pool=ThreadPoolExecutor(max_workers=min(10,len(candidates)))
        futs={pool.submit(engine._project_pitcher,c):c for c in candidates}
        done=0
        try:
            # Bound the whole profile phase. Individual MLB requests already have
            # timeouts, but this prevents one hung future from blocking the UI.
            for fut in as_completed(futs,timeout=45):
                done+=1
                try:
                    r=fut.result()
                    if r:projected.append(r)
                except Exception as exc:
                    errors.append(f"{futs[fut].get('player_name')}: {type(exc).__name__}: {exc}")
                bar.progress(done/max(len(candidates),1),text=f"Pitcher K: starter profiles {done}/{len(candidates)}")
        except TimeoutError:
            errors.append("Starter-profile phase reached the 45-second safety limit; completed starters were kept.")
            for fut,c in futs.items():
                if not fut.done():fut.cancel()
        finally:
            pool.shutdown(wait=False,cancel_futures=True)
            bar.empty()

    # Sportsbook lookup is useful for grading but must never prevent projections
    # from being cached and visibly completing.
    market_lines={};market_meta={"connected":False}
    if projected:
        try:
            with st.spinner("Pitcher K: checking posted sportsbook lines..."):
                market_lines,market_meta=engine._fetch_market_lines(games,projected)
        except Exception as exc:
            market_meta={"connected":False,"error":f"{type(exc).__name__}: {exc}"}

    graded=[];unposted=0
    projected.sort(key=lambda x:x.get("projected_k",0),reverse=True)
    if projected:
        bar=st.progress(0,text=f"Pitcher K: simulations 0/{len(projected)}")
        for i,r in enumerate(projected,1):
            seed=281000+int(r["game_pk"])%100000+int(r["player_id"])%10000
            try:r["sim"]=engine._simulate_distribution(r,250_000,seed)
            except Exception as exc:
                errors.append(f"{r.get('player_name')}: simulation {type(exc).__name__}: {exc}")
                bar.progress(i/max(len(projected),1));continue
            market=market_lines.get((int(r["game_pk"]),engine._norm_name(r.get("player_name"))))
            r["market"]=market
            line=(market or {}).get("line")
            if line is None:unposted+=1
            else:
                try:g=engine._grade_line(r["sim"],line)
                except Exception:g=None
                if g:
                    rr=dict(r);rr["grade"]=g;graded.append(rr)
            bar.progress(i/max(len(projected),1),text=f"Pitcher K: simulations {i}/{len(projected)}")
        bar.empty()
    return {"rows":graded,"projected":projected,"projected_count":len(projected),"candidate_count":len(candidates),"unposted_count":unposted,"market_meta":dict(market_meta or {}),"errors":errors,"sim_depth":250_000}

# Patch V1.8's builder; keep all rendering and scoring behavior unchanged.
base._build=_build


def render_daily_game_picks(games_df,section_header=None,status_info=None,team_logo=None,h=None):
    return base.render_daily_game_picks(games_df,section_header,status_info,team_logo,h)
