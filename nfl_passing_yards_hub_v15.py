"""NFL Passing Yards V15 — cleanup step 3: decision-first game center.

Presentation-only wrapper over certified V14. It promotes the model result,
probability state, confidence, and verified market state to a compact game-center
summary near the top of the page while leaving the full certified Steps 1–10
analysis below. No loader, projection, distribution, market, or grading math is
changed and no extra network calls are made.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v14 as prior
import nfl_passing_yards_hub_v10 as step9_ui
import nfl_passing_yards_hub_v11 as step10_ui

MODEL_VERSION = "NFL PASSING YARDS V15 • CLEANUP STEP 3 • DECISION-FIRST GAME CENTER"

_CLEANUP_STEP3_CSS = r"""
<style>
/* V15 owns the production headline; retire V13's predecessor headline. */
.kpy-final-head{display:none!important}

.kpy15-head{border:1px solid #31546d;background:linear-gradient(135deg,#07131f,#0b1e2d);border-radius:15px;padding:12px 13px;margin:3px 0 8px;box-shadow:0 9px 26px rgba(0,0,0,.18)}
.kpy15-headrow{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.kpy15-title{font-size:1.2rem;font-weight:950;color:#f8fbff;letter-spacing:-.025em;line-height:1.05}.kpy15-title span{color:#7ff2c2}
.kpy15-sub{font-size:.59rem;color:#8498aa;line-height:1.45;margin-top:4px;max-width:760px}
.kpy15-status{border:1px solid #34795b;background:#09271d;color:#81edb7;border-radius:999px;padding:5px 8px;font-size:.48rem;font-weight:950;white-space:nowrap}
.kpy15-chips{display:flex;gap:4px;flex-wrap:wrap;margin-top:8px}.kpy15-chip{border:1px solid #29485f;background:#071725;color:#9dc9e5;border-radius:999px;padding:4px 6px;font-size:.45rem;font-weight:900;white-space:nowrap}

.kpy15-center{border:1px solid #28475d;background:#06111b;border-radius:14px;padding:10px;margin:0 0 10px}
.kpy15-centerhead{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px}.kpy15-centertitle{font-size:.76rem;font-weight:950;color:#edf6fb}.kpy15-centersub{font-size:.45rem;color:#738a9d;margin-top:2px}.kpy15-modeltag{font-size:.44rem;font-weight:900;color:#82eab6;border:1px solid #2d7055;background:#082319;border-radius:999px;padding:4px 6px;white-space:nowrap}
.kpy15-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.kpy15-qb{border:1px solid #315269;background:#081521;border-radius:12px;padding:9px;min-width:0}
.kpy15-qbtop{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:7px}.kpy15-name{font-size:.82rem;font-weight:950;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy15-conf{font-size:.43rem;font-weight:950;border-radius:999px;padding:4px 6px;border:1px solid #405d72;color:#b7c7d3;white-space:nowrap}.kpy15-conf.high{color:#7cebbb;border-color:#32775b;background:#09261c}.kpy15-conf.medium{color:#9ed3ff;border-color:#416d8d;background:#0a2233}.kpy15-conf.low{color:#efc978;border-color:#766239;background:#292312}
.kpy15-hero{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:5px}.kpy15-metric{border:1px solid #1c394d;background:#05101a;border-radius:9px;padding:7px 6px;min-width:0}.kpy15-metric b{display:block;color:#fff;font-size:.9rem;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy15-metric span{display:block;color:#6f8698;font-size:.39rem;text-transform:uppercase;margin-top:3px}
.kpy15-market{margin-top:6px;border-top:1px solid #193348;padding-top:6px;display:flex;justify-content:space-between;gap:8px;align-items:center}.kpy15-marketlead{font-size:.58rem;color:#dce9f1;font-weight:900}.kpy15-marketmeta{font-size:.43rem;color:#7890a3;text-align:right;line-height:1.35}
.kpy15-grade{font-size:.42rem;font-weight:950;border-radius:999px;padding:4px 6px;border:1px solid #415c70;color:#a8bbc9}.kpy15-grade.a{color:#6af0ad;border-color:#2d7c58;background:#09281c}.kpy15-grade.b{color:#8ee9bd;border-color:#39745b;background:#0b251c}.kpy15-grade.c{color:#f1ca72;border-color:#796538;background:#2a2412}.kpy15-grade.pass{color:#9ed3ff;border-color:#416d8d;background:#0b2234}
.kpy15-foot{font-size:.43rem;color:#688094;margin-top:7px;line-height:1.45}

/* De-emphasize the long evidence trail now that the result is promoted. */
.kpy-step-sub{opacity:.78}

@media(max-width:700px){
  .kpy15-head{padding:11px 10px}.kpy15-title{font-size:1.08rem}.kpy15-sub{font-size:.56rem}.kpy15-status{font-size:.44rem;padding:4px 6px}
  .kpy15-grid{grid-template-columns:1fr}
  .kpy15-center{padding:8px}.kpy15-qb{padding:8px}
  .kpy15-hero{grid-template-columns:1.2fr 1fr 1fr}
  .kpy15-metric b{font-size:.84rem}.kpy15-metric span{font-size:.37rem}
}
</style>
"""

_HEADER = """
<section class="kpy15-head">
  <div class="kpy15-headrow">
    <div>
      <div class="kpy15-title">🏈 NFL <span>Passing Yards</span></div>
      <div class="kpy15-sub">Decision-first game center up top. Full verified Steps 1–10 evidence stays below for anyone who wants to audit the pick.</div>
    </div>
    <div class="kpy15-status">10 / 10 COMPLETE</div>
  </div>
  <div class="kpy15-chips">
    <span class="kpy15-chip">MODEL FIRST</span>
    <span class="kpy15-chip">PROBABILITY</span>
    <span class="kpy15-chip">MARKET EDGE</span>
    <span class="kpy15-chip">SPORTSBOOK PROJECTION 0%</span>
  </div>
</section>
"""


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    if not _finite(value):
        return "—"
    return f"{float(value):.{digits}f}{suffix}"


def _pct(value: Any) -> str:
    if not _finite(value):
        return "—"
    return f"{100.0 * float(value):.1f}%"


def _confidence_class(value: Any) -> str:
    label = _safe(value, "CHECK").lower()
    return label if label in {"high", "medium", "low"} else ""


def _market_grade_class(value: Any) -> str:
    label = _safe(value, "CHECK").lower()
    return label if label in {"a", "b", "c", "pass"} else ""


def _summary_card(dist: dict, market_row: dict | None) -> str:
    market_row = market_row or {}
    q = dist.get("quantiles") or {}
    confidence = _safe(dist.get("confidence"), "CHECK").upper()
    conf_css = _confidence_class(confidence)

    if market_row.get("grade_ready"):
        lean = _safe(market_row.get("lean"), "PASS")
        grade = _safe(market_row.get("grade"), "PASS").upper()
        grade_css = _market_grade_class(grade)
        line = _fmt(market_row.get("line"), 1)
        market_meta = f"Line {line} • Over {_pct(market_row.get('model_over_probability'))} • Under {_pct(market_row.get('model_under_probability'))}"
        market_state = f'<span class="kpy15-grade {grade_css}">{escape(grade)}</span>'
    else:
        lean = "MODEL READY • MARKET PENDING"
        market_meta = "Enter a verified two-way half-yard market in Step 10 for final edge/grade."
        market_state = '<span class="kpy15-grade">CHECK</span>'

    return (
        '<section class="kpy15-qb">'
        '<div class="kpy15-qbtop">'
        f'<div class="kpy15-name">{escape(_safe(dist.get("qb_name"), "Unresolved QB1"))}</div>'
        f'<div class="kpy15-conf {conf_css}">{escape(confidence)}</div>'
        '</div>'
        '<div class="kpy15-hero">'
        f'<div class="kpy15-metric"><b>{_fmt(dist.get("location_yards"),1)}</b><span>Model Projection</span></div>'
        f'<div class="kpy15-metric"><b>{_fmt(q.get("p50"),1)}</b><span>P50 Median</span></div>'
        f'<div class="kpy15-metric"><b>{_fmt(dist.get("sigma_yards"),1)}</b><span>Recent SD</span></div>'
        '</div>'
        '<div class="kpy15-market">'
        f'<div><div class="kpy15-marketlead">{escape(lean)}</div><div class="kpy15-marketmeta" style="text-align:left">{escape(market_meta)}</div></div>'
        f'{market_state}'
        '</div>'
        '</section>'
    )


def _summary_html(distributions: list[dict], markets: list[dict]) -> str:
    if not distributions:
        return ""
    cards = []
    for idx, dist in enumerate(distributions):
        market_row = markets[idx] if idx < len(markets) else {}
        cards.append(_summary_card(dist, market_row))
    ready = sum(1 for row in distributions if row.get("ready"))
    return (
        '<section class="kpy15-center">'
        '<div class="kpy15-centerhead">'
        '<div><div class="kpy15-centertitle">⚡ Game Center — Result First</div>'
        f'<div class="kpy15-centersub">{ready}/{len(distributions)} QB probability distributions certified • full evidence trail remains below</div></div>'
        '<div class="kpy15-modeltag">MODEL-INDEPENDENT FROM MARKET</div>'
        '</div>'
        f'<div class="kpy15-grid">{"".join(cards)}</div>'
        '<div class="kpy15-foot">Projection and probability are completed before sportsbook inputs are read. Market line/price can only be compared afterward; sportsbook projection influence remains exactly 0.0%.</div>'
        '</section>'
    )


def render_nfl_passing_yards_hub() -> None:
    """Render V14 and promote already-computed certified results to the top."""
    st.markdown(_CLEANUP_STEP3_CSS, unsafe_allow_html=True)
    st.markdown(_HEADER, unsafe_allow_html=True)
    result_slot = st.empty()

    captured_distributions: list[dict] = []
    captured_markets: list[dict] = []

    original_distribution = step9_ui.distribution.build_distribution
    original_market_card = step10_ui._market_card

    def capture_distribution(*args, **kwargs):
        row = original_distribution(*args, **kwargs)
        captured_distributions.append(row)
        return row

    def capture_market_card(row: dict):
        captured_markets.append(dict(row or {}))
        return original_market_card(row)

    step9_ui.distribution.build_distribution = capture_distribution
    step10_ui._market_card = capture_market_card
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        step9_ui.distribution.build_distribution = original_distribution
        step10_ui._market_card = original_market_card

    summary = _summary_html(captured_distributions, captured_markets)
    if summary:
        result_slot.markdown(summary, unsafe_allow_html=True)


__all__ = [
    "MODEL_VERSION",
    "_CLEANUP_STEP3_CSS",
    "_summary_html",
    "render_nfl_passing_yards_hub",
]
