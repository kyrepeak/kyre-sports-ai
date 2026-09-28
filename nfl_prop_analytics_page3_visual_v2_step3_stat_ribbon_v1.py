"""NFL Prop Analytics Page 3 Visual Composition V2 Step 3 — Quick Stat Ribbon.

Presentation-only rebuild of the approved five-card stat ribbon. All values are
supplied by the frozen Page 3 history / line-control truth. This module does not
load data, own interactions, mutate query state, or introduce projections.
"""
from __future__ import annotations

import html as html_lib
import math
from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 VISUAL COMPOSITION V2 • STEP 3 STAT RIBBON V1"
VISUAL_SERIES = "v2"
VISUAL_STEP = 3
VISUAL_VERSION = "v1"
PRESENTATION_ONLY = True
REAL_COMPOSITION_REBUILD = True
FROZEN_STEP2_HERO_PROTECTED = True
FROZEN_PAGE3_BEHAVIOR_PROTECTED = True
DATA_OWNERSHIP_CHANGED = False
INTERACTION_BEHAVIOR_CHANGED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
CERTIFIED_VIEWPORTS = (390, 768, 1440)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _fmt(value: Any, *, decimal: bool = False) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    if decimal:
        return f"{number:.1f}"
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.1f}"


def _hit_value(summary: dict[str, Any]) -> str:
    value = summary.get("hit_rate_pct")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    return f"{number:.0f}%"


def render_visual_v2_stat_ribbon(
    *,
    summary: dict[str, Any],
    market_label: Any,
    history_label: Any,
    source_note: Any,
    available: bool,
    target: Any | None = None,
) -> dict[str, Any]:
    payload = dict(summary or {})
    sample_size = int(payload.get("sample_size") or 0)
    state = "ready" if available and payload.get("ready") is True else "unavailable"

    average = _fmt(payload.get("average"), decimal=True) if state == "ready" else "—"
    median = _fmt(payload.get("median"), decimal=True) if state == "ready" else "—"
    high = _fmt(payload.get("high")) if state == "ready" else "—"
    low = _fmt(payload.get("low")) if state == "ready" else "—"
    hit_value = _hit_value(payload) if state == "ready" else "—"

    hit_state = _text(payload.get("hit_rate_state")) or "awaiting-line"
    hit_count = payload.get("hit_count")
    hit_note = (
        f"{int(hit_count)}/{sample_size} OVER"
        if state == "ready" and hit_count is not None and sample_size > 0
        else "LINE REQUIRED"
    )
    market = _text(market_label) or "Selected market"
    history = _text(history_label) or "Selected window"
    source = _text(source_note) or "Verified exact-ID history"

    html = f"""
<section class="ks-v2-stat-ribbon"
 data-page3-visual-v2-step3="{VISUAL_VERSION}"
 data-page3-visual-v2-step3-state="{state}"
 data-page3-visual-v2-step3-real-composition="true"
 data-page3-visual-v2-step3-market="{html_lib.escape(market)}"
 data-page3-visual-v2-step3-history="{html_lib.escape(history)}"
 data-page3-visual-v2-step3-sample="{sample_size}"
 data-page3-visual-v2-step3-average="{html_lib.escape(average)}"
 data-page3-visual-v2-step3-median="{html_lib.escape(median)}"
 data-page3-visual-v2-step3-high="{html_lib.escape(high)}"
 data-page3-visual-v2-step3-low="{html_lib.escape(low)}"
 data-page3-visual-v2-step3-hit-rate="{html_lib.escape(hit_value)}"
 data-page3-visual-v2-step3-hit-rate-state="{html_lib.escape(hit_state)}">
  <div class="ks-v2-stat-ribbon-track" role="group" aria-label="Quick statistics">
    <article data-v2-stat-card="average">
      <span>AVERAGE</span>
      <strong>{html_lib.escape(average)}</strong>
      <small>{html_lib.escape(history)} • {html_lib.escape(market.upper())}</small>
    </article>
    <article data-v2-stat-card="median">
      <span>MEDIAN</span>
      <strong>{html_lib.escape(median)}</strong>
      <small>MIDDLE RESULT</small>
    </article>
    <article data-v2-stat-card="season-high">
      <span>SEASON HIGH</span>
      <strong>{html_lib.escape(high)}</strong>
      <small>{html_lib.escape(history)} WINDOW</small>
    </article>
    <article data-v2-stat-card="season-low">
      <span>SEASON LOW</span>
      <strong>{html_lib.escape(low)}</strong>
      <small>{html_lib.escape(history)} WINDOW</small>
    </article>
    <article class="ks-v2-stat-hit" data-v2-stat-card="hit-rate">
      <span>HIT RATE</span>
      <strong>{html_lib.escape(hit_value)}</strong>
      <small>{html_lib.escape(hit_note)}</small>
    </article>
  </div>
  <p class="ks-v2-stat-source">HISTORICAL ONLY • {html_lib.escape(source)}</p>
</section>

<style data-page3-visual-v2-step3-css="{VISUAL_VERSION}">
/* V2 Step 3 replaces the old six-card statistics presentation only. */
.ks-pa3-stats{{display:none!important}}

.ks-v2-stat-ribbon{{
  width:100%;max-width:100%;min-width:0;
  margin:-1px 0 14px;padding:0;
  overflow-x:auto;overflow-y:hidden;
  scrollbar-width:thin;scrollbar-color:rgba(56,189,248,.36) transparent;
}}
.ks-v2-stat-ribbon-track{{
  display:grid;grid-template-columns:repeat(5,minmax(0,1fr));
  gap:10px;min-width:0;
}}
.ks-v2-stat-ribbon article{{
  position:relative;isolation:isolate;overflow:hidden;
  min-width:0;min-height:88px;
  display:flex;flex-direction:column;justify-content:center;gap:3px;
  padding:11px 13px;
  border:1px solid rgba(125,211,252,.28);border-radius:14px;
  background:
    radial-gradient(circle at 15% 0%,rgba(56,189,248,.12),transparent 65%),
    linear-gradient(145deg,rgba(7,20,34,.98),rgba(3,12,22,.98));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.035),0 8px 24px rgba(0,0,0,.22);
}}
.ks-v2-stat-ribbon article::before{{
  content:"";position:absolute;left:0;top:0;bottom:0;width:2px;
  background:linear-gradient(#7dd3fc,#0ea5e9);
  box-shadow:0 0 12px rgba(56,189,248,.42);
}}
.ks-v2-stat-ribbon article>span{{
  color:#7dd3fc;font-size:.58rem;font-weight:950;letter-spacing:.11em;
}}
.ks-v2-stat-ribbon article>strong{{
  margin-top:1px;color:#f8fbff;
  font-size:clamp(1.42rem,2.25vw,2rem);line-height:.95;letter-spacing:-.035em;
}}
.ks-v2-stat-ribbon article>small{{
  color:#71879c;font-size:.49rem;font-weight:800;letter-spacing:.035em;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}}
.ks-v2-stat-ribbon .ks-v2-stat-hit{{
  border-color:rgba(56,189,248,.5);
  background:
    radial-gradient(circle at 50% -20%,rgba(14,165,233,.22),transparent 68%),
    linear-gradient(145deg,rgba(7,23,39,.99),rgba(3,13,24,.99));
}}
.ks-v2-stat-source{{
  margin:6px 2px 0;color:#586f86;font-size:.48rem;font-weight:750;
  letter-spacing:.055em;text-align:right;
}}

@media(max-width:760px){{
  .ks-v2-stat-ribbon-track{{
    grid-template-columns:repeat(5,minmax(112px,1fr));
    min-width:590px;gap:8px;
  }}
  .ks-v2-stat-ribbon article{{min-height:82px;padding:10px 11px}}
  .ks-v2-stat-ribbon article>strong{{font-size:1.45rem}}
}}
@media(max-width:520px){{
  .ks-v2-stat-ribbon{{margin-bottom:12px}}
  .ks-v2-stat-ribbon-track{{grid-template-columns:repeat(5,minmax(108px,1fr));min-width:570px}}
  .ks-v2-stat-source{{text-align:left}}
}}
@media(prefers-reduced-motion:reduce){{
  .ks-v2-stat-ribbon *{{transition:none!important;animation:none!important}}
}}
</style>
"""
    sink = target if target is not None else st
    sink.markdown(html, unsafe_allow_html=True)

    return {
        "ready": state == "ready",
        "state": state,
        "version": VISUAL_VERSION,
        "real_composition_rebuild": True,
        "presentation_only": True,
        "card_count": 5,
        "sample_size": sample_size,
        "average": average,
        "median": median,
        "high": high,
        "low": low,
        "hit_rate": hit_value,
        "data_ownership_changed": False,
        "interaction_behavior_changed": False,
        "projection_weight": 0.0,
    }


__all__ = [
    "CERTIFIED_VIEWPORTS",
    "DATA_OWNERSHIP_CHANGED",
    "INTERACTION_BEHAVIOR_CHANGED",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "REAL_COMPOSITION_REBUILD",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VISUAL_SERIES",
    "VISUAL_STEP",
    "VISUAL_VERSION",
    "render_visual_v2_stat_ribbon",
]
