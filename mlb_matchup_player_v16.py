"""MLB Matchup Explorer player layer V1.6 — Batter vs Pitcher Step 2.

Adds recent starter form, handedness splits, verified pitch mix, and batter
performance versus the starter's primary pitch types. Display/context only:
production projection engines and ranking formulas are unchanged.
"""
from __future__ import annotations

import math
from collections import Counter

import pandas as pd
import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v14 as v14
import mlb_matchup_player_v15 as step1
import mlb_matchup_rankings_v15 as feeds

VERSION = "MLB Player Intelligence V1.6"


def _i(v, default=0):
    try: return int(float(v))
    except Exception: return default


def _f(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception: return default


def _ip(v):
    try:
        s=str(v or "0").strip()
        if "." not in s: return float(s)
        a,b=s.split(".",1); outs=int((b or "0")[:1])
        return float(int(a))+max(0,min(2,outs))/3.0
    except Exception: return 0.0


def _fmt(v, n=2):
    x=_f(v)
    return "—" if x is None else f"{x:.{n}f}"


def _fmt_avg(v):
    x=_f(v)
    if x is None: return "—"
    return f"{x:.3f}".replace("0.",".",1)


@st.cache_data(ttl=900, show_spinner=False)
def _pitcher_game_log(player_id, season):
    if not player_id: return []
    try:
        d=ui._json(f"{ui.MLB_API}/people/{int(player_id)}/stats",{
            "stats":"gameLog","group":"pitching","season":int(season),"gameType":"R"
        })
        blocks=d.get("stats") or []
        splits=(blocks[0].get("splits") or []) if blocks else []
        out=[]
        for s in splits:
            stat=s.get("stat") or {}
            gs=_i(stat.get("gamesStarted"),0)
            # gameLog rows can omit gamesStarted; innings/pitches is enough to
            # identify actual pitching appearances. Prefer starter rows when flag exists.
            if gs<=0 and not stat.get("inningsPitched"): continue
            out.append({
                "date":str(s.get("date") or ""),
                "ip":_ip(stat.get("inningsPitched")),
                "h":_i(stat.get("hits")),"er":_i(stat.get("earnedRuns")),
                "hr":_i(stat.get("homeRuns")),"bb":_i(stat.get("baseOnBalls")),
                "k":_i(stat.get("strikeOuts")),"pitches":_i(stat.get("numberOfPitches") or stat.get("pitchesThrown")),
                "gs":gs,
            })
        out=sorted(out,key=lambda x:x.get("date") or "",reverse=True)
        # Prefer explicit starts if available, otherwise recent appearances.
        starts=[x for x in out if x.get("gs",0)>0]
        return starts if starts else out
    except Exception:
        return []


def _recent_form(player_id, season, n):
    rows=_pitcher_game_log(player_id,season)[:n]
    if not rows: return {"status":"PENDING","n":0}
    ip=sum(x["ip"] for x in rows); er=sum(x["er"] for x in rows)
    h=sum(x["h"] for x in rows); hr=sum(x["hr"] for x in rows)
    bb=sum(x["bb"] for x in rows); k=sum(x["k"] for x in rows)
    return {
        "status":"VERIFIED","n":len(rows),"ip":ip,"era":(9*er/ip if ip else None),
        "whip":((h+bb)/ip if ip else None),"h_start":(h/len(rows)),
        "hr_start":(hr/len(rows)),"k_start":(k/len(rows)),"bb_start":(bb/len(rows)),
    }


@st.cache_data(ttl=900, show_spinner=False)
def _split_stats(player_id, season, group, sit_code):
    if not player_id: return {}
    try:
        d=ui._json(f"{ui.MLB_API}/people/{int(player_id)}/stats",{
            "stats":"statSplits","group":group,"season":int(season),"sitCodes":sit_code,"gameType":"R"
        })
        blocks=d.get("stats") or []
        splits=(blocks[0].get("splits") or []) if blocks else []
        return (splits[0].get("stat") or {}) if splits else {}
    except Exception:
        return {}


def _platoon(player_id, starter_id, season, starter_hand):
    # MLB sitCodes: vl = vs left-handed pitcher/batter, vr = vs right-handed.
    code="vl" if str(starter_hand).upper().startswith("L") else "vr"
    hitter=_split_stats(player_id,season,"hitting",code)
    # For pitcher split, same sit code is used as the requested opponent side.
    pitcher=_split_stats(starter_id,season,"pitching",code)
    return hitter,pitcher,code


def _pitch_name(code):
    names={"FF":"4-Seam","SI":"Sinker","FC":"Cutter","SL":"Slider","ST":"Sweeper","CU":"Curve","KC":"Knuckle Curve","CH":"Changeup","FS":"Splitter","SV":"Slurve","CS":"Slow Curve"}
    return names.get(str(code),str(code or "—"))


def _pitch_context(batter_id, starter_id, season, starter_hand):
    sp=feeds._statcast_rows(starter_id,season,"pitcher") if starter_id else {}
    bt=feeds._statcast_rows(batter_id,season,"batter") if batter_id else {}
    if sp.get("status")!="VERIFIED" or bt.get("status")!="VERIFIED":
        return {"status":"PENDING","error":sp.get("error") or bt.get("error") or "Statcast unavailable"}
    sdf=sp.get("frame"); bdf=bt.get("frame")
    if sdf is None or bdf is None or sdf.empty or bdf.empty:
        return {"status":"PENDING","error":"empty Statcast frame"}
    sdf=sdf.copy(); bdf=bdf.copy()
    pt=sdf["pitch_type"].dropna().astype(str)
    counts=Counter(pt); total=sum(counts.values())
    top=counts.most_common(4)
    arsenal=[(p,n,n/total if total else 0.0) for p,n in top]
    # Batter rows versus same pitcher hand when p_throws is present.
    if "p_throws" in bdf.columns and starter_hand in ("L","R"):
        filt=bdf[bdf["p_throws"].astype(str).str.upper()==starter_hand]
        if len(filt)>=20: bdf=filt
    pitch_perf=[]
    for code,n,share in arsenal:
        z=bdf[bdf["pitch_type"].astype(str)==code].copy()
        pitches=len(z)
        if pitches<10:
            pitch_perf.append({"code":code,"pitches":pitches,"xba":None,"ev":None,"hard":None}); continue
        xba=pd.to_numeric(z.get("estimated_ba_using_speedangle"),errors="coerce") if "estimated_ba_using_speedangle" in z else pd.Series(dtype=float)
        ev=pd.to_numeric(z.get("launch_speed"),errors="coerce") if "launch_speed" in z else pd.Series(dtype=float)
        balls=ev.dropna(); hard=(float((balls>=95).mean()) if len(balls)>=5 else None)
        pitch_perf.append({
            "code":code,"pitches":pitches,
            "xba":(float(xba.dropna().mean()) if len(xba.dropna())>=5 else None),
            "ev":(float(balls.mean()) if len(balls)>=5 else None),"hard":hard,
        })
    return {"status":"VERIFIED","arsenal":arsenal,"pitch_perf":pitch_perf,"starter_rows":len(sdf),"batter_rows":len(bdf)}


def _step2_card(player, season):
    pid=v14._safe_int(player.get("id")); spid=v14._safe_int(player.get("opponent_pitcher_id"))
    hand=v14._pitcher_hand(spid) if spid else "—"
    r5=_recent_form(spid,season,5) if spid else {"status":"PENDING","n":0}
    r10=_recent_form(spid,season,10) if spid else {"status":"PENDING","n":0}
    hs,ps,code=_platoon(pid,spid,season,hand) if pid and spid else ({},{},"")
    pc=_pitch_context(pid,spid,season,hand) if pid and spid else {"status":"PENDING","error":"missing player/starter id"}

    h_ab=_i(hs.get("atBats")); h_avg=hs.get("avg"); h_ops=hs.get("ops"); h_hr=_i(hs.get("homeRuns")); h_k=_i(hs.get("strikeOuts"))
    p_bf=_i(ps.get("battersFaced")); p_avg=ps.get("avg"); p_ops=ps.get("ops"); p_hr=_i(ps.get("homeRuns")); p_k=_i(ps.get("strikeOuts"))
    st.markdown(f'''<div class="mx-proj"><div class="mx-top"><div class="mx-engine">🧬 DEEP PITCHER MATCHUP • STEP 2</div><div class="mx-badge">CONTEXT ONLY</div></div>
    <div class="mx-grid">
      <div class="mx-cell"><span>Starter L5 ERA</span><b>{_fmt(r5.get('era'))}</b></div>
      <div class="mx-cell"><span>L5 WHIP</span><b>{_fmt(r5.get('whip'))}</b></div>
      <div class="mx-cell"><span>L5 H / start</span><b>{_fmt(r5.get('h_start'))}</b></div>
      <div class="mx-cell"><span>L5 HR / start</span><b>{_fmt(r5.get('hr_start'))}</b></div>
      <div class="mx-cell"><span>Starter L10 ERA</span><b>{_fmt(r10.get('era'))}</b></div>
      <div class="mx-cell"><span>L10 K / start</span><b>{_fmt(r10.get('k_start'))}</b></div>
      <div class="mx-cell"><span>Hitter vs {ui._esc(hand)}HP AVG</span><b>{_fmt_avg(h_avg)}</b></div>
      <div class="mx-cell"><span>Hitter vs {ui._esc(hand)}HP OPS</span><b>{_fmt_avg(h_ops)}</b></div>
      <div class="mx-cell"><span>Hitter split AB / HR</span><b>{h_ab} / {h_hr}</b></div>
      <div class="mx-cell"><span>Hitter split K</span><b>{h_k}</b></div>
      <div class="mx-cell"><span>Pitcher split AVG allowed</span><b>{_fmt_avg(p_avg)}</b></div>
      <div class="mx-cell"><span>Pitcher split OPS allowed</span><b>{_fmt_avg(p_ops)}</b></div>
      <div class="mx-cell"><span>Pitcher split BF / HR</span><b>{p_bf} / {p_hr}</b></div>
      <div class="mx-cell"><span>Pitcher split K</span><b>{p_k}</b></div>
    </div></div>''',unsafe_allow_html=True)

    st.markdown("#### 🎯 Starter Pitch Mix + Batter Results")
    if pc.get("status")!="VERIFIED":
        st.info(f"Statcast pitch-type context pending — {pc.get('error') or 'feed unavailable'}")
        return
    arsenal=pc.get("arsenal") or []; perf={x['code']:x for x in pc.get("pitch_perf") or []}
    labels=[]
    for code,n,share in arsenal:
        x=perf.get(code,{})
        parts=[f"**{_pitch_name(code)} {share*100:.0f}%**",f"{n} starter pitches",f"batter sample {x.get('pitches',0)}"]
        if x.get("xba") is not None: parts.append(f"xBA {x['xba']:.3f}")
        if x.get("ev") is not None: parts.append(f"EV {x['ev']:.1f}")
        if x.get("hard") is not None: parts.append(f"HH {x['hard']*100:.0f}%")
        labels.append(" • ".join(parts))
    for line in labels: st.markdown(f"- {line}")
    thin=[x for x in pc.get("pitch_perf") or [] if x.get("pitches",0)<10]
    if thin:
        st.caption("Pitch-type samples under 10 pitches are shown without performance grades. This layer is supporting context only and does not alter the production projection in Step 2.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Preserve Step 1 + all existing player intelligence exactly.
    step1.render_player_layer(games_df,section_header,status_info,team_logo,h)
    if games_df is None or games_df.empty: return
    try:
        gi=int(st.session_state.get("mh12_game",0)); row=games_df.iloc[gi]
        players=v14._all_hitters_v14(row); pi=int(st.session_state.get("mh12_player",0))
        if not players: return
        p=players[max(0,min(pi,len(players)-1))]
        season=int(ui._date_str(row)[:4])
        st.markdown("### 🧬 Pitcher Matchup — Step 2")
        _step2_card(p,season)
        st.caption(f"{VERSION} • recent starter form + L/R splits + verified pitch mix + batter pitch-type context • display-only • production models unchanged")
    except Exception as exc:
        st.caption(f"Step 2 pitcher matchup unavailable: {type(exc).__name__}")
