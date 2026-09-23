"""NFL Passing Yards V63 — New Phase Step 2 Market + Edge Detail.

Additive presentation-only wrapper over frozen V62. Step 2 does not change
projection, probability, market math, sportsbook logic, data providers, query
state, Category Navigation, or Back behavior. It only reads values already
rendered by the certified market card and exposes a compact decision-detail
panel for the selected quarterback.
"""
from __future__ import annotations

from html import escape, unescape
import re

import nfl_passing_yards_hub_v62 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v62

MODEL_VERSION = "NFL PASSING YARDS V63 • NEW PHASE STEP 2 MARKET + EDGE DETAIL"
FROZEN_PRIOR = "nfl_passing_yards_hub_v62"
MARKET_DETAIL_VERSION = "v63"
NEW_PHASE_STEP = 2
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_MARKET_DETAIL_CSS = r"""
<style data-passing-yards-market-detail-css="v63">
.ks-py63-market-detail,.ks-py63-market-detail *{box-sizing:border-box}
.ks-py63-market-detail{
  margin:0 0 12px;padding:12px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-section);
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
}
.ks-py63-market-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
.ks-py63-market-kicker{font-size:.54rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase;color:var(--kyre-sem-text-accent-soft)}
.ks-py63-market-title{margin-top:3px;font-size:.92rem;font-weight:950;line-height:1.15;color:var(--kyre-sem-text-primary)}
.ks-py63-market-badge{flex:0 0 auto;border:1px solid var(--kyre-sem-border-strong);border-radius:999px;padding:5px 8px;font-size:.48rem;font-weight:950;color:var(--kyre-sem-text-muted);white-space:nowrap}
.ks-py63-market-hero{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-bottom:8px}
.ks-py63-market-hero>div,.ks-py63-market-grid>div{
  min-width:0;border:1px solid var(--kyre-sem-border-soft);border-radius:11px;
  background:var(--kyre-sem-surface-column);padding:8px 9px
}
.ks-py63-market-hero b,.ks-py63-market-grid b{display:block;color:var(--kyre-sem-text-primary);font-size:.82rem;line-height:1.2;overflow-wrap:anywhere}
.ks-py63-market-hero span,.ks-py63-market-grid span{display:block;margin-top:3px;color:var(--kyre-sem-text-muted);font-size:.45rem;font-weight:900;line-height:1.25;text-transform:uppercase}
.ks-py63-market-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
.ks-py63-market-source{margin-top:8px;padding-top:8px;border-top:1px solid var(--kyre-sem-border-soft);font-size:.53rem;line-height:1.5;color:var(--kyre-sem-text-muted)}
.ks-py63-market-source strong{color:var(--kyre-sem-text-primary)}
.ks-py63-market-method{margin-top:8px;border-top:1px solid var(--kyre-sem-border-soft);padding-top:8px}
.ks-py63-market-method summary{cursor:pointer;color:var(--kyre-sem-text-accent-soft);font-size:.56rem;font-weight:950}
.ks-py63-market-method p{margin:7px 0 0;color:var(--kyre-sem-text-muted);font-size:.54rem;line-height:1.55}
@media(max-width:760px){
  .ks-py63-market-detail{padding:10px}
  .ks-py63-market-head{gap:8px}
  .ks-py63-market-hero{grid-template-columns:1fr 1fr}
  .ks-py63-market-hero>div:first-child{grid-column:1/-1}
  .ks-py63-market-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
</style>
"""

def _plain(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", str(value or ""), flags=re.S)
    return unescape(text).strip()


def _extract_b_span(body: str, label: str) -> str:
    pattern = rf"<b>(.*?)</b>\s*<span>{re.escape(label)}</span>"
    match = re.search(pattern, body, flags=re.S | re.I)
    return _plain(match.group(1)) if match else "—"


def _extract_b_label(body: str, label: str) -> str:
    pattern = rf"<b>(.*?)</b>\s*{re.escape(label)}"
    match = re.search(pattern, body, flags=re.S | re.I)
    return _plain(match.group(1)) if match else "—"


def _extract_source(body: str) -> str:
    match = re.search(r'<div class="kpy10-sub">(.*?)</div>', body, flags=re.S | re.I)
    value = _plain(match.group(1)) if match else ""
    if " • projection influence" in value:
        value = value.split(" • projection influence", 1)[0].strip()
    return value or "Verified market source unavailable"


def _field(kind: str, label: str, value: str) -> str:
    return (
        f'<div data-market-field="{escape(kind, quote=True)}">'
        f'<b>{escape(value)}</b><span>{escape(label)}</span></div>'
    )


def build_market_detail(body: str) -> str:
    lean = _extract_b_span(body, "Final Lean")
    line = _extract_b_span(body, "Market Line")
    confidence = _extract_b_span(body, "Model Confidence")
    model_probability = _extract_b_label(body, "Model Over / Under")
    fair_odds = _extract_b_label(body, "Model fair Over / Under")
    offered_odds = _extract_b_label(body, "Offered Over / Under")
    no_vig = _extract_b_label(body, "No-vig Over / Under")
    edge = _extract_b_label(body, "Model edge Over / Under")
    ev = _extract_b_label(body, "EV per $1 Over / Under")
    source = _extract_source(body)

    hero = "".join((
        _field("lean", "Final Lean", lean),
        _field("line", "Market Line", line),
        _field("confidence", "Model Confidence", confidence),
    ))
    grid = "".join((
        _field("model-probability", "Model Over / Under", model_probability),
        _field("fair-odds", "Model Fair Odds", fair_odds),
        _field("offered-odds", "Offered Odds", offered_odds),
        _field("no-vig", "No-Vig Market", no_vig),
        _field("edge", "Model Edge", edge),
        _field("ev", "EV per $1", ev),
    ))
    return (
        '<section class="ks-py63-market-detail" data-passing-yards-market-detail="v63">'
        '<div class="ks-py63-market-head"><div>'
        '<div class="ks-py63-market-kicker">Post-model market read</div>'
        '<div class="ks-py63-market-title">Market Decision Detail</div>'
        '</div><div class="ks-py63-market-badge">MODEL INDEPENDENT</div></div>'
        f'<div class="ks-py63-market-hero">{hero}</div>'
        f'<div class="ks-py63-market-grid">{grid}</div>'
        '<div class="ks-py63-market-source"><strong>Source:</strong> '
        f'{escape(source)} • sportsbook projection influence 0.0% • stake sizing OFF</div>'
        '<details class="ks-py63-market-method" data-passing-yards-market-method="v63">'
        '<summary>How to read this market detail</summary>'
        '<p>Model probability and fair odds come from the already-certified model. '
        'Offered odds and no-vig values are the verified market comparison. '
        'Edge is model probability minus the no-vig market probability, and EV '
        'uses the displayed offered price. This panel does not recalculate or '
        'alter any value; it only reorganizes the frozen market card.</p></details>'
        '</section>'
    )


def _inject_market_detail(body: str) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-market-detail="v63"' in text
    ):
        return text

    market_anchor = '<strong>Current Market + Edge</strong>'
    if market_anchor not in text:
        return text

    detail = build_market_detail(text)
    text = text.replace(market_anchor, market_anchor + detail, 1)

    ready = 'data-passing-yards-category-nav-ready="v62"'
    if ready in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-market-detail-ready="v63"',
            1,
        )
    return _MARKET_DETAIL_CSS + text


def _selected_analysis_v63(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_market_detail(_FROZEN_SELECTED_ANALYSIS(captured, slot))


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v62
    prior._selected_analysis_v62 = _selected_analysis_v63
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v62 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V63 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MARKET_DETAIL_VERSION",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NEW_PHASE_STEP",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_inject_market_detail",
    "_selected_analysis_v63",
    "build_market_detail",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
