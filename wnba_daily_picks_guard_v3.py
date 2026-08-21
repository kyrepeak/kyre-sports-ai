"""WNBA Daily Picks final guard V3 — add Spread to the frozen four-market guard.

PRA/Points/Rebounds/Assists are delegated unchanged to Guard V2. Spread is checked
against the exact same-session Step-7 final candidate proof, 5M convergence, quote
freshness, source-run freshness and scheduled tip. No network refresh or backfill.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
import re

import numpy as np
import pandas as pd

import wnba_daily_picks_guard_v2 as four_guard
import wnba_daily_picks_spread_connector_v1 as spread_feed

MODEL_VERSION = "WNBA DAILY PICKS GUARD V3 • FIVE MARKET FINAL GUARD"
GUARD_COLUMNS = list(four_guard.GUARD_COLUMNS)
STANDARD_SIMS = 5_000_000
MAX_OUTPUT_AGE_MIN = 15.0
_ET = ZoneInfo("America/New_York")


def _text(v: Any) -> str:
    if v is None: return ""
    try:
        if pd.isna(v): return ""
    except Exception: pass
    s=str(v).strip(); return "" if s.upper() in {"","—","NONE","NAN","NULL","N/A","NA"} else s


def _num(v: Any) -> float:
    try:
        x=float(v); return x if np.isfinite(x) else np.nan
    except Exception: return np.nan


def _day(v: Any) -> str:
    try: return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception: return ""


def _norm(v: Any) -> str:
    return re.sub(r"[^a-z0-9]","",_text(v).lower())


def _timestamp(v: Any):
    s=_text(v)
    if not s: return None
    try:
        ts=pd.to_datetime(s,errors="raise")
        if getattr(ts,"tzinfo",None) is None: ts=ts.tz_localize(_ET)
        else: ts=ts.tz_convert(_ET)
        return ts.to_pydatetime()
    except Exception: return None


def _tip(day_str: str, v: Any):
    s=_text(v).replace(" ET","").strip()
    if not s: return None
    try: return pd.Timestamp(f"{day_str} {s}").tz_localize(_ET).to_pydatetime()
    except Exception: return None


def _proof_key(team,opp,line,book):
    x=_num(line)
    return (_norm(team),_norm(opp),round(x,6) if np.isfinite(x) else None,_norm(book))


def _spread_guard(rows: pd.DataFrame, slate_day: Any, now_et=None) -> pd.DataFrame:
    target=_day(slate_day)
    if rows is None or rows.empty:
        cols=list(rows.columns) if isinstance(rows,pd.DataFrame) else []
        return pd.DataFrame(columns=cols+[c for c in GUARD_COLUMNS if c not in cols])
    status=spread_feed.status(target)
    proof=spread_feed.final_guard_proof(target)
    pmap={}
    if isinstance(proof,pd.DataFrame) and not proof.empty:
        for _,p in proof.iterrows(): pmap[_proof_key(p.get("Team"),p.get("Opponent"),p.get("Line"),p.get("Book"))]=p
    now=now_et or datetime.now(_ET)
    if now.tzinfo is None: now=now.replace(tzinfo=_ET)
    else: now=now.astimezone(_ET)
    records=[]
    for _,row in rows.copy().iterrows():
        blocked=[]; monitor=[]; gates={}
        if _text(row.get("Selection state")).upper()!="SELECTED" or _text(row.get("Rank state")).upper()!="RANKED":
            blocked.append("row is not a selected ranked candidate")
        if _text(row.get("Safety state")).upper()!="SAFE": blocked.append("Spread safety is not SAFE")
        if _day(row.get("Slate day"))!=target:
            blocked.append("slate date mismatch"); gates["Slate recheck"]="BLOCKED"
        else: gates["Slate recheck"]="PASS"
        if status.get("connected"):
            gates["Connector gate"]="PASS"
        else:
            blocked.append("Spread source connector is not connected"); gates["Connector gate"]="BLOCKED"
        p=pmap.get(_proof_key(row.get("Team"),row.get("Opponent"),row.get("Line"),row.get("Book")))
        exact_ok=bool(p is not None and _text(p.get("Grade proof")).upper()=="QUALIFIED")
        if exact_ok: gates["Exact quote gate"]="PASS"
        else:
            blocked.append("exact QUALIFIED Spread Step-7 proof missing"); gates["Exact quote gate"]="BLOCKED"
        sims=_num(row.get("Simulation count")); proof_sims=_num(p.get("Simulation count proof")) if p is not None else np.nan
        if np.isfinite(sims) and sims>=STANDARD_SIMS and np.isfinite(proof_sims) and proof_sims>=STANDARD_SIMS:
            gates["Simulation recheck"]="PASS"
        else:
            blocked.append("5M Spread simulation proof missing"); gates["Simulation recheck"]="BLOCKED"
        conv=bool(row.get("Converged")) and bool(p.get("Converged proof")) if p is not None else False
        if conv: gates["Convergence recheck"]="PASS"
        else:
            blocked.append("Spread convergence proof missing"); gates["Convergence recheck"]="BLOCKED"
        run_ts=_timestamp(p.get("Run timestamp proof")) if p is not None else _timestamp(status.get("ran_at"))
        if run_ts is None:
            monitor.append("Spread availability snapshot time unavailable"); gates["Availability recheck"]="MONITOR"
        else:
            run_age=max(0.0,(now-run_ts).total_seconds()/60.0)
            if run_age>MAX_OUTPUT_AGE_MIN:
                monitor.append(f"Spread availability snapshot is {run_age:.0f}m old"); gates["Availability recheck"]="MONITOR"
            else: gates["Availability recheck"]="PASS"
        tip=_tip(target,p.get("Tip ET proof")) if p is not None else None
        if tip is None:
            monitor.append("tip-time proof unavailable"); gates["Game-state recheck"]="MONITOR"
        elif tip<=now:
            blocked.append("game has reached/passed scheduled tip"); gates["Game-state recheck"]="BLOCKED"
        else: gates["Game-state recheck"]="PASS"
        quote_ts=_timestamp(p.get("Quote timestamp proof")) if p is not None else None
        if quote_ts is None:
            monitor.append("exact Spread quote timestamp unavailable"); gates["Freshness recheck"]="MONITOR"
        else:
            qage=max(0.0,(now-quote_ts).total_seconds()/60.0)
            if qage>MAX_OUTPUT_AGE_MIN:
                blocked.append(f"Spread quote stale at guard time ({qage:.0f}m)"); gates["Freshness recheck"]="BLOCKED"
            else: gates["Freshness recheck"]="PASS"
        if exact_ok and _text(row.get("Qualification state")).upper()=="PRODUCTION READY": gates["Finalization gate"]="PASS"
        else:
            blocked.append("Spread source is not production-ready"); gates["Finalization gate"]="BLOCKED"
        state="BLOCKED" if blocked else ("MONITOR" if monitor else "READY")
        reasons=blocked if blocked else monitor
        rec=row.to_dict(); rec.update({
            "Guard state":state,
            "Guard reasons":" • ".join(dict.fromkeys(reasons)) if reasons else "ALL FINAL GUARDS PASSED",
            "Guard checked at ET":now.strftime("%Y-%m-%d %I:%M:%S %p ET"),
            "Guard fingerprint":four_guard.v1._row_fingerprint(row),
            **{c:gates.get(c,"—") for c in GUARD_COLUMNS if c not in {"Guard state","Guard reasons","Guard checked at ET","Guard fingerprint"}},
        }); records.append(rec)
    return pd.DataFrame(records)


def evaluate_five_market(selected: pd.DataFrame, slate_day: Any, *, feeds=None, now_et=None) -> pd.DataFrame:
    if selected is None or selected.empty:
        cols=list(selected.columns) if isinstance(selected,pd.DataFrame) else []
        return pd.DataFrame(columns=cols+[c for c in GUARD_COLUMNS if c not in cols])
    work=selected.copy().reset_index(drop=True); work["__order"]=range(len(work))
    market=work.get("Market",pd.Series("",index=work.index)).astype(str).str.upper()
    outputs=[]
    base_rows=work.loc[~market.eq("SPREAD")].copy()
    if not base_rows.empty:
        g=four_guard.evaluate_four_market(base_rows,slate_day,feeds=feeds or {},now_et=now_et)
        if isinstance(g,pd.DataFrame) and not g.empty: outputs.append(g)
    spread_rows=work.loc[market.eq("SPREAD")].copy()
    if not spread_rows.empty:
        g=_spread_guard(spread_rows,slate_day,now_et=now_et)
        if not g.empty: outputs.append(g)
    if not outputs: return pd.DataFrame()
    out=pd.concat(outputs,ignore_index=True,sort=False)
    if "__order" in out.columns: out=out.sort_values("__order",kind="mergesort").drop(columns="__order",errors="ignore")
    return out.reset_index(drop=True)


def ready_rows(guarded: pd.DataFrame) -> pd.DataFrame:
    return four_guard.ready_rows(guarded)


def diagnostics(guarded: pd.DataFrame, selected: pd.DataFrame|None=None) -> dict:
    if guarded is None or guarded.empty:
        return {"selected_input":0 if selected is None else len(selected),"guarded_rows":0,"coverage_pass":False,"ready":0,"monitor":0,"blocked":0,"spread_selected":0,"spread_ready":0}
    states=guarded.get("Guard state",pd.Series(dtype=str)).astype(str).str.upper()
    market=guarded.get("Market",pd.Series(dtype=str)).astype(str).str.upper()
    selected_n=0 if selected is None or not isinstance(selected,pd.DataFrame) else len(selected)
    return {"selected_input":selected_n,"guarded_rows":len(guarded),"coverage_pass":len(guarded)==selected_n,
            "ready":int(states.eq("READY").sum()),"monitor":int(states.eq("MONITOR").sum()),"blocked":int(states.eq("BLOCKED").sum()),
            "spread_selected":int(market.eq("SPREAD").sum()),"spread_ready":int((market.eq("SPREAD")&states.eq("READY")).sum()),
            "spread_monitor":int((market.eq("SPREAD")&states.eq("MONITOR")).sum()),"spread_blocked":int((market.eq("SPREAD")&states.eq("BLOCKED")).sum()),
            "simulations":0,"network_requests":0,"source_model_writes":0,"backfills":0}


__all__=["MODEL_VERSION","GUARD_COLUMNS","evaluate_five_market","ready_rows","diagnostics"]
