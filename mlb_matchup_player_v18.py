"""MLB Matchup Explorer player layer V1.8 — named matchup score.

Adds a human-readable batter-vs-starter label and a calibrated 0-100 Pitch
Matchup Score after optional deep Statcast load. Display/context only: production
projection engines and daily ranking formulas remain unchanged.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v14 as v14
import mlb_matchup_player_v15 as step1
import mlb_matchup_player_v16 as v16

VERSION = "MLB Player Intelligence V1.8"


def _finite(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _starter_name(player):
    return str(player.get("opponent_pitcher") or "TBD")


def _hand_label(hand):
    h=str(hand or "—").upper()
    return "LHP" if h.startswith("L") else "RHP" if h.startswith("R") else "Pitcher"


def _fast_payload(player, season):
    pid=v14._safe_int(player.get("id")); spid=v14._safe_int(player.get("opponent_pitcher_id"))
    hand=v14._pitcher_hand(spid) if spid else "—"
    r5=v16._recent_form(spid,season,5) if spid else {"status":"PENDING","n":0}
    r10=v16._recent_form(spid,season,10) if spid else {"status":"PENDING","n":0}
    hs,ps,_=v16._platoon(pid,spid,season,hand) if pid and spid else ({},{},"")
    return pid,spid,hand,r5,r10,hs,ps


def _fast_step2(player, season):
    pid,spid,hand,r5,r10,hs,ps=_fast_payload(player,season)
    h_ab=v16._i(hs.get("atBats")); h_avg=hs.get("avg"); h_ops=hs.get("ops"); h_hr=v16._i(hs.get("homeRuns")); h_k=v16._i(hs.get("strikeOuts"))
    p_bf=v16._i(ps.get("battersFaced")); p_avg=ps.get("avg"); p_ops=ps.get("ops"); p_hr=v16._i(ps.get("homeRuns")); p_k=v16._i(ps.get("strikeOuts"))
    fast_status="VERIFIED" if r5.get("status")=="VERIFIED" or h_ab or p_bf else "PARTIAL"
    hitter=ui._esc(player.get("name") or "Hitter"); starter=ui._esc(_starter_name(player)); side=_hand_label(hand)
    st.markdown(f'''<div class="mx-proj">
      <div class="mx-top"><div class="mx-engine">⚡ {hitter} vs {starter} ({side})</div><div class="mx-badge">{fast_status}</div></div>
      <div class="rk-details" style="margin:3px 0 13px 0">Platoon view: <b>{hitter} vs {side}</b> • starter recent form + handedness splits</div>
      <div class="mx-grid">
        <div class="mx-cell"><span>Starter L5 ERA</span><b>{v16._fmt(r5.get('era'))}</b></div>
        <div class="mx-cell"><span>L5 WHIP</span><b>{v16._fmt(r5.get('whip'))}</b></div>
        <div class="mx-cell"><span>L5 H / start</span><b>{v16._fmt(r5.get('h_start'))}</b></div>
        <div class="mx-cell"><span>L5 HR / start</span><b>{v16._fmt(r5.get('hr_start'))}</b></div>
        <div class="mx-cell"><span>Starter L10 ERA</span><b>{v16._fmt(r10.get('era'))}</b></div>
        <div class="mx-cell"><span>L10 K / start</span><b>{v16._fmt(r10.get('k_start'))}</b></div>
        <div class="mx-cell"><span>{hitter} vs {side} AVG</span><b>{v16._fmt_avg(h_avg)}</b></div>
        <div class="mx-cell"><span>{hitter} vs {side} OPS</span><b>{v16._fmt_avg(h_ops)}</b></div>
        <div class="mx-cell"><span>Hitter split AB / HR</span><b>{h_ab} / {h_hr}</b></div>
        <div class="mx-cell"><span>Hitter split K</span><b>{h_k}</b></div>
        <div class="mx-cell"><span>{starter} AVG allowed</span><b>{v16._fmt_avg(p_avg)}</b></div>
        <div class="mx-cell"><span>{starter} OPS allowed</span><b>{v16._fmt_avg(p_ops)}</b></div>
        <div class="mx-cell"><span>Pitcher split BF / HR</span><b>{p_bf} / {p_hr}</b></div>
        <div class="mx-cell"><span>Pitcher split K</span><b>{p_k}</b></div>
      </div>
    </div>''',unsafe_allow_html=True)
    if r5.get("status")!="VERIFIED":
        st.caption("Recent starter-form feed is partial/pending; available platoon context is shown without guessing missing values.")
    return pid,spid,hand,r5,hs,ps


def _deep_key(player, season):
    return f"mx_step2_deep_v18_{int(player.get('id') or 0)}_{int(player.get('opponent_pitcher_id') or 0)}_{int(season)}"


def _platoon_component(hs, ps):
    h_ops=_finite(hs.get("ops")); p_ops=_finite(ps.get("ops"))
    h_ab=v16._i(hs.get("atBats")); p_bf=v16._i(ps.get("battersFaced"))
    vals=[]
    if h_ops is not None:
        vals.append(_clamp((h_ops-.720)/.260,-1,1) * min(1.0,h_ab/120.0))
    if p_ops is not None:
        vals.append(_clamp((p_ops-.720)/.260,-1,1) * min(1.0,p_bf/160.0))
    return (sum(vals)/len(vals) if vals else 0.0), h_ab, p_bf


def _form_component(r5):
    era=_finite(r5.get("era")); whip=_finite(r5.get("whip"))
    vals=[]
    if era is not None: vals.append(_clamp((era-4.20)/2.7,-1,1))
    if whip is not None: vals.append(_clamp((whip-1.30)/.45,-1,1))
    return sum(vals)/len(vals) if vals else 0.0


def _pitch_component(pc):
    arsenal=pc.get("arsenal") or []
    perf={x.get("code"):x for x in pc.get("pitch_perf") or []}
    num=den=rel_num=0.0
    for code,_,share in arsenal:
        x=perf.get(code,{})
        n=int(x.get("pitches") or 0)
        if n<15: continue
        reliability=min(1.0,n/45.0)
        signals=[]
        xba=_finite(x.get("xba")); ev=_finite(x.get("ev")); hard=_finite(x.get("hard"))
        if xba is not None: signals.append(_clamp((xba-.260)/.115,-1,1))
        if ev is not None: signals.append(_clamp((ev-88.0)/7.0,-1,1))
        if hard is not None: signals.append(_clamp((hard-.38)/.24,-1,1))
        if not signals: continue
        local=sum(signals)/len(signals)
        w=float(share)*reliability
        num+=local*w; den+=w; rel_num+=float(share)*reliability
    return (num/den if den else 0.0), _clamp(rel_num/.70 if rel_num else 0.0,0,1)


def _matchup_score(r5, hs, ps, pc):
    platoon,h_ab,p_bf=_platoon_component(hs,ps)
    form=_form_component(r5)
    pitch,pitch_rel=_pitch_component(pc)
    # Score centered at 50. Pitch mix matters most only when sample reliability earns it.
    raw=50.0 + 13.0*platoon + 7.0*form + 18.0*pitch*pitch_rel
    score=int(round(_clamp(raw,20,80)))
    if score>=65: label="FAVORABLE"
    elif score>=56: label="SLIGHT EDGE"
    elif score>=45: label="NEUTRAL"
    elif score>=36: label="TOUGH"
    else: label="VERY TOUGH"
    # Overall reliability combines split sample and pitch coverage.
    split_rel=min(1.0,max(h_ab/120.0,p_bf/160.0)) if (h_ab or p_bf) else 0.0
    reliability=int(round(100*_clamp(.45*split_rel+.55*pitch_rel,0,1)))
    return score,label,reliability,platoon,form,pitch,pitch_rel


def _deep_pitch_panel(player, season, pid, spid, hand, r5, hs, ps):
    key=_deep_key(player,season); loaded=bool(st.session_state.get(key,False))
    c1,c2=st.columns([2,1])
    with c1:
        if st.button("🎯 LOAD DEEP PITCH MATCHUP SCORE",key=key+"_btn",use_container_width=True):
            st.session_state[key]=True; loaded=True
    with c2:
        if loaded and st.button("✖️ HIDE DEEP DATA",key=key+"_hide",use_container_width=True):
            st.session_state[key]=False; loaded=False
    if not loaded:
        st.info("⚡ Fast named matchup is ready. Deep Statcast score is optional so player switching stays quick.")
        return
    with st.spinner("Loading cached Statcast pitch matchup…"):
        pc=v16._pitch_context(pid,spid,season,hand) if pid and spid else {"status":"PENDING","error":"missing player/starter id"}
    hitter=str(player.get("name") or "Hitter"); starter=_starter_name(player); side=_hand_label(hand)
    st.markdown(f"#### 🎯 {hitter} vs {starter} ({side}) — Pitch Matchup")
    if pc.get("status")!="VERIFIED":
        st.warning(f"Deep Statcast pending — {pc.get('error') or 'feed unavailable'}. Fast matchup data remains valid.")
        return
    score,label,reliability,plat,form,pitch,pitch_rel=_matchup_score(r5,hs,ps,pc)
    st.markdown(f'''<div class="mx-proj"><div class="mx-top"><div class="mx-engine">🧠 PITCH MATCHUP SCORE</div><div class="mx-badge">{ui._esc(label)}</div></div>
      <div style="font-size:46px;font-weight:900;line-height:1.05;margin:8px 0">{score}<span style="font-size:20px;color:#8ea2b9">/100</span></div>
      <div class="rk-details">{ui._esc(hitter)} vs {ui._esc(side)} • specifically vs {ui._esc(starter)} • reliability {reliability}%</div>
      <div class="mx-grid" style="margin-top:12px">
        <div class="mx-cell"><span>Platoon component</span><b>{plat:+.2f}</b></div>
        <div class="mx-cell"><span>Starter-form component</span><b>{form:+.2f}</b></div>
        <div class="mx-cell"><span>Pitch-type component</span><b>{pitch:+.2f}</b></div>
        <div class="mx-cell"><span>Pitch coverage reliability</span><b>{pitch_rel*100:.0f}%</b></div>
      </div></div>''',unsafe_allow_html=True)
    arsenal=pc.get("arsenal") or []; perf={x['code']:x for x in pc.get("pitch_perf") or []}
    for code,n,share in arsenal:
        x=perf.get(code,{})
        parts=[f"**{v16._pitch_name(code)} {share*100:.0f}%**",f"{n} starter pitches",f"{hitter} sample {x.get('pitches',0)}"]
        if x.get("xba") is not None: parts.append(f"xBA {x['xba']:.3f}")
        if x.get("ev") is not None: parts.append(f"EV {x['ev']:.1f}")
        if x.get("hard") is not None: parts.append(f"HH {x['hard']*100:.0f}%")
        st.markdown("- "+" • ".join(parts))
    st.caption("Score is context-only in V1.8. It does not change 1+ Hit or other production probabilities yet. Pitch-type samples under 15 pitches receive no performance weight.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    step1.render_player_layer(games_df,section_header,status_info,team_logo,h)
    if games_df is None or games_df.empty: return
    try:
        gi=int(st.session_state.get("mh12_game",0)); row=games_df.iloc[gi]
        players=v14._all_hitters_v14(row); pi=int(st.session_state.get("mh12_player",0))
        if not players: return
        p=players[max(0,min(pi,len(players)-1))]; season=int(ui._date_str(row)[:4])
        st.markdown("### 🧬 Pitcher Matchup — Step 2")
        pid,spid,hand,r5,hs,ps=_fast_step2(p,season)
        _deep_pitch_panel(p,season,pid,spid,hand,r5,hs,ps)
        st.caption(f"{VERSION} • named batter-vs-starter matchup • 0-100 deep pitch score • split/pitch sample reliability gates • display-only • production models unchanged")
    except Exception as exc:
        st.caption(f"Step 2 named matchup unavailable: {type(exc).__name__}: {str(exc)[:100]}")
