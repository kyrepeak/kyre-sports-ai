"""NFL Passing Yards V59 — dedicated quarterback analysis view.

Additive over frozen V58. The Step 1 two-quarterback picker is inherited
unchanged. When a quarterback slot is present in the query, V59 renders exactly
one already-certified analytical payload for that quarterback.

No model, projection, probability, market math, data provider, sportsbook
influence, widget-key, or frozen Step 1 behavior is changed.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import nfl_passing_yards_hub_v48 as evidence
import nfl_passing_yards_hub_v58 as prior
from kyre_universal_components_v1 import build_badge, build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

MODEL_VERSION = "NFL PASSING YARDS V59 • QB DRILL-DOWN STEP 2"
FROZEN_PRIOR = "nfl_passing_yards_hub_v58"
DRILLDOWN_STEP = 2
DETAIL_SYSTEM_VERSION = "v59"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_QB_SLOT_PARAM = "ks_qb_slot"

_DETAIL_CSS = r"""
<style data-passing-yards-qb-detail="v59">
.ks-py59,.ks-py59 *{box-sizing:border-box}
.ks-py59{margin:.55rem 0 1.2rem;color:var(--kyre-sem-text-primary)}
.ks-py59-toolbar{
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  margin-bottom:var(--kyre-space-4)
}
.ks-py59-back{
  display:inline-flex;align-items:center;min-height:48px;padding:10px 14px;
  border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-section);
  color:var(--kyre-sem-text-accent-soft)!important;text-decoration:none!important;
  font-size:.72rem;font-weight:900
}
.ks-py59-head{
  display:flex;align-items:flex-start;justify-content:space-between;gap:12px;
  margin-bottom:var(--kyre-space-4);padding:var(--kyre-space-4) var(--kyre-space-5);
  border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-card);
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)
}
.ks-py59-kicker{
  color:var(--kyre-sem-text-accent-soft);font-size:.64rem;font-weight:950;
  letter-spacing:.12em;text-transform:uppercase
}
.ks-py59-title{
  margin:.18rem 0 0;font-size:clamp(1.28rem,2.3vw,1.78rem);
  font-weight:950;line-height:1.08
}
.ks-py59-sub{
  margin:.34rem 0 0;color:var(--kyre-sem-text-muted);font-size:.72rem;line-height:1.45
}
.ks-py59-analysis>.ks-py48-player{
  width:100%;max-width:100%;margin:0
}
@media(max-width:680px){
  .ks-py59-toolbar,.ks-py59-head{align-items:flex-start;flex-direction:column}
  .ks-py59-head{padding:var(--kyre-space-4)}
  .ks-py59-back{width:100%;justify-content:center}
}
</style>
"""

def _selected_analysis(captured: dict[str, list[str]], slot: int) -> str:
    index = slot - 1
    back = escape(prior._current_nav_url(None), quote=True)
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + prior._SELECTION_CSS
        + evidence._EVIDENCE_CSS
        + _DETAIL_CSS
        + f'<section class="ks-py59" data-passing-yards-qb-detail="v59" data-qb-slot="{slot}">'
        + '<div class="ks-py59-toolbar">'
        + f'<a class="ks-py59-back" data-qb-back="true" href="{back}">← Back to Quarterbacks</a>'
        + build_badge("DEDICATED QB VIEW", tone="success")
        + '</div>'
        + '<header class="ks-py59-head"><div>'
        + '<div class="ks-py59-kicker">PASSING YARDS • QUARTERBACK DETAIL</div>'
        + '<h2 class="ks-py59-title">Quarterback Analysis</h2>'
        + '<p class="ks-py59-sub">One player. One workspace. The certified analytical payload is isolated to the selected quarterback.</p>'
        + '</div>'
        + build_badge("MODEL FROZEN", tone="success")
        + '</header>'
        + f'<div class="ks-py59-analysis" data-selected-qb-analysis="{slot}">'
        + evidence._player(captured, index)
        + '</div></section>'
    )

def _qb_drilldown_step2_html(captured: dict[str, list[str]]) -> str:
    raw = prior._param(_QB_SLOT_PARAM)
    if raw in {"1", "2"}:
        return _selected_analysis(captured, int(raw))
    return prior._selection_screen(captured)

def render_nfl_passing_yards_hub() -> None:
    original = prior._qb_drilldown_html
    prior._qb_drilldown_html = _qb_drilldown_step2_html
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._qb_drilldown_html = original

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V59 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DETAIL_SYSTEM_VERSION",
    "DISPLAY_ONLY",
    "DRILLDOWN_STEP",
    "FROZEN_PRIOR",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_qb_drilldown_step2_html",
    "_selected_analysis",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
