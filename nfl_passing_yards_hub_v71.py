"""NFL Passing Yards V71 — Projection Explainability Step 2.

Additive presentation-only wrapper over frozen V70. It surfaces the already-
certified projection, market comparison, confidence, coverage, and five model
driver groups in one selected-QB panel. No projection, probability, market math,
data, sportsbook, widget, or navigation behavior is changed.
"""
from __future__ import annotations

from html import escape

import nfl_passing_yards_hub_v69 as detail_owner
import nfl_passing_yards_hub_v70 as prior

_FROZEN_SELECTED_ANALYSIS = detail_owner._selected_analysis_v69

MODEL_VERSION = "NFL PASSING YARDS V71 • PROJECTION EXPLAINABILITY STEP 2"
FROZEN_PRIOR = "nfl_passing_yards_hub_v70"
EXPLAINABILITY_VERSION = "v71"
NEW_PHASE_STEP = 2
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_EXPLAINABILITY_CSS = r"""
<style data-passing-yards-explainability-css="v71">
.ks-py71-explain,.ks-py71-explain *{box-sizing:border-box}
.ks-py71-explain{
  margin:10px 0 12px;
  padding:12px;
  border:1px solid var(--kyre-sem-border-medium);
  border-radius:14px;
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
}
.ks-py71-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
.ks-py71-kicker{font-size:.54rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase;color:var(--kyre-sem-text-accent-soft)}
.ks-py71-title{margin-top:3px;font-size:.96rem;font-weight:950;color:var(--kyre-sem-text-primary)}
.ks-py71-badge{flex:0 0 auto;border:1px solid var(--kyre-sem-border-medium);border-radius:999px;padding:5px 8px;font-size:.54rem;font-weight:950;color:var(--kyre-sem-text-accent-soft)}
.ks-py71-hero{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-bottom:10px}
.ks-py71-hero>div{min-width:0;padding:9px;border:1px solid var(--kyre-sem-border-soft);border-radius:10px;background:rgba(255,255,255,.018)}
.ks-py71-hero b{display:block;color:var(--kyre-sem-text-primary);font-size:.88rem;line-height:1.15;white-space:normal;overflow-wrap:anywhere}
.ks-py71-hero span{display:block;margin-top:4px;color:var(--kyre-sem-text-muted);font-size:.48rem;font-weight:900;line-height:1.3;text-transform:uppercase}
.ks-py71-drivers{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.ks-py71-driver{min-width:0;padding:9px 10px;border:1px solid var(--kyre-sem-border-soft);border-radius:10px;background:rgba(255,255,255,.012)}
.ks-py71-driver strong{display:block;color:var(--kyre-sem-text-primary);font-size:.66rem;line-height:1.35}
.ks-py71-driver span{display:block;margin-top:4px;color:var(--kyre-sem-text-muted);font-size:.56rem;line-height:1.5}
.ks-py71-driver em{font-style:normal;color:var(--kyre-sem-text-accent-soft);font-weight:900}
.ks-py71-market{margin-top:9px;padding-top:9px;border-top:1px solid var(--kyre-sem-border-soft);color:var(--kyre-sem-text-muted);font-size:.58rem;line-height:1.55}
.ks-py71-market strong{color:var(--kyre-sem-text-primary)}
.ks-py71-method{margin-top:8px}
.ks-py71-method summary{cursor:pointer;color:var(--kyre-sem-text-accent-soft);font-size:.58rem;font-weight:950}
.ks-py71-method p{margin:7px 0 0;color:var(--kyre-sem-text-muted);font-size:.56rem;line-height:1.55}
@media(max-width:760px){
  .ks-py71-head{flex-direction:column}
  .ks-py71-badge{align-self:flex-start}
  .ks-py71-hero{grid-template-columns:repeat(2,minmax(0,1fr))}
  .ks-py71-drivers{grid-template-columns:1fr}
}
@media(max-width:420px){
  .ks-py71-explain{padding:10px}
  .ks-py71-hero{grid-template-columns:1fr}
}
</style>
"""


def _value(source: str, label: str, *, span: bool = True, fallback: str = "—") -> str:
    if span:
        value = detail_owner._extract_b_span(source, label)
    else:
        value = detail_owner._extract_b_label(source, label)
    value = detail_owner._safe_text(value, limit=160, fallback=fallback)
    return value


def build_projection_explainability(source: str) -> str:
    """Build one read-only explanation panel from already-rendered frozen values."""
    projection = _value(source, "Baseline Pass Yards")
    attempts = _value(source, "Expected Attempts")
    ypa = _value(source, "Expected YPA")
    attempt_coverage = _value(source, "Attempt-source coverage", span=False)
    ypa_coverage = _value(source, "Efficiency-source coverage", span=False)

    line = _value(source, "Market Line")
    lean = _value(source, "Final Lean")
    confidence = _value(source, "Model Confidence")
    edge = _value(source, "Model edge Over / Under", span=False)

    pressure = _value(source, "Pressure context • not numerically adjusted", span=False)
    personnel = _value(source, "Personnel context • not numerically adjusted", span=False)

    drivers = (
        (
            "QB season workload",
            f"<em>45%</em> intended weight in the attempts blend. The frozen aggregate currently resolves to Expected Attempts {escape(attempts)}.",
        ),
        (
            "QB recent workload",
            "<em>20%</em> intended weight in the attempts blend, using the verified recent-three passing workload when available.",
        ),
        (
            "Opponent pass-defense volume + efficiency",
            "<em>20%</em> of intended attempts weight plus <em>25%</em> season and <em>10%</em> recent intended YPA weight.",
        ),
        (
            "QB passing efficiency",
            f"<em>45%</em> season + <em>20%</em> recent intended YPA weight. The frozen aggregate currently resolves to Expected YPA {escape(ypa)}.",
        ),
        (
            "Team passing pace",
            "<em>15%</em> intended attempts weight from verified team pass-attempt pace. Missing inputs are renormalized; source coverage remains visible.",
        ),
    )
    driver_html = "".join(
        f'<div class="ks-py71-driver" data-explainability-driver="{idx}"><strong>{escape(title)}</strong><span>{text}</span></div>'
        for idx, (title, text) in enumerate(drivers, start=1)
    )

    return (
        '<section class="ks-py71-explain" data-passing-yards-projection-explainability="v71">'
        '<div class="ks-py71-head"><div>'
        '<div class="ks-py71-kicker">Projection explainability • read-only</div>'
        '<div class="ks-py71-title">Why the model landed here</div>'
        f'</div><div class="ks-py71-badge">{escape(confidence)}</div></div>'
        '<div class="ks-py71-hero">'
        f'<div data-explainability-field="projection"><b>{escape(projection)}</b><span>Model Projection</span></div>'
        f'<div data-explainability-field="attempts"><b>{escape(attempts)}</b><span>Expected Attempts</span></div>'
        f'<div data-explainability-field="ypa"><b>{escape(ypa)}</b><span>Expected YPA</span></div>'
        f'<div data-explainability-field="coverage"><b>{escape(attempt_coverage)} / {escape(ypa_coverage)}</b><span>Attempt / Efficiency Coverage</span></div>'
        '</div>'
        f'<div class="ks-py71-drivers">{driver_html}</div>'
        '<div class="ks-py71-market" data-explainability-market-read="v71">'
        f'<strong>Post-model market comparison:</strong> Line {escape(line)} • Lean {escape(lean)} • Edge {escape(edge)} • Confidence {escape(confidence)}.<br>'
        f'<strong>Context carried separately:</strong> Pressure {escape(pressure)} • Personnel {escape(personnel)}. '
        'These labels do not silently change the frozen baseline unless the upstream certified model explicitly does so. '
        'Sportsbook projection influence remains 0.0%.'
        '</div>'
        '<details class="ks-py71-method" data-passing-yards-explainability-method="v71">'
        '<summary>How these reasons are produced</summary>'
        '<p>The five driver groups mirror the frozen Step 7 weight contract: attempts = QB season 45%, recent QB 20%, opponent attempts allowed 20%, team pace 15%; '
        'efficiency = QB season YPA 45%, recent QB YPA 20%, opponent season YPA allowed 25%, opponent recent YPA allowed 10%. '
        'Missing verified inputs are renormalized upstream and the coverage readouts expose how much intended weight was available. '
        'This panel only explains already-rendered values; it does not recalculate projection, probability, edge, lean, or confidence.</p>'
        '</details></section>'
    )


def _inject_projection_explainability(body: str) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-detail-cleanup="v69"' not in text
        or 'data-passing-yards-projection-explainability="v71"' in text
    ):
        return text

    panel = build_projection_explainability(text)
    projection_anchor = '<section class="ks-py69-clean-detail" data-passing-yards-clean-detail="projection"'
    pos = text.find(projection_anchor)
    if pos < 0:
        return text

    text = text[:pos] + panel + text[pos:]
    ready = 'data-passing-yards-detail-cleanup-ready="v69"'
    if ready in text and 'data-passing-yards-explainability-ready="v71"' not in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-explainability-ready="v71"',
            1,
        )
    return _EXPLAINABILITY_CSS + text


def _selected_analysis_v71(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_projection_explainability(
        _FROZEN_SELECTED_ANALYSIS(captured, slot)
    )


def render_nfl_passing_yards_hub() -> None:
    original = detail_owner._selected_analysis_v69
    detail_owner._selected_analysis_v69 = _selected_analysis_v71
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        detail_owner._selected_analysis_v69 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V71 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "EXPLAINABILITY_VERSION",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NEW_PHASE_STEP",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_inject_projection_explainability",
    "_selected_analysis_v71",
    "build_projection_explainability",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
