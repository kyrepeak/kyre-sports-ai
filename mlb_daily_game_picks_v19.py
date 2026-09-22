"""MLB Daily Game Picks V1.9.2 — full-slate Moneyline connector.

Preserves V1.9 scoring and the existing V16.3/V16.1/V16 moneyline production
model at Standard 150K simulations per game. The connector now uses a longer
bounded build window, more parallel workers, and resumable partial-slate caching
so every eligible game can be completed without weakening production math.
Sportsbook prices remain outside model inputs.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import streamlit as st
import mlb_daily_game_picks_v181 as base
import moneyline_hub_v16 as ml

VERSION="MLB Daily Game Picks V1.9.2 • FULL-SLATE MONEYLINE CONNECTOR"
_ACTIVE_GAMES=None
_orig_candidates=base.base._production_candidates


def _day(games):
    if games is None or games.empty:return ""
    return str(games.iloc[0].get("game_date") or "")[:10]


def _key(games):return f"dgp_prod_moneyline_v19::{_day(games)}"


def _row_pk(row):
    try:return int(row.get("game_pk"))
    except Exception:return None


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


def _build(games,previous=None):
    verified=ml._verified_df(games)
    rows=ml._available_rows(verified,include_live=False)
    total=len(rows)
    if not total:
        return {"rows":[],"modeled_count":0,"candidate_count":0,"total_games":0,"remaining_count":0,"complete":False,"timed_out":False,"errors":["No actionable verified pregame MLB games were available."],"sim_depth":150_000}

    kept={}
    errors=[]
    if previous and not previous.get("complete"):
        for r in previous.get("rows",[]):
            try:kept[int(r.get("game_pk"))]=r
            except Exception:pass
        # Keep real game errors, but remove the old timeout message before a resume.
        for err in previous.get("errors",[]):
            if "safety limit" not in str(err).lower():errors.append(str(err))

    pending=[row for row in rows if _row_pk(row) not in kept]
    retained=len(kept)
    if not pending:
        results=list(kept.values())
        results.sort(key=lambda x:float(x.get("win_prob") or 0),reverse=True)
        return {"rows":results,"modeled_count":len(results),"candidate_count":len(results)*2,"total_games":total,"remaining_count":0,"complete":len(results)>=total,"timed_out":False,"errors":errors,"sim_depth":150_000}

    bar=st.progress(retained/max(total,1),text=f"Moneyline: {retained}/{total} games complete")
    pool=ThreadPoolExecutor(max_workers=min(6,len(pending)))
    futs={pool.submit(_run_one,row):row for row in pending}
    timed_out=False
    finished=retained
    try:
        for fut in as_completed(futs,timeout=110):
            row=futs[fut]
            try:
                r=fut.result()
                if r:
                    pk=_row_pk(r)
                    if pk is not None:kept[pk]=r
            except Exception as exc:
                errors.append(f"{row.get('away_team','Away')} @ {row.get('home_team','Home')}: {type(exc).__name__}: {exc}")
            finished=len(kept)
            bar.progress(min(1.0,finished/max(total,1)),text=f"Moneyline: {finished}/{total} games complete")
    except TimeoutError:
        timed_out=True
        remaining=max(0,total-len(kept))
        errors.append(f"Moneyline reached the 110-second safety limit with {remaining} game(s) remaining. Tap CONTINUE MONEYLINE to finish only the missing games; completed games are preserved.")
        for fut,row in futs.items():
            if not fut.done():fut.cancel()
    finally:
        pool.shutdown(wait=False,cancel_futures=True)
        bar.empty()

    results=list(kept.values())
    results.sort(key=lambda x:float(x.get("win_prob") or 0),reverse=True)
    remaining=max(0,total-len(results))
    return {
        "rows":results,"modeled_count":len(results),"candidate_count":len(results)*2,
        "total_games":total,"remaining_count":remaining,"complete":remaining==0,
        "timed_out":timed_out,"errors":errors,"sim_depth":150_000,
    }


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
        if pack and pack.get("rows") and pack.get("complete"):
            st.success(f"💰 Moneyline production connector ready • {pack.get('modeled_count',0)}/{pack.get('total_games',pack.get('modeled_count',0))} games modeled • {pack.get('candidate_count',0)} team sides normalized • 150K sims/game • {day}")
        elif pack and pack.get("rows"):
            st.warning(f"💰 Moneyline partial slate saved • {pack.get('modeled_count',0)}/{pack.get('total_games',0)} games modeled • {pack.get('remaining_count',0)} remaining • completed models preserved")
        else:
            st.info("💰 Moneyline connector is ready to build. Tap CONNECT once; visible full-slate progress will begin immediately.")
    with c2:
        if pack and pack.get("rows") and not pack.get("complete"):
            label="▶ CONTINUE MONEYLINE"
        elif pack and pack.get("rows"):
            label="↻ REFRESH MONEYLINE"
        else:
            label="💰 CONNECT MONEYLINE"
        if st.button(label,use_container_width=True,key=f"dgp_moneyline_connect_v192::{day}"):
            resume=pack if pack and pack.get("rows") and not pack.get("complete") else None
            st.toast("💰 Moneyline build started" if resume is None else "💰 Resuming remaining Moneyline games")
            status=st.status("Moneyline connector is working…",expanded=True)
            status.write("Running the existing V16 production model at 150K simulations per game. Completed games are cached during partial builds.")
            try:
                st.session_state[key]=_build(games_df,resume)
                built=st.session_state[key]
                if built.get("complete"):
                    status.update(label=f"Moneyline complete — {built.get('modeled_count',0)}/{built.get('total_games',0)} games modeled",state="complete",expanded=False)
                elif built.get("rows"):
                    status.update(label=f"Moneyline partial — {built.get('modeled_count',0)}/{built.get('total_games',0)} complete; {built.get('remaining_count',0)} remaining",state="complete",expanded=True)
                else:
                    status.update(label="Moneyline finished with no completed models",state="error",expanded=True)
            except Exception as exc:
                st.session_state[key]={"rows":[],"modeled_count":0,"candidate_count":0,"total_games":0,"remaining_count":0,"complete":False,"errors":[f"{type(exc).__name__}: {exc}"]}
                status.update(label=f"Moneyline error: {type(exc).__name__}",state="error",expanded=True)
            st.rerun()

    if pack and pack.get("errors"):
        with st.expander(f"⚠️ Moneyline connector diagnostics ({len(pack['errors'])})"):
            for err in pack["errors"]:st.caption(str(err))
    st.caption("🔌 Step 4E V1.9.2: Moneyline still uses the existing V16.3/V16.1/V16 production model at Standard 150K depth. Full-slate builds now use up to 6 workers, a 110-second bounded window, and resumable caching so a slow request cannot erase completed games or force the model to weaken its simulation depth.")
    return base.render_daily_game_picks(games_df,section_header,status_info,team_logo,h)
