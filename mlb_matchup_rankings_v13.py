"""MLB Daily Rankings V1.3 — verified bullpen intelligence.

Extends V1.2 environment-aware rankings with opponent bullpen workload/quality
built only from official MLB schedule + boxscore data. Recent relief innings,
relievers used, earned runs and starter depth determine a small, capped bullpen
adjustment. Missing bullpen data remains PENDING; nothing is fabricated.
"""
from __future__ import annotations

import math
from datetime import timedelta
import pandas as pd
import streamlit as st

import mlb_matchup_rankings_v12 as base
import mlb_matchup_rankings_v11 as matchup
import mlb_matchup_hub_v10 as ui
from engine import odds

VERSION = "MLB Daily Rankings V1.3"


def _finite(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _ip(v):
    """Convert baseball IP notation (e.g. 2.1 = 2 1/3) to true innings."""
    try:
        s=str(v or "0").strip()
        if "." not in s:
            return float(s)
        whole,frac=s.split(".",1)
        outs=int(frac[:1]) if frac else 0
        return float(int(whole)) + max(0,min(2,outs))/3.0
    except Exception:
        return 0.0


def _game_map(games_df):
    out={}
    if games_df is None: return out
    for _,r in games_df.iterrows():
        try: pk=int(r.get("game_pk"))
        except Exception: continue
        out[pk]={
            "away_team":str(r.get("away_team") or ""),
            "home_team":str(r.get("home_team") or ""),
            "away_team_id":r.get("away_team_id"),
            "home_team_id":r.get("home_team_id"),
            "away_pitcher_id":r.get("away_pitcher_id"),
            "home_pitcher_id":r.get("home_pitcher_id"),
        }
    return out


@st.cache_data(ttl=900, show_spinner=False)
def _starter_depth(pid, season):
    if not pid: return None
    try:
        d=ui._json(f"{ui.MLB_API}/people/{int(pid)}/stats", {"stats":"season","group":"pitching","season":int(season)})
        blocks=d.get("stats") or []
        s=(blocks[0].get("splits") or [{}])[0].get("stat",{}) if blocks else {}
        gs=int(_finite(s.get("gamesStarted"),0) or 0)
        innings=_ip(s.get("inningsPitched"))
        if gs<=0: return None
        return max(2.5,min(7.5,innings/gs))
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def _bullpen_profile(team_id, target_day):
    out={"bullpen_status":"PENDING"}
    if not team_id: return out
    try:
        day=pd.to_datetime(str(target_day)[:10]).date()
        start=(day-timedelta(days=4)).isoformat(); end=(day-timedelta(days=1)).isoformat()
        sched=ui._json(f"{ui.MLB_API}/schedule", {"sportId":1,"teamId":int(team_id),"startDate":start,"endDate":end})
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
        if not games: return out

        total_ip=total_er=total_pitches=0.0; total_rel=0; last_ip=0.0; last_rel=0
        samples=[]
        for idx,(gd,pk) in enumerate(games):
            box=ui._json(f"{ui.MLB_API}/game/{pk}/boxscore", {})
            teams=box.get("teams") or {}; side=None
            for label in ("away","home"):
                t=teams.get(label) or {}
                try: tid=int(((t.get("team") or {}).get("id")))
                except Exception: tid=None
                if tid==int(team_id): side=t; break
            if not side: continue
            pitcher_ids=side.get("pitchers") or []
            # MLB boxscore pitcher order is appearance order; first is starter.
            reliever_ids=pitcher_ids[1:] if len(pitcher_ids)>1 else []
            gip=ger=gpitches=0.0; grel=0
            players=side.get("players") or {}
            for pid in reliever_ids:
                p=players.get(f"ID{pid}") or {}
                ps=((p.get("stats") or {}).get("pitching") or {})
                rip=_ip(ps.get("inningsPitched")); er=_finite(ps.get("earnedRuns"),0) or 0
                pitches=_finite(ps.get("pitchesThrown"),0) or 0
                if rip<=0 and pitches<=0: continue
                gip+=rip; ger+=er; gpitches+=pitches; grel+=1
            total_ip+=gip; total_er+=ger; total_pitches+=gpitches; total_rel+=grel
            if idx==0: last_ip=gip; last_rel=grel
            samples.append({"date":gd,"ip":gip,"er":ger,"relievers":grel,"pitches":gpitches})
        if total_ip<=0: return out
        era=total_er*9.0/total_ip
        out.update({
            "bullpen_status":"VERIFIED",
            "bp_games":len(samples),"bp_ip_3g":total_ip,"bp_er_3g":total_er,
            "bp_era_3g":era,"bp_pitches_3g":total_pitches,"bp_relievers_3g":total_rel,
            "bp_last_ip":last_ip,"bp_last_relievers":last_rel,"bp_samples":samples,
        })
    except Exception:
        pass
    return out


def _bullpen_adjust(row, games, year, market):
    try: g=games.get(int(row.get("game_pk") or 0),{})
    except Exception: g={}
    team=str(row.get("team") or "")
    is_away=team==str(g.get("away_team") or "")
    opp_tid=g.get("home_team_id") if is_away else g.get("away_team_id")
    opp_spid=g.get("home_pitcher_id") if is_away else g.get("away_pitcher_id")
    bp=_bullpen_profile(opp_tid,row.get("game_date"))
    if bp.get("bullpen_status")!="VERIFIED":
        return 0.0,{**bp,"bullpen_adj":0.0,"bullpen_exposure":None,"bullpen_reasons":[]}

    raw=0.0; reasons=[]
    era=bp.get("bp_era_3g"); last_ip=bp.get("bp_last_ip") or 0; ip3=bp.get("bp_ip_3g") or 0; last_rel=bp.get("bp_last_relievers") or 0
    # Recent quality: intentionally modest because 3 games is noisy.
    if era is not None:
        quality=max(-1.0,min(1.0,(era-4.20)/3.0))
        raw += quality*0.006
        reasons.append(f"3G BP ERA {era:.2f}")
    # Fatigue from yesterday + rolling three-game workload.
    fatigue=0.0
    if last_ip>=6.0: fatigue+=0.005
    elif last_ip>=4.0: fatigue+=0.003
    elif last_ip<=1.5: fatigue-=0.001
    if ip3>=13.0: fatigue+=0.003
    elif ip3>=10.0: fatigue+=0.0015
    if last_rel>=6: fatigue+=0.002
    elif last_rel>=5: fatigue+=0.001
    raw += fatigue
    reasons.append(f"Last BP {last_ip:.1f} IP/{last_rel} RP")
    reasons.append(f"3G BP {ip3:.1f} IP")

    # Only the expected bullpen share of the game gets this adjustment.
    depth=_starter_depth(opp_spid,year)
    exposure=max(.25,min(.60,(9.0-(depth if depth is not None else 5.3))/9.0))
    # Runs/RBI/H+R+RBI depend slightly more on bullpen sequencing; HR slightly less.
    scale={"Runs":1.15,"RBIs":1.15,"H+R+RBI":1.10,"Home Run":0.85}.get(market,1.0)
    adj=raw*exposure*scale
    adj=max(-0.010,min(0.010,adj))
    return adj,{**bp,"bullpen_adj":adj,"bullpen_exposure":exposure,"starter_avg_ip":depth,"bullpen_reasons":reasons}


def scan_market(games_df, market, sims=20_000, include_live=False):
    rows,diag=base.scan_market(games_df,market,sims,include_live)
    gm=_game_map(games_df)
    year=int(str(games_df.iloc[0].get("game_date"))[:4]) if games_df is not None and not games_df.empty else 2026
    for r in rows:
        bp_adj,bp=_bullpen_adjust(r,gm,year,market)
        rel=float(r.get("reliability") or 0)
        applied=bp_adj*(0.70+0.30*rel)
        r["pre_bullpen_p"]=float(r.get("p") or 0)
        r["p"]=max(.001,min(.999,r["pre_bullpen_p"]+applied))
        r.update(bp); r["applied_bullpen_adj"]=applied
    rows.sort(key=lambda x:(x["p"],x.get("reliability",0),1 if x.get("confirmed") else 0),reverse=True)
    diag=dict(diag); diag["bullpen_version"]="V1.3"
    return rows,diag


def _render_top5(rows,market,sims):
    top=rows[:5]
    if not top:
        st.warning("No eligible hitters were successfully modeled for this market."); return
    cards=[]
    for i,r in enumerate(top,1):
        status="✅ CONFIRMED" if r.get("confirmed") else "🕒 PROJECTED"
        fair=odds(r["p"]); starter=f"{r.get('starter','TBD')} ({r.get('starter_hand','—')})"
        sb=[]
        if r.get("starter_era") is not None: sb.append(f"ERA {r['starter_era']:.2f}")
        if r.get("starter_k9") is not None: sb.append(f"K/9 {r['starter_k9']:.1f}")
        ctx=float(r.get("applied_context_adj") or 0)*100; env=float(r.get("applied_environment_adj") or 0)*100; bp=float(r.get("applied_bullpen_adj") or 0)*100
        if r.get("weather_status")=="VERIFIED":
            wx=[]
            if r.get("temp_f") is not None: wx.append(f"{r['temp_f']:.0f}°F")
            if r.get("wind_mph") is not None: wx.append(f"Wind {r['wind_mph']:.0f} mph")
            if r.get("precip_pct") is not None: wx.append(f"Precip {r['precip_pct']:.0f}%")
            wx_text=" • ".join(wx) or "verified"
        else: wx_text="pending"
        if r.get("bullpen_status")=="VERIFIED":
            bp_text=f"3G ERA {r.get('bp_era_3g',0):.2f} • Last {r.get('bp_last_ip',0):.1f} IP/{int(r.get('bp_last_relievers',0))} RP • Exposure {r.get('bullpen_exposure',0)*100:.0f}%"
        else: bp_text="pending"
        cards.append(f'''<div class="rk-card {'first' if i==1 else ''}"><div class="rk-rank">{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '•'} RANK {i} • {status}</div><div class="rk-name">{ui._esc(r['player'])}</div><div class="rk-match">{ui._esc(r['team'])} vs {ui._esc(r['opponent'])} • Bat #{ui._esc(r.get('bat_spot'))}</div><div class="rk-p">{r['p']*100:.1f}%</div><div class="rk-label">{ui._esc(market)} probability • Fair {ui._esc(fair)}</div><div class="rk-details">{ui._esc(r['support'])}</div><div class="rk-details">⚾ vs {ui._esc(starter)} • {' • '.join(sb) if sb else 'starter stats pending'} • Matchup {ctx:+.1f} pts</div><div class="rk-details">🌦️ {ui._esc(r.get('venue_name') or r.get('venue') or 'Venue')} • {ui._esc(wx_text)} • Environment {env:+.1f} pts</div><div class="rk-details">🧯 Opponent bullpen • {ui._esc(bp_text)} • Bullpen {bp:+.1f} pts</div><div class="rk-badges"><span class="rk-pill good">{ui._esc(r['confidence'])}</span><span class="rk-pill">Reliability {r['reliability']*100:.0f}%</span><span class="rk-pill">{r['sample']:.0f} {ui._esc(r['sample_unit'])}</span></div></div>''')
    st.markdown(f'<div class="rk-grid">{"".join(cards)}</div>',unsafe_allow_html=True)
    st.caption(f"{VERSION} • {int(sims):,} simulations/hitter • matchup + verified environment + verified bullpen workload context • bullpen effect capped at ±1.0 probability point before reliability damping • sportsbook prices excluded from model inputs.")
    st.info("🧪 Advanced Statcast contact quality and pitch-mix compatibility remain PENDING until verified feeds are connected. No synthetic values are assigned.")


def render_daily_rankings(games_df):
    base.base.base._css()
    st.markdown('<div class="rk-wrap"><div class="rk-head"><div><div class="rk-title">🏆 Daily Slate Rankings — Bullpen Intelligence</div><div class="rk-sub">Frozen production engines + matchup + environment + official recent bullpen workload</div></div><div class="rk-sub">V1.3</div></div></div>',unsafe_allow_html=True)
    if games_df is None or games_df.empty:
        st.info("No verified MLB slate is available for rankings."); return
    market=st.selectbox("RANKING MARKET",base.base.base.MARKETS,key="mx_rank_market_v13")
    c1,c2=st.columns([2,1])
    with c1: depth=st.selectbox("SCAN DEPTH",[20_000,50_000,100_000],index=1,format_func=lambda n:f"{n//1000}K simulations / hitter",key="mx_rank_depth_v13")
    with c2: include_live=st.checkbox("Include live games",value=False,key="mx_rank_live_v13")
    day=str(games_df.iloc[0].get("game_date"))[:10]; key=f"mx_rank_v13::{day}::{market}::{depth}::{int(include_live)}"
    if st.button(f"🔥 BUILD BULLPEN-CALIBRATED TOP 5 — {market.upper()}",use_container_width=True,key="mx_rank_build_v13"):
        with st.spinner(f"Scanning {market} slate + starter/weather/bullpen intelligence..."):
            rows,diag=scan_market(games_df,market,depth,include_live); st.session_state[key]={"rows":rows,"diag":diag}
    result=st.session_state.get(key)
    if result:
        d=result["diag"]; st.success(f"✅ {d['modeled']}/{d['pool']} eligible hitters modeled • {d['errors']} profile errors • bullpen intelligence checked")
        _render_top5(result["rows"],market,depth)
    else:
        st.info("Choose a market and build the Top 5. The bullpen-enriched scan runs only on demand.")
