"""MLB Daily Rankings V1.6 — fast-first two-stage Statcast workflow.

Stage 1 builds the full-slate core ranking immediately from the verified
starter/lineup/environment/bullpen stack. Stage 2 is optional and only deep-
enriches the top bubble candidates with Baseball Savant Statcast/platoon/pitch
mix. Frozen market engines and all calibration caps remain unchanged.
"""
from __future__ import annotations

import streamlit as st

import mlb_matchup_rankings_v14 as scbase
import mlb_matchup_rankings_v15 as feeds
import mlb_matchup_rankings_v13 as core

VERSION = "MLB Daily Rankings V1.6"


def _install():
    feeds._install_hotfixes()
    # Make sure V1.4 helpers use repaired feed functions.
    scbase._savant_params = feeds._savant_params
    scbase._statcast_rows = feeds._statcast_rows


def fast_scan(games_df, market, sims=20_000, include_live=False):
    """Core ranking only: no Savant requests."""
    _install()
    rows, diag = core.scan_market(games_df, market, sims, include_live)
    rows = list(rows or [])
    for r in rows:
        r.setdefault("statcast_status", "FAST STAGE — NOT RUN")
        r.setdefault("pitch_mix_status", "FAST STAGE — NOT RUN")
        r.setdefault("platoon_status", "FAST STAGE — NOT RUN")
        r.setdefault("applied_statcast_adj", 0.0)
    diag = dict(diag or {})
    diag.update({"stage":"FAST","statcast_contenders":0,"ranking_version":"V1.6"})
    return rows, diag


def _starter_map(games_df):
    return scbase._starter_ids(games_df)


def deep_calibrate(games_df, rows, market):
    """Deep-enrich only candidates that can realistically affect Top 5.

    Minimum 7, maximum 8 candidates. The threshold is deliberately tighter than
    V1.4 because the Statcast layer itself is hard capped at +/-1.8 percentage
    points before reliability damping.
    """
    _install()
    rows = [dict(r) for r in (rows or [])]
    if not rows:
        return rows, {"stage":"DEEP","statcast_contenders":0}
    year = int(str(games_df.iloc[0].get("game_date"))[:4]) if games_df is not None and not games_df.empty else 2026
    gm = _starter_map(games_df)
    fifth = float(rows[min(4, len(rows)-1)].get("p") or 0)
    contenders=[]
    for idx,r in enumerate(rows):
        p=float(r.get("p") or 0)
        if idx < 7 or p >= fifth - .012:
            contenders.append(r)
        if len(contenders) >= 8:
            break

    # Warm each unique opposing starter once. Batter downloads remain one/player
    # and are cached by player/year across all ranking markets.
    starter_ids=[]
    for r in contenders:
        try:
            g=gm.get(int(r.get("game_pk") or 0),{})
            is_away=str(r.get("team") or "")==g.get("away_team")
            spid=g.get("home_pitcher_id") if is_away else g.get("away_pitcher_id")
            if spid and spid not in starter_ids: starter_ids.append(spid)
        except Exception:
            pass
    for spid in starter_ids:
        try: feeds._statcast_rows(spid, year, "pitcher")
        except Exception: pass

    enriched=set()
    for r in contenders:
        try:
            g=gm.get(int(r.get("game_pk") or 0),{})
            is_away=str(r.get("team") or "")==g.get("away_team")
            spid=g.get("home_pitcher_id") if is_away else g.get("away_pitcher_id")
            r["_statcast_starter_id"]=spid
            adj, sc = scbase._statcast_adjust(r, year, market)
            rel=float(r.get("reliability") or 0)
            applied=adj*(0.68+0.32*rel)
            r["pre_statcast_p"]=float(r.get("p") or 0)
            r["p"]=max(.001,min(.999,r["pre_statcast_p"]+applied))
            r.update(sc)
            r["applied_statcast_adj"]=applied
            enriched.add(id(r))
        except Exception as exc:
            r.update({"statcast_status":"PENDING","statcast_error":f"{type(exc).__name__}: {exc}"[:180],
                      "pitch_mix_status":"PENDING","platoon_status":"PENDING","applied_statcast_adj":0.0})
    for r in rows:
        if id(r) not in enriched:
            r.update({"statcast_status":"OUTSIDE DEEP TOP-8 GATE","pitch_mix_status":"NOT SCANNED",
                      "platoon_status":"NOT SCANNED","applied_statcast_adj":0.0})
    rows.sort(key=lambda x:(float(x.get("p") or 0),float(x.get("reliability") or 0),1 if x.get("confirmed") else 0),reverse=True)
    return rows,{"stage":"DEEP","statcast_contenders":len(contenders),"starter_profiles":len(starter_ids)}


def render_daily_rankings(games_df):
    _install()
    core.base.base.base._css()
    st.markdown('<div class="rk-wrap"><div class="rk-head"><div><div class="rk-title">🏆 Daily Slate Rankings — Fast + Deep</div><div class="rk-sub">Instant core board first; optional Statcast deep calibration only for Top-8 contenders</div></div><div class="rk-sub">V1.6</div></div></div>',unsafe_allow_html=True)
    if games_df is None or games_df.empty:
        st.info("No verified MLB slate is available for rankings."); return
    market=st.selectbox("RANKING MARKET",core.base.base.base.MARKETS,key="mx_rank_market_v16")
    c1,c2=st.columns([2,1])
    with c1:
        depth=st.selectbox("SCAN DEPTH",[20_000,50_000,100_000],index=1,format_func=lambda n:f"{n//1000}K simulations / hitter",key="mx_rank_depth_v16")
    with c2:
        include_live=st.checkbox("Include live games",value=False,key="mx_rank_live_v16")
    day=str(games_df.iloc[0].get("game_date"))[:10]
    fast_key=f"mx_rank_fast_v16::{day}::{market}::{depth}::{int(include_live)}"
    deep_key=f"mx_rank_deep_v16::{day}::{market}::{depth}::{int(include_live)}"

    if st.button(f"⚡ BUILD FAST TOP 5 — {market.upper()}",use_container_width=True,key="mx_rank_fast_btn_v16"):
        with st.spinner(f"Building fast {market} board..."):
            rows,diag=fast_scan(games_df,market,depth,include_live)
            st.session_state[fast_key]={"rows":rows,"diag":diag}
            st.session_state.pop(deep_key,None)

    fast=st.session_state.get(fast_key)
    if fast:
        d=fast["diag"]
        st.success(f"⚡ FAST BOARD READY • {d.get('modeled',len(fast['rows']))}/{d.get('pool',len(fast['rows']))} hitters modeled • {d.get('errors',0)} profile errors")
        scbase._render_top5(fast["rows"],market,depth)
        st.caption("Fast board uses the verified core stack and makes zero new Baseball Savant requests.")
        if st.button(f"🎯 DEEP CALIBRATE TOP 5 — STATCAST TOP-8 ONLY",use_container_width=True,key="mx_rank_deep_btn_v16"):
            with st.spinner("Deep-calibrating only the Top-8 bubble candidates; cached profiles are reused..."):
                rows,diag=deep_calibrate(games_df,fast["rows"],market)
                st.session_state[deep_key]={"rows":rows,"diag":diag}

    deep=st.session_state.get(deep_key)
    if deep:
        d=deep["diag"]
        st.success(f"🎯 DEEP BOARD READY • {d.get('statcast_contenders',0)} hitters checked • {d.get('starter_profiles',0)} unique starter profiles reused")
        scbase._render_top5(deep["rows"],market,depth)
        st.caption(f"{VERSION} • two-stage workflow • only Top-8 bubble receives Statcast deep pass • batter/starter profiles cached across markets • model caps unchanged")
    elif not fast:
        st.info("Start with ⚡ FAST TOP 5. Run the optional deep Statcast pass only when you want the final calibrated board.")
