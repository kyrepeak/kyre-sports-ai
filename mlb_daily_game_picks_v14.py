"""MLB Daily Game Picks V1.4 — Step 4A real 1+ Hit connector.

Uses the exact production 1+ Hit fast scanner once per slate, then splits its
verified outputs by MLB game ID. No hit probability is recomputed here.
"""
from __future__ import annotations
import streamlit as st
import mlb_daily_game_picks_v13 as base
import mlb_matchup_rankings_v21 as hitprod

VERSION="MLB Daily Game Picks V1.4 • STEP 4A"
_ACTIVE_GAMES=None
_orig_candidates=base._production_candidates

def _quality_from_hit_row(r):
    """Data-quality score derived only from production metadata already present.
    Reliability remains separate; sample coverage supplies the independent part.
    """
    try: rel=max(0.0,min(1.0,float(r.get("reliability") or 0)))
    except Exception: rel=0.0
    try: sample=max(0.0,float(r.get("sample") or 0))
    except Exception: sample=0.0
    sample_q=max(0.0,min(1.0,sample/400.0))
    return max(0.0,min(1.0,.35*rel+.65*sample_q))

def _hit_rows():
    global _ACTIVE_GAMES
    games=_ACTIVE_GAMES
    if games is None or games.empty:return []
    day=str(games.iloc[0].get("game_date") or "")[:10]
    key=f"dgp_prod_1hit_v14::{day}"
    cached=st.session_state.get(key)
    if cached is not None:return cached
    try:
        rows,diag=hitprod.fast_scan(games,"1+ Hit",20_000,True)
        payload={"rows":[dict(r) for r in (rows or [])],"diag":dict(diag or {})}
    except Exception as exc:
        payload={"rows":[],"diag":{"error":f"{type(exc).__name__}: {exc}"}}
    st.session_state[key]=payload
    return payload

def _production_candidates(row,market):
    if market!="1+ Hit":return _orig_candidates(row,market)
    gpk=str(base._gamepk(row)); pack=_hit_rows(); out=[]
    for r in pack.get("rows",[]):
        if str(r.get("game_pk") or "")!=gpk:continue
        try:p=float(r.get("p")); rel=float(r.get("reliability"))
        except Exception:continue
        dq=_quality_from_hit_row(r)
        norm=base.base.normalize_candidate(market="1+ Hit",probability=p,reliability=rel,data_quality=dq,confirmed=bool(r.get("confirmed")),uncertainty=None,stale=False)
        if norm.get("status")!="SCORED":continue
        out.append({"market":"1+ Hit","name":str(r.get("player") or "Hitter"),"side":"1+ Hit","line":0.5,"probability":p,"reliability":rel,"data_quality":dq,"score":norm["score"],"source":"1+ Hit V2.1 production fast scan","normalization":norm,"team":r.get("team"),"sample":r.get("sample"),"sample_unit":r.get("sample_unit")})
    out.sort(key=lambda x:x["score"],reverse=True)
    return out

# Patch only the bridge lookup. Existing Step 1-3 UI and all production engines remain unchanged.
base._production_candidates=_production_candidates

def render_daily_game_picks(games_df,section_header=None,status_info=None,team_logo=None,h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES=games_df
    st.caption("🔌 Step 4A: 1+ Hit is directly connected to the production V2.1 fast scanner; other markets remain on the generic bridge until individually verified.")
    return base.render_daily_game_picks(games_df,section_header,status_info,team_logo,h)
