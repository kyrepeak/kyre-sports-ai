"""MLB Matchup Explorer player layer V2.0 — Step 4 Production Calibration.

Preserves Steps 1-3 and applies a tightly capped, reliability-weighted matchup
verdict adjustment to the Matchup Explorer's already sample-calibrated 1+ Hit
probability only. Standalone production engines and all other markets remain
unchanged.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v13 as shell13
import mlb_matchup_hub_v14 as v14
import mlb_matchup_player_v19 as v19

VERSION = "MLB Player Intelligence V2.0"


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _finite(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _calibration_from_verdict(verdict):
    """Return probability-point delta for 1+ Hit only.

    Design rules:
    - neutral 50/100 => zero movement
    - reliability directly damps the move
    - low-reliability verdicts barely move the projection
    - deep data not loaded => reduced cap
    - absolute final cap is 2.5 percentage points
    """
    score=float(verdict.get("score") or 50.0)
    reliability=_clamp(float(verdict.get("reliability") or 0.0)/100.0,0.0,1.0)
    centered=_clamp((score-50.0)/25.0,-1.0,1.0)

    # Require some real evidence before production movement begins.
    evidence_gate=_clamp((reliability-0.25)/0.55,0.0,1.0)
    deep_loaded=bool(verdict.get("deep_loaded"))
    max_move=0.025 if deep_loaded else 0.0125

    delta=centered * max_move * evidence_gate
    return _clamp(delta,-0.025,0.025)


def _selected_player(games_df):
    if games_df is None or games_df.empty:
        return None,None
    gi=int(st.session_state.get("mh12_game",0))
    gi=max(0,min(gi,len(games_df)-1))
    row=games_df.iloc[gi]
    players=v14._all_hitters_v14(row)
    if not players:
        return None,None
    pi=int(st.session_state.get("mh12_player",0))
    pi=max(0,min(pi,len(players)-1))
    return players[pi],row


def _apply_hit_calibration(rr, games_df):
    player,row=_selected_player(games_df)
    if not player or row is None:
        return rr,None
    try:
        season=int(ui._date_str(row)[:4])
        verdict=v19._verdict_score(player,season)
        s=dict(rr.get("sim") or {})
        baseline=_finite(s.get("p_one_plus"))
        if baseline is None:
            return rr,None

        delta=_calibration_from_verdict(verdict)
        final=_clamp(baseline+delta,0.001,0.999)
        s["p_one_plus_pre_matchup"] = baseline
        s["p_one_plus"] = final
        out=dict(rr); out["sim"] = s
        info={
            "player":str(player.get("name") or "Hitter"),
            "starter":str(player.get("opponent_pitcher") or "TBD"),
            "baseline":baseline,"final":final,"delta":delta,
            "score":int(verdict.get("score") or 50),
            "label":str(verdict.get("label") or "NEUTRAL"),
            "reliability":int(verdict.get("reliability") or 0),
            "deep_loaded":bool(verdict.get("deep_loaded")),
        }
        st.session_state["mh_step4_last"] = info
        return out,info
    except Exception:
        return rr,None


def _render_step4_summary(games_df):
    player,row=_selected_player(games_df)
    if not player or row is None:
        return
    info=st.session_state.get("mh_step4_last") or {}
    if str(info.get("player")) != str(player.get("name")):
        return

    delta_pp=float(info.get("delta") or 0.0)*100.0
    baseline=float(info.get("baseline") or 0.0)*100.0
    final=float(info.get("final") or 0.0)*100.0
    direction="+" if delta_pp>0 else ""
    badge="BOOST" if delta_pp>.05 else "DOWNGRADE" if delta_pp<-.05 else "NO MATERIAL CHANGE"

    st.markdown("### 🧪 Production Calibration — Step 4")
    st.markdown(f'''<div class="mx-proj">
      <div class="mx-top"><div class="mx-engine">🧪 1+ HIT MATCHUP CALIBRATION</div><div class="mx-badge">{ui._esc(badge)}</div></div>
      <div class="rk-details" style="margin:4px 0 12px 0">{ui._esc(info.get('player'))} vs {ui._esc(info.get('starter'))} • Step 3 {ui._esc(info.get('label'))} {info.get('score')}/100 • evidence reliability {info.get('reliability')}%</div>
      <div class="mx-grid">
        <div class="mx-cell"><span>Pre-matchup 1+ Hit</span><b>{baseline:.1f}%</b></div>
        <div class="mx-cell"><span>Step 4 adjustment</span><b>{direction}{delta_pp:.1f} pts</b></div>
        <div class="mx-cell"><span>Final Explorer 1+ Hit</span><b>{final:.1f}%</b></div>
        <div class="mx-cell"><span>Adjustment cap</span><b>±2.5 pts</b></div>
      </div>
    </div>''',unsafe_allow_html=True)
    if not info.get("deep_loaded"):
        st.caption("Deep pitch data is not loaded, so Step 4 uses the reduced ±1.25-point cap. Load Step 2 deep data to make the full reliability-gated calibration eligible.")
    else:
        st.caption("Deep pitch data is loaded. The full Step 4 cap is available, but actual movement is still damped by evidence reliability and distance from a neutral 50/100 verdict.")
    st.caption("Step 4 modifies only the Matchup Explorer 1+ Hit display. Standalone 1+ Hit V13.3 and HR/TB/RBI/Runs/H+R+RBI engines remain unchanged.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # v13's sample-calibration wrapper eventually calls this renderer. Intercept it
    # here so Step 4 occurs AFTER sample shrinkage, not before it.
    original=shell13._ORIG_HIT_RENDER

    def calibrated_renderer(rr, started=False):
        adjusted,_=_apply_hit_calibration(rr,games_df)
        return original(adjusted,started)

    shell13._ORIG_HIT_RENDER=calibrated_renderer
    try:
        v19.render_player_layer(games_df,section_header,status_info,team_logo,h)
        _render_step4_summary(games_df)
        st.caption(f"{VERSION} • Step 4 = reliability-gated matchup calibration for Explorer 1+ Hit only • max ±2.5 pts • standalone engines unchanged")
    finally:
        shell13._ORIG_HIT_RENDER=original
