"""MLB Daily Rankings V2.0 — strict-budget Top-5 deep micro-pass.

Replaces V1.9's duplicate legacy deep workflow. Deep calibration now warms only
current Top-5 batter/starter Statcast profiles concurrently, then applies the
Step 2-5 player-intelligence matchup calibration directly from the shared cache.
The old V1.6 Statcast adjustment pass is intentionally skipped to avoid duplicate
network work and double-counting matchup evidence.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
import streamlit as st

import mlb_matchup_rankings_v18 as v18

VERSION = "MLB Daily Rankings V2.0"


def _top5_jobs(games_df, rows):
    gm=v18.base._starter_map(games_df)
    season=int(str(games_df.iloc[0].get("game_date"))[:4]) if games_df is not None and not games_df.empty else 2026
    jobs=[];seen=set()
    for r in list(rows or [])[:5]:
        pid=r.get("player_id") or r.get("id")
        spid=v18._starter_for_row(gm,r)
        for player_id,kind in ((pid,"batter"),(spid,"pitcher")):
            try:key=(int(player_id),season,kind)
            except Exception:continue
            if not key[0] or key in seen:continue
            seen.add(key);jobs.append(key)
    return jobs


def _warm(job):
    pid,season,kind=job
    try:
        res=v18.fastfeeds._statcast_rows(pid,season,kind)
        return str((res or {}).get("status") or "PENDING")
    except Exception:
        return "PENDING"


def _warm_top5(games_df,rows):
    jobs=_top5_jobs(games_df,rows)
    if not jobs:return {"profiles_requested":0,"profiles_verified":0,"profiles_pending":0}
    pool=ThreadPoolExecutor(max_workers=min(5,len(jobs)),thread_name_prefix="mx-top5-statcast")
    futures=[pool.submit(_warm,j) for j in jobs]
    done,not_done=wait(futures,timeout=11)
    verified=pending=0
    for f in done:
        try:
            if f.result()=="VERIFIED":verified+=1
            else:pending+=1
        except Exception:pending+=1
    pending+=len(not_done)
    for f in not_done:f.cancel()
    pool.shutdown(wait=False,cancel_futures=True)
    return {"profiles_requested":len(jobs),"profiles_verified":verified,"profiles_pending":pending}


def deep_calibrate(games_df,rows,market):
    """Single-pass deep calibration with a strict network budget.

    No call to V1.6/base.deep_calibrate: that legacy path performed a second
    Statcast model pass after warming and was the main source of long waits.
    """
    v18._install_fast_feed()
    warm=_warm_top5(games_df,rows)
    # _apply_matchup reuses verified/pending shared cache entries. Failed
    # profiles are briefly failure-cached and therefore contribute zero deep
    # pitch edge instead of triggering another long request.
    deep_rows=v18._apply_matchup(games_df,[dict(r) for r in (rows or [])],market,deep=True)
    diag={
        "stage":"DEEP",
        "matchup_stage":"DEEP",
        "ranking_version":"V2.0",
        "deep_execution":"TOP5_MICRO_PASS",
        "statcast_contenders":min(5,len(rows or [])),
        "starter_profiles":0,
        **warm,
    }
    return deep_rows,diag


# Reuse V1.8 UI/audit while replacing only the expensive deep execution path.
v18.deep_calibrate=deep_calibrate
render_daily_rankings=v18.render_daily_rankings
fast_scan=v18.fast_scan
