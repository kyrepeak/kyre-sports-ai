"""NFL Passing Yards V64 — New Phase Step 3 Projection Detail.

Additive presentation-only wrapper over frozen V63. Step 3 does not change
projection, probability, market math, sportsbook logic, data providers, query
state, Category Navigation, Market Decision Detail, or Back behavior. It only
reads values already rendered by the certified Baseline Projection card and
exposes a compact projection-detail panel for the selected quarterback.
"""
from __future__ import annotations

from html import escape, unescape
import re

import nfl_passing_yards_hub_v63 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v63

MODEL_VERSION = "NFL PASSING YARDS V64 • NEW PHASE STEP 3 PROJECTION DETAIL"
FROZEN_PRIOR = "nfl_passing_yards_hub_v63"
PROJECTION_DETAIL_VERSION = "v64"
NEW_PHASE_STEP = 3
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_PROJECTION_DETAIL_CSS = r"""
<style data-passing-yards-projection-detail-css="v64">
.ks-py64-projection-detail,.ks-py64-projection-detail *{box-sizing:border-box}
.ks-py64-projection-detail{
  margin:0 0 12px;padding:12px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-section);
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
}
.ks-py64-projection-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
.ks-py64-projection-kicker{font-size:.54rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase;color:var(--kyre-sem-text-accent-soft)}
.ks-py64-projection-title{margin-top:3px;font-size:.92rem;font-weight:950;line-height:1.15;color:var(--kyre-sem-text-primary)}
.ks-py64-projection-badge{flex:0 0 auto;border:1px solid var(--kyre-sem-border-medium);border-radius:999px;padding:5px 8px;font-size:.54rem;font-weight:950;color:var(--kyre-sem-text-accent-soft)}
.ks-py64-projection-hero{display:grid;grid-template-columns:1.2fr repeat(2,minmax(0,1fr));gap:8px;margin-bottom:8px}
.ks-py64-projection-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.ks-py64-projection-hero>div,.ks-py64-projection-grid>div{
  min-width:0;padding:10px;border:1px solid var(--kyre-sem-border-soft);
  border-radius:11px;background:rgba(255,255,255,.018)
}
.ks-py64-projection-detail [data-projection-field] b{
  display:block;color:var(--kyre-sem-text-primary);font-size:.94rem;font-weight:950;
  line-height:1.12;white-space:normal;overflow-wrap:anywhere
}
.ks-py64-projection-detail [data-projection-field] span{
  display:block;margin-top:4px;color:var(--kyre-sem-text-muted);font-size:.57rem;
  line-height:1.3;text-transform:uppercase;letter-spacing:.03em
}
.ks-py64-projection-source{
  margin-top:9px;padding-top:9px;border-top:1px solid var(--kyre-sem-border-soft);
  color:var(--kyre-sem-text-muted);font-size:.64rem;line-height:1.5
}
.ks-py64-projection-source strong{color:var(--kyre-sem-text-primary)}
.ks-py64-projection-method{margin-top:8px}
.ks-py64-projection-method summary{cursor:pointer;color:var(--kyre-sem-text-accent-soft);font-size:.64rem;font-weight:900}
.ks-py64-projection-method p{margin:7px 0 0;color:var(--kyre-sem-text-muted);font-size:.64rem;line-height:1.55}
@media(max-width:700px){
  .ks-py64-projection-head{flex-direction:column;gap:8px}
  .ks-py64-projection-badge{align-self:flex-start}
  .ks-py64-projection-hero{grid-template-columns:repeat(2,minmax(0,1fr))}
  .ks-py64-projection-hero>div:first-child{grid-column:1/-1}
  .ks-py64-projection-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:430px){
  .ks-py64-projection-grid{grid-template-columns:1fr}
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
    match = re.search(r'<div class="kpy-projgrade[^"]*">(.*?)</div>', body, flags=re.S | re.I)
    return _plain(match.group(1)) if match else "CHECK"


def _extract_projection_sub(body: str) -> str:
    match = re.search(r'<div class="kpy-projsub">(.*?)</div>', body, flags=re.S | re.I)
    return _plain(match.group(1)) if match else "Certified volume × efficiency baseline"


def _extract_environment(body: str) -> tuple[str, str, str]:
    match = re.search(r'<div class="kpy-projctx">(.*?)</div>', body, flags=re.S | re.I)
    if not match:
        return "—", "—", "Projection evidence context unavailable"
    chunk = match.group(1)
    env = re.search(r'Environment:\s*<b>(.*?)</b>', chunk, flags=re.S | re.I)
    weather = re.search(r'weather:\s*<b>(.*?)</b>', chunk, flags=re.S | re.I)
    basis = chunk.split("<br>", 1)[1] if "<br>" in chunk else ""
    return (
        _plain(env.group(1)) if env else "—",
        _plain(weather.group(1)) if weather else "—",
        _plain(basis) or "Projection evidence basis unavailable",
    )


def _field(kind: str, label: str, value: str) -> str:
    return (
        f'<div data-projection-field="{escape(kind, quote=True)}">'
        f'<b>{escape(value)}</b><span>{escape(label)}</span></div>'
    )


def build_projection_detail(body: str) -> str:
    baseline = _extract_b_span(body, "Baseline Pass Yards")
    attempts = _extract_b_span(body, "Expected Attempts")
    ypa = _extract_b_span(body, "Expected YPA")
    attempt_coverage = _extract_b_label(body, "Attempt-source coverage")
    ypa_coverage = _extract_b_label(body, "Efficiency-source coverage")
    pressure = _extract_b_label(body, "Pressure context • not numerically adjusted")
    personnel = _extract_b_label(body, "Personnel context • not numerically adjusted")
    environment, weather, basis = _extract_environment(body)
    grade = _extract_grade(body)
    projection_sub = _extract_projection_sub(body)

    hero = "".join((
        _field("baseline-yards", "Baseline Pass Yards", baseline),
        _field("expected-attempts", "Expected Attempts", attempts),
        _field("expected-ypa", "Expected YPA", ypa),
    ))
    grid = "".join((
        _field("attempt-coverage", "Attempt Coverage", attempt_coverage),
        _field("ypa-coverage", "Efficiency Coverage", ypa_coverage),
        _field("pressure-context", "Pressure Context", pressure),
        _field("personnel-context", "Personnel Context", personnel),
        _field("environment-context", "Environment Context", environment),
        _field("weather-context", "Weather Context", weather),
    ))
    return (
        '<section class="ks-py64-projection-detail" data-passing-yards-projection-detail="v64">'
        '<div class="ks-py64-projection-head"><div>'
        '<div class="ks-py64-projection-kicker">Frozen baseline decomposition</div>'
        '<div class="ks-py64-projection-title">Projection Detail</div>'
        f'</div><div class="ks-py64-projection-badge">{escape(grade)}</div></div>'
        f'<div class="ks-py64-projection-hero">{hero}</div>'
        f'<div class="ks-py64-projection-grid">{grid}</div>'
        '<div class="ks-py64-projection-source"><strong>Projection basis:</strong> '
        f'{escape(projection_sub)} • {escape(basis)} • sportsbook projection influence 0.0%</div>'
        '<details class="ks-py64-projection-method" data-passing-yards-projection-method="v64">'
        '<summary>How to read this projection detail</summary>'
        '<p>Baseline yards, expected attempts, expected YPA, coverage, and context '
        'are copied from the already-certified Baseline Projection card. Pressure, '
        'personnel, environment, and weather remain context-only unless the frozen '
        'projection already says otherwise. This panel does not recalculate the '
        'projection, infer a new directional adjustment, or alter any model value.</p></details>'
        '</section>'
    )


def _inject_projection_detail(body: str) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-market-detail="v63"' not in text
        or 'data-passing-yards-projection-detail="v64"' in text
    ):
        return text

    projection_anchor = '<strong>Baseline Projection</strong>'
    if projection_anchor not in text:
        return text

    detail = build_projection_detail(text)
    text = text.replace(projection_anchor, projection_anchor + detail, 1)

    ready = 'data-passing-yards-market-detail-ready="v63"'
    if ready in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-projection-detail-ready="v64"',
            1,
        )
    return _PROJECTION_DETAIL_CSS + text


def _selected_analysis_v64(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_projection_detail(_FROZEN_SELECTED_ANALYSIS(captured, slot))


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v63
    prior._selected_analysis_v63 = _selected_analysis_v64
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v63 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V64 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
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
    "PROJECTION_DETAIL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_inject_projection_detail",
    "_selected_analysis_v64",
    "build_projection_detail",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
