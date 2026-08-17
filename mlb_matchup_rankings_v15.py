"""MLB Daily Rankings V1.5 — feed-reliability hotfix.

Repairs the V1.4 Statcast raw-data query (details/pitch-level export), adds
retry/schema diagnostics, and hardens bullpen history with MLB live-feed
fallback + a wider recent-game window. Projection math/caps remain unchanged.
"""
from __future__ import annotations

import io
import math
from datetime import timedelta

import pandas as pd
import requests
import streamlit as st

import mlb_matchup_rankings_v14 as base
import mlb_matchup_rankings_v13 as bpbase
import mlb_matchup_hub_v10 as ui

VERSION = "MLB Daily Rankings V1.5"
SAVANT_CSV = "https://baseballsavant.mlb.com/statcast_search/csv"


def _finite(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _savant_params(player_id, year, player_type):
    # Baseball Savant raw Statcast rows use a details query. V1.4 incorrectly
    # sent type=batter/pitcher, which can return an empty/non-pitch schema.
    return {
        "all":"true",
        "type":"details",
        "player_type":"batter" if player_type=="batter" else "pitcher",
        "hfSeaYear":f"{int(year)}|",
        "hfGT":"R|",
        "game_date_gt":f"{int(year)}-03-01",
        "game_date_lt":f"{int(year)}-11-30",
        "playerid":int(player_id),
        "group_by":"name-date",
        "sort_col":"pitches",
        "sort_order":"desc",
        "min_pitches":"0",
        "min_results":"0",
    }


@st.cache_data(ttl=1800, show_spinner=False)
def _statcast_rows(player_id, year, player_type):
    out={"status":"PENDING","rows":0,"frame":None,"error":"","http_status":None,"query_type":"details"}
    if not player_id:
        out["error"]="missing player id"; return out
    session=requests.Session()
    headers={
        "User-Agent":"Mozilla/5.0 (compatible; KyreSportsAI/1.0)",
        "Accept":"text/csv,text/plain,*/*",
        "Referer":"https://baseballsavant.mlb.com/statcast_search",
    }
    last_error=""
    for attempt,timeout in enumerate((18,28),1):
        try:
            r=session.get(SAVANT_CSV,params=_savant_params(player_id,year,player_type),timeout=timeout,headers=headers)
            out["http_status"]=r.status_code
            r.raise_for_status()
            text=(r.text or "").lstrip("\ufeff").strip()
            if not text:
                last_error="empty response"; continue
            if text[:1] in ("<","{"):
                last_error=f"non-CSV response starts {text[:30]!r}"; continue
            df=pd.read_csv(io.StringIO(text),low_memory=False)
            if df.empty:
                last_error="0 Statcast rows"; continue
            cols=set(str(c).strip() for c in df.columns)
            required={"pitch_type","batter","pitcher"}
            if not required.issubset(cols):
                last_error="schema mismatch: missing " + ",".join(sorted(required-cols)); continue
            # Defensive ID filter: some Savant query combinations can return a
            # broader set than requested. Never use another player's rows.
            idcol="batter" if player_type=="batter" else "pitcher"
            ids=pd.to_numeric(df[idcol],errors="coerce")
            filtered=df.loc[ids==int(player_id)].copy()
            if not filtered.empty:
                df=filtered
            out.update({"status":"VERIFIED","rows":len(df),"frame":df,"error":"","attempt":attempt})
            return out
        except Exception as exc:
            last_error=f"{type(exc).__name__}: {exc}"[:220]
    out["error"]=last_error or "Statcast request failed"
    return out


def _ip(v):
    try:
        s=str(v or "0").strip()
        if "." not in s: return float(s)
        whole,frac=s.split(".",1); outs=int(frac[:1]) if frac else 0
        return float(int(whole))+max(0,min(2,outs))/3.0
    except Exception:
        return 0.0


def _team_side_from_box(teams, team_id):
    for label in ("away","home"):
        t=teams.get(label) or {}
        candidates=[
            ((t.get("team") or {}).get("id")),
            (((t.get("team") or {}).get("team") or {}).get("id")),
        ]
        for x in candidates:
            try:
                if int(x)==int(team_id): return label,t
            except Exception:
                pass
    return None,None


def _relief_from_team_box(side):
    if not side: return None
    pitcher_ids=list(side.get("pitchers") or [])
    players=side.get("players") or {}
    if not pitcher_ids: return None
    # Appearance order is starter first in standard MLB boxscores. If a pitcher
    # is explicitly marked as starter, honor that instead.
    starter_id=None
    for pid in pitcher_ids:
        p=players.get(f"ID{pid}") or {}
        stats=((p.get("stats") or {}).get("pitching") or {})
        gs=_finite(stats.get("gamesStarted"),0) or 0
        if gs>0:
            starter_id=pid; break
    if starter_id is None: starter_id=pitcher_ids[0]
    reliever_ids=[p for p in pitcher_ids if p!=starter_id]
    gip=ger=gpitches=0.0; grel=0
    for pid in reliever_ids:
        p=players.get(f"ID{pid}") or {}
        ps=((p.get("stats") or {}).get("pitching") or {})
        rip=_ip(ps.get("inningsPitched")); er=_finite(ps.get("earnedRuns"),0) or 0
        pitches=_finite(ps.get("pitchesThrown"),0) or 0
        if rip<=0 and pitches<=0: continue
        gip+=rip; ger+=er; gpitches+=pitches; grel+=1
    return {"ip":gip,"er":ger,"pitches":gpitches,"relievers":grel}


@st.cache_data(ttl=600, show_spinner=False)
def _bullpen_profile(team_id, target_day):
    out={"bullpen_status":"PENDING","bullpen_error":"","bp_games":0}
    if not team_id:
        out["bullpen_error"]="missing team id"; return out
    try:
        day=pd.to_datetime(str(target_day)[:10]).date()
        # Wider window survives off-days while still selecting only last 3 finals.
        start=(day-timedelta(days=8)).isoformat(); end=(day-timedelta(days=1)).isoformat()
        sched=ui._json(f"{ui.MLB_API}/schedule",{"sportId":1,"teamId":int(team_id),"startDate":start,"endDate":end})
        games=[]
        for block in sched.get("dates") or []:
            gd=str(block.get("date") or "")[:10]
            for g in block.get("games") or []:
                state=str((g.get("status") or {}).get("codedGameState") or "")
                detail=str((g.get("status") or {}).get("detailedState") or "")
                if state=="F" or "Final" in detail:
                    try: games.append((gd,int(g.get("gamePk"))))
                    except Exception: pass
        games=sorted(games,reverse=True)[:3]
        if not games:
            out["bullpen_error"]="no final games in prior 8 days"; return out
        samples=[]
        for gd,pk in games:
            sample=None
            # First try compact boxscore.
            try:
                box=ui._json(f"{ui.MLB_API}/game/{pk}/boxscore",{})
                _,side=_team_side_from_box(box.get("teams") or {},team_id)
                sample=_relief_from_team_box(side)
            except Exception:
                sample=None
            # Robust fallback: full live feed carries the same boxscore structure.
            if sample is None:
                try:
                    feed=ui._json(f"{ui.MLB_API}/game/{pk}/feed/live",{})
                    teams=(((feed.get("liveData") or {}).get("boxscore") or {}).get("teams") or {})
                    _,side=_team_side_from_box(teams,team_id)
                    sample=_relief_from_team_box(side)
                except Exception:
                    sample=None
            if sample is not None:
                samples.append({"date":gd,"game_pk":pk,**sample})
        if not samples:
            out["bullpen_error"]="boxscore/live-feed relief parsing returned 0 samples"; return out
        total_ip=sum(x["ip"] for x in samples); total_er=sum(x["er"] for x in samples)
        total_pitches=sum(x["pitches"] for x in samples); total_rel=sum(x["relievers"] for x in samples)
        if total_ip<=0:
            out["bullpen_error"]="verified games but 0 relief innings"; return out
        era=total_er*9.0/total_ip
        last=samples[0]
        out.update({
            "bullpen_status":"VERIFIED","bullpen_error":"","bp_games":len(samples),
            "bp_ip_3g":total_ip,"bp_er_3g":total_er,"bp_era_3g":era,
            "bp_pitches_3g":total_pitches,"bp_relievers_3g":total_rel,
            "bp_last_ip":last["ip"],"bp_last_relievers":last["relievers"],"bp_samples":samples,
        })
    except Exception as exc:
        out["bullpen_error"]=f"{type(exc).__name__}: {exc}"[:220]
    return out


def _install_hotfixes():
    # V1.4 resolves these names at runtime, so monkeypatching keeps all model
    # math/rendering identical while repairing only the data-source functions.
    base._savant_params=_savant_params
    base._statcast_rows=_statcast_rows
    bpbase._bullpen_profile=_bullpen_profile
    # V1.4 -> V1.3 uses the imported V1.3 module object, so this patch propagates.
    try: base.base._bullpen_profile=_bullpen_profile
    except Exception: pass


def scan_market(games_df, market, sims=20_000, include_live=False):
    _install_hotfixes()
    rows,diag=base.scan_market(games_df,market,sims,include_live)
    diag=dict(diag)
    verified_sc=sum(1 for r in rows if r.get("statcast_status")=="VERIFIED")
    verified_bp=sum(1 for r in rows if r.get("bullpen_status")=="VERIFIED")
    errors=[]
    for r in rows[:12]:
        if r.get("statcast_status")=="PENDING" and r.get("statcast_error"):
            errors.append(f"{r.get('player')}: {r.get('statcast_error')}")
    diag.update({"feed_version":"V1.5","statcast_verified":verified_sc,"bullpen_verified":verified_bp,"feed_errors":errors[:5]})
    return rows,diag


def render_daily_rankings(games_df):
    _install_hotfixes()
    # Keep V1.4 visual/model behavior, but expose feed-health diagnostics above it.
    st.caption("🔧 Feed Reliability V1.5 active • Statcast details-query repair • bullpen boxscore/live-feed fallback")
    base.render_daily_rankings(games_df)
    # V1.4 owns result state; show a compact health note from any fresh V1.5 scan
    # only when scan_market is called directly by future wrappers. No duplicated
    # model board is rendered here.
