"""MLB Matchup Explorer player layer V2.1 — Step 5 Final Player Intelligence.

Adds an executive-summary card above Steps 1-4 while preserving the detailed
audit trail and the existing Step 4 Explorer-only 1+ Hit calibration.
"""
from __future__ import annotations

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v14 as v14
import mlb_matchup_player_v19 as v19
import mlb_matchup_player_v20 as v20

VERSION = "MLB Player Intelligence V2.1"


def _grade(final_p, verdict_score, reliability):
    """Readable final grade; probability is primary, matchup verdict is secondary."""
    p=float(final_p or 0.0)*100.0
    rel=max(0.0,min(1.0,float(reliability or 0)/100.0))
    # Small summary-only matchup influence. Step 4 already performs production calibration.
    composite=p + ((float(verdict_score or 50)-50.0)/25.0)*1.5*rel
    if composite >= 75: return "ELITE", composite
    if composite >= 67: return "STRONG", composite
    if composite >= 59: return "NEUTRAL", composite
    if composite >= 51: return "TOUGH", composite
    return "AVOID", composite


def _render_step5(slot, games_df):
    player,row=v20._selected_player(games_df)
    if not player or row is None:
        return
    info=v20._current_step4_info(games_df)
    if not info:
        return
    try:
        season=int(ui._date_str(row)[:4])
        verdict=v19._verdict_score(player,season)
    except Exception:
        return

    final=float(info.get("final") or 0.0)
    baseline=float(info.get("baseline") or 0.0)
    delta=float(info.get("delta") or 0.0)
    grade,composite=_grade(final,verdict.get("score"),verdict.get("reliability"))
    b=verdict.get("bvp_info") or {}
    bvp=("No history" if not b.get("ab") else f"{b.get('hits',0)}/{b.get('ab',0)} • AVG {float(b.get('avg') or 0):.3f}")
    deep=bool(verdict.get("deep_loaded"))
    pitch=(f"{verdict.get('pitch_score')}/100 • {verdict.get('pitch_label')}" if verdict.get("pitch_score") is not None else "Not loaded")
    starter=str(player.get("opponent_pitcher") or "TBD")
    hand=str(verdict.get("hand") or "—")
    hand_label={"R":"RHP","L":"LHP"}.get(hand,hand)
    rel=int(verdict.get("reliability") or 0)
    direction="+" if delta>0 else ""
    lineup=str(player.get("source") or "")

    with slot.container():
        st.markdown("### 🧠 Final Player Intelligence — Step 5")
        st.markdown(f'''<div class="mx-proj">
          <div class="mx-top"><div class="mx-engine">🧠 {ui._esc(player.get('name'))} vs {ui._esc(starter)} ({ui._esc(hand_label)})</div><div class="mx-badge">{ui._esc(grade)}</div></div>
          <div style="display:flex;align-items:end;gap:14px;margin:8px 0 12px"><div style="font-size:48px;font-weight:900;line-height:1">{final*100:.1f}%</div><div class="rk-details" style="padding-bottom:5px">FINAL EXPLORER 1+ HIT • {ui._esc('DEEP VERIFIED' if deep else 'FAST ONLY')}</div></div>
          <div class="mx-grid">
            <div class="mx-cell"><span>Final grade</span><b>{ui._esc(grade)}</b></div>
            <div class="mx-cell"><span>Matchup verdict</span><b>{verdict.get('score')}/100 • {ui._esc(verdict.get('label'))}</b></div>
            <div class="mx-cell"><span>Evidence reliability</span><b>{rel}%</b></div>
            <div class="mx-cell"><span>Step 4 movement</span><b>{direction}{delta*100:.1f} pts</b></div>
            <div class="mx-cell"><span>Pre-matchup 1+ Hit</span><b>{baseline*100:.1f}%</b></div>
            <div class="mx-cell"><span>BvP</span><b>{ui._esc(bvp)}</b></div>
            <div class="mx-cell"><span>Platoon component</span><b>{float(verdict.get('platoon') or 0):+.2f}</b></div>
            <div class="mx-cell"><span>Starter-form component</span><b>{float(verdict.get('form') or 0):+.2f}</b></div>
            <div class="mx-cell"><span>Deep pitch matchup</span><b>{ui._esc(pitch)}</b></div>
            <div class="mx-cell"><span>Lineup status</span><b>{ui._esc(lineup)}</b></div>
          </div>
        </div>''',unsafe_allow_html=True)
        st.caption("Step 5 is the summary layer: final calibrated 1+ Hit probability + matchup evidence in one card. Steps 1-4 remain below for full detail and auditability.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Reserve the summary position first, then let Steps 1-4 render and update lazy deep state.
    step5_slot=st.empty()
    v20.render_player_layer(games_df,section_header,status_info,team_logo,h)
    # Fill the reserved top slot using the synchronized Step 4/Step 3 state.
    _render_step5(step5_slot,games_df)
    st.caption(f"{VERSION} • Step 5 executive summary • final Explorer 1+ Hit + BvP/platoon/starter/pitch/verdict context • Steps 1-4 preserved")
