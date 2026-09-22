"""MLB Matchup Explorer V2 — Steps 1-11 player intelligence stack.

Step 11 activates the first raw V2 game-level hit-probability engine. It consumes
certified Steps 1-10, produces starter/bullpen per-PA hit probabilities and an
uncertainty-aware hit distribution, but deliberately leaves calibration, final
confidence and final grades to Step 12.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean
import mlb_matchup_player_v24 as step1
import mlb_matchup_player_v25 as step2
import mlb_matchup_player_v26 as step3
import mlb_matchup_player_v27 as step4
import mlb_matchup_player_v28 as step5
import mlb_matchup_player_v29 as step6
import mlb_matchup_player_v30 as step7
import mlb_matchup_player_v31 as step8
import mlb_matchup_player_v32 as step9
import mlb_matchup_player_v33 as step10
import mlb_matchup_probability_v1 as probability

VERSION = "MLB Matchup Intelligence V2 Step 11"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "ACTIVE_RAW_V2"
STEP11_ROLE = "RAW_HIT_PROBABILITY_ENGINE"


def _esc(value: Any) -> str:
    return ui._esc(value)


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _fmt_rate(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def _fmt_signed(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):+.{digits}f}"
    except Exception:
        return "—"


def _fmt_odds(value: Any) -> str:
    try:
        n = int(value)
        return f"+{n}" if n > 0 else str(n)
    except Exception:
        return "—"


def _build_step11(games_df, simulations: int | None = None) -> dict[str, Any] | None:
    foundation = step1._build_foundation(games_df)
    if not foundation:
        return None
    hitter = step2._build_step2(games_df)
    starter = step3._build_step3(games_df)
    platoon = step4._build_step4(games_df)
    pitch = step5._build_step5(games_df)
    batted = step6._build_step6(games_df)
    environment = step7._build_step7(games_df)
    bullpen = step8._build_step8(games_df)
    opportunity = step9._build_step9(games_df)
    recent = step10._build_step10(games_df)
    kwargs = {}
    if simulations is not None:
        kwargs["simulations"] = int(simulations)
    return probability.build_probability_profile(
        foundation,
        hitter,
        starter,
        platoon,
        pitch,
        batted,
        environment,
        bullpen,
        opportunity,
        recent,
        **kwargs,
    )


def _distribution_text(distribution: dict[int, float] | dict[str, float] | None) -> str:
    rows = []
    for key, value in sorted((distribution or {}).items(), key=lambda pair: int(pair[0])):
        k = int(key)
        if k > 4:
            continue
        rows.append(f"{k} H {_fmt_rate(value)}")
    return " • ".join(rows) if rows else "—"


def _adjustment_text(adjustments: dict[str, Any] | None) -> str:
    parts = []
    for name, value in (adjustments or {}).items():
        try:
            if abs(float(value)) < 0.0005:
                continue
            parts.append(f"{name.replace('_', ' ')} {_fmt_signed(value, 3)}")
        except Exception:
            continue
    return " • ".join(parts) if parts else "neutral / unavailable adjustments"


def _render_step11(games_df) -> None:
    d = _build_step11(games_df)
    if not d:
        st.warning("Step 11 probability engine is waiting for a verified player selection.")
        return

    status = str(d.get("probability_status") or "GATED")
    gated = status == "GATED"
    p1 = d.get("p1_plus")
    p2 = d.get("p2_plus")
    p0 = d.get("p0")
    expected_hits = d.get("expected_hits")
    composite = d.get("composite_data_score")
    convergence = "CONVERGED" if d.get("monte_carlo_converged") else "CHECK"
    mc_dist = d.get("monte_carlo_distribution") or {}

    st.markdown(
        f'''<div class="mxv2-step mxv2-step11">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 11 • RAW HIT PROBABILITY ENGINE</div>
            <div class="mxv2-badge">{_esc(status)} • data {_fmt(composite,0)}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('player_name'))}</b> • first V2 game-level hit distribution</div>
          <div class="mxv2-status">ACTIVE raw probability • pre-calibration • Step 12 owns calibration, confidence and final grade</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini mxv2-probhero"><span>P(1+ HIT)</span><b>{_fmt_rate(p1)}</b></div>
            <div class="mxv2-mini"><span>P(0 HIT)</span><b>{_fmt_rate(p0)}</b></div>
            <div class="mxv2-mini"><span>P(2+ HIT)</span><b>{_fmt_rate(p2)}</b></div>
            <div class="mxv2-mini"><span>P(exactly 1)</span><b>{_fmt_rate(d.get('p_exactly_1'))}</b></div>
            <div class="mxv2-mini"><span>Expected hits</span><b>{_fmt(expected_hits,2)}</b></div>
            <div class="mxv2-mini"><span>Median hits</span><b>{_fmt(d.get('median_hits'),0)}</b></div>
            <div class="mxv2-mini"><span>Mode hits</span><b>{_fmt(d.get('mode_hits'),0)}</b></div>
            <div class="mxv2-mini"><span>Raw fair odds 1+</span><b>{_fmt_odds(d.get('raw_fair_odds_1_plus'))}</b></div>
            <div class="mxv2-mini"><span>Starter hit / PA</span><b>{_fmt_rate(d.get('starter_hit_per_pa'))}</b></div>
            <div class="mxv2-mini"><span>Bullpen hit / PA</span><b>{_fmt_rate(d.get('bullpen_hit_per_pa'))}</b></div>
            <div class="mxv2-mini"><span>Expected PA</span><b>{_fmt(d.get('expected_pa'),2)}</b></div>
            <div class="mxv2-mini"><span>Starter / bullpen PA</span><b>{_fmt(d.get('starter_pa'),2)} / {_fmt(d.get('bullpen_pa'),2)}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Raw probability verdict</b> • {_esc(status)} • P(1+) {_fmt_rate(p1)} • P(2+) {_fmt_rate(p2)} • expected hits {_fmt(expected_hits,2)} • these numbers are not yet backtest-calibrated.</div>
          <div class="mxv2-row"><b>Neutral baseline</b> • season H/PA {_fmt_rate(d.get('season_hit_per_pa'))} • xBA translated to H/PA {_fmt_rate(d.get('xba_hit_per_pa'))} • blended base {_fmt_rate(d.get('base_hit_per_pa'))}.</div>
          <div class="mxv2-row"><b>Starter path</b> • {_fmt(d.get('starter_pa'),2)} expected PA • {_fmt_rate(d.get('starter_hit_per_pa'))} hit probability per PA • total bounded logit shift {_fmt_signed(d.get('starter_total_logit_shift'),3)}.</div>
          <div class="mxv2-row"><b>Bullpen path</b> • {_fmt(d.get('bullpen_pa'),2)} expected PA • {_fmt_rate(d.get('bullpen_hit_per_pa'))} hit probability per PA • total bounded logit shift {_fmt_signed(d.get('bullpen_total_logit_shift'),3)}.</div>
          <div class="mxv2-row"><b>Starter adjustments</b> • {_esc(_adjustment_text(d.get('starter_adjustments')))}</div>
          <div class="mxv2-row"><b>Bullpen adjustments</b> • {_esc(_adjustment_text(d.get('bullpen_adjustments')))}</div>
          <div class="mxv2-row"><b>Monte Carlo distribution</b> • {_esc(_distribution_text(mc_dist))}</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>Simulation</b> • {int(d.get('simulations') or 0):,} trials • {int(d.get('batches') or 0)} batches • seed {int(d.get('random_seed') or 0)} • P(1+) SE {_fmt_rate(d.get('mc_se_p1_plus'))} • max batch spread {_fmt_rate(d.get('max_batch_difference'))} • {convergence}.</div>
          <div class="mxv2-row mxv2-muted"><b>Uncertainty</b> • starter logit σ {_fmt(d.get('starter_probability_sigma'),3)} • bullpen logit σ {_fmt(d.get('bullpen_probability_sigma'),3)} • projected lineups and weaker source coverage widen uncertainty automatically.</div>
          <div class="mxv2-row mxv2-muted"><b>Exposure basis</b> • {_esc(d.get('basis'))} • fractional PA are preserved rather than rounded away.</div>
          <div class="mxv2-row mxv2-muted"><b>Model boundary</b> • Step 11 is raw probability only. Step 12 must backtest-calibrate P(0)/P(1+)/P(2+), apply missing-data/reliability penalties, and publish final confidence, final fair odds and final grade.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if gated:
        gates = " • ".join(str(x) for x in (d.get("probability_gates") or [])) or "essential probability inputs unavailable"
        st.info(f"Step 11 gate: {gates}. No raw probability is manufactured until the required inputs are present.")
    elif status == "PROVISIONAL_RAW":
        st.info("Step 11 is producing a provisional raw probability because lineup confirmation, data completeness or simulation convergence is not yet at the READY_RAW threshold.")
    if d.get("calibration_status") == "DEFERRED_TO_STEP12":
        st.info("Step 11 reminder: raw fair odds are mathematical only. Step 12 will create the calibrated final probability, confidence and playable decision layer.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render Steps 1-11 together while preserving the complete frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("V2 rebuild • certified Steps 1-10 plus Step 11 raw probability engine • Step 12 will calibrate and finalize.")
        step1._render_step1(games_df)
        step2._render_step2(games_df)
        step3._render_step3(games_df)
        step4._render_step4(games_df)
        step5._render_step5(games_df)
        step6._render_step6(games_df)
        step7._render_step7(games_df)
        step8._render_step8(games_df)
        step9._render_step9(games_df)
        step10._render_step10(games_df)
        _render_step11(games_df)

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
    "STEP11_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_step11",
    "render_player_layer",
]
