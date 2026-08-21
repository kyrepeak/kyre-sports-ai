"""WNBA Daily Picks ranking V3 — five-market read-only ranking.

Preserves the existing four-market safety/ranking formulas and adds SPREAD as a
fifth market. Spread uses the same probability/edge/EV/freshness/quality weights;
its projection component is the independent team-margin cushion versus the exact
spread. No source model is rerun or altered.
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

import wnba_daily_picks_ranking_v2 as four
import wnba_daily_picks_standardizer_v3 as standardizer
import wnba_daily_picks_safety_v3 as spread_safety
import wnba_daily_picks_spread_connector_v1 as spread_feed
import wnba_daily_picks_protection_v1 as protection
import wnba_daily_picks_ranking_v1 as ranking

MODEL_VERSION = "WNBA DAILY PICKS RANKING V3 • FIVE MARKET + SPREAD"


def _day(v: Any) -> str:
    try: return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception: return ""


def _score_spread(row: pd.Series) -> dict:
    p = ranking._prob(row.get("Model probability"))
    nv = ranking._prob(row.get("No-vig probability"))
    edge = ranking._edge(row.get("Edge"))
    if not np.isfinite(edge) and np.isfinite(p) and np.isfinite(nv): edge = p - nv
    if not np.isfinite(nv) and np.isfinite(p) and np.isfinite(edge): nv = p - edge
    ev100 = ranking._num(row.get("EV / $100"))
    ev_source = "SOURCE"
    if not np.isfinite(ev100) and np.isfinite(p):
        ev100 = ranking._american_ev100(p, row.get("Posted odds")); ev_source = "DERIVED: model p + posted odds"
    proj = ranking._num(row.get("Projection")); line = ranking._num(row.get("Line"))
    cushion = proj + line if np.isfinite(proj) and np.isfinite(line) else np.nan
    rankable = bool(
        ranking._text(row.get("Safety state")).upper() == "SAFE"
        and np.isfinite(p) and np.isfinite(nv) and np.isfinite(edge) and np.isfinite(ev100)
        and np.isfinite(cushion) and np.isfinite(line)
    )
    if not rankable:
        return {"Rank state":"SCORE HOLD","Ranking score":np.nan,"Raw score":np.nan,"Exposure penalty":np.nan,
                "Probability score":np.nan,"Edge score":np.nan,"EV score":np.nan,"Projection score":np.nan,
                "Freshness score":np.nan,"Quality score":np.nan,"EV / $100 ranked":ev100,"No-vig ranked":nv,
                "Edge ranked":edge,"Projection edge":cushion,"EV source":ev_source}
    probability_score = float(np.clip((p-0.50)/0.25,0,1)*40)
    edge_score = float(np.clip(edge/0.15,0,1)*25)
    ev_score = float(np.clip(ev100/25.0,0,1)*15)
    proj_ratio = max(cushion,0.0) / max(abs(line),3.0)
    projection_score = float(np.clip(proj_ratio/0.15,0,1)*10)
    fresh = ranking._fresh_minutes(row.get("Freshness"))
    freshness_score = 2.0 if fresh is None else (5.0 if fresh<=5 else (3.5 if fresh<=10 else (1.5 if fresh<=15 else 0.0)))
    quality_score = ranking._quality_points(row.get("Confidence"), row.get("Qualification state"))
    raw = probability_score+edge_score+ev_score+projection_score+freshness_score+quality_score
    alt = max(int(ranking._num(row.get("Alternate lines")) if np.isfinite(ranking._num(row.get("Alternate lines"))) else 0)-1,0)
    player_markets = max(int(ranking._num(row.get("Player markets")) if np.isfinite(ranking._num(row.get("Player markets"))) else 0)-1,0)
    game_groups = max(int(ranking._num(row.get("Game candidate groups")) if np.isfinite(ranking._num(row.get("Game candidate groups"))) else 0)-1,0)
    team_groups = max(int(ranking._num(row.get("Team candidate groups")) if np.isfinite(ranking._num(row.get("Team candidate groups"))) else 0)-1,0)
    penalty = float(min(8.0,1.5*alt+3.0*player_markets+0.75*game_groups+0.35*team_groups))
    return {"Rank state":"RANKED","Ranking score":max(raw-penalty,0.0),"Raw score":raw,"Exposure penalty":penalty,
            "Probability score":probability_score,"Edge score":edge_score,"EV score":ev_score,"Projection score":projection_score,
            "Freshness score":freshness_score,"Quality score":quality_score,"EV / $100 ranked":ev100,"No-vig ranked":nv,
            "Edge ranked":edge,"Projection edge":cushion,"EV source":ev_source}


def _rank_spread(protected: pd.DataFrame) -> pd.DataFrame:
    if protected is None or protected.empty: return pd.DataFrame()
    d = protected.loc[protected.get("Market", pd.Series("",index=protected.index)).astype(str).str.upper().eq("SPREAD")].copy()
    if d.empty: return d
    picked=[]
    for _, group in d.loc[d["Safety state"].astype(str).str.upper().eq("SAFE")].groupby("Candidate key",dropna=False,sort=False):
        scored=[]
        for _, row in group.iterrows(): scored.append((row.copy(),_score_spread(row)))
        if not scored: continue
        def key(item):
            row, s=item; ev=ranking._num(s.get("EV / $100 ranked")); odds=ranking._num(row.get("Posted odds"))
            return (ev if np.isfinite(ev) else -1e9, odds if np.isfinite(odds) else -1e9)
        row, score=max(scored,key=key)
        for k,v in score.items(): row[k]=v
        row["Quote selection"] = f"BEST OF {len(group)}" if len(group)>1 else "ONLY QUOTE"
        picked.append(row)
    return pd.DataFrame(picked)


def build_five_market_ranking(day: Any) -> dict:
    day_str=_day(day)
    base_bundle=four.build_four_market_ranking(day_str)
    base_audit=base_bundle.get("audit") if isinstance(base_bundle,dict) else pd.DataFrame()
    if not isinstance(base_audit,pd.DataFrame): base_audit=pd.DataFrame()
    spread_rows=standardizer.normalize_spread(day_str)
    spread_audit=spread_safety.evaluate_spread(spread_rows,day_str)
    audits=[f for f in (base_audit,spread_audit) if isinstance(f,pd.DataFrame) and not f.empty]
    audit=pd.concat(audits,ignore_index=True,sort=False) if audits else pd.DataFrame()
    protected=protection.annotate(audit)
    market=protected.get("Market",pd.Series("",index=protected.index)).astype(str).str.upper() if not protected.empty else pd.Series(dtype=str)
    base_ranked=ranking.rank_candidates(protected.loc[~market.eq("SPREAD")].copy()) if not protected.empty else pd.DataFrame()
    spread_ranked=_rank_spread(protected)
    pieces=[f for f in (base_ranked,spread_ranked) if isinstance(f,pd.DataFrame) and not f.empty]
    ranked=pd.concat(pieces,ignore_index=True,sort=False) if pieces else pd.DataFrame()
    if not ranked.empty:
        mask=ranked["Rank state"].astype(str).str.upper().eq("RANKED")
        good=ranked.loc[mask].copy().sort_values(["Ranking score","Model probability","Edge ranked","EV / $100 ranked"],ascending=[False,False,False,False],na_position="last",kind="mergesort")
        good["Rank"]=np.arange(1,len(good)+1)
        holds=ranked.loc[~mask].copy(); holds["Rank"]=np.nan
        ranked=pd.concat([good,holds],ignore_index=True,sort=False)
    feeds=dict(base_bundle.get("feeds",{}) if isinstance(base_bundle,dict) else {})
    feeds["SPREAD"]=spread_feed.status(day_str)
    return {"day":day_str,"feeds":feeds,"common":standardizer.normalize_all(day_str),"audit":audit,"protected":protected,"ranked":ranked}


def diagnostics(bundle: dict) -> dict:
    ranked=bundle.get("ranked") if isinstance(bundle,dict) else pd.DataFrame()
    common=bundle.get("common") if isinstance(bundle,dict) else pd.DataFrame()
    spread_status=(bundle.get("feeds",{}) or {}).get("SPREAD",{}) if isinstance(bundle,dict) else {}
    spread_input=int(common.get("Market",pd.Series(dtype=str)).astype(str).str.upper().eq("SPREAD").sum()) if isinstance(common,pd.DataFrame) and not common.empty else 0
    spread_rank_rows=int(ranked.get("Market",pd.Series(dtype=str)).astype(str).str.upper().eq("SPREAD").sum()) if isinstance(ranked,pd.DataFrame) and not ranked.empty else 0
    return {"spread_connected":bool(spread_status.get("connected")),"spread_input":spread_input,"spread_rank_rows":spread_rank_rows,
            "spread_coverage":bool(spread_status.get("connected") and spread_input==spread_rank_rows),"ranked":int((ranked.get("Rank state",pd.Series(dtype=str)).astype(str).str.upper()=="RANKED").sum()) if isinstance(ranked,pd.DataFrame) else 0,
            "simulations":0,"network_requests":0,"writes":0}


__all__=["MODEL_VERSION","build_five_market_ranking","diagnostics"]
