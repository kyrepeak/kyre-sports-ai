"""MLB Daily Rankings V1.9 — bounded parallel deep calibration.

Wraps V1.8 Player Intelligence rankings. The Top-8 deep pass now warms all
required batter/starter Statcast profiles concurrently before running the normal
V1.8/V1.6 calibration. Individual Savant calls retain the short timeout and
failure backoff from V1.7. Slow/unavailable profiles therefore contribute no
synthetic deep edge while the rest of the board can complete.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import streamlit as st

import mlb_matchup_rankings_v18 as v18

VERSION = "MLB Daily Rankings V1.9"


def _deep_contenders(games_df, rows):
    rows = [dict(r) for r in (rows or [])]
    if not rows:
        return []
    fifth = float(rows[min(4, len(rows)-1)].get("p") or 0)
    out=[]
    for idx,r in enumerate(rows):
        p=float(r.get("p") or 0)
        if idx < 7 or p >= fifth - .012:
            out.append(r)
        if len(out) >= 8:
            break
    return out


def _profile_jobs(games_df, rows):
    gm=v18.base._starter_map(games_df)
    season=int(str(games_df.iloc[0].get("game_date"))[:4]) if games_df is not None and not games_df.empty else 2026
    jobs=[]; seen=set()
    for r in _deep_contenders(games_df, rows):
        pid=r.get("player_id") or r.get("id")
        spid=v18._starter_for_row(gm,r)
        for player_id,kind in ((pid,"batter"),(spid,"pitcher")):
            try: key=(int(player_id),season,kind)
            except Exception: continue
            if key in seen or not key[0]: continue
            seen.add(key); jobs.append(key)
    return jobs,season


def _warm_one(job):
    pid,season,kind=job
    try:
        res=v18.fastfeeds._statcast_rows(pid,season,kind)
        return job, str((res or {}).get("status") or "PENDING")
    except Exception:
        return job,"PENDING"


def _parallel_warm(games_df, rows):
    jobs,_=_profile_jobs(games_df,rows)
    if not jobs:
        return {"profiles_requested":0,"profiles_verified":0,"profiles_pending":0}
    verified=pending=0
    # Savant read ceiling is already ~10s/profile. Parallel warming prevents
    # eight sequential waits; six workers keeps pressure bounded.
    pool=ThreadPoolExecutor(max_workers=min(6,len(jobs)),thread_name_prefix="mx-statcast")
    futures=[pool.submit(_warm_one,j) for j in jobs]
    try:
        for f in as_completed(futures, timeout=14):
            try:
                _,status=f.result()
                if status=="VERIFIED": verified+=1
                else: pending+=1
            except Exception:
                pending+=1
    except Exception:
        # Any unfinished work is allowed to finish in the background request
        # thread, but ranking proceeds using only profiles already cached.
        pass
    finally:
        unfinished=sum(1 for f in futures if not f.done())
        pending+=unfinished
        for f in futures:
            if not f.done(): f.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
    return {"profiles_requested":len(jobs),"profiles_verified":verified,"profiles_pending":pending}


def deep_calibrate(games_df, rows, market):
    v18._install_fast_feed()
    warm=_parallel_warm(games_df,rows)
    # Existing V1.6 deep logic and V1.8 Step 2-5 calibration remain the source
    # of truth. Because profiles were warmed concurrently, these calls should
    # hit cache; missing profiles stay PENDING and yield no fabricated edge.
    deep_rows,diag=v18.base.deep_calibrate(games_df,rows,market)
    deep_rows=v18._apply_matchup(games_df,deep_rows,market,deep=True)
    diag=dict(diag or {})
    diag.update(warm)
    diag.update({"matchup_stage":"DEEP","ranking_version":"V1.9","deep_execution":"PARALLEL_BOUNDED"})
    return deep_rows,diag


# V1.8's renderer resolves its module-global deep_calibrate at runtime, so
# installing this function preserves the UI while upgrading execution.
v18.deep_calibrate=deep_calibrate
render_daily_rankings=v18.render_daily_rankings
fast_scan=v18.fast_scan
