"""NFL Passing Yards V60 — polished Passing Yards page header.

Additive over frozen V59. Step 3 adds only a responsive page-level header with
slate/date context and compact status/filter chips. The frozen V58 picker and V59
selected-QB analysis render unchanged underneath.

No model, projection, probability, market math, data provider, sportsbook,
widget-key, or frozen Step 1/2 behavior is changed.
"""
from __future__ import annotations

from html import escape

import streamlit as st
import nfl_passing_yards_hub_v59 as prior

MODEL_VERSION = "NFL PASSING YARDS V60 • QB DRILL-DOWN STEP 3 HEADER"
FROZEN_PRIOR = "nfl_passing_yards_hub_v59"
DRILLDOWN_STEP = 3
HEADER_SYSTEM_VERSION = "v60"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_HEADER_CSS = r"""
<style data-passing-yards-step3-header-css="v60">
.ks-py60-header,.ks-py60-header *{box-sizing:border-box}
.ks-py60-header{
  position:relative;overflow:hidden;margin:.55rem 0 1rem;padding:24px;
  border:1px solid rgba(76,165,234,.30);border-radius:22px;
  background:linear-gradient(135deg,rgba(12,31,49,.96),rgba(7,19,31,.96) 58%,rgba(8,39,48,.88));
  box-shadow:0 22px 70px rgba(0,0,0,.26),inset 0 1px 0 rgba(255,255,255,.035)
}
.ks-py60-header:after{
  content:"";position:absolute;width:320px;height:320px;right:-110px;top:-170px;
  border-radius:50%;background:radial-gradient(circle,rgba(47,165,255,.22),transparent 67%);
  pointer-events:none
}
.ks-py60-main{
  position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1fr) auto;
  gap:26px;align-items:start
}
.ks-py60-eyebrow{
  display:flex;align-items:center;gap:8px;color:#5bc1ff;font-size:.64rem;font-weight:950;
  letter-spacing:.15em;text-transform:uppercase;margin-bottom:9px
}
.ks-py60-dot{
  width:7px;height:7px;border-radius:50%;background:#39e2bd;
  box-shadow:0 0 14px rgba(57,226,189,.74)
}
.ks-py60-title{
  margin:0;color:#f8fbff;font-size:clamp(1.9rem,4vw,3.35rem);
  line-height:.98;letter-spacing:-.055em;font-weight:950
}
.ks-py60-subtitle{
  max-width:760px;margin:12px 0 0;color:#9eb4c8;font-size:.88rem;
  line-height:1.55;font-weight:650
}
.ks-py60-slate{
  min-width:232px;border:1px solid #1d435f;border-radius:16px;padding:14px 16px;
  background:linear-gradient(180deg,rgba(9,28,44,.95),rgba(7,22,35,.95))
}
.ks-py60-slate-label{
  color:#67849d;font-size:.56rem;font-weight:950;letter-spacing:.14em;text-transform:uppercase
}
.ks-py60-slate-date{margin-top:5px;color:#eef8ff;font-size:.95rem;font-weight:900;letter-spacing:-.02em}
.ks-py60-slate-context{margin-top:3px;color:#6d8aa3;font-size:.68rem;font-weight:750}
.ks-py60-controls{
  position:relative;z-index:1;display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  margin-top:22px;padding-top:16px;border-top:1px solid rgba(69,129,170,.22)
}
.ks-py60-filter{
  display:inline-flex;align-items:center;min-height:32px;border:1px solid #244963;
  background:#091b2a;color:#9eb8cd;border-radius:999px;padding:8px 12px;
  font-size:.66rem;font-weight:900;letter-spacing:.01em
}
.ks-py60-filter.is-active{
  color:#f5fbff;border-color:#2b8dde;background:linear-gradient(180deg,#123c60,#0c2b46);
  box-shadow:0 0 0 1px rgba(53,163,255,.07),0 8px 22px rgba(0,0,0,.18)
}
.ks-py60-status{
  margin-left:auto;display:flex;align-items:center;gap:7px;border:1px solid #255b4c;
  background:#0a281f;color:#7af0bb;border-radius:999px;padding:8px 11px;
  font-size:.62rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase
}
.ks-py60-status-dot{
  width:7px;height:7px;border-radius:50%;background:#50e3a4;
  box-shadow:0 0 12px rgba(80,227,164,.72)
}
@media(max-width:760px){
  .ks-py60-header{padding:18px;border-radius:18px}
  .ks-py60-main{grid-template-columns:1fr;gap:16px}
  .ks-py60-slate{min-width:0;width:100%;display:grid;grid-template-columns:1fr auto;column-gap:12px;align-items:end}
  .ks-py60-slate-context{grid-column:1/-1}
  .ks-py60-controls{margin-top:16px;padding-top:14px}
  .ks-py60-status{margin-left:0}
}
@media(max-width:460px){
  .ks-py60-header{padding:15px}
  .ks-py60-title{font-size:2rem}
  .ks-py60-subtitle{font-size:.78rem}
  .ks-py60-controls{gap:6px}
  .ks-py60-filter,.ks-py60-status{padding:7px 9px;font-size:.58rem}
}
</style>
"""

def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return str(value or "").strip()

def _header_html() -> str:
    slate_date = _query_param("ks_py_date") or "CURRENT SLATE"
    selected = _query_param("ks_qb_slot")
    context = "Dedicated quarterback analysis" if selected in {"1", "2"} else "Choose a quarterback to open dedicated analysis"

    return (
        _HEADER_CSS
        + '<section class="ks-py60-header" data-passing-yards-step3-header="v60">'
        + '<div class="ks-py60-main"><div>'
        + '<div class="ks-py60-eyebrow"><span class="ks-py60-dot"></span>NFL PLAYER PROPS</div>'
        + '<h1 class="ks-py60-title">Passing Yards</h1>'
        + '<p class="ks-py60-subtitle">Quarterback projection hub built for fast matchup scanning, '
          'clear model context, and a clean path from slate to player detail.</p>'
        + '</div><aside class="ks-py60-slate" data-passing-yards-step3-slate="true">'
        + '<div class="ks-py60-slate-label">NFL • PASSING YARDS</div>'
        + f'<div class="ks-py60-slate-date">{escape(slate_date)}</div>'
        + f'<div class="ks-py60-slate-context">{escape(context)}</div>'
        + '</aside></div>'
        + '<div class="ks-py60-controls" data-passing-yards-step3-controls="true">'
        + '<span class="ks-py60-filter is-active" data-step3-filter="all">ALL QBs</span>'
        + '<span class="ks-py60-filter" data-step3-filter="home">HOME</span>'
        + '<span class="ks-py60-filter" data-step3-filter="away">AWAY</span>'
        + '<span class="ks-py60-filter" data-step3-filter="available">AVAILABLE</span>'
        + '<span class="ks-py60-status"><span class="ks-py60-status-dot"></span>CERTIFIED ANALYSIS</span>'
        + '</div></section>'
    )

def render_nfl_passing_yards_hub() -> None:
    header_html = _header_html()
    header_body = header_html[len(_HEADER_CSS):] if header_html.startswith(_HEADER_CSS) else header_html
    st.markdown(_HEADER_CSS, unsafe_allow_html=True)
    st.html(header_body)
    return prior.render_nfl_passing_yards_hub()

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V60 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "DRILLDOWN_STEP",
    "FROZEN_PRIOR",
    "HEADER_SYSTEM_VERSION",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_header_html",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
