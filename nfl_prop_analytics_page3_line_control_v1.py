"""NFL Prop Analytics Page 3 Step 4 — movable historical analysis line.

This module adds a user-controlled threshold to the already-certified Page 3
historical sample. It never fetches or invents a sportsbook line: the control is
an explicit manual analysis line used only to recalculate descriptive historical
OVER/UNDER hit rates from verified Step 3 game rows.
"""
from __future__ import annotations

import html as html_lib
import math
from statistics import median
from typing import Any

import streamlit as st

from nfl_prop_analytics_history_stats_v1 import summarize_history

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 STEP 4 • MOVABLE ANALYSIS LINE V1"
PAGE3_LINE_STEP = 4
PAGE3_LINE_VERSION = "v1"
LINE_INCREMENT = 0.5
SPORTSBOOK_LINE_SOURCE = False
SPORTSBOOK_ODDS_LOGIC = False
PROJECTION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
WAGER_ACTIONS = False


def _number(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _values(games: Any) -> list[float]:
    out: list[float] = []
    for row in games or []:
        if not isinstance(row, dict):
            continue
        value = _number(row.get("value"))
        if value is not None:
            out.append(value)
    return out


def build_analysis_line_spec(
    games: Any,
    market_key: str,
) -> dict[str, Any]:
    """Build a safe half-point slider range from the verified historical sample."""
    values = _values(games)
    if not values:
        return {
            "ready": False,
            "reason": "verified historical sample is empty",
            "values": [],
        }

    market = str(market_key or "").strip()
    if market == "anytime_touchdown":
        return {
            "ready": True,
            "market_key": market,
            "values": values,
            "minimum": 0.5,
            "maximum": 0.5,
            "default": 0.5,
            "increment": LINE_INCREMENT,
            "movable": False,
        }

    low = min(values)
    high = max(values)
    span = max(1.0, high - low)
    padding = max(2.0, float(math.ceil(span * 0.25)))

    minimum_base = max(0.0, math.floor(low - padding))
    maximum_base = max(minimum_base + 1.0, math.ceil(high + padding))
    minimum = float(minimum_base) + 0.5
    maximum = float(maximum_base) + 0.5
    default = float(math.floor(median(values))) + 0.5
    default = min(max(default, minimum), maximum)

    return {
        "ready": True,
        "market_key": market,
        "values": values,
        "minimum": minimum,
        "maximum": maximum,
        "default": default,
        "increment": LINE_INCREMENT,
        "movable": maximum > minimum,
    }


def _pct(count: int, sample: int) -> float:
    return (float(count) / float(sample) * 100.0) if sample else 0.0


def render_analysis_line_control(
    *,
    games: Any,
    player_id: Any,
    market_key: Any,
    market_label: Any,
    history_key: Any,
    history_label: Any,
) -> dict[str, Any]:
    """Render Step 4 and return the selected line + recalculated hit-rate summary."""
    market = str(market_key or "").strip()
    market_name = str(market_label or market or "Selected prop").strip()
    history = str(history_key or "").strip()
    history_name = str(history_label or history or "Selected window").strip()
    athlete = str(player_id or "").strip()
    spec = build_analysis_line_spec(games, market)

    if not spec.get("ready"):
        st.markdown(
            f"""
<section class="ks-pa4-line ks-pa4-line-unavailable"
         data-prop-page3-step4-line-control="{PAGE3_LINE_VERSION}"
         data-prop-page3-step4-state="unavailable"
         data-prop-page3-step4-market="{html_lib.escape(market)}"
         data-prop-page3-step4-history="{html_lib.escape(history)}">
  <div class="ks-pa4-line-head">
    <span>LINE LAB</span>
    <strong>Manual analysis line unavailable</strong>
  </div>
  <p>{html_lib.escape(str(spec.get("reason") or "Verified history is required."))}</p>
</section>
""",
            unsafe_allow_html=True,
        )
        return {
            "ready": False,
            "reason": spec.get("reason") or "line control unavailable",
            "line": None,
            "summary": summarize_history([]),
        }

    minimum = float(spec["minimum"])
    maximum = float(spec["maximum"])
    default = float(spec["default"])
    movable = bool(spec.get("movable"))

    st.markdown(
        f"""
<section class="ks-pa4-line-intro"
         data-prop-page3-step4-intro="{PAGE3_LINE_VERSION}">
  <div>
    <span>STEP 4 • LINE LAB</span>
    <strong>{html_lib.escape(market_name)} • {html_lib.escape(history_name)}</strong>
  </div>
  <em>MANUAL ANALYSIS LINE • NOT A SPORTSBOOK LINE</em>
</section>
""",
        unsafe_allow_html=True,
    )

    if movable:
        line = float(
            st.slider(
                "Move analysis line",
                min_value=minimum,
                max_value=maximum,
                value=default,
                step=LINE_INCREMENT,
                key=(
                    "nfl_prop_analytics_page3_step4_line_v1_"
                    + "_".join((athlete or "player", market or "market", history or "window"))
                ),
                help=(
                    "Move this manual threshold to recalculate the verified historical "
                    "OVER/UNDER hit rate. It is not a sportsbook line."
                ),
            )
        )
    else:
        line = default
        st.caption("Anytime Touchdown uses the fixed 0.5 analysis threshold.")

    summary = summarize_history(list(games or []), line=line)
    values = list(spec["values"])
    sample = len(values)
    over_count = sum(1 for value in values if value > line)
    under_count = sum(1 for value in values if value < line)
    push_count = sample - over_count - under_count
    over_pct = _pct(over_count, sample)
    under_pct = _pct(under_count, sample)

    st.markdown(
        f"""
<section class="ks-pa4-line"
         data-prop-page3-step4-line-control="{PAGE3_LINE_VERSION}"
         data-prop-page3-step4-state="ready"
         data-prop-page3-step4-market="{html_lib.escape(market)}"
         data-prop-page3-step4-history="{html_lib.escape(history)}"
         data-prop-page3-step4-line="{line:.1f}"
         data-prop-page3-step4-min="{minimum:.1f}"
         data-prop-page3-step4-max="{maximum:.1f}"
         data-prop-page3-step4-increment="{LINE_INCREMENT:.1f}"
         data-prop-page3-step4-sample="{sample}"
         data-prop-page3-step4-over-count="{over_count}"
         data-prop-page3-step4-over-pct="{over_pct:.1f}"
         data-prop-page3-step4-under-count="{under_count}"
         data-prop-page3-step4-under-pct="{under_pct:.1f}"
         data-prop-page3-step4-push-count="{push_count}"
         data-prop-page3-step4-sportsbook-line="0">
  <div class="ks-pa4-line-head">
    <div>
      <span>LIVE HISTORICAL RECALCULATION</span>
      <strong>{html_lib.escape(market_name)} at {line:.1f}</strong>
    </div>
    <em>{html_lib.escape(history_name)} • {sample} VERIFIED GAMES</em>
  </div>
  <div class="ks-pa4-line-grid">
    <article class="ks-pa4-line-value">
      <span>ANALYSIS LINE</span>
      <strong>{line:.1f}</strong>
      <small>MOVE THE SLIDER</small>
    </article>
    <article>
      <span>OVER</span>
      <strong>{over_pct:.0f}%</strong>
      <small>{over_count}/{sample} GAMES</small>
    </article>
    <article>
      <span>UNDER</span>
      <strong>{under_pct:.0f}%</strong>
      <small>{under_count}/{sample} GAMES</small>
    </article>
  </div>
  <p class="ks-pa4-line-note">
    Historical threshold analysis only. No sportsbook line, odds, projection,
    recommendation, staking, or wager action is used.
  </p>
</section>
<style data-prop-page3-step4-css="{PAGE3_LINE_VERSION}">
.ks-pa4-line-intro{{
  width:100%;max-width:100%;min-width:0;margin:10px 0 6px;padding:10px 12px;
  border:1px solid rgba(56,189,248,.16);border-radius:13px;
  background:linear-gradient(180deg,rgba(7,18,31,.96),rgba(4,11,20,.98));
  display:flex;align-items:flex-end;justify-content:space-between;gap:10px;
}}
.ks-pa4-line-intro>div{{display:flex;flex-direction:column;gap:2px;min-width:0}}
.ks-pa4-line-intro span{{color:#38bdf8;font-size:.52rem;font-weight:950;letter-spacing:.12em}}
.ks-pa4-line-intro strong{{color:#edf8ff;font-size:.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa4-line-intro em{{color:#6f839c;font-size:.48rem;font-style:normal;font-weight:850;text-align:right}}
div[data-testid="stSlider"]{{margin:.08rem 0 .45rem;padding:0 2px}}
div[data-testid="stSlider"] label{{color:#91a4bc!important;font-size:.62rem!important;font-weight:850!important;letter-spacing:.06em!important;text-transform:uppercase!important}}
.ks-pa4-line{{
  width:100%;max-width:100%;min-width:0;margin:6px 0 12px;padding:13px;
  border:1px solid rgba(56,189,248,.20);border-radius:15px;
  background:
    radial-gradient(circle at 92% 0%,rgba(14,165,233,.10),transparent 17rem),
    linear-gradient(180deg,rgba(6,16,28,.98),rgba(3,10,18,.99));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
}}
.ks-pa4-line-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:10px}}
.ks-pa4-line-head>div{{display:flex;flex-direction:column;gap:2px;min-width:0}}
.ks-pa4-line-head span{{color:#6f839c;font-size:.5rem;font-weight:900;letter-spacing:.10em}}
.ks-pa4-line-head strong{{color:#e7f7ff;font-size:.84rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa4-line-head em{{color:#688098;font-size:.48rem;font-style:normal;font-weight:800;text-align:right}}
.ks-pa4-line-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}}
.ks-pa4-line-grid article{{min-width:0;padding:11px 10px;border:1px solid rgba(148,163,184,.10);border-radius:11px;background:rgba(15,23,42,.45);display:flex;flex-direction:column;gap:3px}}
.ks-pa4-line-grid article>span{{color:#71859d;font-size:.48rem;font-weight:900;letter-spacing:.08em}}
.ks-pa4-line-grid article>strong{{color:#f8fafc;font-size:1.28rem;line-height:1}}
.ks-pa4-line-grid article>small{{color:#60758d;font-size:.45rem;font-weight:850}}
.ks-pa4-line-grid .ks-pa4-line-value{{border-color:rgba(56,189,248,.25);background:linear-gradient(180deg,rgba(14,165,233,.10),rgba(15,23,42,.44))}}
.ks-pa4-line-grid .ks-pa4-line-value>strong{{color:#7dd3fc}}
.ks-pa4-line-note{{margin:9px 0 0;color:#657b94;font-size:.55rem;line-height:1.45}}
.ks-pa4-line-unavailable{{border-color:rgba(248,113,113,.16)}}
.ks-pa4-line-unavailable p{{margin:6px 0 0;color:#8295aa;font-size:.62rem}}
@media(max-width:560px){{
  .ks-pa4-line-intro,.ks-pa4-line-head{{align-items:flex-start;flex-direction:column}}
  .ks-pa4-line-intro em,.ks-pa4-line-head em{{text-align:left}}
  .ks-pa4-line-grid{{grid-template-columns:1fr 1fr}}
  .ks-pa4-line-grid .ks-pa4-line-value{{grid-column:1/-1}}
}}
</style>
""",
        unsafe_allow_html=True,
    )

    return {
        "ready": True,
        "state": "ready",
        "line": line,
        "minimum": minimum,
        "maximum": maximum,
        "increment": LINE_INCREMENT,
        "sample_size": sample,
        "over_count": over_count,
        "over_pct": over_pct,
        "under_count": under_count,
        "under_pct": under_pct,
        "push_count": push_count,
        "summary": summary,
        "sportsbook_line": False,
    }


__all__ = [
    "LINE_INCREMENT",
    "MODEL_VERSION",
    "PAGE3_LINE_STEP",
    "PAGE3_LINE_VERSION",
    "PROJECTION_LOGIC",
    "SPORTSBOOK_LINE_SOURCE",
    "SPORTSBOOK_ODDS_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "WAGER_ACTIONS",
    "build_analysis_line_spec",
    "render_analysis_line_control",
]
