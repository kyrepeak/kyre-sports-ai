"""MLB Matchup Explorer V2 — Steps 1-6 player intelligence stack.

Step 6 adds hitter batted-ball quality and spray context. It remains descriptive
only: frozen V1 Matchup, Daily Top 5, Moneyline, game-level hit probability,
fair odds, simulation and calibration remain untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_batted_ball_v1 as batted_ball
import mlb_matchup_hub_v10 as ui
import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean
import mlb_matchup_player_v24 as step1
import mlb_matchup_player_v25 as step2
import mlb_matchup_player_v26 as step3
import mlb_matchup_player_v27 as step4
import mlb_matchup_player_v28 as step5

VERSION = "MLB Matchup Intelligence V2 Step 6"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "NONE"
STEP6_ROLE = "BATTED_BALL_QUALITY_CONTEXT_ONLY"


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


def _build_step6(games_df) -> dict[str, Any] | None:
    foundation = step1._build_foundation(games_df)
    if not foundation:
        return None
    player_id = foundation.get("player_id")
    season = foundation.get("season")
    if not player_id or not season:
        return batted_ball.build_batted_ball_profile(foundation, None)
    payload = batted_ball.fetch_batted_ball_input(int(player_id), int(season))
    return batted_ball.build_batted_ball_profile(foundation, payload)


def _render_step6(games_df) -> None:
    d = _build_step6(games_df)
    if not d:
        st.warning("Step 6 batted-ball quality is waiting for a verified player selection.")
        return

    components = " • ".join(
        f"{name} {earned}/{maximum}"
        for name, (earned, maximum) in (d.get("batted_ball_data_components") or {}).items()
    )
    score = d.get("batted_ball_score")
    score_text = f"{int(score)}/100" if score is not None else "—"

    st.markdown(
        f'''<div class="mxv2-step mxv2-step6">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 6 • BATTED-BALL QUALITY</div>
            <div class="mxv2-badge">{_esc(d.get('batted_ball_data_label'))} • {int(d.get('batted_ball_data_score') or 0)}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('player_name'))}</b> • quality of contact when the ball is put in play</div>
          <div class="mxv2-status">Contact-quality context only • probability impact: NONE • no park/defense/bullpen/opportunity adjustment yet</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini"><span>Contact index</span><b>{score_text}</b></div>
            <div class="mxv2-mini"><span>Sample reliability</span><b>{_fmt_rate(d.get('batted_ball_reliability'))}</b></div>
            <div class="mxv2-mini"><span>Avg EV</span><b>{_fmt_num(d.get('avg_ev'),1)}</b></div>
            <div class="mxv2-mini"><span>Max EV</span><b>{_fmt_num(d.get('max_ev'),1)}</b></div>
            <div class="mxv2-mini"><span>Hard-hit</span><b>{_fmt_rate(d.get('hard_hit_pct'))}</b></div>
            <div class="mxv2-mini"><span>Barrel</span><b>{_fmt_rate(d.get('barrel_pct'))}</b></div>
            <div class="mxv2-mini"><span>xBA on contact</span><b>{_fmt_avg(d.get('xba_contact'))}</b></div>
            <div class="mxv2-mini"><span>Avg launch angle</span><b>{_fmt_num(d.get('avg_launch_angle'),1)}°</b></div>
            <div class="mxv2-mini"><span>Sweet spot</span><b>{_fmt_rate(d.get('sweet_spot_pct'))}</b></div>
            <div class="mxv2-mini"><span>Tracked BBE</span><b>{int(d.get('bbe') or 0)}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Batted-ball verdict</b> • {_esc(d.get('batted_ball_label'))} • {score_text} • sample reliability {_fmt_rate(d.get('batted_ball_reliability'))} • descriptive index, not a 1+ hit probability.</div>
          <div class="mxv2-row"><b>Launch profile</b> • {_esc(d.get('launch_profile_label'))} • GB {_fmt_rate(d.get('ground_ball_pct'))} • LD {_fmt_rate(d.get('line_drive_pct'))} • FB {_fmt_rate(d.get('fly_ball_pct'))} • PU {_fmt_rate(d.get('popup_pct'))}</div>
          <div class="mxv2-row"><b>Spray tendencies</b> • {_esc(d.get('spray_label'))} • pull {_fmt_rate(d.get('pull_pct'))} • center {_fmt_rate(d.get('center_pct'))} • opposite field {_fmt_rate(d.get('oppo_pct'))} • {int(d.get('spray_bip') or 0)} tracked BIP</div>
          <div class="mxv2-row"><b>Field sectors</b> • left {_fmt_rate(d.get('left_pct'))} • center {_fmt_rate(d.get('center_pct'))} • right {_fmt_rate(d.get('right_pct'))} • spray uses Statcast hit coordinates plus the batter side recorded on each ball in play.</div>
          <div class="mxv2-row"><b>Contact evidence</b> • {int(d.get('ev_bbe') or 0)} EV balls • {int(d.get('launch_bbe') or 0)} launch-angle balls • {int(d.get('barrel_bbe') or 0)} barrel-classified balls • {int(d.get('xba_bbe') or 0)} xBA-on-contact balls</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>Sample rules</b> • below {batted_ball.BBE_MIN_SAMPLE} tracked BBE, no contact-quality index is issued • reliability reaches full weight at {batted_ball.BBE_FULL_SAMPLE} BBE • smaller samples are shrunk toward neutral.</div>
          <div class="mxv2-row mxv2-muted"><b>Definitions</b> • hard-hit = ≥{int(batted_ball.HARD_HIT_MPH)} mph • sweet spot = {int(batted_ball.SWEET_SPOT_LOW)}°–{int(batted_ball.SWEET_SPOT_HIGH)}° launch angle • Statcast launch-speed-angle class 6 is treated as a barrel.</div>
          <div class="mxv2-row mxv2-muted"><b>Data completeness</b> • {_esc(components)}</div>
          <div class="mxv2-row mxv2-muted"><b>Model boundary</b> • Step 6 measures hitter contact quality only. Step 7 adds park, weather and defense; later steps handle bullpen, opportunity and final probability.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if d.get("hitter_statcast_status") != "VERIFIED":
        st.info("Step 6 data note: hitter Statcast is pending. Batted-ball metrics stay blank rather than being fabricated.")
    elif score is None:
        st.info(f"Step 6 sample gate: fewer than {batted_ball.BBE_MIN_SAMPLE} usable tracked BBE are available, so no contact-quality index is issued yet.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Steps 1-6 together while preserving the complete frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • certified Steps 1-5 plus Step 6 batted-ball quality • later steps will accumulate here.")
        step1._render_step1(games_df)
        step2._render_step2(games_df)
        step3._render_step3(games_df)
        step4._render_step4(games_df)
        step5._render_step5(games_df)
        _render_step6(games_df)

    original_caption = st.caption
    st.caption = clean._filtered_caption(original_caption)
    try:
        with st.expander(LEGACY_AUDIT_LABEL, expanded=False):
            st.caption("Frozen V1 calculations remain available here while V2 is rebuilt step-by-step.")
            frozen_detail.render_player_layer(games_df, section_header, status_info, team_logo, h)
    finally:
        st.caption = original_caption

    clean._render_snapshot(snapshot_slot, games_df)


__all__ = [
    "LEGACY_AUDIT_LABEL",
    "PROBABILITY_IMPACT",
    "STEP6_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_step6",
    "render_player_layer",
]
