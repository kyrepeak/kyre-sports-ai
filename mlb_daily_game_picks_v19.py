"""MLB Daily Game Picks V1.9.1 — Moneyline connector responsiveness hotfix.

Preserves V1.9 scoring and the existing V16.3/V16.1/V16 moneyline production
model, but bounds the slate build so a slow game-model request cannot make the
CONNECT button appear unresponsive. Sportsbook prices remain outside model inputs.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import streamlit as st
import mlb_daily_game_picks_v181 as base
import moneyline_hub_v16 as ml

VERSION="MLB Daily Game Picks V1.9.1 • MONEYLINE CONNECTOR HOTFIX"
_ACTIVE_GAMES=None
_orig_candidates=base.base._production_candidates


def _day(games):
    if games is None or games.empty:return ""
    return str(games.iloc[0].get("game_date") or "")[:10]


def _key(games):return f"dgp_prod_moneyline_v19::{_day(games)}"


def _confidence_rel(v):
    t=str(v or "").upper()
    if t=="HIGH":return .90
    if "MEDIUM-HIGH" in t:return .80
    if "MEDIUM" in t:return .70
    return .58


def _quality(r):
    try:s=float(r.get("data_score") or 0)
    except Exception:s=0.0
    return max(0.0,min(1.0,s/9.0))


def _ml_candidates(row):
    games=_ACTIVE_GAMES
    if games is None or games.empty:return []
    pack=st.session_state.get(_key(games),{})
    try:gpk=str(int(row.get("game_pk")))
    except Exception:gpk=str(row.get("game_pk") or "")
    out=[]
    for r in pack.get("rows",[]):
        if str(r.get("game_pk") or "")!=gpk:continue
        rel=_confidence_rel(r.get("confidence"));dq=_quality(r)
        confirmed=base.base.base.base.base._confirmed_flag(row)
        for side,team,team_id,opp,p in (
            ("away",r.get("away_name"),r.get("away_team_id"),r.get("home_name"),r.get("final_away")),
            ("home",r.get("home_name"),r.get("home_team_id"),r.get("away_name"),r.get("final_home")),
        ):
            try:p=float(p)
            except Exception:continue
            norm=base.base.base.base.base.base.normalize_candidate(
                market="Moneyline",probability=p,reliability=rel,data_quality=dq,
                confirmed=confirmed,uncertainty=None,stale=False)
            if norm.get("status")!="SCORED":continue
            out.append({
                "market":"Moneyline","name":str(team or "Team"),"side":"ML","line":None,
                "probability":p,"reliability":rel,"data_quality":dq,"score":norm["score"],
                "source":"Moneyline V16.3 production model","normalization":norm,
                "team":team,"team_id":team_id,"opponent":opp,"confidence":r.get("confidence"),
                "fair_odds":ml.odds(p),"projected_margin":(r.get("projected_margin") if side==r.get("selected_side") else -float(r.get("projected_margin") or 0)),
                "simulations":r.get("simulations"),"mc_se":r.get("mc_se"),"converged":r.get("converged")})
    return sorted(out,key=lambda x:x["score"],reverse=True)


def _production_candidates(row,market):
    if market=="Moneyline":return _ml_candidates(row)
    return _orig_candidates(row,market)

base.base._production_candidates=_production_candidates


def _run_one(row):
    return ml._scan_game(row,150_000)


def _build(games):
    verified=ml._verified_df(games)
    rows=ml._available_rows(verified,include_live=False)
    results=[];errors=[]
    total=len(rows)
    if not total:
        return {"rows":[],"modeled_count":0,"candidate_count":0,"errors":["No actionable verified pregame MLB games were available."],"sim_depth":150_000}

    bar=st.progress(0,text=f"Moneyline: starting 0/{total} games")
    pool=ThreadPoolExecutor(max_workers=min(4,total))
    futs={pool.submit(_run_one,row):row for row in rows}
    done=0
    try:
        for fut in as_completed(futs,timeout=55):
            done+=1
            row=futs[fut]
            try:
                r=fut.result()
                if r:results.append(r)
            except Exception as exc:
                errors.append(f"{row.get('away_team','Away')} @ {row.get('home_team','Home')}: {type(exc).__name__}: {exc}")
            bar.progress(done/max(total,1),text=f"Moneyline: modeled {done}/{total} games")
    except TimeoutError:
        errors.append("Moneyline build reached the 55-second safety limit; completed games were kept.")
        for fut,row in futs.items():
            if not fut.done():fut.cancel()
    finally:
        pool.shutdown(wait=False,cancel_futures=True)
        bar.empty()

    results.sort(key=lambda x:float(x.get("win_prob") or 0),reverse=True)
    return {"rows":results,"modeled_count":len(results),"candidate_count":len(results)*2,"errors":errors,"sim_depth":150_000}


def render_daily_game_picks(games_df,section_header=None,status_info=None,team_logo=None,h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES=games_df
    base.base._ACTIVE_GAMES=games_df
    base.base.base._ACTIVE_GAMES=games_df
    base.base.base.base._ACTIVE_GAMES=games_df
    base.base.base.base.base._ACTIVE_GAMES=games_df
    day=_day(games_df);key=_key(games_df);pack=st.session_state.get(key)

    c1,c2=st.columns([4,1])
    with c1:
        if pack and pack.get("rows"):
            st.success(f"💰 Moneyline production connector ready • {pack.get('modeled_count',0)} games modeled • {pack.get('candidate_count',0)} team sides normalized • 150K sims/game • {day}")
        else:
            st.info("💰 Moneyline connector is ready to build. Tap CONNECT once; a progress bar should appear immediately.")
    with c2:
        label="↻ REFRESH MONEYLINE" if pack and pack.get("rows") else "💰 CONNECT MONEYLINE"
        if st.button(label,use_container_width=True,key=f"dgp_moneyline_connect_v191::{day}"):
            st.toast("💰 Moneyline build started")
            status=st.status("Moneyline connector is working…",expanded=True)
            status.write("Loading verified pregame games and running V16 production models.")
            try:
                st.session_state[key]=_build(games_df)
                built=st.session_state[key]
                if built.get("rows"):
                    status.update(label=f"Moneyline complete — {built.get('modeled_count',0)} games modeled",state="complete",expanded=False)
                else:
                    status.update(label="Moneyline finished with no completed models",state="error",expanded=True)
            except Exception as exc:
                st.session_state[key]={"rows":[],"modeled_count":0,"candidate_count":0,"errors":[f"{type(exc).__name__}: {exc}"]}
                status.update(label=f"Moneyline error: {type(exc).__name__}",state="error",expanded=True)
            st.rerun()

    if pack and pack.get("errors"):
        with st.expander(f"⚠️ Moneyline connector diagnostics ({len(pack['errors'])})"):
            for err in pack["errors"]:st.caption(str(err))
    st.caption("🔌 Step 4E hotfix: Moneyline still uses the existing V16.3/V16.1/V16 production model at Standard 150K depth, but the build is now concurrent, visibly acknowledged, and capped at 55 seconds so a slow request cannot silently hang the button.")
    return base.render_daily_game_picks(games_df,section_header,status_info,team_logo,h)
