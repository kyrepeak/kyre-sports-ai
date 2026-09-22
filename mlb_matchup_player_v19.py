"""MLB Matchup Explorer player layer V1.9 — Step 3 Matchup Verdict.

Preserves Steps 1-2 and adds a conservative context-only verdict combining BvP,
platoon, starter recent form, and optional deep pitch-matchup intelligence.
Production projections and rankings remain unchanged.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v14 as v14
import mlb_matchup_player_v15 as step1
import mlb_matchup_player_v16 as v16
import mlb_matchup_player_v18 as v18

VERSION = "MLB Player Intelligence V1.9"


def _finite(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _bvp_component(player, season):
    pid=v14._safe_int(player.get("id")); spid=v14._safe_int(player.get("opponent_pitcher_id"))
    bvp=v14._bvp(pid,spid,season) if pid and spid else {}
    ab=step1._i(bvp.get("atBats")); hits=step1._i(bvp.get("hits")); hr=step1._i(bvp.get("homeRuns")); k=step1._i(bvp.get("strikeOuts"))
    avg=_finite(bvp.get("avg")); ops=_finite(bvp.get("ops"))
    if avg is None and ab: avg=hits/ab
    if ab<=0:
        return 0.0,0.0,{"ab":0,"hits":0,"avg":None,"ops":None,"hr":0,"k":0}
    # BvP is deliberately capped and sample-damped. Even a large sample remains context.
    signals=[]
    if avg is not None: signals.append(_clamp((avg-.255)/.145,-1,1))
    if ops is not None: signals.append(_clamp((ops-.720)/.360,-1,1))
    raw=sum(signals)/len(signals) if signals else 0.0
    rel=min(1.0,ab/30.0)
    comp=raw*rel
    return comp,rel,{"ab":ab,"hits":hits,"avg":avg,"ops":ops,"hr":hr,"k":k}


def _verdict_label(score):
    if score>=68: return "STRONG MATCHUP"
    if score>=59: return "FAVORABLE"
    if score>=46: return "NEUTRAL"
    if score>=37: return "TOUGH"
    return "AVOID / VERY TOUGH"


def _verdict_score(player, season):
    pid,spid,hand,r5,_,hs,ps=v18._fast_payload(player,season)
    bvp,bvp_rel,bvp_info=_bvp_component(player,season)
    platoon,h_ab,p_bf=v18._platoon_component(hs,ps)
    form=v18._form_component(r5)

    deep_loaded=bool(st.session_state.get(v18._deep_key(player,season),False))
    pitch=0.0; pitch_rel=0.0; pitch_score=None; pitch_label="NOT LOADED"
    if deep_loaded and pid and spid:
        pc=v16._pitch_context(pid,spid,season,hand)
        if pc.get("status")=="VERIFIED":
            pitch,pitch_rel=v18._pitch_component(pc)
            pitch_score,pitch_label,_,_,_,_,_=v18._matchup_score(r5,hs,ps,pc)

    # Base weights: BvP deliberately smallest. Missing deep pitch weight is not replaced
    # by BvP; the result simply has lower confidence and leans on verified fast context.
    weighted=0.0; denom=0.0
    parts=[]
    def add(name,value,weight,reliability):
        nonlocal weighted,denom
        effective=weight*_clamp(reliability,0,1)
        if effective<=0: return
        weighted+=value*effective; denom+=effective
        parts.append((name,value,effective))

    add("BvP",bvp,0.15,bvp_rel)
    split_rel=min(1.0,max(h_ab/120.0,p_bf/160.0)) if (h_ab or p_bf) else 0.0
    add("Platoon",platoon,0.30,split_rel)
    form_rel=min(1.0,float(r5.get("n") or 0)/5.0) if r5.get("status")=="VERIFIED" else 0.0
    add("Starter form",form,0.25,form_rel)
    add("Pitch mix",pitch,0.30,pitch_rel if deep_loaded else 0.0)

    combined=(weighted/denom) if denom else 0.0
    # Context verdict intentionally compressed to avoid false certainty.
    score=int(round(_clamp(50.0+22.0*combined,25,75)))
    label=_verdict_label(score)

    # Reliability reflects actual evidence coverage, not just number of modules present.
    max_weight=.15+.30+.25+.30
    evidence_weight=denom
    reliability=int(round(100*_clamp(evidence_weight/max_weight,0,1)))
    return {
        "score":score,"label":label,"reliability":reliability,"bvp":bvp,"bvp_rel":bvp_rel,
        "bvp_info":bvp_info,"platoon":platoon,"split_rel":split_rel,"form":form,
        "form_rel":form_rel,"pitch":pitch,"pitch_rel":pitch_rel,"deep_loaded":deep_loaded,
        "pitch_score":pitch_score,"pitch_label":pitch_label,"hand":hand,
    }


def _render_verdict(player, season):
    d=_verdict_score(player,season)
    hitter=str(player.get("name") or "Hitter"); starter=v18._starter_name(player); side=v18._hand_label(d.get("hand"))
    b=d["bvp_info"]
    bvp_text="No BvP history" if not b.get("ab") else f"{b['hits']}/{b['ab']} • AVG {step1._fmt3(b.get('avg'))}"
    pitch_text=(f"{d['pitch_score']}/100 • {d['pitch_label']}" if d.get("pitch_score") is not None else "Not loaded")
    st.markdown("### 🧭 Matchup Verdict — Step 3")
    st.markdown(f'''<div class="mx-proj">
      <div class="mx-top"><div class="mx-engine">🧭 {ui._esc(hitter)} vs {ui._esc(starter)} ({ui._esc(side)})</div><div class="mx-badge">{ui._esc(d['label'])}</div></div>
      <div style="font-size:46px;font-weight:900;line-height:1.05;margin:8px 0">{d['score']}<span style="font-size:20px;color:#8ea2b9">/100</span></div>
      <div class="rk-details">Overall matchup verdict • evidence reliability {d['reliability']}% • context-only</div>
      <div class="mx-grid" style="margin-top:12px">
        <div class="mx-cell"><span>BvP history</span><b>{ui._esc(bvp_text)}</b></div>
        <div class="mx-cell"><span>BvP component</span><b>{d['bvp']:+.2f}</b></div>
        <div class="mx-cell"><span>Platoon component</span><b>{d['platoon']:+.2f}</b></div>
        <div class="mx-cell"><span>Starter-form component</span><b>{d['form']:+.2f}</b></div>
        <div class="mx-cell"><span>Deep pitch matchup</span><b>{ui._esc(pitch_text)}</b></div>
        <div class="mx-cell"><span>Pitch component</span><b>{d['pitch']:+.2f}</b></div>
        <div class="mx-cell"><span>Split reliability</span><b>{d['split_rel']*100:.0f}%</b></div>
        <div class="mx-cell"><span>Pitch reliability</span><b>{d['pitch_rel']*100:.0f}%</b></div>
      </div>
    </div>''',unsafe_allow_html=True)
    if not d.get("deep_loaded"):
        st.info("🎯 Load the Step 2 Deep Pitch Matchup Score above to add verified pitch-mix evidence to this verdict. Until then, Step 3 uses BvP + platoon + starter form only.")
    if b.get("ab",0)<10 and b.get("ab",0)>0:
        st.caption(f"BvP is only {b['ab']} AB and receives heavily reduced weight. It cannot override the larger matchup evidence.")
    st.caption("Step 3 is a research verdict, not a production probability adjustment. No 1+ Hit, HR, Total Bases, RBI, Runs or H+R+RBI projection is changed in V1.9.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Preserve the full Step 1 + Step 2 experience first.
    v18.render_player_layer(games_df,section_header,status_info,team_logo,h)
    if games_df is None or games_df.empty: return
    try:
        gi=int(st.session_state.get("mh12_game",0)); row=games_df.iloc[gi]
        players=v14._all_hitters_v14(row); pi=int(st.session_state.get("mh12_player",0))
        if not players: return
        p=players[max(0,min(pi,len(players)-1))]; season=int(ui._date_str(row)[:4])
        _render_verdict(p,season)
        st.caption(f"{VERSION} • Step 3 verdict = BvP + platoon + starter form + optional verified pitch matchup • reliability-weighted • context-only")
    except Exception as exc:
        st.caption(f"Step 3 matchup verdict unavailable: {type(exc).__name__}: {str(exc)[:120]}")
