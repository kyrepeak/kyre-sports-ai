"""NFL Passing Yards V11 — Step 10 market edge + final certification.

Certified V10 / Steps 1–9 render unchanged. V11 captures the exact certified
Step 9 distribution results and appends a post-model market evaluator. Market
inputs never flow backward into projection or probability math.
"""
from __future__ import annotations

from html import escape
import math
import re

import pandas as pd
import streamlit as st

import nfl_passing_yards_hub_v10 as prior
import nfl_passing_yards_market_v1 as market

MODEL_VERSION = "NFL PASSING YARDS V11 • STEP 10 MARKET EDGE + FINAL"

_STEP10_CSS = r"""
<style>
.kpy10-active{border:1px solid #356c4d;background:#092218;border-radius:13px;padding:10px 12px;margin:4px 0 10px}
.kpy10-active b{color:#8cf0b8;font-size:.84rem}.kpy10-active span{color:#9faeb9;font-size:.52rem;display:block;margin-top:3px;line-height:1.5}
.kpy10-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0 10px}
.kpy10-card{border:1px solid #4a657b;background:#07131f;border-radius:14px;padding:11px}
.kpy10-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:9px}
.kpy10-name{font-size:.94rem;font-weight:950;color:#f8fbff}.kpy10-sub{font-size:.5rem;color:#7890a3;margin-top:3px;line-height:1.45}
.kpy10-grade{font-size:.54rem;font-weight:950;border-radius:999px;padding:5px 8px;border:1px solid #4b6278;white-space:nowrap}
.kpy10-grade.a{color:#6af0ad;border-color:#2d7c58;background:#09281c}.kpy10-grade.b{color:#8ee9bd;border-color:#39745b;background:#0b251c}.kpy10-grade.c{color:#f1ca72;border-color:#796538;background:#2a2412}.kpy10-grade.pass{color:#9ed3ff;border-color:#416d8d;background:#0b2234}.kpy10-grade.check{color:#a6b6c3}
.kpy10-hero{display:grid;grid-template-columns:1.1fr 1fr 1fr;gap:6px;margin-bottom:7px}.kpy10-hero>div{border:1px solid #213e54;background:#06111b;border-radius:10px;padding:8px}
.kpy10-hero b{display:block;font-size:1.08rem;color:#fff}.kpy10-hero span{display:block;font-size:.43rem;color:#70879a;text-transform:uppercase;margin-top:2px}
.kpy10-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.kpy10-metrics>div{border:1px solid #1d374b;background:#07121c;border-radius:9px;padding:7px 6px;font-size:.47rem;color:#7990a4}
.kpy10-metrics b{display:block;color:#eff6fb;font-size:.69rem;margin-bottom:2px}.kpy10-note{margin-top:7px;padding-top:7px;border-top:1px solid #1b3449;color:#7f97a9;font-size:.49rem;line-height:1.55}
@media(max-width:820px){.kpy10-grid{grid-template-columns:1fr}.kpy10-hero{grid-template-columns:1fr 1fr}.kpy10-hero>div:first-child{grid-column:1/-1}}
</style>
"""


def _safe(value, default="") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _fmt(value, digits=1, suffix="") -> str:
    if not _finite(value):
        return "—"
    return f"{float(value):.{digits}f}{suffix}"


def _pct(value) -> str:
    if not _finite(value):
        return "—"
    return f"{100.0 * float(value):.1f}%"


def _american(value) -> str:
    if not _finite(value):
        return "—"
    number = float(value)
    return f"{number:+.0f}"


def _signed_pct_points(value) -> str:
    if not _finite(value):
        return "—"
    return f"{float(value):+.1f} pp"


def _ev(value) -> str:
    if not _finite(value):
        return "—"
    return f"{100.0 * float(value):+.1f}%"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _safe(value).lower()).strip("_") or "qb"


def _market_card(row: dict) -> str:
    grade = _safe(row.get("grade"), "CHECK").upper()
    css = grade.lower() if grade.lower() in {"a", "b", "c", "pass"} else "check"
    state = _safe(row.get("grade_label"), "MARKET CHECK")
    side = _safe(row.get("lean"), "PASS")
    return (
        '<section class="kpy10-card">'
        '<div class="kpy10-top">'
        f'<div><div class="kpy10-name">{escape(_safe(row.get("qb_name"),"Unresolved QB1"))} • Market Evaluation</div>'
        f'<div class="kpy10-sub">{escape(_safe(row.get("source"),"Manual verified market"))} • projection influence remains 0.0%</div></div>'
        f'<div class="kpy10-grade {css}">{escape(grade)} • {escape(state)}</div></div>'
        '<div class="kpy10-hero">'
        f'<div><b>{escape(side)}</b><span>Final Lean</span></div>'
        f'<div><b>{_fmt(row.get("line"),1)}</b><span>Market Line</span></div>'
        f'<div><b>{_safe(row.get("model_confidence"),"CHECK")}</b><span>Model Confidence</span></div>'
        '</div>'
        '<div class="kpy10-metrics">'
        f'<div><b>{_pct(row.get("model_over_probability"))} / {_pct(row.get("model_under_probability"))}</b>Model Over / Under</div>'
        f'<div><b>{_american(row.get("model_fair_over_odds"))} / {_american(row.get("model_fair_under_odds"))}</b>Model fair Over / Under</div>'
        f'<div><b>{_american(row.get("over_odds"))} / {_american(row.get("under_odds"))}</b>Offered Over / Under</div>'
        f'<div><b>{_pct(row.get("no_vig_over"))} / {_pct(row.get("no_vig_under"))}</b>No-vig Over / Under</div>'
        f'<div><b>{_signed_pct_points(row.get("over_edge_pp"))} / {_signed_pct_points(row.get("under_edge_pp"))}</b>Model edge Over / Under</div>'
        f'<div><b>{_ev(row.get("over_ev"))} / {_ev(row.get("under_ev"))}</b>EV per $1 Over / Under</div>'
        '</div>'
        '<div class="kpy10-note">'
        f'{escape(_safe(row.get("reason"),"Two-way market evaluated after the model was completed."))}<br>'
        f'Sportsbook projection influence: <b>0.0%</b> • stake sizing: <b>OFF</b>'
        '</div></section>'
    )


def _detail_table(row: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {"Side": "OVER", "Model P": _pct(row.get("model_over_probability")), "Fair Odds": _american(row.get("model_fair_over_odds")), "Offered": _american(row.get("over_odds")), "Raw Implied": _pct(row.get("raw_over_implied")), "No-Vig": _pct(row.get("no_vig_over")), "Edge": _signed_pct_points(row.get("over_edge_pp")), "EV": _ev(row.get("over_ev"))},
        {"Side": "UNDER", "Model P": _pct(row.get("model_under_probability")), "Fair Odds": _american(row.get("model_fair_under_odds")), "Offered": _american(row.get("under_odds")), "Raw Implied": _pct(row.get("raw_under_implied")), "No-Vig": _pct(row.get("no_vig_under")), "Edge": _signed_pct_points(row.get("under_edge_pp")), "EV": _ev(row.get("under_ev"))},
    ])


def _capture_step9_calls():
    captured = []
    original = prior.distribution.build_distribution

    def wrapped(step8, thresholds=prior.distribution.DEFAULT_THRESHOLDS):
        result = original(step8, thresholds=thresholds)
        captured.append(result)
        return result

    prior.distribution.build_distribution = wrapped
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        prior.distribution.build_distribution = original
    return captured


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_STEP10_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy10-active"><b>🏁 STEP 10 ACTIVE — MARKET EDGE + FINAL CERTIFICATION • 10/10</b>'
        '<span>Certified Steps 1–9 render unchanged below. Enter a real verified passing-yards market only after the model is finished. The line and prices are comparison inputs only and can never alter the projection or distribution.</span></div>',
        unsafe_allow_html=True,
    )

    captured = _capture_step9_calls()
    if not captured:
        return

    st.markdown(
        '<div class="kpy-step"><div class="kpy-step-title">🏁💹 Step 10 — Market Edge + Final Grade</div>'
        '<div class="kpy-step-sub">Post-model market comparison • raw implied + no-vig + model fair odds + EV • sportsbook projection influence 0.0%</div></div>',
        unsafe_allow_html=True,
    )
    st.info("Enter the current passing-yards prop exactly as shown by the sportsbook. No default line or price is fabricated. Both sides are required for a no-vig edge and final grade.")

    evaluated = []
    cols = st.columns(len(captured)) if captured else []
    for idx, (col, dist) in enumerate(zip(cols, captured)):
        name = _safe(dist.get("qb_name"), f"QB {idx + 1}")
        key = f"kpy10_{idx}_{_slug(name)}"
        with col:
            st.markdown(f"**{name} — verified market input**")
            source = st.text_input("Sportsbook / source", value="", key=f"{key}_source", placeholder="Example: FanDuel")
            line_text = st.text_input("Passing yards line", value="", key=f"{key}_line", placeholder="Example: 249.5")
            over_text = st.text_input("Over American odds", value="", key=f"{key}_over", placeholder="Example: -110")
            under_text = st.text_input("Under American odds", value="", key=f"{key}_under", placeholder="Example: -110")
            timestamp = st.text_input("Price timestamp / note", value="", key=f"{key}_timestamp", placeholder="Optional, but recommended")

        if not line_text.strip() and not over_text.strip() and not under_text.strip():
            row = {
                "ready": False,
                "grade_ready": False,
                "qb_name": name,
                "source": source,
                "grade": "CHECK",
                "grade_label": "MARKET CHECK",
                "lean": "PASS",
                "reason": "verified market input not entered",
                "sportsbook_projection_influence": 0.0,
            }
        else:
            row = market.evaluate_market(dist, line_text, over_text, under_text, source=source, market_timestamp=timestamp)
        evaluated.append(row)

    st.markdown('<div class="kpy10-grid">' + "".join(_market_card(row) for row in evaluated) + '</div>', unsafe_allow_html=True)

    for row in evaluated:
        if row.get("integer_line_push_risk"):
            st.warning(f"⚠️ {row.get('qb_name')}: integer line {row.get('line'):.0f} has push risk. Step 10 withholds the value grade because the certified Step 9 continuous model is not discrete-push-aware.")

    grade_ready = [row for row in evaluated if row.get("grade_ready")]
    if evaluated and len(grade_ready) == len(evaluated):
        st.success("✅ STEP 10 MARKET EVALUATION GREEN • both verified markets have complete two-way prices and passed the push/no-vig guardrails. The 10-step NFL Passing Yards build is structurally complete.")
    else:
        st.info("ℹ️ STEP 10 MARKET CHECK • the 10-step system is complete, but a live final value grade appears only when a verified two-way half-yard market is entered for that quarterback.")

    cols = st.columns(len(evaluated)) if evaluated else []
    for col, row in zip(cols, evaluated):
        with col:
            with st.expander(f"Step 10 market math — {_safe(row.get('qb_name'),'QB')}", expanded=False):
                if row.get("ready"):
                    st.dataframe(_detail_table(row), hide_index=True, use_container_width=True)
                    st.caption(f"Sportsbook hold before no-vig: {_pct(row.get('market_hold'))}")
                    st.caption(f"Selected edge: {_signed_pct_points(row.get('selected_edge_pp'))} • selected EV: {_ev(row.get('selected_ev'))}")
                else:
                    st.info(_safe(row.get("reason"), "Market evaluation unavailable."))

    with st.expander("Step 10 methodology + permanent guardrails", expanded=False):
        st.write("Steps 1–9 finish before Step 10 receives any market input. The sportsbook line and prices are used only for comparison; sportsbook projection influence is permanently 0.0% and projection adjustment is 0.0 yards.")
        st.write("Raw American-odds implied probabilities are shown, then both sides are normalized to remove the two-way sportsbook hold. Model edge is model probability minus no-vig market probability. EV is calculated at the entered offered price per $1 of hypothetical risk; it is an analytical comparison, not a guarantee.")
        st.write("Final grading is conservative: A requires HIGH model confidence, at least +7.5 percentage points of no-vig edge and at least +10% EV; B requires HIGH/MEDIUM confidence, +5 points and +5% EV; C requires at least +2.5 points with positive EV; otherwise PASS.")
        st.write("Both sides are required for final grading. Integer lines are not graded because NFL passing yards settle as whole numbers and can push, while the certified Step 9 distribution is continuous. Missing or malformed market information fails closed—there are no synthetic odds or fallback lines.")
        st.write("Stake sizing is OFF. Step 10 reports evidence, fair odds, edge, EV and a conservative lean; it does not tell the user how much money to wager and does not promise an outcome.")
        st.caption("10/10 COMPLETE • sportsbook projection influence = 0.0% • no synthetic market • push guardrail ON • stake sizing OFF")

    st.success("🏆 NFL PASSING YARDS BUILD: 10 OF 10 STEPS COMPLETE • certified model → distribution → post-model market evaluation architecture is now connected end to end.")
    st.caption(f"{MODEL_VERSION} • certified Steps 1–9 preserved • market comparison ON • fair model odds/no-vig/edge/EV/final grading ON only after verified market input • projection independence preserved.")


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
