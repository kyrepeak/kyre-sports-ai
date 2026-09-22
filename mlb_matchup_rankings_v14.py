"""MLB Daily Rankings V1.4 — verified Statcast + platoon + pitch-mix intelligence.

Extends V1.3 bullpen-aware rankings. Baseball Savant's documented Statcast CSV
feed is queried only for contenders close enough to the current Top 5 to move
into it after the hard-capped adjustment. Contact quality, platoon behavior and
pitch-type compatibility are derived from observed Statcast pitch/BBE rows.
Missing/thin data remains PENDING and contributes 0.0 probability points.
"""
from __future__ import annotations

import io
import math
from collections import Counter

import pandas as pd
import requests
import streamlit as st

import mlb_matchup_rankings_v13 as base
import mlb_matchup_hub_v10 as ui
from engine import odds

VERSION = "MLB Daily Rankings V1.4"
SAVANT_CSV = "https://baseballsavant.mlb.com/statcast_search/csv"


def _finite(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _mean(series):
    vals=pd.to_numeric(series,errors="coerce").dropna() if series is not None else pd.Series(dtype=float)
    return float(vals.mean()) if len(vals) else None


def _pct(num,den):
    return float(num)/float(den) if den else None


def _savant_params(player_id, year, player_type):
    # Statcast search CSV parameters. Unknown/extra params are intentionally
    # avoided; the documented CSV columns are consumed defensively below.
    return {
        "all":"true",
        "type":"batter" if player_type=="batter" else "pitcher",
        "player_type":player_type,
        "hfSeaYear":f"{int(year)}|",
        "playerid":int(player_id),
    }


@st.cache_data(ttl=1800, show_spinner=False)
def _statcast_rows(player_id, year, player_type):
    out={"status":"PENDING","rows":0,"frame":None,"error":""}
    if not player_id:
        return out
    try:
        r=requests.get(
            SAVANT_CSV,
            params=_savant_params(player_id,year,player_type),
            timeout=12,
            headers={"User-Agent":"Mozilla/5.0","Accept":"text/csv,text/plain,*/*"},
        )
        r.raise_for_status()
        text=(r.text or "").strip()
        if not text or "," not in text[:500]:
            out["error"]="empty/non-CSV response"; return out
        df=pd.read_csv(io.StringIO(text),low_memory=False)
        if df.empty:
            out["error"]="0 Statcast rows"; return out
        # Verify the response is Statcast-shaped before using it.
        required={"pitch_type","batter","pitcher"}
        if not required.issubset(set(df.columns)):
            out["error"]="unexpected CSV schema"; return out
        out.update({"status":"VERIFIED","rows":len(df),"frame":df})
    except Exception as exc:
        out["error"]=f"{type(exc).__name__}: {exc}"[:180]
    return out


def _is_whiff(desc):
    return str(desc or "").lower() in {
        "swinging_strike","swinging_strike_blocked","missed_bunt","foul_tip"
    }


def _is_swing(desc):
    s=str(desc or "").lower()
    return s in {
        "swinging_strike","swinging_strike_blocked","missed_bunt","foul_tip",
        "foul","foul_bunt","hit_into_play"
    }


def _contact_profile(df):
    if df is None or df.empty:
        return {"status":"PENDING"}
    ev=pd.to_numeric(df.get("launch_speed"),errors="coerce") if "launch_speed" in df else pd.Series(dtype=float)
    bbe=df.loc[ev.notna()].copy() if len(ev) else pd.DataFrame()
    if bbe.empty:
        return {"status":"PENDING"}
    evv=pd.to_numeric(bbe["launch_speed"],errors="coerce").dropna()
    n=len(evv)
    hard=float((evv>=95).mean()) if n else None
    barrel=None
    if "launch_speed_angle" in bbe.columns:
        lsa=pd.to_numeric(bbe["launch_speed_angle"],errors="coerce")
        barrel=float((lsa==6).mean()) if lsa.notna().sum() else None
    xba=_mean(bbe.get("estimated_ba_using_speedangle")) if "estimated_ba_using_speedangle" in bbe else None
    xwoba=_mean(bbe.get("estimated_woba_using_speedangle")) if "estimated_woba_using_speedangle" in bbe else None
    return {
        "status":"VERIFIED","bbe":n,"avg_ev":float(evv.mean()),"hard_hit":hard,
        "barrel":barrel,"contact_xba":xba,"contact_xwoba":xwoba,
    }


def _pitcher_arsenal(df):
    if df is None or df.empty or "pitch_type" not in df:
        return {"status":"PENDING","mix":[]}
    pts=df["pitch_type"].dropna().astype(str)
    pts=pts[pts.str.len()>0]
    if pts.empty:
        return {"status":"PENDING","mix":[]}
    counts=Counter(pts.tolist()); total=sum(counts.values())
    mix=[(pt,n/total,n) for pt,n in counts.most_common(5)]
    hand="—"
    if "p_throws" in df.columns:
        h=df["p_throws"].dropna().astype(str)
        if len(h): hand=h.mode().iloc[0]
    return {"status":"VERIFIED","mix":mix,"pitches":total,"hand":hand}


def _batter_pitch_and_platoon(df, arsenal):
    out={"status":"PENDING","matched_pitches":0,"pitch_score":0.0,"platoon_score":0.0,
         "platoon_n":0,"pitch_notes":[],"platoon_note":"pending"}
    if df is None or df.empty or not arsenal or arsenal.get("status")!="VERIFIED":
        return out
    overall=_contact_profile(df)
    overall_xba=overall.get("contact_xba") if overall.get("status")=="VERIFIED" else None

    # Pitch-type compatibility: compare batter contact xBA and whiff behavior on
    # the starter's actual top pitch types. Thin pitch-type samples get no boost.
    weighted=weight_sum=0.0; matched=0; notes=[]
    for pt,share,_ in arsenal.get("mix",[])[:4]:
        sub=df[df["pitch_type"].astype(str)==str(pt)].copy()
        if len(sub)<10:
            continue
        swings=sum(_is_swing(x) for x in sub.get("description",pd.Series(dtype=object)))
        whiffs=sum(_is_whiff(x) for x in sub.get("description",pd.Series(dtype=object)))
        whiff=_pct(whiffs,swings)
        cp=_contact_profile(sub); pxba=cp.get("contact_xba")
        score=0.0
        if pxba is not None and overall_xba is not None:
            score += max(-1.0,min(1.0,(pxba-overall_xba)/0.070))*0.65
        if whiff is not None:
            # ~25% whiff baseline on swings; lower is favorable for contact.
            score += max(-1.0,min(1.0,(0.25-whiff)/0.12))*0.35
        weighted += score*share; weight_sum += share; matched += len(sub)
        notes.append(f"{pt} {share*100:.0f}%")
    pitch_score=(weighted/weight_sum) if weight_sum>0 else 0.0

    # Platoon behavior against the starter's throwing hand from the same verified
    # Statcast rows. This is contact/whiff context, not a fabricated career split.
    hand=str(arsenal.get("hand") or "").upper()
    platoon_score=0.0; pn=0; pnote="pending"
    if hand in ("L","R") and "p_throws" in df.columns:
        sub=df[df["p_throws"].astype(str).str.upper()==hand].copy(); pn=len(sub)
        if pn>=35:
            cp=_contact_profile(sub); sxba=cp.get("contact_xba")
            swings=sum(_is_swing(x) for x in sub.get("description",pd.Series(dtype=object)))
            whiffs=sum(_is_whiff(x) for x in sub.get("description",pd.Series(dtype=object)))
            wr=_pct(whiffs,swings)
            if sxba is not None and overall_xba is not None:
                platoon_score += max(-1.0,min(1.0,(sxba-overall_xba)/0.060))*0.70
            if wr is not None:
                platoon_score += max(-1.0,min(1.0,(0.25-wr)/0.12))*0.30
            pnote=f"vs {hand}HP • {pn} pitches"
    out.update({"status":"VERIFIED" if matched>=20 or pn>=35 else "THIN",
                "matched_pitches":matched,"pitch_score":pitch_score,
                "platoon_score":platoon_score,"platoon_n":pn,
                "pitch_notes":notes,"platoon_note":pnote})
    return out


def _statcast_adjust(row, year, market):
    bid=row.get("player_id")
    # V1.1 context already resolved the opposing starter name but not its id. We
    # can recover the id from the candidate pool only through game context; V1.3
    # keeps it in its bullpen lookup path, so use the game/starter map exposed by
    # the current slate when attached below.
    spid=row.get("_statcast_starter_id")
    b=_statcast_rows(bid,year,"batter") if bid else {"status":"PENDING"}
    p=_statcast_rows(spid,year,"pitcher") if spid else {"status":"PENDING"}
    if b.get("status")!="VERIFIED":
        return 0.0,{"statcast_status":"PENDING","statcast_adj":0.0,"statcast_error":b.get("error",""),
                   "pitch_mix_status":"PENDING","platoon_status":"PENDING"}
    contact=_contact_profile(b.get("frame"))
    arsenal=_pitcher_arsenal(p.get("frame")) if p.get("status")=="VERIFIED" else {"status":"PENDING","mix":[]}
    matchup=_batter_pitch_and_platoon(b.get("frame"),arsenal)

    raw=0.0; reasons=[]
    if contact.get("status")=="VERIFIED" and contact.get("bbe",0)>=35:
        ev=contact.get("avg_ev"); hh=contact.get("hard_hit"); br=contact.get("barrel"); xba=contact.get("contact_xba")
        cscore=0.0
        if xba is not None: cscore += max(-1,min(1,(xba-.300)/.080))*0.40
        if hh is not None: cscore += max(-1,min(1,(hh-.390)/.120))*0.25
        if ev is not None: cscore += max(-1,min(1,(ev-88.5)/4.5))*0.20
        if br is not None: cscore += max(-1,min(1,(br-.075)/.075))*0.15
        scale={"Home Run":.010,"Total Bases":.009,"H+R+RBI":.007,"RBIs":.006,"Runs":.005}.get(market,.007)
        raw += cscore*scale
        reasons.append(f"EV {ev:.1f}" if ev is not None else "EV —")
        if hh is not None: reasons.append(f"HardHit {hh*100:.0f}%")
        if br is not None: reasons.append(f"Barrel {br*100:.1f}%")
        if xba is not None: reasons.append(f"contact-xBA {xba:.3f}")

    if matchup.get("status") in ("VERIFIED","THIN"):
        # Pitch compatibility and platoon are capped separately; thin samples are
        # automatically damped by requiring minimum pitch counts above.
        raw += max(-.006,min(.006,matchup.get("pitch_score",0)*.006))
        raw += max(-.005,min(.005,matchup.get("platoon_score",0)*.005))

    raw=max(-.018,min(.018,raw))
    return raw,{
        "statcast_status":"VERIFIED" if contact.get("status")=="VERIFIED" else "PENDING",
        "statcast_adj":raw,"statcast_bbe":contact.get("bbe"),"statcast_ev":contact.get("avg_ev"),
        "statcast_hard_hit":contact.get("hard_hit"),"statcast_barrel":contact.get("barrel"),
        "statcast_contact_xba":contact.get("contact_xba"),"statcast_reasons":reasons,
        "pitch_mix_status":arsenal.get("status","PENDING"),"pitch_mix":arsenal.get("mix",[]),
        "pitch_mix_matched":matchup.get("matched_pitches",0),"pitch_mix_notes":matchup.get("pitch_notes",[]),
        "platoon_status":matchup.get("status","PENDING"),"platoon_note":matchup.get("platoon_note","pending"),
        "savant_batter_rows":b.get("rows",0),"savant_pitcher_rows":p.get("rows",0),
    }


def _starter_ids(games_df):
    out={}
    if games_df is None: return out
    for _,g in games_df.iterrows():
        try: pk=int(g.get("game_pk"))
        except Exception: continue
        out[pk]={
            "away_team":str(g.get("away_team") or ""),"home_team":str(g.get("home_team") or ""),
            "away_pitcher_id":g.get("away_pitcher_id"),"home_pitcher_id":g.get("home_pitcher_id"),
        }
    return out


def scan_market(games_df, market, sims=20_000, include_live=False):
    rows,diag=base.scan_market(games_df,market,sims,include_live)
    if not rows:
        return rows,diag
    year=int(str(games_df.iloc[0].get("game_date"))[:4]) if games_df is not None and not games_df.empty else 2026
    gm=_starter_ids(games_df)
    # Deep-enrich only candidates that can plausibly enter Top 5 after max 1.8pp
    # Statcast adjustment. Always enrich at least the first 12.
    fifth=rows[min(4,len(rows)-1)]["p"]
    contenders=[]
    for idx,r in enumerate(rows):
        if idx<12 or float(r.get("p") or 0)>=float(fifth)-.020:
            contenders.append(r)
    contenders=contenders[:32]
    enriched_ids=set()
    for r in contenders:
        try:
            g=gm.get(int(r.get("game_pk") or 0),{})
            is_away=str(r.get("team") or "")==g.get("away_team")
            spid=g.get("home_pitcher_id") if is_away else g.get("away_pitcher_id")
            r["_statcast_starter_id"]=spid
            adj,sc=_statcast_adjust(r,year,market)
            rel=float(r.get("reliability") or 0)
            applied=adj*(0.68+0.32*rel)
            r["pre_statcast_p"]=float(r.get("p") or 0)
            r["p"]=max(.001,min(.999,r["pre_statcast_p"]+applied))
            r.update(sc); r["applied_statcast_adj"]=applied
            enriched_ids.add(id(r))
        except Exception:
            r.update({"statcast_status":"PENDING","pitch_mix_status":"PENDING","platoon_status":"PENDING","applied_statcast_adj":0.0})
    for r in rows:
        if id(r) not in enriched_ids:
            r.update({"statcast_status":"NOT NEEDED FOR TOP-5 GATE","pitch_mix_status":"NOT SCANNED","platoon_status":"NOT SCANNED","applied_statcast_adj":0.0})
    rows.sort(key=lambda x:(x["p"],x.get("reliability",0),1 if x.get("confirmed") else 0),reverse=True)
    diag=dict(diag); diag.update({"statcast_version":"V1.4","statcast_contenders":len(contenders)})
    return rows,diag


def _fmt_pct(v):
    return "—" if v is None else f"{float(v)*100:.1f}%"


def _render_top5(rows,market,sims):
    top=rows[:5]
    if not top:
        st.warning("No eligible hitters were successfully modeled for this market."); return
    cards=[]
    for i,r in enumerate(top,1):
        status="✅ CONFIRMED" if r.get("confirmed") else "🕒 PROJECTED"; fair=odds(r["p"])
        starter=f"{r.get('starter','TBD')} ({r.get('starter_hand','—')})"
        sb=[]
        if r.get("starter_era") is not None: sb.append(f"ERA {r['starter_era']:.2f}")
        if r.get("starter_k9") is not None: sb.append(f"K/9 {r['starter_k9']:.1f}")
        ctx=float(r.get("applied_context_adj") or 0)*100; env=float(r.get("applied_environment_adj") or 0)*100
        bp=float(r.get("applied_bullpen_adj") or 0)*100; sc=float(r.get("applied_statcast_adj") or 0)*100
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
        if r.get("statcast_status")=="VERIFIED":
            sc_bits=[]
            if r.get("statcast_ev") is not None: sc_bits.append(f"EV {r['statcast_ev']:.1f}")
            if r.get("statcast_hard_hit") is not None: sc_bits.append(f"HH {_fmt_pct(r['statcast_hard_hit'])}")
            if r.get("statcast_barrel") is not None: sc_bits.append(f"Barrel {_fmt_pct(r['statcast_barrel'])}")
            if r.get("statcast_contact_xba") is not None: sc_bits.append(f"c-xBA {r['statcast_contact_xba']:.3f}")
            sc_text=" • ".join(sc_bits) or "verified"
        else: sc_text="pending"
        mix=" / ".join(f"{pt} {share*100:.0f}%" for pt,share,_ in (r.get("pitch_mix") or [])[:3]) or "pending"
        cards.append(f'''<div class="rk-card {'first' if i==1 else ''}"><div class="rk-rank">{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else '•'} RANK {i} • {status}</div><div class="rk-name">{ui._esc(r['player'])}</div><div class="rk-match">{ui._esc(r['team'])} vs {ui._esc(r['opponent'])} • Bat #{ui._esc(r.get('bat_spot'))}</div><div class="rk-p">{r['p']*100:.1f}%</div><div class="rk-label">{ui._esc(market)} probability • Fair {ui._esc(fair)}</div><div class="rk-details">{ui._esc(r['support'])}</div><div class="rk-details">⚾ vs {ui._esc(starter)} • {' • '.join(sb) if sb else 'starter stats pending'} • Matchup {ctx:+.1f} pts</div><div class="rk-details">🌦️ {ui._esc(r.get('venue_name') or r.get('venue') or 'Venue')} • {ui._esc(wx_text)} • Environment {env:+.1f} pts</div><div class="rk-details">🧯 Opponent bullpen • {ui._esc(bp_text)} • Bullpen {bp:+.1f} pts</div><div class="rk-details">📡 Statcast • {ui._esc(sc_text)} • Statcast/platoon/pitch {sc:+.1f} pts</div><div class="rk-details">🎯 Starter arsenal • {ui._esc(mix)} • {ui._esc(r.get('platoon_note') or 'platoon pending')}</div><div class="rk-badges"><span class="rk-pill good">{ui._esc(r['confidence'])}</span><span class="rk-pill">Reliability {r['reliability']*100:.0f}%</span><span class="rk-pill">{r['sample']:.0f} {ui._esc(r['sample_unit'])}</span></div></div>''')
    st.markdown(f'<div class="rk-grid">{"".join(cards)}</div>',unsafe_allow_html=True)
    st.caption(f"{VERSION} • {int(sims):,} simulations/hitter • matchup + environment + bullpen + verified Statcast/platoon/pitch-mix context • Statcast layer capped at ±1.8 probability points before reliability damping • sportsbook prices excluded from model inputs.")
    st.info("📡 Statcast is read from Baseball Savant CSV only when the response schema and samples verify. Thin/unavailable contact, platoon or pitch-type samples contribute 0.0 points rather than synthetic estimates.")


def render_daily_rankings(games_df):
    base.base.base.base._css()
    st.markdown('<div class="rk-wrap"><div class="rk-head"><div><div class="rk-title">🏆 Daily Slate Rankings — Statcast Intelligence</div><div class="rk-sub">Frozen production engines + starter/lineup + environment + bullpen + verified Statcast contact/platoon/pitch mix</div></div><div class="rk-sub">V1.4</div></div></div>',unsafe_allow_html=True)
    if games_df is None or games_df.empty:
        st.info("No verified MLB slate is available for rankings."); return
    market=st.selectbox("RANKING MARKET",base.base.base.base.MARKETS,key="mx_rank_market_v14")
    c1,c2=st.columns([2,1])
    with c1: depth=st.selectbox("SCAN DEPTH",[20_000,50_000,100_000],index=1,format_func=lambda n:f"{n//1000}K simulations / hitter",key="mx_rank_depth_v14")
    with c2: include_live=st.checkbox("Include live games",value=False,key="mx_rank_live_v14")
    day=str(games_df.iloc[0].get("game_date"))[:10]; key=f"mx_rank_v14::{day}::{market}::{depth}::{int(include_live)}"
    if st.button(f"🔥 BUILD STATCAST-CALIBRATED TOP 5 — {market.upper()}",use_container_width=True,key="mx_rank_build_v14"):
        with st.spinner(f"Scanning {market} slate + Statcast/platoon/pitch-mix intelligence..."):
            rows,diag=scan_market(games_df,market,depth,include_live); st.session_state[key]={"rows":rows,"diag":diag}
    result=st.session_state.get(key)
    if result:
        d=result["diag"]; st.success(f"✅ {d['modeled']}/{d['pool']} eligible hitters modeled • {d['errors']} profile errors • {d.get('statcast_contenders',0)} Statcast contenders checked")
        _render_top5(result["rows"],market,depth)
    else:
        st.info("Choose a market and build the Top 5. Deep Statcast enrichment runs only on contenders close enough to affect the Top 5.")
