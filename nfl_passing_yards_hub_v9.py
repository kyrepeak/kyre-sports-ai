"""NFL Passing Yards V9 — Step 8 bounded context + uncertainty.

Certified V8 / Steps 1–7 are rendered unchanged. V9 captures the exact Step 7
builder inputs/results during that render and appends Step 8 without repeating
network work or rewriting certified predecessor logic.
"""
from __future__ import annotations

from html import escape
import math

import pandas as pd
import streamlit as st

import nfl_passing_yards_hub_v8 as prior
import nfl_passing_yards_context_v1 as context

MODEL_VERSION = "NFL PASSING YARDS V9 • STEP 8 CONTEXT + UNCERTAINTY"

_STEP8_CSS = r"""
<style>
.kpy8-active{border:1px solid #7a5b25;background:#221a0c;border-radius:13px;padding:10px 12px;margin:4px 0 10px}
.kpy8-active b{color:#ffd47f;font-size:.84rem}.kpy8-active span{color:#9faeb9;font-size:.52rem;display:block;margin-top:3px}
.kpy8-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0 10px}
.kpy8-card{border:1px solid #49627a;background:#07131f;border-radius:14px;padding:11px}
.kpy8-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:9px}
.kpy8-name{font-size:.94rem;font-weight:950;color:#f8fbff}.kpy8-sub{font-size:.5rem;color:#7890a3;margin-top:3px;line-height:1.45}
.kpy8-grade{font-size:.54rem;font-weight:950;border-radius:999px;padding:5px 8px;border:1px solid #4b6278;white-space:nowrap}
.kpy8-grade.high{color:#78efbb;border-color:#32775b;background:#0a2a20}.kpy8-grade.medium{color:#9ed3ff;border-color:#416d8d;background:#0b2234}.kpy8-grade.low{color:#f2ca74;border-color:#796538;background:#2a2412}.kpy8-grade.check{color:#a6b6c3}
.kpy8-hero{display:grid;grid-template-columns:1.35fr 1fr 1fr;gap:6px;margin-bottom:7px}.kpy8-hero>div{border:1px solid #213e54;background:#06111b;border-radius:10px;padding:8px}
.kpy8-hero b{display:block;font-size:1.12rem;color:#fff}.kpy8-hero span{display:block;font-size:.43rem;color:#70879a;text-transform:uppercase;margin-top:2px}
.kpy8-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.kpy8-meta>div{border:1px solid #1d374b;background:#07121c;border-radius:9px;padding:7px 6px;font-size:.47rem;color:#7990a4}
.kpy8-meta b{display:block;color:#eff6fb;font-size:.69rem;margin-bottom:2px}.kpy8-note{margin-top:7px;padding-top:7px;border-top:1px solid #1b3449;color:#7f97a9;font-size:.49rem;line-height:1.55}
@media(max-width:820px){.kpy8-grid{grid-template-columns:1fr}.kpy8-hero{grid-template-columns:1fr 1fr}.kpy8-hero>div:first-child{grid-column:1/-1}}
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


def _signed(value, digits=1, suffix="") -> str:
    if not _finite(value):
        return "—"
    return f"{float(value):+.{digits}f}{suffix}"


def _context_card(row: dict) -> str:
    grade = _safe(row.get("confidence"), "CHECK").upper()
    css = grade.lower() if grade.lower() in {"high", "medium", "low"} else "check"
    pressure = row.get("pressure") or {}
    state = "READY" if row.get("ready") else "WITHHELD"
    return (
        '<section class="kpy8-card">'
        '<div class="kpy8-top">'
        f'<div><div class="kpy8-name">{escape(_safe(row.get("qb_name"),"Unresolved QB1"))} • Context Projection</div>'
        f'<div class="kpy8-sub">bounded pressure opportunity + visible uncertainty • {state}</div></div>'
        f'<div class="kpy8-grade {css}">{escape(grade)}</div></div>'
        '<div class="kpy8-hero">'
        f'<div><b>{_fmt(row.get("context_projection_yards"),1)}</b><span>Context Pass Yards</span></div>'
        f'<div><b>{_fmt(row.get("baseline_yards"),1)}</b><span>Step 7 Baseline</span></div>'
        f'<div><b>{_signed(row.get("pressure_adjustment_yards"),1)}</b><span>Pressure Adjustment</span></div>'
        '</div>'
        '<div class="kpy8-meta">'
        f'<div><b>{_fmt(row.get("context_attempts"),1)}</b>Context attempts</div>'
        f'<div><b>{_fmt(row.get("expected_ypa"),2)}</b>YPA held at Step 7 value</div>'
        f'<div><b>{_fmt(row.get("uncertainty_lower"),1)} – {_fmt(row.get("uncertainty_upper"),1)}</b>Descriptive uncertainty envelope</div>'
        f'<div><b>{_signed(pressure.get("bounded_delta_pct_points"),2," pp")}</b>Bounded sack-rate delta</div>'
        f'<div><b>{escape(_safe(row.get("personnel_context"),"CHECK"))}</b>Personnel • numerical effect 0.0</div>'
        f'<div><b>{escape(_safe(row.get("weather_context"),"CHECK"))}</b>Weather • numerical effect 0.0</div>'
        '</div>'
        '<div class="kpy8-note">'
        f'Rest: <b>{escape(_safe(row.get("rest_context"),"CHECK"))}</b> • '
        f'pressure cap hit: <b>{"YES" if pressure.get("cap_hit") else "NO"}</b><br>'
        f'{escape(_safe(row.get("confidence_basis"), row.get("reason") or "evidence incomplete"))}'
        '</div></section>'
    )


def _detail_table(row: dict) -> pd.DataFrame:
    pressure = row.get("pressure") or {}
    uncertainty = row.get("uncertainty") or {}
    recent = uncertainty.get("recent") or {}
    source = uncertainty.get("source") or {}
    rows = [
        {"Layer": "Pressure", "Metric": "Offense sack rate", "Value": _fmt(pressure.get("offense_sack_rate_pct"), 2, "%")},
        {"Layer": "Pressure", "Metric": "Opponent generated sack rate", "Value": _fmt(pressure.get("defense_sack_rate_pct"), 2, "%")},
        {"Layer": "Pressure", "Metric": "Matchup sack rate", "Value": _fmt(pressure.get("matchup_sack_rate_pct"), 2, "%")},
        {"Layer": "Pressure", "Metric": "Raw delta", "Value": _signed(pressure.get("raw_delta_pct_points"), 2, " pp")},
        {"Layer": "Pressure", "Metric": "Bounded delta", "Value": _signed(pressure.get("bounded_delta_pct_points"), 2, " pp")},
        {"Layer": "Pressure", "Metric": "Attempt adjustment", "Value": _signed(pressure.get("attempt_adjustment"), 2)},
        {"Layer": "Pressure", "Metric": "Yard adjustment", "Value": _signed(pressure.get("yard_adjustment"), 1)},
        {"Layer": "Recent variability", "Metric": "Recent games", "Value": str(recent.get("games") or 0)},
        {"Layer": "Recent variability", "Metric": "Sample SD", "Value": _fmt(recent.get("sample_std_yards"), 1, " yds")},
        {"Layer": "Source disagreement", "Metric": "Lower envelope", "Value": _fmt(source.get("lower"), 1)},
        {"Layer": "Source disagreement", "Metric": "Upper envelope", "Value": _fmt(source.get("upper"), 1)},
    ]
    return pd.DataFrame(rows)


def _capture_step7_calls():
    captured = []
    original = prior.projection.build_baseline_projection

    def wrapped(qb_ctx, qb_profile, defense_profile, pressure_ctx, personnel_ctx, environment_ctx, side, preseason=False):
        result = original(qb_ctx, qb_profile, defense_profile, pressure_ctx, personnel_ctx, environment_ctx, side, preseason=preseason)
        captured.append({
            "step7": result,
            "qb_profile": qb_profile,
            "pressure_ctx": pressure_ctx,
            "personnel_ctx": personnel_ctx,
            "environment_ctx": environment_ctx,
            "side": side,
            "preseason": preseason,
        })
        return result

    prior.projection.build_baseline_projection = wrapped
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        prior.projection.build_baseline_projection = original
    return captured


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_STEP8_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy8-active"><b>🧠 STEP 8 ACTIVE — BOUNDED CONTEXT + UNCERTAINTY</b>'
        '<span>Certified Steps 1–7 render unchanged below. Step 8 captures their exact verified inputs, applies only the mechanical pressure-opportunity adjustment, then exposes uncertainty instead of hiding it.</span></div>',
        unsafe_allow_html=True,
    )

    captured = _capture_step7_calls()
    if not captured:
        return

    st.markdown(
        '<div class="kpy-step"><div class="kpy-step-title">🧠📏 Step 8 — Bounded Context + Uncertainty</div>'
        '<div class="kpy-step-sub">Pressure opportunity can move the central number within a hard cap • personnel/weather/rest stay qualitative • uncertainty is descriptive, not a probability interval</div></div>',
        unsafe_allow_html=True,
    )

    rows = []
    for item in captured:
        rows.append(context.build_context_projection(
            item["step7"],
            item["qb_profile"],
            item["pressure_ctx"],
            item["personnel_ctx"],
            item["environment_ctx"],
            item["side"],
            preseason=item["preseason"],
        ))

    st.markdown('<div class="kpy8-grid">' + "".join(_context_card(row) for row in rows) + '</div>', unsafe_allow_html=True)
    if rows and all(row.get("ready") for row in rows):
        st.success("✅ STEP 8 CONTEXT + UNCERTAINTY GREEN • both Step 7 baselines received bounded verified pressure-opportunity treatment and transparent uncertainty evidence.")
    else:
        reasons = [row.get("reason") for row in rows if not row.get("ready") and row.get("reason")]
        st.warning("⚠️ STEP 8 CONTEXT + UNCERTAINTY CHECK • " + " • ".join(reasons or ["context evidence incomplete"]))

    cols = st.columns(len(rows)) if rows else []
    for col, row in zip(cols, rows):
        with col:
            with st.expander(f"Step 8 evidence — {_safe(row.get('qb_name'),'QB')}", expanded=False):
                st.dataframe(_detail_table(row), hide_index=True, use_container_width=True)
                uncertainty = row.get("uncertainty") or {}
                st.caption(_safe(uncertainty.get("band_type"), "DESCRIPTIVE ENVELOPE — NOT A PROBABILITY INTERVAL"))
                st.caption(_safe(uncertainty.get("basis"), "uncertainty evidence unavailable"))

    with st.expander("Step 8 methodology + hard guardrails", expanded=False):
        st.write("The only central numerical context adjustment is pressure opportunity: matchup sack rate versus the offense's own verified season sack rate. The difference is capped at ±5 percentage points and translated into pass-attempt opportunity while Step 7 YPA stays unchanged.")
        st.write("Personnel, weather, rest and site/travel can lower evidence confidence, but Step 8 gives them exactly 0.0 yardage adjustment because their effect sizes have not been calibrated here.")
        st.write("The uncertainty envelope is not a confidence interval and carries no hit probability. It uses observed recent-game variability when at least three games exist and the min/max disagreement among the verified Step 7 source components; when both exist, the wider union is shown.")
        st.write("A verified OUT / IR / PUP / reserve / doubtful QB status blocks the full-game contextual projection instead of guessing workload.")
        st.caption("sportsbook influence = 0.0% • personnel/weather/rest numerical adjustment = 0.0 • Monte Carlo/probability/fair-line/EV/ranking/recommendation OFF")

    st.caption(f"{MODEL_VERSION} • Step 7 certified baseline preserved • bounded context ON • uncertainty envelope ON • sportsbook influence 0.0% • betting outputs still OFF.")


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
