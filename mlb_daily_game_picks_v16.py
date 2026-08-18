"""MLB Daily Game Picks V1.6 — Step 4B non-blocking Home Run connector.

Preserves the V1.5 cached 1+ Hit connector and connects the existing calibrated
HR V1.1 production model without changing its probability math. HR is built only
when explicitly requested, then cached by slate date.
"""
from __future__ import annotations
import streamlit as st
import mlb_daily_game_picks_v15 as base
import mlb_hr_hub_v11 as hrprod
import mlb_hr_hub_v10 as hrcore

VERSION="MLB Daily Game Picks V1.6 • STEP 4B HR CONNECTOR"
_ACTIVE_GAMES=None
_orig_candidates=base.base._production_candidates


def _day(games):
    if games is None or games.empty:return ""
    return str(games.iloc[0].get("game_date") or "")[:10]


def _hr_key(games):return f"dgp_prod_hr_v16::{_day(games)}"


def _quality(r):
    # Uses only quality evidence already produced by HR V1.1; nothing is invented.
    try: score=float(r.get("data_score") or 0)
    except Exception: score=0.0
    return max(0.0,min(1.0,score/7.0))


def _reliability(r):
    # Independent production evidence: season sample + Statcast reliability.
    try: season=float(r.get("season_reliability") or 0)
    except Exception: season=0.0
    try: sc=float(r.get("statcast_reliability") or 0)
    except Exception: sc=0.0
    return max(0.0,min(1.0,.70*season+.30*sc))


def _hr_candidates(row):
    games=_ACTIVE_GAMES
    if games is None or games.empty:return []
    pack=st.session_state.get(_hr_key(games),{})
    gpk=str(base.base._gamepk(row)); out=[]
    for r in pack.get("rows",[]):
        if str(r.get("game_pk") or "")!=gpk:continue
        try:p=float(r.get("p_hr"))
        except Exception:continue
        rel=_reliability(r); dq=_quality(r)
        norm=base.base.base.normalize_candidate(
            market="Home Run",probability=p,reliability=rel,data_quality=dq,
            confirmed=bool(r.get("lineup_confirmed")),uncertainty=None,stale=False)
        if norm.get("status")!="SCORED":continue
        out.append({
            "market":"Home Run","name":str(r.get("player_name") or "Hitter"),
            "side":"1+ HR","line":0.5,"probability":p,"reliability":rel,
            "data_quality":dq,"score":norm["score"],"source":"HR V1.1 calibrated production model",
            "normalization":norm,"team":r.get("team"),"season_pa":r.get("season_pa"),
            "confidence":r.get("confidence"),"expected_hr":r.get("expected_hr")})
    return sorted(out,key=lambda x:x["score"],reverse=True)


def _production_candidates(row,market):
    if market=="Home Run":return _hr_candidates(row)
    return _orig_candidates(row,market)

# Patch only Step 4 candidate lookup; V1.5's 1+ Hit connector remains intact.
base.base._production_candidates=_production_candidates


def _build_hr(games):
    candidates,meta=hrcore._candidate_pool(games,False)
    rows=hrprod._bulk_prescreen(candidates) if candidates else []
    return {"rows":[dict(r) for r in (rows or [])],"meta":dict(meta or {})}


def render_daily_game_picks(games_df,section_header=None,status_info=None,team_logo=None,h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES=games_df
    # Keep every inherited active-game pointer synchronized.
    base._ACTIVE_GAMES=games_df
    base.base._ACTIVE_GAMES=games_df
    day=_day(games_df); key=_hr_key(games_df); pack=st.session_state.get(key)

    c1,c2=st.columns([4,1])
    with c1:
        if pack and pack.get("rows"):
            st.success(f"💣 Home Run production connector ready • {len(pack['rows'])} calibrated hitter outputs cached • {day}")
        else:
            st.info("💣 Home Run connector is ready to build. HR V1.1 will run only when requested.")
    with c2:
        label="↻ REFRESH HOME RUN" if pack and pack.get("rows") else "💣 CONNECT HOME RUN"
        if st.button(label,use_container_width=True,key=f"dgp_hr_connect_v16::{day}"):
            with st.spinner("Building calibrated HR V1.1 production outputs once for the slate..."):
                try:st.session_state[key]=_build_hr(games_df)
                except Exception as exc:st.session_state[key]={"rows":[],"meta":{"error":f"{type(exc).__name__}: {exc}"}}
            st.rerun()

    st.caption("🔌 Step 4B: Home Run now connects directly to calibrated HR V1.1. Production HR math is unchanged; results are cached and do not auto-run on rerender.")
    return base.render_daily_game_picks(games_df,section_header,status_info,team_logo,h)
