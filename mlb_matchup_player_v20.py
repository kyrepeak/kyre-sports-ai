"""MLB Matchup Explorer player layer V2.0.1 — Step 4 Production Calibration.

Preserves Steps 1-3 and applies a tightly capped, reliability-weighted matchup
verdict adjustment to the Matchup Explorer's already sample-calibrated 1+ Hit
probability only. Step 4 re-reads the current Step 3 state after Step 2/3 render
so lazy-loaded deep pitch data is synchronized before the final card is shown.
Standalone production engines and all other markets remain unchanged.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v13 as shell13
import mlb_matchup_hub_v14 as v14
import mlb_matchup_player_v19 as v19

VERSION = "MLB Player Intelligence V2.0.1"


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _finite(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _calibration_from_verdict(verdict):
    """Return probability-point delta for Matchup Explorer 1+ Hit only."""
    score=float(verdict.get("score") or 50.0)
    reliability=_clamp(float(verdict.get("reliability") or 0.0)/100.0,0.0,1.0)
    centered=_clamp((score-50.0)/25.0,-1.0,1.0)
    evidence_gate=_clamp((reliability-0.25)/0.55,0.0,1.0)
    deep_loaded=bool(verdict.get("deep_loaded"))
    max_move=0.025 if deep_loaded else 0.0125
    delta=centered * max_move * evidence_gate
    return _clamp(delta,-max_move,max_move)


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
    """Intercept the sample-calibrated hit card.

    Store the post-sample-shrink baseline. An initial Step 4 adjustment is applied
    for the embedded hit card, but the summary is recomputed after Steps 2-3 render
    so lazy deep-data state cannot be stale.
    """
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
            "player_id":v14._safe_int(player.get("id")),
            "starter":str(player.get("opponent_pitcher") or "TBD"),
            "starter_id":v14._safe_int(player.get("opponent_pitcher_id")),
            "season":season,
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


def _current_step4_info(games_df):
    """Recompute Step 4 from the CURRENT Step 3/deep state after page render."""
    player,row=_selected_player(games_df)
    if not player or row is None:
        return None
    prior=st.session_state.get("mh_step4_last") or {}
    if str(prior.get("player")) != str(player.get("name")):
        return None
    baseline=_finite(prior.get("baseline"))
    if baseline is None:
        return None
    try:
        season=int(ui._date_str(row)[:4])
        verdict=v19._verdict_score(player,season)
        delta=_calibration_from_verdict(verdict)
        final=_clamp(baseline+delta,0.001,0.999)
        info={
            **prior,
            "starter":str(player.get("opponent_pitcher") or "TBD"),
            "season":season,
            "baseline":baseline,"final":final,"delta":delta,
            "score":int(verdict.get("score") or 50),
            "label":str(verdict.get("label") or "NEUTRAL"),
            "reliability":int(verdict.get("reliability") or 0),
            "deep_loaded":bool(verdict.get("deep_loaded")),
        }
        st.session_state["mh_step4_last"] = info
        return info
    except Exception:
        return prior or None


def _render_step4_summary(games_df):
    info=_current_step4_info(games_df)
    if not info:
        return

    delta_pp=float(info.get("delta") or 0.0)*100.0
    baseline=float(info.get("baseline") or 0.0)*100.0
    final=float(info.get("final") or 0.0)*100.0
    direction="+" if delta_pp>0 else ""
    badge="BOOST" if delta_pp>.05 else "DOWNGRADE" if delta_pp<-.05 else "NO MATERIAL CHANGE"
    deep_loaded=bool(info.get("deep_loaded"))
    cap_pp=2.5 if deep_loaded else 1.25
    state_label="DEEP VERIFIED" if deep_loaded else "FAST ONLY"

    st.markdown("### 🧪 Production Calibration — Step 4")
    st.markdown(f'''<div class="mx-proj">
      <div class="mx-top"><div class="mx-engine">🧪 1+ HIT MATCHUP CALIBRATION • {state_label}</div><div class="mx-badge">{ui._esc(badge)}</div></div>
      <div class="rk-details" style="margin:4px 0 12px 0">{ui._esc(info.get('player'))} vs {ui._esc(info.get('starter'))} • Step 3 {ui._esc(info.get('label'))} {info.get('score')}/100 • evidence reliability {info.get('reliability')}%</div>
      <div class="mx-grid">
        <div class="mx-cell"><span>Pre-matchup 1+ Hit</span><b>{baseline:.1f}%</b></div>
        <div class="mx-cell"><span>Step 4 adjustment</span><b>{direction}{delta_pp:.1f} pts</b></div>
        <div class="mx-cell"><span>Final Explorer 1+ Hit</span><b>{final:.1f}%</b></div>
        <div class="mx-cell"><span>Active adjustment cap</span><b>±{cap_pp:.2f} pts</b></div>
      </div>
    </div>''',unsafe_allow_html=True)
    if not deep_loaded:
        st.caption("Fast-only calibration is active, so Step 4 uses the reduced ±1.25-point cap. Load Step 2 deep data to unlock the full reliability-gated calibration.")
    else:
        st.caption("✅ Step 2 deep pitch data is loaded and synchronized. Step 4 is using the current deep-aware Step 3 verdict with the full ±2.5-point ceiling; actual movement remains reliability-damped.")
    st.caption("Step 4 modifies only the Matchup Explorer 1+ Hit display. Standalone 1+ Hit V13.3 and HR/TB/RBI/Runs/H+R+RBI engines remain unchanged.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    original=shell13._ORIG_HIT_RENDER

    def calibrated_renderer(rr, started=False):
        adjusted,_=_apply_hit_calibration(rr,games_df)
        return original(adjusted,started)

    shell13._ORIG_HIT_RENDER=calibrated_renderer
    try:
        # Steps 1-3 render first. Any Step 2 lazy-load button updates session state here.
        v19.render_player_layer(games_df,section_header,status_info,team_logo,h)
        # Recompute from current state AFTER Step 2/3 have rendered.
        _render_step4_summary(games_df)
        st.caption(f"{VERSION} • Step 4 synchronized after Step 2/3 render • reliability-gated Explorer 1+ Hit calibration • max ±2.5 pts • standalone engines unchanged")
    finally:
        shell13._ORIG_HIT_RENDER=original
