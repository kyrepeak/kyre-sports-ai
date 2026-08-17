"""MLB Matchup Explorer player layer V1.7 — Step 2 speed calibration.

Fast MLB recent-form + platoon context renders immediately. Expensive Baseball
Savant pitch-mix work is lazy-loaded by button and cached. Display/context only;
production projections and rankings are unchanged.
"""
from __future__ import annotations

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v14 as v14
import mlb_matchup_player_v15 as step1
import mlb_matchup_player_v16 as v16

VERSION = "MLB Player Intelligence V1.7"


def _fast_step2(player, season):
    pid=v14._safe_int(player.get("id")); spid=v14._safe_int(player.get("opponent_pitcher_id"))
    hand=v14._pitcher_hand(spid) if spid else "—"
    r5=v16._recent_form(spid,season,5) if spid else {"status":"PENDING","n":0}
    r10=v16._recent_form(spid,season,10) if spid else {"status":"PENDING","n":0}
    hs,ps,_=v16._platoon(pid,spid,season,hand) if pid and spid else ({},{},"")

    h_ab=v16._i(hs.get("atBats")); h_avg=hs.get("avg"); h_ops=hs.get("ops"); h_hr=v16._i(hs.get("homeRuns")); h_k=v16._i(hs.get("strikeOuts"))
    p_bf=v16._i(ps.get("battersFaced")); p_avg=ps.get("avg"); p_ops=ps.get("ops"); p_hr=v16._i(ps.get("homeRuns")); p_k=v16._i(ps.get("strikeOuts"))

    fast_status = "VERIFIED" if r5.get("status")=="VERIFIED" or h_ab or p_bf else "PARTIAL"
    st.markdown(f'''<div class="mx-proj"><div class="mx-top"><div class="mx-engine">⚡ FAST PITCHER MATCHUP • STEP 2</div><div class="mx-badge">{fast_status}</div></div>
    <div class="mx-grid">
      <div class="mx-cell"><span>Starter L5 ERA</span><b>{v16._fmt(r5.get('era'))}</b></div>
      <div class="mx-cell"><span>L5 WHIP</span><b>{v16._fmt(r5.get('whip'))}</b></div>
      <div class="mx-cell"><span>L5 H / start</span><b>{v16._fmt(r5.get('h_start'))}</b></div>
      <div class="mx-cell"><span>L5 HR / start</span><b>{v16._fmt(r5.get('hr_start'))}</b></div>
      <div class="mx-cell"><span>Starter L10 ERA</span><b>{v16._fmt(r10.get('era'))}</b></div>
      <div class="mx-cell"><span>L10 K / start</span><b>{v16._fmt(r10.get('k_start'))}</b></div>
      <div class="mx-cell"><span>Hitter vs {ui._esc(hand)}HP AVG</span><b>{v16._fmt_avg(h_avg)}</b></div>
      <div class="mx-cell"><span>Hitter vs {ui._esc(hand)}HP OPS</span><b>{v16._fmt_avg(h_ops)}</b></div>
      <div class="mx-cell"><span>Hitter split AB / HR</span><b>{h_ab} / {h_hr}</b></div>
      <div class="mx-cell"><span>Hitter split K</span><b>{h_k}</b></div>
      <div class="mx-cell"><span>Pitcher split AVG allowed</span><b>{v16._fmt_avg(p_avg)}</b></div>
      <div class="mx-cell"><span>Pitcher split OPS allowed</span><b>{v16._fmt_avg(p_ops)}</b></div>
      <div class="mx-cell"><span>Pitcher split BF / HR</span><b>{p_bf} / {p_hr}</b></div>
      <div class="mx-cell"><span>Pitcher split K</span><b>{p_k}</b></div>
    </div></div>''',unsafe_allow_html=True)

    if r5.get("status")!="VERIFIED":
        st.caption("Recent starter-form feed is partial/pending; available platoon context is still shown without guessing missing values.")
    return pid,spid,hand


def _deep_key(player, season):
    return f"mx_step2_deep_{int(player.get('id') or 0)}_{int(player.get('opponent_pitcher_id') or 0)}_{int(season)}"


def _deep_pitch_panel(player, season, pid, spid, hand):
    key=_deep_key(player,season)
    loaded=bool(st.session_state.get(key,False))
    c1,c2=st.columns([2,1])
    with c1:
        if st.button("🎯 LOAD DEEP PITCH MIX + STATCAST",key=key+"_btn",use_container_width=True):
            st.session_state[key]=True
            loaded=True
    with c2:
        if loaded and st.button("✖️ HIDE DEEP DATA",key=key+"_hide",use_container_width=True):
            st.session_state[key]=False
            loaded=False
    if not loaded:
        st.info("⚡ Fast matchup is ready. Deep pitch-mix/Statcast is optional so player switching stays quick.")
        return

    with st.spinner("Loading cached Statcast pitch mix…"):
        pc=v16._pitch_context(pid,spid,season,hand) if pid and spid else {"status":"PENDING","error":"missing player/starter id"}
    st.markdown("#### 🎯 Starter Pitch Mix + Batter Results")
    if pc.get("status")!="VERIFIED":
        st.warning(f"Deep Statcast pending — {pc.get('error') or 'feed unavailable'}. Fast Step 2 data remains valid.")
        return
    arsenal=pc.get("arsenal") or []; perf={x['code']:x for x in pc.get("pitch_perf") or []}
    for code,n,share in arsenal:
        x=perf.get(code,{})
        parts=[f"**{v16._pitch_name(code)} {share*100:.0f}%**",f"{n} starter pitches",f"batter sample {x.get('pitches',0)}"]
        if x.get("xba") is not None: parts.append(f"xBA {x['xba']:.3f}")
        if x.get("ev") is not None: parts.append(f"EV {x['ev']:.1f}")
        if x.get("hard") is not None: parts.append(f"HH {x['hard']*100:.0f}%")
        st.markdown("- "+" • ".join(parts))
    thin=[x for x in pc.get("pitch_perf") or [] if x.get("pitches",0)<15]
    if thin:
        st.caption("Pitch-type samples under 15 pitches are informational only. Deep Step 2 remains display/context-only and does not modify production probabilities.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Step 1 and original player page render first; no Savant requests here.
    step1.render_player_layer(games_df,section_header,status_info,team_logo,h)
    if games_df is None or games_df.empty: return
    try:
        gi=int(st.session_state.get("mh12_game",0)); row=games_df.iloc[gi]
        players=v14._all_hitters_v14(row); pi=int(st.session_state.get("mh12_player",0))
        if not players: return
        p=players[max(0,min(pi,len(players)-1))]
        season=int(ui._date_str(row)[:4])
        st.markdown("### 🧬 Pitcher Matchup — Step 2")
        pid,spid,hand=_fast_step2(p,season)
        _deep_pitch_panel(p,season,pid,spid,hand)
        st.caption(f"{VERSION} • fast MLB recent-form/platoon data first • optional lazy Statcast pitch mix • stronger 15-pitch deep-sample gate • production models unchanged")
    except Exception as exc:
        st.caption(f"Step 2 pitcher matchup unavailable: {type(exc).__name__}: {str(exc)[:100]}")
