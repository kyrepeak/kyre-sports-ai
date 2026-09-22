"""MLB Matchup Explorer V2 — Steps 1-5 player intelligence stack.

Step 5 adds starter-arsenal versus hitter pitch-type performance context. It is
descriptive only: frozen V1 Matchup, Daily Top 5, Moneyline, game-level hit
probability, fair odds, simulation and calibration remain untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_pitch_mix_v1 as pitch_mix
import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean
import mlb_matchup_player_v24 as step1
import mlb_matchup_player_v25 as step2
import mlb_matchup_player_v26 as step3
import mlb_matchup_player_v27 as step4

VERSION = "MLB Matchup Intelligence V2 Step 5"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "NONE"
STEP5_ROLE = "PITCH_MIX_CONTEXT_ONLY"


def _esc(value: Any) -> str:
    return ui._esc(value)


def _fmt_avg(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except Exception:
        return "—"


def _fmt_rate(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def _fmt_num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _build_step5(games_df) -> dict[str, Any] | None:
    foundation = step1._build_foundation(games_df)
    if not foundation:
        return None
    player_id = foundation.get("player_id")
    starter_id = foundation.get("starter_id")
    season = foundation.get("season")
    if not player_id or not starter_id or not season:
        return pitch_mix.build_pitch_mix_profile(foundation, None, None)
    pitcher_payload, hitter_payload = pitch_mix.fetch_pitch_mix_inputs(
        int(player_id), int(starter_id), int(season)
    )
    return pitch_mix.build_pitch_mix_profile(
        foundation,
        pitcher_payload,
        hitter_payload,
    )


def _pitch_row_html(row: dict[str, Any]) -> str:
    component = row.get("component")
    component_text = "—" if component is None else f"{float(component):+.2f}"
    return (
        '<div class="mxv2-pitchrow">'
        f'<div><b>{_esc(row.get("name"))}</b><span>{_fmt_rate(row.get("usage"))} usage • {int(row.get("starter_pitches") or 0)} starter pitches</span></div>'
        f'<div><b>{_fmt_avg(row.get("xba"))}</b><span>xBA • {int(row.get("xba_bip") or 0)} BIP</span></div>'
        f'<div><b>{_fmt_rate(row.get("contact_pct"))}</b><span>contact</span></div>'
        f'<div><b>{_fmt_rate(row.get("whiff_pct"))}</b><span>whiff</span></div>'
        f'<div><b>{_fmt_num(row.get("avg_ev"),1)}</b><span>avg EV</span></div>'
        f'<div><b>{_fmt_rate(row.get("hard_hit_pct"))}</b><span>hard-hit</span></div>'
        f'<div><b>{int(row.get("pitches") or 0)}</b><span>hitter pitches</span></div>'
        f'<div><b>{_fmt_rate(row.get("reliability"))}</b><span>sample rel.</span></div>'
        f'<div><b>{component_text}</b><span>component</span></div>'
        '</div>'
    )


def _render_step5(games_df) -> None:
    d = _build_step5(games_df)
    if not d:
        st.warning("Step 5 pitch-mix context is waiting for a verified game and player selection.")
        return

    components = " • ".join(
        f"{name} {earned}/{maximum}"
        for name, (earned, maximum) in (d.get("pitch_mix_data_components") or {}).items()
    )
    score = d.get("pitch_mix_score")
    score_text = f"{int(score)}/100" if score is not None else "—"
    hand = d.get("hand_filter") or {}
    hand_text = (
        f"same-hand history applied ({int(hand.get('rows') or 0)} pitches vs {hand.get('hand')}HP)"
        if hand.get("applied")
        else str(hand.get("reason") or "hand filter pending")
    )
    rows_html = "".join(_pitch_row_html(row) for row in (d.get("pitch_rows") or []))
    if not rows_html:
        rows_html = '<div class="mxv2-row mxv2-muted">Starter arsenal is pending; no pitch-type matchup signal is assumed.</div>'

    st.markdown(
        f'''<div class="mxv2-step mxv2-step5">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 5 • PITCH-MIX MATCHUP</div>
            <div class="mxv2-badge">{_esc(d.get('pitch_mix_data_label'))} • {int(d.get('pitch_mix_data_score') or 0)}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('player_name'))}</b> vs <b>{_esc(d.get('starter_name'))}</b> • starter arsenal mapped to hitter pitch-type results</div>
          <div class="mxv2-status">Pitch-shape family context only • probability impact: NONE • sample reliability gates every pitch-type signal</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini"><span>Pitch-mix index</span><b>{score_text}</b></div>
            <div class="mxv2-mini"><span>Evidence coverage</span><b>{_fmt_rate(d.get('pitch_mix_coverage'))}</b></div>
            <div class="mxv2-mini"><span>Arsenal coverage</span><b>{_fmt_rate(d.get('arsenal_coverage'))}</b></div>
            <div class="mxv2-mini"><span>Weighted xBA</span><b>{_fmt_avg(d.get('weighted_xba'))}</b></div>
            <div class="mxv2-mini"><span>Weighted contact</span><b>{_fmt_rate(d.get('weighted_contact_pct'))}</b></div>
            <div class="mxv2-mini"><span>Weighted whiff</span><b>{_fmt_rate(d.get('weighted_whiff_pct'))}</b></div>
            <div class="mxv2-mini"><span>Weighted EV</span><b>{_fmt_num(d.get('weighted_avg_ev'),1)}</b></div>
            <div class="mxv2-mini"><span>Weighted hard-hit</span><b>{_fmt_rate(d.get('weighted_hard_hit_pct'))}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Pitch-mix verdict</b> • {_esc(d.get('pitch_mix_label'))} • {score_text} • effective evidence coverage {_fmt_rate(d.get('pitch_mix_coverage'))} • descriptive index, not a hit probability.</div>
          <div class="mxv2-row"><b>Handedness filter</b> • {_esc(hand_text)}</div>
          <div class="mxv2-row"><b>Statcast feeds</b> • pitcher {_esc(d.get('pitcher_statcast_status'))} ({int(d.get('pitcher_statcast_rows') or 0)} rows) • hitter {_esc(d.get('hitter_statcast_status'))} ({int(d.get('hitter_statcast_rows') or 0)} rows)</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-pitchhead">STARTER ARSENAL → HITTER RESULTS BY PITCH TYPE</div>
          {rows_html}
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>Sample rules</b> • pitch types below {pitch_mix.PITCH_MIN_SAMPLE} hitter pitches receive zero performance weight • reliability reaches full weight at {pitch_mix.PITCH_FULL_SAMPLE} pitches • starter arsenal is capped at the top {pitch_mix.MAX_ARSENAL_PITCHES} pitch types.</div>
          <div class="mxv2-row mxv2-muted"><b>Data completeness</b> • {_esc(components)}</div>
          <div class="mxv2-row mxv2-muted"><b>Model boundary</b> • Step 5 compares arsenal usage with hitter xBA/contact/whiff/EV/hard-hit by pitch type only. Step 6 handles batted-ball quality; later steps handle environment, bullpen, opportunity and final probability.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if d.get("pitcher_statcast_status") != "VERIFIED":
        st.info("Step 5 data note: starter Statcast is pending. Arsenal usage stays blank rather than being guessed.")
    if d.get("hitter_statcast_status") != "VERIFIED":
        st.info("Step 5 data note: hitter Statcast is pending. Pitch-type performance stays blank rather than being fabricated.")
    if score is None and d.get("pitcher_statcast_status") == "VERIFIED" and d.get("hitter_statcast_status") == "VERIFIED":
        st.info("Step 5 sample gate: verified Statcast feeds exist, but pitch-type samples have not earned enough reliability to form a matchup index.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Steps 1-5 together while preserving the complete frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • certified Steps 1-4 plus Step 5 pitch-mix context • later steps will accumulate here.")
        step1._render_step1(games_df)
        step2._render_step2(games_df)
        step3._render_step3(games_df)
        step4._render_step4(games_df)
        _render_step5(games_df)

    original_caption = st.caption
    st.caption = clean._filtered_caption(original_caption)
    try:
        with st.expander(LEGACY_AUDIT_LABEL, expanded=False):
            st.caption("Frozen V1 calculations remain available here while V2 is rebuilt step-by-step.")
            frozen_detail.render_player_layer(
                games_df,
                section_header,
                status_info,
                team_logo,
                h,
            )
    finally:
        st.caption = original_caption

    clean._render_snapshot(snapshot_slot, games_df)


__all__ = [
    "LEGACY_AUDIT_LABEL",
    "PROBABILITY_IMPACT",
    "STEP5_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_step5",
    "render_player_layer",
]
