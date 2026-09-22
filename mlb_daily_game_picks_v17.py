"""MLB Daily Game Picks V1.7 — Step 4C non-blocking H+R+RBI connector.

Preserves V1.6 1+ Hit + Home Run connectors and adds the existing H+R+RBI V1.0
joint-event model. The connector is manual, cached by slate date, and simulates
three production finalists per game at the module's Quick depth (250K each).
No H+R+RBI probability math is reimplemented or altered.
"""
from __future__ import annotations
import streamlit as st
import mlb_daily_game_picks_v16 as base
import mlb_hrrbi_hub_v10 as hrr

VERSION="MLB Daily Game Picks V1.7 • STEP 4C H+R+RBI CONNECTOR"
_ACTIVE_GAMES=None
_orig_candidates=base._production_candidates


def _day(games):
    if games is None or games.empty:return ""
    return str(games.iloc[0].get("game_date") or "")[:10]


def _key(games):return f"dgp_prod_hrrbi_v17::{_day(games)}"


def _quality(r):
    try:s=float(r.get("data_score") or 0)
    except Exception:s=0.0
    return max(0.0,min(1.0,s/7.0))


def _reliability(r):
    try:pa=float((r.get("profile") or {}).get("pa") or 0)
    except Exception:pa=0.0
    sample_rel=pa/(pa+180.0) if pa>0 else 0.0
    return max(0.0,min(1.0,.65*sample_rel+.35*_quality(r)))


def _hrr_candidates(row):
    games=_ACTIVE_GAMES
    if games is None or games.empty:return []
    pack=st.session_state.get(_key(games),{})
    gpk=str(base.base.base._gamepk(row));out=[]
    for r in pack.get("rows",[]):
        if str(r.get("game_pk") or "")!=gpk:continue
        sim=r.get("sim") or {}
        try:p=float(sim.get("p2"))
        except Exception:continue
        rel=_reliability(r);dq=_quality(r)
        norm=base.base.base.base.normalize_candidate(
            market="H+R+RBI",probability=p,reliability=rel,data_quality=dq,
            confirmed=bool(r.get("lineup_confirmed")),uncertainty=None,stale=False)
        if norm.get("status")!="SCORED":continue
        out.append({
            "market":"H+R+RBI","name":str(r.get("player_name") or "Hitter"),
            "side":"2+ H+R+RBI","line":1.5,"probability":p,"reliability":rel,
            "data_quality":dq,"score":norm["score"],"source":"H+R+RBI V1.0 joint-event production model",
            "normalization":norm,"team":r.get("team"),"confidence":r.get("confidence"),
            "expected_total":sim.get("expected_total"),"median":sim.get("median"),"mode":sim.get("mode"),
            "simulations":sim.get("n")})
    return sorted(out,key=lambda x:x["score"],reverse=True)


def _production_candidates(row,market):
    if market=="H+R+RBI":return _hrr_candidates(row)
    return _orig_candidates(row,market)

base._production_candidates=_production_candidates


def _build(games):
    candidates,meta=hrr._candidate_pool(games,False)
    profiles=hrr._bulk_profiles(candidates) if candidates else []
    by_game={}
    for r in profiles:
        by_game.setdefault(str(r.get("game_pk") or ""),[]).append(r)
    deep=[]
    groups=list(by_game.items())
    total=sum(min(3,len(v)) for _,v in groups)
    done=0
    bar=st.progress(0,text="Building H+R+RBI game finalists...") if total else None
    for _,rows in groups:
        rows=sorted(rows,key=lambda x:float(x.get("expected_total") or 0),reverse=True)[:3]
        for r in rows:
            try:
                rr=dict(r);rr["sim"]=hrr._simulate(rr,250_000);deep.append(rr)
            except Exception:
                pass
            done+=1
            if bar:bar.progress(done/max(total,1),text=f"Simulating H+R+RBI finalist {done}/{total}")
    if bar:bar.empty()
    return {"rows":deep,"meta":dict(meta or {}),"sim_depth":250_000}


def render_daily_game_picks(games_df,section_header=None,status_info=None,team_logo=None,h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES=games_df
    base._ACTIVE_GAMES=games_df
    base.base._ACTIVE_GAMES=games_df
    base.base.base._ACTIVE_GAMES=games_df
    day=_day(games_df);key=_key(games_df);pack=st.session_state.get(key)

    c1,c2=st.columns([4,1])
    with c1:
        if pack and pack.get("rows"):
            st.success(f"🧮 H+R+RBI production connector ready • {len(pack['rows'])} per-game finalists cached • 250K sims each • {day}")
        else:
            st.info("🧮 H+R+RBI connector is ready to build. It will run only when requested.")
    with c2:
        label="↻ REFRESH H+R+RBI" if pack and pack.get("rows") else "🧮 CONNECT H+R+RBI"
        if st.button(label,use_container_width=True,key=f"dgp_hrrbi_connect_v17::{day}"):
            with st.spinner("Building H+R+RBI V1.0 per-game finalists with joint-event simulations..."):
                try:st.session_state[key]=_build(games_df)
                except Exception as exc:st.session_state[key]={"rows":[],"meta":{"error":f"{type(exc).__name__}: {exc}"}}
            st.rerun()

    st.caption("🔌 Step 4C: H+R+RBI now connects directly to the V1.0 joint-event engine. Three finalists per game are simulated at the module's Quick 250K depth; production math is unchanged and cached after build.")
    return base.render_daily_game_picks(games_df,section_header,status_info,team_logo,h)
