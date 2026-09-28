"""NFL Prop Analytics Page 3 Visual Composition V2 Step 5 — lower analytics.

Presentation-only composition for the approved Line Lab, live recalculation,
and game-by-game chart regions. Frozen Page 3 owners continue to own the real
Streamlit slider, history math, selected line, OVER/UNDER classification, and
chart truth.
"""
from __future__ import annotations

import html as html_lib
import math
from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 VISUAL COMPOSITION V2 • STEP 5 LOWER ANALYTICS V1"
VISUAL_SERIES = "v2"
VISUAL_STEP = 5
VISUAL_VERSION = "v1"
PRESENTATION_ONLY = True
REAL_COMPOSITION_REBUILD = True
FROZEN_STEP2_HERO_PROTECTED = True
FROZEN_STEP3_RIBBON_PROTECTED = True
FROZEN_STEP4_SETTINGS_PROTECTED = True
FROZEN_LINE_CONTROL_PROTECTED = True
FROZEN_GAME_CHART_PROTECTED = True
DATA_OWNERSHIP_CHANGED = False
INTERACTION_BEHAVIOR_CHANGED = False
QUERY_SEMANTICS_CHANGED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MIN_TOUCH_TARGET_PX = 44
CERTIFIED_VIEWPORTS = (390, 768, 1440)

LINE_CONTAINER_KEY = "nfl_prop_visual_v2_step5_line_lab_v1"
CHART_CONTAINER_KEY = "nfl_prop_visual_v2_step5_game_chart_v1"


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _number(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fmt(value: Any, *, percent: bool = False) -> str:
    number = _number(value)
    if number is None:
        return "—"
    if percent:
        return f"{number:.0f}%"
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.1f}"


def _base_css() -> str:
    return f"""
<style data-page3-visual-v2-step5-css="{VISUAL_VERSION}">
/* V2 Step 5 owns presentation only. Frozen owners remain in the DOM. */
.st-key-{LINE_CONTAINER_KEY}{{
  width:100%;max-width:100%;min-width:0;
  margin:14px 0 12px!important;
  padding:15px 16px 14px!important;
  border:1px solid rgba(125,211,252,.30)!important;
  border-radius:15px!important;
  background:
    radial-gradient(circle at 92% 0%,rgba(14,165,233,.13),transparent 21rem),
    linear-gradient(180deg,rgba(5,17,30,.99),rgba(2,9,17,.995))!important;
  box-shadow:
    0 18px 44px rgba(0,0,0,.22),
    inset 0 1px 0 rgba(255,255,255,.035)!important;
  overflow:visible!important;
}}
.st-key-{LINE_CONTAINER_KEY} .ks-pa4-line-intro,
.st-key-{LINE_CONTAINER_KEY} .ks-pa4-line{{
  display:none!important;
}}

.ks-v2-step5-line-head{{
  display:grid;
  grid-template-columns:minmax(0,1fr) auto;
  grid-template-areas:
    "copy disclaimer"
    "value value";
  align-items:start;gap:10px 16px;
  padding:1px 1px 13px;
  border-bottom:1px solid rgba(125,211,252,.10);
}}
.ks-v2-step5-line-copy{{grid-area:copy;min-width:0;display:flex;flex-direction:column;gap:2px}}
.ks-v2-step5-line-copy>span{{
  color:#69d4ff;font-size:.55rem;font-weight:950;letter-spacing:.135em;
}}
.ks-v2-step5-line-copy>strong{{
  color:#f2f9ff;font-size:.96rem;line-height:1.15;letter-spacing:-.012em;
}}
.ks-v2-step5-line-copy>small{{
  color:#70869d;font-size:.52rem;font-weight:760;
}}
.ks-v2-step5-line-disclaimer{{
  grid-area:disclaimer;align-self:start;
  padding:6px 9px;border-radius:999px;
  border:1px solid rgba(125,211,252,.14);
  background:rgba(14,165,233,.05);
  color:#8199af;font-size:.48rem;font-weight:900;letter-spacing:.055em;
  white-space:nowrap;
}}
.ks-v2-step5-line-value{{
  grid-area:value;justify-self:center;
  min-width:150px;margin-top:2px;text-align:center;
  display:flex;flex-direction:column;gap:0;
}}
.ks-v2-step5-line-value>span{{
  color:#70869d;font-size:.48rem;font-weight:950;letter-spacing:.13em;
}}
.ks-v2-step5-line-value>strong{{
  color:#a7e8ff;font-size:2.55rem;line-height:1;
  letter-spacing:-.055em;text-shadow:0 0 24px rgba(56,189,248,.22);
}}
.ks-v2-step5-line-value>small{{
  margin-top:3px;color:#60758c;font-size:.46rem;font-weight:820;
}}

.st-key-{LINE_CONTAINER_KEY} [data-testid="stSlider"]{{
  width:100%!important;
  margin:.55rem 0 0!important;
  padding:11px 8px 4px!important;
  border:0!important;background:transparent!important;box-shadow:none!important;
}}
.st-key-{LINE_CONTAINER_KEY} [data-testid="stSlider"] label{{
  position:absolute!important;width:1px!important;height:1px!important;
  padding:0!important;margin:-1px!important;overflow:hidden!important;
  clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important;
}}
.st-key-{LINE_CONTAINER_KEY} [data-testid="stSlider"] [role="slider"]{{
  min-width:{MIN_TOUCH_TARGET_PX}px!important;
  min-height:{MIN_TOUCH_TARGET_PX}px!important;
  filter:drop-shadow(0 0 10px rgba(56,189,248,.50))!important;
}}

.ks-v2-step5-live{{
  width:100%;max-width:100%;min-width:0;
  margin:0 0 12px;padding:13px;
  border:1px solid rgba(125,211,252,.21);border-radius:15px;
  background:
    radial-gradient(circle at 92% 0%,rgba(56,189,248,.08),transparent 18rem),
    linear-gradient(180deg,rgba(5,15,27,.98),rgba(3,10,18,.99));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
}}
.ks-v2-step5-live-head{{
  display:flex;align-items:flex-end;justify-content:space-between;gap:12px;
  margin-bottom:9px;padding-bottom:9px;
  border-bottom:1px solid rgba(125,211,252,.08);
}}
.ks-v2-step5-live-head>div{{min-width:0;display:flex;flex-direction:column;gap:2px}}
.ks-v2-step5-live-head span{{
  color:#69d4ff;font-size:.53rem;font-weight:950;letter-spacing:.12em;
}}
.ks-v2-step5-live-head strong{{
  color:#edf8ff;font-size:.86rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}}
.ks-v2-step5-live-head em{{
  color:#657b92;font-size:.47rem;font-style:normal;font-weight:850;text-align:right;
}}
.ks-v2-step5-live-grid{{
  display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;
}}
.ks-v2-step5-live-grid article{{
  position:relative;overflow:hidden;min-width:0;min-height:88px;
  padding:12px 11px;border:1px solid rgba(125,211,252,.11);border-radius:12px;
  background:linear-gradient(180deg,rgba(12,27,44,.72),rgba(6,15,27,.90));
  display:flex;flex-direction:column;justify-content:center;gap:3px;
}}
.ks-v2-step5-live-grid article::before{{
  content:"";position:absolute;left:0;top:11px;bottom:11px;width:2px;
  border-radius:999px;background:linear-gradient(180deg,#38bdf8,rgba(56,189,248,.08));
}}
.ks-v2-step5-live-grid article>span{{
  color:#7b91a8;font-size:.47rem;font-weight:930;letter-spacing:.085em;
}}
.ks-v2-step5-live-grid article>strong{{
  color:#f4fbff;font-size:1.44rem;line-height:1;letter-spacing:-.035em;
}}
.ks-v2-step5-live-grid article>small{{
  color:#60758d;font-size:.44rem;font-weight:800;
}}
.ks-v2-step5-live-grid article[data-v2-live-card="analysis-line"]{{
  border-color:rgba(56,189,248,.28);
  background:linear-gradient(180deg,rgba(7,35,54,.88),rgba(5,18,31,.97));
}}
.ks-v2-step5-live-grid article[data-v2-live-card="analysis-line"]>strong{{
  color:#8bdcff;text-shadow:0 0 17px rgba(56,189,248,.16);
}}

.st-key-{CHART_CONTAINER_KEY}{{
  width:100%;max-width:100%;min-width:0;margin:0 0 14px!important;
}}
.ks-v2-step5-chart-marker{{display:none!important}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-chart{{
  margin:0!important;padding:14px!important;
  border:1px solid rgba(125,211,252,.22)!important;
  border-radius:15px!important;
  background:
    radial-gradient(circle at 94% 2%,rgba(56,189,248,.09),transparent 21rem),
    linear-gradient(180deg,rgba(5,16,28,.99),rgba(2,9,17,.995))!important;
  box-shadow:0 18px 44px rgba(0,0,0,.20),inset 0 1px 0 rgba(255,255,255,.03)!important;
}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-head{{
  padding-bottom:9px!important;border-bottom:1px solid rgba(125,211,252,.08)!important;
}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-head span{{color:#69d4ff!important;letter-spacing:.13em!important}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-head strong{{font-size:.91rem!important}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-legend{{
  margin:9px 0 6px!important;gap:7px!important;flex-wrap:wrap!important;
}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-legend span{{
  padding:4px 7px!important;border:1px solid rgba(125,211,252,.10);
  border-radius:999px;background:rgba(15,23,42,.37);
}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-scroll{{
  margin-top:7px;padding:9px 7px 5px!important;
  border:1px solid rgba(125,211,252,.08);border-radius:12px;
  background:
    repeating-linear-gradient(0deg,rgba(125,211,252,.024) 0 1px,transparent 1px 32px),
    linear-gradient(180deg,rgba(3,12,22,.64),rgba(3,9,17,.34));
}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-plot{{height:246px!important}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-bar{{border-radius:7px 7px 3px 3px!important}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-over{{box-shadow:0 0 17px rgba(56,189,248,.20)!important}}
.st-key-{CHART_CONTAINER_KEY} .ks-pa5-foot{{
  padding-top:8px!important;border-top:1px solid rgba(125,211,252,.06)!important;
}}

@media(max-width:760px){{
  .ks-v2-step5-live-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}
}}
@media(max-width:560px){{
  .st-key-{LINE_CONTAINER_KEY}{{padding:12px 11px 11px!important;border-radius:14px!important}}
  .ks-v2-step5-line-head{{
    grid-template-columns:1fr;grid-template-areas:"copy" "disclaimer" "value";
    gap:8px;
  }}
  .ks-v2-step5-line-disclaimer{{justify-self:start;white-space:normal}}
  .ks-v2-step5-line-value>strong{{font-size:2.25rem}}
  .ks-v2-step5-live{{padding:11px;border-radius:14px}}
  .ks-v2-step5-live-head{{align-items:flex-start;flex-direction:column;gap:3px}}
  .ks-v2-step5-live-head em{{text-align:left}}
  .ks-v2-step5-live-grid{{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
  .ks-v2-step5-live-grid article{{min-height:82px;padding:10px 9px}}
  .st-key-{CHART_CONTAINER_KEY} .ks-pa5-chart{{padding:11px!important;border-radius:14px!important}}
  .st-key-{CHART_CONTAINER_KEY} .ks-pa5-scroll{{padding:7px 5px 4px!important}}
}}
@media(prefers-reduced-motion:reduce){{
  .st-key-{LINE_CONTAINER_KEY} *, .ks-v2-step5-live *, .st-key-{CHART_CONTAINER_KEY} *{{
    transition:none!important;animation:none!important;
  }}
}}
</style>
"""


def render_visual_v2_line_lab(
    *,
    line_control: dict[str, Any],
    market_label: Any,
    history_label: Any,
    target: Any | None = None,
) -> dict[str, Any]:
    ready = bool((line_control or {}).get("ready"))
    line = _number((line_control or {}).get("line"))
    minimum = _number((line_control or {}).get("minimum"))
    maximum = _number((line_control or {}).get("maximum"))
    state = "ready" if ready and line is not None else "unavailable"

    html = f"""
<section class="ks-v2-step5-line-head"
 data-page3-visual-v2-step5="{VISUAL_VERSION}"
 data-page3-visual-v2-step5-region="line-lab"
 data-page3-visual-v2-step5-state="{state}"
 data-page3-visual-v2-step5-line="{_fmt(line)}"
 data-page3-visual-v2-step5-min="{_fmt(minimum)}"
 data-page3-visual-v2-step5-max="{_fmt(maximum)}"
 data-page3-visual-v2-step5-real-composition="true"
 data-page3-visual-v2-step5-presentation-only="true"
 data-page3-visual-v2-step5-interaction-change="false"
 data-page3-visual-v2-step5-data-owner-change="false">
  <div class="ks-v2-step5-line-copy">
    <span>LINE LAB</span>
    <strong>{html_lib.escape(_text(market_label) or "Selected prop")} • {html_lib.escape(_text(history_label) or "Selected history")}</strong>
    <small>Move the verified historical analysis threshold</small>
  </div>
  <div class="ks-v2-step5-line-disclaimer">MANUAL ANALYSIS LINE • NOT A SPORTSBOOK LINE</div>
  <div class="ks-v2-step5-line-value">
    <span>CURRENT LINE</span>
    <strong>{_fmt(line)}</strong>
    <small>{_fmt(minimum)} MIN • {_fmt(maximum)} MAX</small>
  </div>
</section>
{_base_css()}
"""
    sink = target if target is not None else st
    sink.markdown(html, unsafe_allow_html=True)
    return {
        "ready": ready,
        "state": state,
        "version": VISUAL_VERSION,
        "line": line,
        "minimum": minimum,
        "maximum": maximum,
        "presentation_only": True,
        "interaction_behavior_changed": False,
        "data_ownership_changed": False,
    }


def render_visual_v2_live_recalculation(
    *,
    line_control: dict[str, Any],
    history_summary: dict[str, Any],
    market_label: Any,
    history_label: Any,
) -> dict[str, Any]:
    ready = bool((line_control or {}).get("ready"))
    line = _number((line_control or {}).get("line"))
    over_pct = _number((line_control or {}).get("over_pct"))
    under_pct = _number((line_control or {}).get("under_pct"))
    average = _number((history_summary or {}).get("average"))
    sample = int((line_control or {}).get("sample_size") or (history_summary or {}).get("sample_size") or 0)
    state = "ready" if ready and line is not None else "unavailable"

    st.markdown(
        f"""
<section class="ks-v2-step5-live"
 data-page3-visual-v2-step5="{VISUAL_VERSION}"
 data-page3-visual-v2-step5-region="live-recalculation"
 data-page3-visual-v2-step5-live-state="{state}"
 data-page3-visual-v2-step5-live-card-count="4"
 data-page3-visual-v2-step5-live-line="{_fmt(line)}"
 data-page3-visual-v2-step5-live-over="{_fmt(over_pct, percent=True)}"
 data-page3-visual-v2-step5-live-under="{_fmt(under_pct, percent=True)}">
  <div class="ks-v2-step5-live-head">
    <div>
      <span>LIVE HISTORICAL RECALCULATION</span>
      <strong>{html_lib.escape(_text(market_label) or "Selected prop")} • {html_lib.escape(_text(history_label) or "Selected history")}</strong>
    </div>
    <em>{sample} VERIFIED GAMES • FROZEN HISTORY MATH</em>
  </div>
  <div class="ks-v2-step5-live-grid">
    <article data-v2-live-card="analysis-line"><span>ANALYSIS LINE</span><strong>{_fmt(line)}</strong><small>MANUAL THRESHOLD</small></article>
    <article data-v2-live-card="over-percent"><span>OVER %</span><strong>{_fmt(over_pct, percent=True)}</strong><small>VERIFIED HISTORY</small></article>
    <article data-v2-live-card="under-percent"><span>UNDER %</span><strong>{_fmt(under_pct, percent=True)}</strong><small>VERIFIED HISTORY</small></article>
    <article data-v2-live-card="average-stat"><span>AVERAGE STAT</span><strong>{_fmt(average)}</strong><small>{html_lib.escape((_text(market_label) or "SELECTED PROP").upper())}</small></article>
  </div>
</section>
""",
        unsafe_allow_html=True,
    )
    return {
        "ready": ready,
        "state": state,
        "card_count": 4,
        "line": line,
        "over_pct": over_pct,
        "under_pct": under_pct,
        "average": average,
        "sample_size": sample,
    }


def render_visual_v2_game_chart_marker(
    *,
    market_label: Any,
    history_label: Any,
) -> dict[str, Any]:
    st.markdown(
        f"""
<div class="ks-v2-step5-chart-marker"
 data-page3-visual-v2-step5="{VISUAL_VERSION}"
 data-page3-visual-v2-step5-region="game-chart"
 data-page3-visual-v2-step5-chart-state="ready"
 data-page3-visual-v2-step5-market="{html_lib.escape(_text(market_label))}"
 data-page3-visual-v2-step5-history="{html_lib.escape(_text(history_label))}"></div>
""",
        unsafe_allow_html=True,
    )
    return {
        "ready": True,
        "state": "ready",
        "market_label": _text(market_label),
        "history_label": _text(history_label),
    }


__all__ = [
    "CERTIFIED_VIEWPORTS",
    "CHART_CONTAINER_KEY",
    "DATA_OWNERSHIP_CHANGED",
    "FROZEN_GAME_CHART_PROTECTED",
    "FROZEN_LINE_CONTROL_PROTECTED",
    "FROZEN_STEP2_HERO_PROTECTED",
    "FROZEN_STEP3_RIBBON_PROTECTED",
    "FROZEN_STEP4_SETTINGS_PROTECTED",
    "INTERACTION_BEHAVIOR_CHANGED",
    "LINE_CONTAINER_KEY",
    "MIN_TOUCH_TARGET_PX",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "QUERY_SEMANTICS_CHANGED",
    "REAL_COMPOSITION_REBUILD",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VISUAL_SERIES",
    "VISUAL_STEP",
    "VISUAL_VERSION",
    "render_visual_v2_game_chart_marker",
    "render_visual_v2_line_lab",
    "render_visual_v2_live_recalculation",
]
