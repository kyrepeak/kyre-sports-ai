"""NFL Passing Yards V65 — New Phase Step 4 Context + Uncertainty Detail.

Additive presentation-only wrapper over frozen V64. Step 4 does not change
projection, probability, market math, sportsbook logic, data providers, query
state, Category Navigation, Market Decision Detail, Projection Detail, or Back
behavior. It only reads values already rendered by the certified Context +
Uncertainty card and exposes a compact context-detail panel for the selected QB.
"""
from __future__ import annotations

from html import escape, unescape
import re

import nfl_passing_yards_hub_v64 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v64

MODEL_VERSION = "NFL PASSING YARDS V65 • NEW PHASE STEP 4 CONTEXT + UNCERTAINTY DETAIL"
FROZEN_PRIOR = "nfl_passing_yards_hub_v64"
CONTEXT_DETAIL_VERSION = "v65"
NEW_PHASE_STEP = 4
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_CONTEXT_DETAIL_CSS = r"""
<style data-passing-yards-context-detail-css="v65">
.ks-py65-context-detail,.ks-py65-context-detail *{box-sizing:border-box}
.ks-py65-context-detail{
  margin:0 0 12px;padding:12px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-section);
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
}
.ks-py65-context-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
.ks-py65-context-kicker{font-size:.54rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase;color:var(--kyre-sem-text-accent-soft)}
.ks-py65-context-title{margin-top:3px;font-size:.92rem;font-weight:950;line-height:1.15;color:var(--kyre-sem-text-primary)}
.ks-py65-context-badge{flex:0 0 auto;border:1px solid var(--kyre-sem-border-medium);border-radius:999px;padding:5px 8px;font-size:.54rem;font-weight:950;color:var(--kyre-sem-text-accent-soft)}
.ks-py65-context-hero{display:grid;grid-template-columns:1.2fr repeat(2,minmax(0,1fr));gap:8px;margin-bottom:8px}
.ks-py65-context-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
.ks-py65-context-hero>div,.ks-py65-context-grid>div{
  min-width:0;padding:10px;border:1px solid var(--kyre-sem-border-soft);
  border-radius:11px;background:rgba(255,255,255,.018)
}
.ks-py65-context-detail [data-context-field] b{
  display:block;color:var(--kyre-sem-text-primary);font-size:.92rem;font-weight:950;
  line-height:1.12;white-space:normal;overflow-wrap:anywhere
}
.ks-py65-context-detail [data-context-field] span{
  display:block;margin-top:4px;color:var(--kyre-sem-text-muted);font-size:.56rem;
  line-height:1.3;text-transform:uppercase;letter-spacing:.03em
}
.ks-py65-context-source{
  margin-top:9px;padding-top:9px;border-top:1px solid var(--kyre-sem-border-soft);
  color:var(--kyre-sem-text-muted);font-size:.64rem;line-height:1.5
}
.ks-py65-context-source strong{color:var(--kyre-sem-text-primary)}
.ks-py65-context-method{margin-top:8px}
.ks-py65-context-method summary{cursor:pointer;color:var(--kyre-sem-text-accent-soft);font-size:.64rem;font-weight:900}
.ks-py65-context-method p{margin:7px 0 0;color:var(--kyre-sem-text-muted);font-size:.64rem;line-height:1.55}
@media(max-width:900px){
  .ks-py65-context-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:700px){
  .ks-py65-context-head{flex-direction:column;gap:8px}
  .ks-py65-context-badge{align-self:flex-start}
  .ks-py65-context-hero{grid-template-columns:repeat(2,minmax(0,1fr))}
  .ks-py65-context-hero>div:first-child{grid-column:1/-1}
}
@media(max-width:430px){
  .ks-py65-context-grid{grid-template-columns:1fr}
}
</style>
"""


def _plain(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = unescape(text)
    return " ".join(text.split()).strip()


def _extract_b_span(body: str, label: str) -> str:
    pattern = rf"<b>(.*?)</b>\s*<span>{re.escape(label)}</span>"
    match = re.search(pattern, body, flags=re.S | re.I)
    return _plain(match.group(1)) if match else "—"


def _extract_b_label(body: str, label: str) -> str:
    pattern = rf"<b>(.*?)</b>\s*{re.escape(label)}"
    match = re.search(pattern, body, flags=re.S | re.I)
    return _plain(match.group(1)) if match else "—"


def _extract_grade(body: str) -> str:
    match = re.search(r'<div class="kpy8-grade[^"]*">(.*?)</div>', body, flags=re.S | re.I)
    return _plain(match.group(1)) if match else "CHECK"


def _extract_context_sub(body: str) -> str:
    match = re.search(r'<div class="kpy8-sub">(.*?)</div>', body, flags=re.S | re.I)
    return _plain(match.group(1)) if match else "Certified bounded context + visible uncertainty"


def _extract_note(body: str) -> tuple[str, str, str]:
    match = re.search(r'<div class="kpy8-note">(.*?)</div>', body, flags=re.S | re.I)
    if not match:
        return "—", "—", "Context evidence basis unavailable"
    chunk = match.group(1)
    rest = re.search(r'Rest:\s*<b>(.*?)</b>', chunk, flags=re.S | re.I)
    cap = re.search(r'pressure cap hit:\s*<b>(.*?)</b>', chunk, flags=re.S | re.I)
    basis = chunk.split("<br>", 1)[1] if "<br>" in chunk else ""
    return (
        _plain(rest.group(1)) if rest else "—",
        _plain(cap.group(1)) if cap else "—",
        _plain(basis) or "Context evidence basis unavailable",
    )


def _field(kind: str, label: str, value: str) -> str:
    return (
        f'<div data-context-field="{escape(kind, quote=True)}">'
        f'<b>{escape(value)}</b><span>{escape(label)}</span></div>'
    )


def build_context_detail(body: str) -> str:
    context_yards = _extract_b_span(body, "Context Pass Yards")
    baseline = _extract_b_span(body, "Step 7 Baseline")
    pressure_adjustment = _extract_b_span(body, "Pressure Adjustment")
    attempts = _extract_b_label(body, "Context attempts")
    ypa = _extract_b_label(body, "YPA held at Step 7 value")
    envelope = _extract_b_label(body, "Descriptive uncertainty envelope")
    sack_delta = _extract_b_label(body, "Bounded sack-rate delta")
    personnel = _extract_b_label(body, "Personnel • numerical effect 0.0")
    weather = _extract_b_label(body, "Weather • numerical effect 0.0")
    rest, pressure_cap, basis = _extract_note(body)
    grade = _extract_grade(body)
    context_sub = _extract_context_sub(body)

    hero = "".join((
        _field("context-yards", "Context Pass Yards", context_yards),
        _field("baseline-yards", "Baseline Pass Yards", baseline),
        _field("pressure-adjustment", "Pressure Adjustment", pressure_adjustment),
    ))
    grid = "".join((
        _field("context-attempts", "Context Attempts", attempts),
        _field("held-ypa", "Held Expected YPA", ypa),
        _field("uncertainty-envelope", "Uncertainty Envelope", envelope),
        _field("bounded-sack-delta", "Bounded Sack-Rate Delta", sack_delta),
        _field("personnel-context", "Personnel Context", personnel),
        _field("weather-context", "Weather Context", weather),
        _field("rest-context", "Rest Context", rest),
        _field("pressure-cap", "Pressure Cap Hit", pressure_cap),
    ))
    return (
        '<section class="ks-py65-context-detail" data-passing-yards-context-detail="v65">'
        '<div class="ks-py65-context-head"><div>'
        '<div class="ks-py65-context-kicker">Bounded context decomposition</div>'
        '<div class="ks-py65-context-title">Context + Uncertainty Detail</div>'
        f'</div><div class="ks-py65-context-badge">{escape(grade)}</div></div>'
        f'<div class="ks-py65-context-hero">{hero}</div>'
        f'<div class="ks-py65-context-grid">{grid}</div>'
        '<div class="ks-py65-context-source"><strong>Context basis:</strong> '
        f'{escape(context_sub)} • {escape(basis)} • sportsbook projection influence 0.0%</div>'
        '<details class="ks-py65-context-method" data-passing-yards-context-method="v65">'
        '<summary>How to read this context detail</summary>'
        '<p>Every value is copied from the already-certified Context + Uncertainty '
        'card. Pressure may move the frozen baseline only within the pre-existing '
        'bounded logic. Personnel, weather, and rest remain exactly as the frozen '
        'context layer reports them. The uncertainty envelope remains descriptive '
        'and is not converted into a new probability or confidence interval here.</p></details>'
        '</section>'
    )


def _inject_context_detail(body: str) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-market-detail="v63"' not in text
        or 'data-passing-yards-projection-detail="v64"' not in text
        or 'data-passing-yards-context-detail="v65"' in text
    ):
        return text

    context_anchor = '<strong>Context + Uncertainty</strong>'
    if context_anchor not in text:
        return text

    detail = build_context_detail(text)
    text = text.replace(context_anchor, context_anchor + detail, 1)

    ready = 'data-passing-yards-projection-detail-ready="v64"'
    if ready in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-context-detail-ready="v65"',
            1,
        )
    return _CONTEXT_DETAIL_CSS + text


def _selected_analysis_v65(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_context_detail(_FROZEN_SELECTED_ANALYSIS(captured, slot))


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v64
    prior._selected_analysis_v64 = _selected_analysis_v65
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v64 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V65 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "CONTEXT_DETAIL_VERSION",
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
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
    "_inject_context_detail",
    "_selected_analysis_v65",
    "build_context_detail",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
