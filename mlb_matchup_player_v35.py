"""MLB Matchup Explorer V2 — complete Steps 1-12 intelligence stack.

Step 12 finalizes the raw Step 11 hit distribution with empirical V2 history when
available, reliability shrinkage, final confidence, calibrated fair odds and a
pure-probability grade. Frozen V1 remains a separate rollback/audit surface.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_calibration_v1 as calibration
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
import mlb_matchup_player_v34 as step11

VERSION = "MLB Matchup Intelligence V2 Step 12 FINAL"
V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — complete"
LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"
PROBABILITY_IMPACT = "ACTIVE_FINAL_V2"
STEP12_ROLE = "CALIBRATION_FINAL_INTELLIGENCE"


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


def _fmt_signed_rate(value: Any) -> str:
    try:
        return f"{float(value) * 100:+.1f} pts"
    except Exception:
        return "—"


def _fmt_odds(value: Any) -> str:
    try:
        n = int(value)
        return f"+{n}" if n > 0 else str(n)
    except Exception:
        return "—"


def _build_step12(games_df, simulations: int | None = None, persist: bool = True) -> dict[str, Any] | None:
    raw = step11._build_step11(games_df, simulations=simulations)
    if not raw:
        return None
    return calibration.build_final_intelligence(raw, persist=persist)


def _render_step11_profile(raw: dict[str, Any] | None) -> None:
    """Render the already-computed certified Step 11 result without a second 5M run."""
    d = raw or {}
    status = str(d.get("probability_status") or "GATED")
    st.markdown(
        f'''<div class="mxv2-step mxv2-step11">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 11 • RAW HIT PROBABILITY ENGINE</div>
            <div class="mxv2-badge">{_esc(status)} • data {_fmt(d.get('composite_data_score'),0)}/100</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('player_name'))}</b> • certified pre-calibration V2 distribution</div>
          <div class="mxv2-status">RAW / PRE-CALIBRATION • Step 12 below owns the final published probability</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini mxv2-probhero"><span>RAW P(1+ HIT)</span><b>{_fmt_rate(d.get('p1_plus'))}</b></div>
            <div class="mxv2-mini"><span>RAW P(0 HIT)</span><b>{_fmt_rate(d.get('p0'))}</b></div>
            <div class="mxv2-mini"><span>RAW P(2+ HIT)</span><b>{_fmt_rate(d.get('p2_plus'))}</b></div>
            <div class="mxv2-mini"><span>Expected hits</span><b>{_fmt(d.get('expected_hits'),2)}</b></div>
            <div class="mxv2-mini"><span>Starter hit / PA</span><b>{_fmt_rate(d.get('starter_hit_per_pa'))}</b></div>
            <div class="mxv2-mini"><span>Bullpen hit / PA</span><b>{_fmt_rate(d.get('bullpen_hit_per_pa'))}</b></div>
            <div class="mxv2-mini"><span>Expected PA</span><b>{_fmt(d.get('expected_pa'),2)}</b></div>
            <div class="mxv2-mini"><span>Raw fair odds 1+</span><b>{_fmt_odds(d.get('raw_fair_odds_1_plus'))}</b></div>
          </div>
          <div class="mxv2-row mxv2-muted"><b>Simulation</b> • {int(d.get('simulations') or 0):,} trials • {int(d.get('batches') or 0)} batches • seed {int(d.get('random_seed') or 0)} • SE {_fmt_rate(d.get('mc_se_p1_plus'))} • {'CONVERGED' if d.get('monte_carlo_converged') else 'CHECK'}.</div>
          <div class="mxv2-row mxv2-muted"><b>Boundary</b> • These are the immutable Step 11 raw numbers. Step 12 may calibrate/shrink them but never rewrites Step 11.</div>
        </div>''',
        unsafe_allow_html=True,
    )
    if status == "GATED":
        gates = " • ".join(str(x) for x in (d.get("probability_gates") or [])) or "essential raw probability inputs unavailable"
        st.info(f"Step 11 gate: {gates}.")


def _confidence_components_text(components: dict[str, Any] | None) -> str:
    parts = []
    for name, pair in (components or {}).items():
        try:
            earned, maximum = pair
            parts.append(f"{name} {float(earned):.0f}/{float(maximum):.0f}")
        except Exception:
            continue
    return " • ".join(parts) if parts else "—"


def _render_step12_profile(d: dict[str, Any] | None) -> None:
    d = d or {}
    status = str(d.get("final_status") or "GATED")
    calibration_status = str(d.get("calibration_status_step12") or "GATED")
    confidence = int(d.get("final_confidence") or 0)
    sample = int(d.get("calibration_sample") or 0)

    st.markdown(
        f'''<div class="mxv2-step mxv2-step12">
          <div class="mxv2-top">
            <div class="mxv2-kicker">STEP 12 • CALIBRATION + FINAL INTELLIGENCE</div>
            <div class="mxv2-badge">{_esc(status)} • {_esc(d.get('final_grade'))}</div>
          </div>
          <div class="mxv2-lead"><b>{_esc(d.get('player_name'))}</b> • FINAL V2 1+ Hit Intelligence</div>
          <div class="mxv2-status">FINAL probability layer • calibration {_esc(calibration_status)} • confidence {confidence}/100</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-statgrid">
            <div class="mxv2-mini mxv2-finalhero"><span>FINAL P(1+ HIT)</span><b>{_fmt_rate(d.get('final_p1_plus'))}</b></div>
            <div class="mxv2-mini"><span>FINAL P(0 HIT)</span><b>{_fmt_rate(d.get('final_p0'))}</b></div>
            <div class="mxv2-mini"><span>FINAL P(2+ HIT)</span><b>{_fmt_rate(d.get('final_p2_plus'))}</b></div>
            <div class="mxv2-mini"><span>FINAL P(exactly 1)</span><b>{_fmt_rate(d.get('final_p_exactly_1'))}</b></div>
            <div class="mxv2-mini"><span>Expected hits</span><b>{_fmt(d.get('final_expected_hits'),2)}</b></div>
            <div class="mxv2-mini"><span>Median / mode</span><b>{_fmt(d.get('final_median_hits'),0)} / {_fmt(d.get('final_mode_hits'),0)}</b></div>
            <div class="mxv2-mini"><span>Final fair odds 1+</span><b>{_fmt_odds(d.get('final_fair_odds_1_plus'))}</b></div>
            <div class="mxv2-mini"><span>Final fair odds 2+</span><b>{_fmt_odds(d.get('final_fair_odds_2_plus'))}</b></div>
            <div class="mxv2-mini"><span>Confidence</span><b>{confidence}/100</b></div>
            <div class="mxv2-mini"><span>Confidence label</span><b>{_esc(d.get('final_confidence_label'))}</b></div>
            <div class="mxv2-mini"><span>Final grade</span><b>{_esc(d.get('final_grade'))}</b></div>
            <div class="mxv2-mini"><span>Reliability range</span><b>{_fmt_rate(d.get('reliability_low'))}–{_fmt_rate(d.get('reliability_high'))}</b></div>
          </div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row"><b>Final verdict</b> • {_esc(d.get('final_grade'))} • P(1+) {_fmt_rate(d.get('final_p1_plus'))} • P(2+) {_fmt_rate(d.get('final_p2_plus'))} • fair 1+ {_fmt_odds(d.get('final_fair_odds_1_plus'))} • {_esc(d.get('final_confidence_label'))}.</div>
          <div class="mxv2-row"><b>Raw → final</b> • Step 11 {_fmt_rate(d.get('p1_plus'))} → empirical {_fmt_rate(d.get('empirical_p1_plus'))} → reliability-adjusted final {_fmt_rate(d.get('final_p1_plus'))} • total {_fmt_signed_rate(d.get('total_final_delta'))}.</div>
          <div class="mxv2-row"><b>Missing-data / reliability control</b> • evidence weight {_fmt_rate(d.get('reliability_weight'))} • shrinkage toward neutral {_fmt_rate(d.get('missing_data_penalty'))} • neutral P(1+) {_fmt_rate(d.get('neutral_p1_plus'))}.</div>
          <div class="mxv2-row"><b>Empirical calibration</b> • {_esc(calibration_status)} • {sample} graded forecasts from the exact Step 11 raw model • raw Brier {_fmt(d.get('backtest_brier_raw'),3)} • calibrated Brier {_fmt(d.get('backtest_brier_calibrated'),3)}.</div>
          <div class="mxv2-row"><b>Backtest read</b> • average predicted {_fmt_rate(d.get('backtest_avg_prediction'))} • actual 1+ hit rate {_fmt_rate(d.get('backtest_actual_hit_rate'))} • empirical shift {_fmt_signed_rate(d.get('empirical_calibration_delta'))}.</div>
          <div class="mxv2-row"><b>Calibration note</b> • {_esc(d.get('calibration_note'))}</div>
          <div class="mxv2-rule"></div>
          <div class="mxv2-row mxv2-muted"><b>History integrity</b> • {_esc(d.get('calibration_backtest_source'))} • current forecast persistence {_esc(d.get('history_persistence_status'))} • empirical correction never borrows frozen V1 outcomes as if they were V2.</div>
          <div class="mxv2-row mxv2-muted"><b>Confidence components</b> • {_esc(_confidence_components_text(d.get('final_confidence_components')))}</div>
          <div class="mxv2-row mxv2-muted"><b>Cold-start protection</b> • fewer than {calibration.MIN_BACKTEST_GAMES} graded V2 forecasts = identity empirical calibration and grade capped at B+; {calibration.STRONG_BACKTEST_GAMES}+ strengthens calibration; {calibration.MATURE_BACKTEST_GAMES}+ is mature.</div>
          <div class="mxv2-row mxv2-muted"><b>Grade meaning</b> • {_esc(d.get('grade_basis'))}</div>
          <div class="mxv2-row mxv2-muted"><b>Architecture complete</b> • Step 12 is the final Matchup Intelligence V2 layer. Frozen V1 and Daily Top 5 rankings remain separately preserved for rollback/audit.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if status == "GATED":
        st.info("Step 12 gate: the raw Step 11 engine is not ready, so no final probability is manufactured.")
    elif calibration_status == "COLD_START":
        st.info(f"Step 12 calibration cold start: the exact V2 raw model has {sample} graded forecasts. Empirical correction stays identity until {calibration.MIN_BACKTEST_GAMES}; reliability/confidence protections remain active now.")
    elif calibration_status == "WARMUP":
        st.info("Step 12 calibration is live but still warming up; final grades remain capped until the graded V2 sample reaches the strong-history threshold.")


def _render_step12(games_df) -> None:
    d = _build_step12(games_df)
    if not d:
        st.warning("Step 12 final intelligence is waiting for a verified player selection.")
        return
    _render_step12_profile(d)


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render complete V2 Steps 1-12 plus the separate frozen V1 audit."""
    snapshot_slot = st.empty()

    with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):
        st.caption("MLB Matchup Intelligence V2 • COMPLETE • Steps 1-12 certified architecture with final probability/calibration layer.")
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

        # Step 11 is expensive (5M simulations). Build it once, then feed the same
        # immutable raw object to both Step 11 presentation and Step 12 finalization.
        raw = step11._build_step11(games_df)
        _render_step11_profile(raw)
        final = calibration.build_final_intelligence(raw, persist=True) if raw else None
        _render_step12_profile(final)

    original_caption = st.caption
    st.caption = clean._filtered_caption(original_caption)
    try:
        with st.expander(LEGACY_AUDIT_LABEL, expanded=False):
            st.caption("Frozen V1 calculations remain available here as the rollback/audit model.")
            frozen_detail.render_player_layer(games_df, section_header, status_info, team_logo, h)
    finally:
        st.caption = original_caption

    clean._render_snapshot(snapshot_slot, games_df)


__all__ = [
    "LEGACY_AUDIT_LABEL",
    "PROBABILITY_IMPACT",
    "STEP12_ROLE",
    "V2_INTELLIGENCE_LABEL",
    "VERSION",
    "_build_step12",
    "render_player_layer",
]
