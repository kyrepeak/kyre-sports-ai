"""NFL Passing Yards V10 — Step 9 outcome distribution + probability.

Certified V9 / Steps 1–8 render unchanged. V10 captures the exact Step 8
contextual projections during that render and appends a sportsbook-free analytic
outcome distribution without repeating network work or rewriting predecessors.
"""
from __future__ import annotations

from html import escape
import math

import pandas as pd
import streamlit as st

import nfl_passing_yards_hub_v9 as prior
import nfl_passing_yards_distribution_v1 as distribution

MODEL_VERSION = "NFL PASSING YARDS V10 • STEP 9 DISTRIBUTION + PROBABILITY"

_STEP9_CSS = r"""
<style>
.kpy9-active{border:1px solid #32697d;background:#08202a;border-radius:13px;padding:10px 12px;margin:4px 0 10px}
.kpy9-active b{color:#9ee8ff;font-size:.84rem}.kpy9-active span{color:#9faeb9;font-size:.52rem;display:block;margin-top:3px;line-height:1.5}
.kpy9-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0 10px}
.kpy9-card{border:1px solid #46677f;background:#07131f;border-radius:14px;padding:11px}
.kpy9-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:9px}
.kpy9-name{font-size:.94rem;font-weight:950;color:#f8fbff}.kpy9-sub{font-size:.5rem;color:#7890a3;margin-top:3px;line-height:1.45}
.kpy9-grade{font-size:.54rem;font-weight:950;border-radius:999px;padding:5px 8px;border:1px solid #4b6278;white-space:nowrap}
.kpy9-grade.high{color:#78efbb;border-color:#32775b;background:#0a2a20}.kpy9-grade.medium{color:#9ed3ff;border-color:#416d8d;background:#0b2234}.kpy9-grade.low{color:#f2ca74;border-color:#796538;background:#2a2412}.kpy9-grade.check{color:#a6b6c3}
.kpy9-hero{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:6px;margin-bottom:7px}.kpy9-hero>div{border:1px solid #213e54;background:#06111b;border-radius:10px;padding:8px}
.kpy9-hero b{display:block;font-size:1.1rem;color:#fff}.kpy9-hero span{display:block;font-size:.43rem;color:#70879a;text-transform:uppercase;margin-top:2px}
.kpy9-q{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px}.kpy9-q>div{border:1px solid #1d374b;background:#07121c;border-radius:9px;padding:7px 5px;text-align:center}
.kpy9-q b{display:block;color:#eff6fb;font-size:.67rem}.kpy9-q span{display:block;color:#7990a4;font-size:.42rem;margin-top:2px}.kpy9-note{margin-top:7px;padding-top:7px;border-top:1px solid #1b3449;color:#7f97a9;font-size:.49rem;line-height:1.55}
@media(max-width:820px){.kpy9-grid{grid-template-columns:1fr}.kpy9-hero{grid-template-columns:1fr 1fr}.kpy9-hero>div:first-child{grid-column:1/-1}.kpy9-q{grid-template-columns:repeat(3,minmax(0,1fr))}}
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


def _distribution_card(row: dict) -> str:
    grade = _safe(row.get("confidence"), "CHECK").upper()
    css = grade.lower() if grade.lower() in {"high", "medium", "low"} else "check"
    q = row.get("quantiles") or {}
    state = "READY" if row.get("ready") else "WITHHELD"
    return (
        '<section class="kpy9-card">'
        '<div class="kpy9-top">'
        f'<div><div class="kpy9-name">{escape(_safe(row.get("qb_name"),"Unresolved QB1"))} • Outcome Distribution</div>'
        f'<div class="kpy9-sub">{escape(_safe(row.get("distribution"),"CHECK"))} • {state}</div></div>'
        f'<div class="kpy9-grade {css}">{escape(grade)}</div></div>'
        '<div class="kpy9-hero">'
        f'<div><b>{_fmt(row.get("location_yards"),1)}</b><span>Step 8 Location</span></div>'
        f'<div><b>{_fmt(row.get("sigma_yards"),1)}</b><span>Observed Recent SD</span></div>'
        f'<div><b>{int(row.get("recent_games") or 0)}</b><span>Recent Games</span></div>'
        '</div>'
        '<div class="kpy9-q">'
        f'<div><b>{_fmt(q.get("p10"),1)}</b><span>P10</span></div>'
        f'<div><b>{_fmt(q.get("p25"),1)}</b><span>P25</span></div>'
        f'<div><b>{_fmt(q.get("p50"),1)}</b><span>P50 Median</span></div>'
        f'<div><b>{_fmt(q.get("p75"),1)}</b><span>P75</span></div>'
        f'<div><b>{_fmt(q.get("p90"),1)}</b><span>P90</span></div>'
        '</div>'
        '<div class="kpy9-note">'
        f'{escape(_safe(row.get("confidence_basis"), row.get("reason") or "probability evidence incomplete"))}<br>'
        f'Engine: <b>analytic</b> • Monte Carlo sampling error: <b>{_fmt(row.get("sampling_error"),1)}</b> • sportsbook influence: <b>0.0%</b>'
        '</div></section>'
    )


def _threshold_table(row: dict) -> pd.DataFrame:
    rows = []
    for item in row.get("thresholds") or []:
        rows.append({
            "Passing Yards": f"{int(round(float(item.get('threshold'))))}+" if _finite(item.get("threshold")) else "—",
            "P(At or Above)": _pct(item.get("over_probability")),
            "P(Below)": _pct(item.get("under_probability")),
        })
    return pd.DataFrame(rows)


def _capture_step8_calls():
    captured = []
    original = prior.context.build_context_projection

    def wrapped(step7, qb_profile, pressure_ctx, personnel_ctx, environment_ctx, side, preseason=False):
        result = original(step7, qb_profile, pressure_ctx, personnel_ctx, environment_ctx, side, preseason=preseason)
        captured.append(result)
        return result

    prior.context.build_context_projection = wrapped
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        prior.context.build_context_projection = original
    return captured


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_STEP9_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy9-active"><b>📊 STEP 9 ACTIVE — OUTCOME DISTRIBUTION + PROBABILITY</b>'
        '<span>Certified Steps 1–8 render unchanged below. Step 9 uses the exact Step 8 contextual location plus verified recent QB passing-yard variability to build a zero-truncated analytic distribution. No sportsbook line or price enters the model.</span></div>',
        unsafe_allow_html=True,
    )

    captured = _capture_step8_calls()
    if not captured:
        return

    st.markdown(
        '<div class="kpy-step"><div class="kpy-step-title">📊🧮 Step 9 — Outcome Distribution + Probability</div>'
        '<div class="kpy-step-sub">Step 8 central projection + observed recent-game variance • zero-truncated normal • exact analytic CDF • sportsbook influence 0.0%</div></div>',
        unsafe_allow_html=True,
    )

    rows = [distribution.build_distribution(item) for item in captured]
    st.markdown('<div class="kpy9-grid">' + "".join(_distribution_card(row) for row in rows) + '</div>', unsafe_allow_html=True)

    if rows and all(row.get("ready") for row in rows):
        st.success("✅ STEP 9 DISTRIBUTION + PROBABILITY GREEN • both verified Step 8 projections have an analytic outcome distribution driven by observed recent QB variability.")
    else:
        reasons = [row.get("reason") for row in rows if not row.get("ready") and row.get("reason")]
        st.warning("⚠️ STEP 9 DISTRIBUTION + PROBABILITY CHECK • " + " • ".join(reasons or ["probability evidence incomplete"]))

    cols = st.columns(len(rows)) if rows else []
    for col, row in zip(cols, rows):
        with col:
            with st.expander(f"Step 9 threshold probabilities — {_safe(row.get('qb_name'),'QB')}", expanded=False):
                table = _threshold_table(row)
                if table.empty:
                    st.info("Probability thresholds are withheld because the Step 9 distribution is not certified for this quarterback.")
                else:
                    st.dataframe(table, hide_index=True, use_container_width=True)
                st.caption(_safe(row.get("scale_source"), "recent variability unavailable"))
                st.caption("These are model probabilities from the displayed distribution assumption, not sportsbook-implied probabilities and not guarantees.")

    with st.expander("Step 9 methodology + hard guardrails", expanded=False):
        st.write("Step 9 uses the certified Step 8 contextual projection as the distribution location and the sample standard deviation from the last 3–5 verified QB games as the only probability scale. The Step 8 source-disagreement envelope is not converted into probability because it was explicitly descriptive, not a confidence interval.")
        st.write("Passing yards cannot be negative, so the normal approximation is conditioned on outcomes at or above zero. Quantiles and threshold probabilities are solved analytically with the standard-library normal CDF instead of Monte Carlo; under the stated distribution assumption this has zero simulation sampling error and avoids slowing the page with millions of unnecessary random draws.")
        st.write("If fewer than three verified recent games exist, observed variance is zero/invalid, Step 8 is withheld, or preseason workload is uncertified upstream, Step 9 fails closed and shows no probabilities.")
        st.write("Step 9 still does not read a sportsbook prop line or price. Fair odds, EV, ranking and recommendations remain OFF for the final build step.")
        st.caption("sportsbook influence = 0.0% • probability engine ON • Monte Carlo = OFF by design • fair odds/EV/ranking/recommendation OFF")

    st.caption(f"{MODEL_VERSION} • certified Steps 1–8 preserved • analytic distribution ON • generic threshold probabilities ON • sportsbook influence 0.0% • market betting outputs still OFF.")


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
