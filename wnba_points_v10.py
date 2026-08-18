"""WNBA Points V1.0 — production points-only connector.

WNBA-only. MLB V2.1.7 remains frozen.

Pipeline:
verified minutes/role -> points-specific matchup/pace mean -> exact SportsGameOdds
Points over/under pair -> empirical points variance -> actual 5M Monte Carlo ->
same-book no-vig grading -> optional 10M finalist pass -> reload-safe summary
persistence. PRA is never used as a shortcut for the points projection.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import time
import zlib

import numpy as np
import pandas as pd
import streamlit as st

try:
    from streamlit_local_storage import LocalStorage
except Exception:
    LocalStorage = None

import wnba_pra_matchup_v30 as matchup
import wnba_pra_market_v29 as market
import wnba_pra_monte_carlo_v31 as mcbase
import wnba_pra_monte_carlo_v311 as empirical
import wnba_role_v282 as role
import wnba_sportsgameodds_v1 as sgo

MODEL_VERSION = "WNBA POINTS V1.0"
MODEL_SCHEMA = "WNBA-POINTS-V1.0-EMPIRICAL"
STANDARD_SIMS = 5_000_000
FINAL_SIMS = 10_000_000
BATCH_SIZE = 250_000
CONVERGENCE_BATCH_SPREAD = 0.006
CACHE_DIR = Path(".kyre_runtime_cache")
_LOCAL = LocalStorage() if LocalStorage is not None else None


def _num(v, default=np.nan):
    try:
        x = float(v)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _day(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def std_key(day):
    return f"wnba_points_v10_standard::{_day(day)}"


def final_key(day):
    return f"wnba_points_v10_final::{_day(day)}"


def source_key(day):
    return f"wnba_points_v10_restore_source::{_day(day)}"


def _browser_key(day):
    return f"kyre_sports_ai_wnba_points_v10::{_day(day)}"


def _component_key(day):
    return f"wnba_points_v10_local_get::{_day(day)}"


def _disk_path(day):
    return CACHE_DIR / f"wnba_points_v10_{_day(day)}.json.gz"


def _stable_seed(day, game_id, player_key, line, sims):
    token = f"{MODEL_VERSION}|{_day(day)}|{game_id}|{player_key}|{float(line):.3f}|{int(sims)}"
    return int(hashlib.sha256(token.encode()).hexdigest()[:8], 16)


def _paired_points_markets(day):
    snap = sgo.market_snapshot(day)
    props = snap.get("player_props")
    if props is None or not isinstance(props, pd.DataFrame) or props.empty:
        return pd.DataFrame(), snap
    p = props.loc[props["market"].astype(str).str.upper().eq("POINTS")].copy()
    if p.empty:
        return pd.DataFrame(), snap
    keys = ["game_id","player_key","player_name","line","book"]
    over = p.loc[p["side"].astype(str).str.lower().eq("over")].rename(columns={"odds":"over_odds","age_seconds":"over_age","updated_at":"over_updated"})
    under = p.loc[p["side"].astype(str).str.lower().eq("under")].rename(columns={"odds":"under_odds","age_seconds":"under_age","updated_at":"under_updated"})
    if over.empty or under.empty:
        return pd.DataFrame(), snap
    pairs = over[keys+["over_odds","over_age","over_updated"]].merge(
        under[keys+["under_odds","under_age","under_updated"]], on=keys, how="inner"
    )
    if not pairs.empty:
        pairs["market_age"] = pairs[["over_age","under_age"]].max(axis=1, skipna=True)
    return pairs, snap


def _prepare(day):
    projections, pmeta = matchup.matchup_projection_frame(day)
    pairs, snap = _paired_points_markets(day)
    schedule = pmeta.get("schedule")
    stats = role.player_form_table()
    lineups = mcbase._lineup_map(day, schedule, stats)
    return projections, pairs, snap, pmeta, lineups


def _points_distribution(proj, lineup_ready=False):
    mu = max(0.0, _num(proj.get("PROJ_PTS"), 0.0))
    profile = empirical._profile_for_projection(proj) or {}
    games = int(profile.get("games") or 0)
    if games >= 5:
        hist_mu = max(1.0, _num(profile.get("pts"), mu or 1.0))
        role_scale = float(np.clip((max(mu,1.0)/hist_mu) ** 0.25, 0.82, 1.20))
        sd = max(1.25, _num(profile.get("sd_pts"), 2.8) * role_scale)
        source = f"EMPIRICAL POINTS • {profile.get('source') or 'verified game log'}"
        quality = min(1.0, 0.58 + min(games,30)/30.0*0.34)
    else:
        sd = max(2.4, math.sqrt(max(mu,1.0))*1.20)
        source = "FALLBACK POINTS • no verified >=5-game log"
        quality = 0.48
    context_q = float(np.clip(_num(proj.get("context_quality"),0.5),0.0,1.0))
    role_label = str(proj.get("ROLE_LABEL") or "ACTIVE").upper()
    uncertainty = 1.0 + 0.08*(1.0-context_q)
    if not lineup_ready:
        uncertainty += 0.08
    if "UNCERTAIN" in role_label:
        uncertainty += 0.10
    if _num(proj.get("PROJ_MIN"),0.0) < 15.0:
        uncertainty += 0.04
    return mu, sd*uncertainty, {
        "hist_games": games,
        "variance_source": source,
        "data_quality": quality,
        "uncertainty_mult": uncertainty,
    }


def _hist_quantile(hist, q):
    total = int(np.sum(hist)) if hist is not None else 0
    if total <= 0:
        return np.nan
    target = max(1, int(math.ceil(float(q)*total)))
    return float(np.searchsorted(np.cumsum(hist), target, side="left"))


@st.cache_data(ttl=900, show_spinner=False, max_entries=256)
def _simulate_cached(day, game_id, player_key, line, mu, sd, sims, seed, batch_size):
    rng = np.random.default_rng(int(seed))
    n_sims = int(sims); batch_size = int(max(10_000,batch_size))
    completed = over = under = push = batches = 0
    total_sum = total_sq = 0.0
    hist = np.zeros(96, dtype=np.int64)
    batch_ps = []
    started = time.perf_counter()
    integer_line = abs(float(line)-round(float(line))) < 1e-9
    while completed < n_sims:
        n = min(batch_size, n_sims-completed)
        draws = np.rint(np.clip(rng.normal(float(mu), float(sd), size=n), 0.0, None)).astype(np.int16, copy=False)
        if integer_line:
            target = int(round(float(line)))
            o = int(np.count_nonzero(draws > target)); u = int(np.count_nonzero(draws < target)); p = n-o-u
        else:
            o = int(np.count_nonzero(draws > float(line))); u = n-o; p = 0
        over += o; under += u; push += p; completed += n; batches += 1
        total_sum += float(draws.sum(dtype=np.int64)); total_sq += float(np.square(draws.astype(float)).sum())
        bc = np.bincount(np.minimum(draws, len(hist)-1), minlength=len(hist)); hist += bc[:len(hist)]
        resolved = o+u; batch_ps.append(o/resolved if resolved else 0.5)
    resolved = over+under
    p_over = over/resolved if resolved else 0.5
    p_under = under/resolved if resolved else 0.5
    p_push = push/completed if completed else 0.0
    mean = total_sum/completed if completed else np.nan
    var = max(total_sq/completed - mean*mean, 0.0) if completed else np.nan
    se = math.sqrt(max(p_over*(1-p_over),0.0)/max(resolved,1))
    spread = max(batch_ps)-min(batch_ps) if len(batch_ps)>1 else 0.0
    return {
        "sims": completed, "batches": batches, "seed": int(seed),
        "p_over": float(p_over), "p_under": float(p_under), "p_push": float(p_push),
        "p_over_raw": over/completed if completed else 0.0,
        "p_under_raw": under/completed if completed else 0.0,
        "mc_se": float(se), "max_batch_diff": float(spread),
        "converged": bool(spread <= CONVERGENCE_BATCH_SPREAD and se <= 0.0005),
        "mean": float(mean), "sd": float(math.sqrt(var)) if np.isfinite(var) else np.nan,
        "median": _hist_quantile(hist,.50), "mode": float(np.argmax(hist)) if hist.sum() else np.nan,
        "p10": _hist_quantile(hist,.10), "p90": _hist_quantile(hist,.90),
        "elapsed_s": float(time.perf_counter()-started),
    }


def _market_rows(day, sim_count=STANDARD_SIMS, progress=None, only_units=None):
    projections, pairs, snap, pmeta, lineups = _prepare(day)
    if projections is None or projections.empty or pairs is None or pairs.empty:
        return pd.DataFrame(), {"snapshot":snap,"pairs":0,**pmeta}
    pmap = {(str(r.get("game_id") or ""),str(r.get("player_key") or "")):r for _,r in projections.iterrows()}
    units = pairs[["game_id","player_key","player_name","line"]].drop_duplicates().reset_index(drop=True)
    if only_units:
        allowed = set(only_units)
        units = units[units.apply(lambda r:(str(r["game_id"]),str(r["player_key"]),float(r["line"])) in allowed,axis=1)].reset_index(drop=True)
    sim_map={}; meta_map={}; total=len(units)
    for i,u in units.iterrows():
        gid=str(u.get("game_id") or ""); pkey=str(u.get("player_key") or ""); line=_num(u.get("line"),np.nan)
        proj=pmap.get((gid,pkey))
        if proj is None or pd.isna(line): continue
        lineup_ready=bool(lineups.get(gid,False))
        mu,sd,dmeta=_points_distribution(proj,lineup_ready)
        seed=_stable_seed(day,gid,pkey,line,sim_count)
        sim=_simulate_cached(_day(day),gid,pkey,float(line),float(mu),float(sd),int(sim_count),int(seed),BATCH_SIZE)
        key=(gid,pkey,float(line)); sim_map[key]=sim; meta_map[key]={**dmeta,"lineup_ready":lineup_ready,"proj":proj}
        if progress is not None:
            try: progress.progress((i+1)/max(total,1), text=f"Points simulated {i+1}/{total} unique player/line distributions")
            except Exception: pass
    rows=[]
    for _,m in pairs.iterrows():
        gid=str(m.get("game_id") or ""); pkey=str(m.get("player_key") or ""); line=_num(m.get("line"),np.nan)
        if pd.isna(line): continue
        key=(gid,pkey,float(line)); sim=sim_map.get(key); dm=meta_map.get(key)
        if sim is None or dm is None: continue
        proj=dm["proj"]
        nv_over,nv_under=market._no_vig(m.get("over_odds"),m.get("under_odds"))
        edge=sim["p_over"]-nv_over if pd.notna(nv_over) else np.nan
        profit=market._profit_per_dollar(m.get("over_odds"))
        ev100=(sim["p_over_raw"]*profit-sim["p_under_raw"])*100 if pd.notna(profit) else np.nan
        fresh,fscore=market._freshness(m.get("market_age"))
        context_q=float(np.clip(_num(proj.get("context_quality"),.5),0,1)); data_q=float(np.clip(dm.get("data_quality",.48),0,1))
        role_label=str(proj.get("ROLE_LABEL") or "ACTIVE"); lineup_ready=bool(dm.get("lineup_ready"))
        qualified=(pd.notna(nv_over) and pd.notna(edge) and sim["p_over"]>=.55 and edge>=.030 and _num(proj.get("PROJ_MIN"),0)>=10 and fresh!="STALE" and context_q>=.60 and role_label.upper()!="OUT" and sim["converged"])
        final_ready=bool(qualified and lineup_ready)
        status="AVOID" if fresh=="STALE" or role_label.upper()=="OUT" else ("FINAL READY" if final_ready else ("MONITOR LINEUP" if qualified else "NO EDGE"))
        rows.append({
            "market":"Points","player":str(proj.get("PLAYER_NAME") or m.get("player_name") or "Player"),"player_key":pkey,
            "team":str(proj.get("team_name") or ""),"opponent":str(proj.get("opponent") or ""),"game_id":gid,"book":str(m.get("book") or ""),
            "line":float(line),"raw_projection":_num(proj.get("RAW_PROJ_PTS"),np.nan),"projection":_num(proj.get("PROJ_PTS"),np.nan),
            "matchup_delta":_num(proj.get("PROJ_PTS"),0)-_num(proj.get("RAW_PROJ_PTS"),0),"sim_mean":sim["mean"],"sim_median":sim["median"],"sim_mode":sim["mode"],"p10":sim["p10"],"p90":sim["p90"],
            "model_over":sim["p_over"],"model_under":sim["p_under"],"push":sim["p_push"],"no_vig_over":nv_over,"no_vig_under":nv_under,"edge":edge,
            "over_odds":m.get("over_odds"),"under_odds":m.get("under_odds"),"fair_over":market._fair_american(sim["p_over"]),"ev100":ev100,
            "market_age":_num(m.get("market_age"),np.nan),"freshness":fresh,"fresh_score":fscore,"data_quality":data_q,"hist_games":dm.get("hist_games",0),
            "variance_source":dm.get("variance_source"),"proj_min":_num(proj.get("PROJ_MIN"),np.nan),"role_label":role_label,"context_quality":context_q,
            "lineup_ready":lineup_ready,"model_qualified":bool(qualified),"final_ready":final_ready,"status":status,
            "sims":sim["sims"],"batches":sim["batches"],"seed":sim["seed"],"mc_se":sim["mc_se"],"max_batch_diff":sim["max_batch_diff"],"converged":sim["converged"],
            "pass_source":"10M" if int(sim_count)>=FINAL_SIMS else "5M",
        })
    return pd.DataFrame(rows), {"snapshot":snap,"pairs":len(pairs),"unique_units":len(units),**pmeta}


def run_standard(day, progress=None):
    rows,meta=_market_rows(day,STANDARD_SIMS,progress)
    st.session_state[std_key(day)]={"rows":rows,"meta":meta,"ran_at":datetime.now(timezone.utc).isoformat()}
    return rows,meta


def _finalist_units(rows):
    if rows is None or rows.empty: return set()
    f=rows[(rows["model_qualified"].fillna(False)) | ((rows["model_over"]>=.53)&(rows["edge"].fillna(-1)>=.015))]
    return {(str(r.game_id),str(r.player_key),float(r.line)) for r in f.itertuples()}


def run_final(day, standard_rows, progress=None):
    units=_finalist_units(standard_rows)
    if not units:
        return pd.DataFrame(), {"reason":"no finalists/close calls"}
    rows,meta=_market_rows(day,FINAL_SIMS,progress,only_units=units)
    st.session_state[final_key(day)]={"rows":rows,"meta":meta,"ran_at":datetime.now(timezone.utc).isoformat()}
    return rows,meta


def combined_rows(day):
    std=st.session_state.get(std_key(day)) or {}; rows=std.get("rows")
    if not isinstance(rows,pd.DataFrame) or rows.empty: return pd.DataFrame()
    out=rows.copy(); fin=st.session_state.get(final_key(day)) or {}; fr=fin.get("rows")
    if isinstance(fr,pd.DataFrame) and not fr.empty:
        keys=["game_id","player_key","line","book"]
        fkeys=set(tuple(x) for x in fr[keys].astype(str).itertuples(index=False,name=None))
        keep=[tuple(x) not in fkeys for x in out[keys].astype(str).itertuples(index=False,name=None)]
        out=pd.concat([out.loc[keep],fr],ignore_index=True)
    return out


def _records(frame):
    if not isinstance(frame,pd.DataFrame) or frame.empty:return []
    return json.loads(frame.to_json(orient="records",date_format="iso"))


def _snapshot(day):
    std=st.session_state.get(std_key(day)) or {}; rows=std.get("rows")
    if not isinstance(rows,pd.DataFrame) or rows.empty:return None
    fin=st.session_state.get(final_key(day)) or {}; fr=fin.get("rows")
    return {"schema":1,"model_schema":MODEL_SCHEMA,"day":_day(day),"saved_at":datetime.now(timezone.utc).isoformat(),"standard_ran_at":std.get("ran_at"),"standard_rows":_records(rows),"final_ran_at":fin.get("ran_at"),"final_rows":_records(fr)}


def _valid(snap,day):
    if not isinstance(snap,dict) or snap.get("model_schema")!=MODEL_SCHEMA or snap.get("day")!=_day(day):return False
    rows=snap.get("standard_rows"); return isinstance(rows,list) and any(int(float(r.get("sims") or 0))>=STANDARD_SIMS for r in rows if isinstance(r,dict))


def _encode(snap):
    raw=json.dumps(snap,separators=(",",":"),ensure_ascii=False).encode(); return "z1:"+base64.urlsafe_b64encode(zlib.compress(raw,9)).decode()


def _decode(v):
    text=str(v or "").strip()
    if not text:return None
    try:
        return json.loads(zlib.decompress(base64.urlsafe_b64decode(text[3:].encode())).decode()) if text.startswith("z1:") else json.loads(text)
    except Exception:return None


def _write_disk(snap):
    try:
        CACHE_DIR.mkdir(parents=True,exist_ok=True); path=_disk_path(snap["day"]); tmp=path.with_suffix(path.suffix+".tmp")
        tmp.write_bytes(gzip.compress(json.dumps(snap,separators=(",",":"),ensure_ascii=False).encode(),9)); os.replace(tmp,path); return True
    except Exception:return False


def _read_disk(day):
    try:
        path=_disk_path(day); return json.loads(gzip.decompress(path.read_bytes()).decode()) if path.exists() else None
    except Exception:return None


def _regrade(day,rows):
    if not isinstance(rows,pd.DataFrame) or rows.empty:return rows
    pairs,_=_paired_points_markets(day)
    if pairs.empty:
        out=rows.copy(); out["freshness"]="STALE"; out["fresh_score"]=.25; out["model_qualified"]=False; out["final_ready"]=False; out["status"]="AVOID"; return out
    lookup={(str(p.get("game_id") or ""),str(p.get("player_key") or ""),round(float(p.get("line")),3),str(p.get("book") or "").lower()):p for _,p in pairs.iterrows()}
    updated=[]
    for _,r in rows.iterrows():
        o=r.to_dict(); key=(str(o.get("game_id") or ""),str(o.get("player_key") or ""),round(float(o.get("line")),3),str(o.get("book") or "").lower()); p=lookup.get(key)
        if p is None:
            o.update({"freshness":"STALE","fresh_score":.25,"model_qualified":False,"final_ready":False,"status":"AVOID"}); updated.append(o); continue
        nv,_=market._no_vig(p.get("over_odds"),p.get("under_odds")); fresh,fs=market._freshness(p.get("market_age")); mo=float(o.get("model_over") or 0); edge=mo-nv if pd.notna(nv) else np.nan
        profit=market._profit_per_dollar(p.get("over_odds")); push=float(o.get("push") or 0); raw_over=mo*max(0,1-push); raw_under=max(0,1-push-raw_over); ev=(raw_over*profit-raw_under)*100 if pd.notna(profit) else np.nan
        o.update({"over_odds":p.get("over_odds"),"under_odds":p.get("under_odds"),"no_vig_over":nv,"edge":edge,"ev100":ev,"market_age":p.get("market_age"),"freshness":fresh,"fresh_score":fs})
        q=(pd.notna(nv) and pd.notna(edge) and mo>=.55 and edge>=.030 and float(o.get("proj_min") or 0)>=10 and fresh!="STALE" and float(o.get("context_quality") or 0)>=.60 and str(o.get("role_label") or "ACTIVE").upper()!="OUT" and bool(o.get("converged")))
        o["model_qualified"]=bool(q); o["final_ready"]=bool(q and o.get("lineup_ready")); o["status"]="AVOID" if fresh=="STALE" else ("FINAL READY" if o["final_ready"] else ("MONITOR LINEUP" if q else "NO EDGE")); updated.append(o)
    return pd.DataFrame(updated)


def restore_if_missing(day):
    cur=st.session_state.get(std_key(day)) or {}; r=cur.get("rows")
    if isinstance(r,pd.DataFrame) and not r.empty:return False
    snap=_read_disk(day)
    if not _valid(snap,day) and _LOCAL is not None:
        try:snap=_decode(_LOCAL.getItem(_browser_key(day),key=_component_key(day)))
        except Exception:snap=None
    if not _valid(snap,day):return False
    sr=_regrade(day,pd.DataFrame(snap.get("standard_rows") or [])); st.session_state[std_key(day)]={"rows":sr,"meta":{"restored":True},"ran_at":snap.get("standard_ran_at")};
    fr=pd.DataFrame(snap.get("final_rows") or [])
    if not fr.empty:st.session_state[final_key(day)]={"rows":_regrade(day,fr),"meta":{"restored":True},"ran_at":snap.get("final_ran_at")}
    st.session_state[source_key(day)]="persistent snapshot"; return True


def persist_if_ready(day):
    snap=_snapshot(day)
    if not snap:return False
    sig=f"{snap.get('standard_ran_at')}::{len(snap.get('standard_rows') or [])}::{len(snap.get('final_rows') or [])}"; sk=f"wnba_points_v10_saved::{_day(day)}"
    if st.session_state.get(sk)==sig:return True
    _write_disk(snap)
    if _LOCAL is not None:
        try:_LOCAL.setItem(_browser_key(day),_encode(snap))
        except Exception:pass
    st.session_state[sk]=sig; st.session_state[source_key(day)]="current completed Points pass"; return True


def _fmt_pct(v):
    try:return f"{100*float(v):.1f}%"
    except Exception:return "—"


def render_points_connector(day):
    st.markdown("## 🏀 Points — WNBA Production Connector")
    st.caption("Points-only model • exact SportsGameOdds Points lines • empirical scoring variance • actual 5M standard / 10M finalists • sportsbook price never changes the projection.")
    if restore_if_missing(day):
        st.toast("💾 Restored completed WNBA Points snapshot — no 5M rerun required."); st.rerun()
    pairs,snap=_paired_points_markets(day); current=combined_rows(day)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Points players",0 if pairs.empty else pairs["player_key"].nunique())
    c2.metric("Exact pairs",len(pairs))
    c3.metric("5M distributions",0 if current.empty else current[["game_id","player_key","line"]].drop_duplicates().shape[0])
    c4.metric("Qualified overs",0 if current.empty else int(current["model_qualified"].fillna(False).sum()))
    if current.empty:
        if st.button("🚀 RUN POINTS 5,000,000 STANDARD SIMS",use_container_width=True,key=f"wnba_points_run_{_day(day)}"):
            prog=st.progress(0.0,text="Starting Points Monte Carlo…"); run_standard(day,prog); prog.empty(); persist_if_ready(day); st.rerun()
        st.info("Points connector is armed. Run the 5M pass once; completed summaries will persist across reloads/redeploys.")
        return
    persist_if_ready(day)
    src=st.session_state.get(source_key(day)) or "active session"; uniq=current[["game_id","player_key","line"]].drop_duplicates().shape[0]
    st.success(f"✅ Points production LIVE • {uniq} unique distributions • snapshot protected • source: {src}")
    display=current.sort_values(["model_qualified","model_over","edge"],ascending=[False,False,False]).copy()
    st.dataframe(pd.DataFrame({
        "Player":display["player"],"Book":display["book"],"Line":display["line"],"Adj PTS":display["projection"].round(2),"MC Mean":display["sim_mean"].round(2),"P(Over)":display["model_over"].map(_fmt_pct),"No-vig O":display["no_vig_over"].map(_fmt_pct),"Edge":display["edge"].map(lambda x:"—" if pd.isna(x) else f"{100*x:+.1f} pp"),"Status":display["status"]
    }),use_container_width=True,hide_index=True)
    units=_finalist_units(current)
    if units and not isinstance((st.session_state.get(final_key(day)) or {}).get("rows"),pd.DataFrame):
        if st.button("🎯 RUN POINTS 10,000,000 FINALIST PASS",use_container_width=True,key=f"wnba_points_final_{_day(day)}"):
            prog=st.progress(0.0,text="Starting Points finalist Monte Carlo…"); run_final(day,current,prog); prog.empty(); persist_if_ready(day); st.rerun()
    with st.expander("🧪 Points Monte Carlo diagnostics",expanded=False):
        diag=current.drop_duplicates(["game_id","player_key","line"])
        st.dataframe(pd.DataFrame({"Player":diag["player"],"Line":diag["line"],"Sims":diag["sims"],"Batches":diag["batches"],"Seed":diag["seed"],"MC SE":diag["mc_se"].map(lambda x:f"{100*x:.4f} pp"),"Max batch Δ":diag["max_batch_diff"].map(lambda x:f"{100*x:.3f} pp"),"Converged":diag["converged"].map(lambda x:"YES" if x else "NO"),"Hist GP":diag["hist_games"],"Variance":diag["variance_source"]}),use_container_width=True,hide_index=True)


__all__=["MODEL_VERSION","STANDARD_SIMS","FINAL_SIMS","std_key","final_key","combined_rows","restore_if_missing","persist_if_ready","render_points_connector"]
