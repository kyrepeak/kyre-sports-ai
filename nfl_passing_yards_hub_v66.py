"""NFL Passing Yards V66 — New Phase Step 5 Distribution + Probability Detail.

Additive presentation-only wrapper over frozen V65. Step 5 does not change
projection, context, probability, market math, sportsbook logic, data providers,
query state, Category Navigation, prior detail panels, or Back behavior. It only
reads values already rendered by the certified Distribution + Probability card
and exposes a compact distribution-detail panel for the selected quarterback.
"""
from __future__ import annotations

from html import escape, unescape
import re

import nfl_passing_yards_hub_v65 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v65

MODEL_VERSION = "NFL PASSING YARDS V66 • NEW PHASE STEP 5 DISTRIBUTION + PROBABILITY DETAIL"
FROZEN_PRIOR = "nfl_passing_yards_hub_v65"
DISTRIBUTION_DETAIL_VERSION = "v66"
NEW_PHASE_STEP = 5
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_DISTRIBUTION_DETAIL_CSS = r"""
<style data-passing-yards-distribution-detail-css="v66">
.ks-py66-distribution-detail,.ks-py66-distribution-detail *{box-sizing:border-box}
.ks-py66-distribution-detail{
  margin:0 0 12px;padding:12px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-section);
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
}
.ks-py66-distribution-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
.ks-py66-distribution-kicker{font-size:.54rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase;color:var(--kyre-sem-text-accent-soft)}
.ks-py66-distribution-title{margin-top:3px;font-size:.92rem;font-weight:950;line-height:1.15;color:var(--kyre-sem-text-primary)}
.ks-py66-distribution-badge{flex:0 0 auto;border:1px solid var(--kyre-sem-border-medium);border-radius:999px;padding:5px 8px;font-size:.54rem;font-weight:950;color:var(--kyre-sem-text-accent-soft)}
.ks-py66-distribution-hero{display:grid;grid-template-columns:1.2fr repeat(2,minmax(0,1fr));gap:8px;margin-bottom:8px}
.ks-py66-distribution-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.ks-py66-distribution-hero>div,.ks-py66-distribution-grid>div{
  min-width:0;padding:10px;border:1px solid var(--kyre-sem-border-soft);
  border-radius:11px;background:rgba(255,255,255,.018)
}
.ks-py66-distribution-detail [data-distribution-field] b{
  display:block;color:var(--kyre-sem-text-primary);font-size:.92rem;font-weight:950;
  line-height:1.12;white-space:normal;overflow-wrap:anywhere
}
.ks-py66-distribution-detail [data-distribution-field] span{
  display:block;margin-top:4px;color:var(--kyre-sem-text-muted);font-size:.56rem;
  line-height:1.3;text-transform:uppercase;letter-spacing:.03em
}
.ks-py66-distribution-source{
  margin-top:9px;padding-top:9px;border-top:1px solid var(--kyre-sem-border-soft);
  color:var(--kyre-sem-text-muted);font-size:.64rem;line-height:1.5
}
.ks-py66-distribution-source strong{color:var(--kyre-sem-text-primary)}
.ks-py66-distribution-method{margin-top:8px}
.ks-py66-distribution-method summary{cursor:pointer;color:var(--kyre-sem-text-accent-soft);font-size:.64rem;font-weight:900}
.ks-py66-distribution-method p{margin:7px 0 0;color:var(--kyre-sem-text-muted);font-size:.64rem;line-height:1.55}
@media(max-width:900px){
  .ks-py66-distribution-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:700px){
  .ks-py66-distribution-head{flex-direction:column;gap:8px}
  .ks-py66-distribution-badge{align-self:flex-start}
  .ks-py66-distribution-hero{grid-template-columns:repeat(2,minmax(0,1fr))}
  .ks-py66-distribution-hero>div:first-child{grid-column:1/-1}
}
@media(max-width:430px){
  .ks-py66-distribution-grid{grid-template-columns:1fr}
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


def _extract_grade(body: str) -> str:
    match = re.search(r'<div class="kpy9-grade[^"]*">(.*?)</div>', body, flags=re.S | re.I)
    return _plain(match.group(1)) if match else "CHECK"


def _extract_distribution_sub(body: str) -> str:
    match = re.search(r'<div class="kpy9-sub">(.*?)</div>', body, flags=re.S | re.I)
    return _plain(match.group(1)) if match else "Certified analytic distribution"


def _extract_note(body: str) -> tuple[str, str]:
    match = re.search(r'<div class="kpy9-note">(.*?)</div>', body, flags=re.S | re.I)
    if not match:
        return "—", "Probability evidence basis unavailable"
    chunk = match.group(1)
    sampling = re.search(r'Monte Carlo sampling error:\s*<b>(.*?)</b>', chunk, flags=re.S | re.I)
    basis = chunk.split("<br>", 1)[0] if "<br>" in chunk else chunk
    return (
        _plain(sampling.group(1)) if sampling else "—",
        _plain(basis) or "Probability evidence basis unavailable",
    )


def _field(kind: str, label: str, value: str) -> str:
    return (
        f'<div data-distribution-field="{escape(kind, quote=True)}">'
        f'<b>{escape(value)}</b><span>{escape(label)}</span></div>'
    )


def build_distribution_detail(body: str) -> str:
    location = _extract_b_span(body, "Step 8 Location")
    sigma = _extract_b_span(body, "Observed Recent SD")
    recent_games = _extract_b_span(body, "Recent Games")
    p10 = _extract_b_span(body, "P10")
    p25 = _extract_b_span(body, "P25")
    p50 = _extract_b_span(body, "P50 Median")
    p75 = _extract_b_span(body, "P75")
    p90 = _extract_b_span(body, "P90")
    sampling_error, basis = _extract_note(body)
    grade = _extract_grade(body)
    distribution_sub = _extract_distribution_sub(body)

    hero = "".join((
        _field("location-yards", "Distribution Location", location),
        _field("sigma-yards", "Observed Recent SD", sigma),
        _field("recent-games", "Recent Games", recent_games),
    ))
    grid = "".join((
        _field("p10", "P10", p10),
        _field("p25", "P25", p25),
        _field("p50", "P50 Median", p50),
        _field("p75", "P75", p75),
        _field("p90", "P90", p90),
        _field("sampling-error", "Sampling Error", sampling_error),
    ))
    return (
        '<section class="ks-py66-distribution-detail" data-passing-yards-distribution-detail="v66">'
        '<div class="ks-py66-distribution-head"><div>'
        '<div class="ks-py66-distribution-kicker">Frozen outcome distribution read</div>'
        '<div class="ks-py66-distribution-title">Distribution + Probability Detail</div>'
        f'</div><div class="ks-py66-distribution-badge">{escape(grade)}</div></div>'
        f'<div class="ks-py66-distribution-hero">{hero}</div>'
        f'<div class="ks-py66-distribution-grid">{grid}</div>'
        '<div class="ks-py66-distribution-source"><strong>Distribution basis:</strong> '
        f'{escape(distribution_sub)} • {escape(basis)} • engine analytic • sportsbook influence 0.0%</div>'
        '<details class="ks-py66-distribution-method" data-passing-yards-distribution-method="v66">'
        '<summary>How to read this distribution detail</summary>'
        '<p>Every value is copied from the already-certified Distribution + Probability '
        'card. Location, observed recent standard deviation, sample size, and quantiles '
        'are not recalculated here. The engine remains the frozen analytic distribution, '
        'and sportsbook lines or prices do not enter this detail panel.</p></details>'
        '</section>'
    )


def _inject_distribution_detail(body: str) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-market-detail="v63"' not in text
        or 'data-passing-yards-projection-detail="v64"' not in text
        or 'data-passing-yards-context-detail="v65"' not in text
        or 'data-passing-yards-distribution-detail="v66"' in text
    ):
        return text

    distribution_anchor = '<strong>Distribution + Probability</strong>'
    if distribution_anchor not in text:
        return text

    detail = build_distribution_detail(text)
    text = text.replace(distribution_anchor, distribution_anchor + detail, 1)

    ready = 'data-passing-yards-context-detail-ready="v65"'
    if ready in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-distribution-detail-ready="v66"',
            1,
        )
    return _DISTRIBUTION_DETAIL_CSS + text


def _selected_analysis_v66(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_distribution_detail(_FROZEN_SELECTED_ANALYSIS(captured, slot))


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v65
    prior._selected_analysis_v65 = _selected_analysis_v66
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v65 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V66 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "DISTRIBUTION_DETAIL_VERSION",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT",
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
    "_inject_distribution_detail",
    "_selected_analysis_v66",
    "build_distribution_detail",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
