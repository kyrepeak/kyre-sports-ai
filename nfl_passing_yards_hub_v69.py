"""NFL Passing Yards V69 — selected-QB detail cleanup repair.

Additive presentation-only repair over frozen V68. The frozen V63-V66 detail
parsers used broad DOTALL <b> captures against the entire selected-QB document,
which could absorb unrelated HTML before a later label and render giant repeated
raw evidence blobs. V69 leaves V58-V68 untouched and rebuilds the four detail
panels from their isolated captured payloads with bounded extraction.

No projection, context, probability, market math, sportsbook logic, data,
provider, widget, query, or navigation-state behavior changes.
"""
from __future__ import annotations

import re
from html import escape, unescape

import nfl_passing_yards_hub_v68 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v68

MODEL_VERSION = "NFL PASSING YARDS V69 • SELECTED QB DETAIL CLEANUP"
FROZEN_PRIOR = "nfl_passing_yards_hub_v68"
DETAIL_CLEANUP_VERSION = "v69"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_RAW_DUMP_TOKENS = (
    "ESPN Athlete ID",
    "ESPN Team ID",
    "Current Market + EdgePost-model",
    "MARKET CHECKPASS",
)

_DETAIL_CLEANUP_CSS = r"""
<style data-passing-yards-detail-cleanup-css="v69">
[data-passing-yards-detail-cleanup="v69"] .ks-py63-market-detail,
[data-passing-yards-detail-cleanup="v69"] .ks-py64-projection-detail,
[data-passing-yards-detail-cleanup="v69"] .ks-py65-context-detail,
[data-passing-yards-detail-cleanup="v69"] .ks-py66-distribution-detail{
  display:none!important;
}

[data-passing-yards-detail-cleanup="v69"] .ks-py69-clean-detail,
[data-passing-yards-detail-cleanup="v69"] .ks-py69-clean-detail *{
  box-sizing:border-box;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-clean-detail{
  width:100%;
  min-width:0;
  margin:9px 0 10px;
  padding:12px;
  border:1px solid var(--kyre-sem-border-soft);
  border-radius:var(--kyre-sem-radius-section);
  background:linear-gradient(155deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
  overflow:hidden;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-head{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:10px;
  margin-bottom:10px;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-kicker{
  color:var(--kyre-sem-text-accent-soft);
  font-size:.54rem;
  font-weight:950;
  letter-spacing:.1em;
  text-transform:uppercase;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-title{
  margin-top:3px;
  color:var(--kyre-sem-text-primary);
  font-size:.94rem;
  font-weight:950;
  line-height:1.18;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-badge{
  flex:0 0 auto;
  border:1px solid var(--kyre-sem-border-medium);
  border-radius:999px;
  padding:5px 8px;
  color:var(--kyre-sem-text-accent-soft);
  font-size:.52rem;
  font-weight:950;
  white-space:nowrap;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-hero,
[data-passing-yards-detail-cleanup="v69"] .ks-py69-grid{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:8px;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-grid{
  margin-top:8px;
}
[data-passing-yards-detail-cleanup="v69"] [data-clean-field]{
  min-width:0;
  min-height:68px;
  padding:10px;
  border:1px solid var(--kyre-sem-border-soft);
  border-radius:11px;
  background:rgba(255,255,255,.018);
  overflow:hidden;
}
[data-passing-yards-detail-cleanup="v69"] [data-clean-field] b{
  display:block;
  color:var(--kyre-sem-text-primary);
  font-size:.82rem;
  font-weight:950;
  line-height:1.2;
  overflow-wrap:anywhere;
}
[data-passing-yards-detail-cleanup="v69"] [data-clean-field] span{
  display:block;
  margin-top:5px;
  color:var(--kyre-sem-text-muted);
  font-size:.47rem;
  font-weight:900;
  line-height:1.25;
  letter-spacing:.045em;
  text-transform:uppercase;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-source{
  margin-top:9px;
  padding:9px 10px;
  border:1px solid var(--kyre-sem-border-soft);
  border-radius:10px;
  color:var(--kyre-sem-text-muted);
  font-size:.58rem;
  line-height:1.45;
  overflow-wrap:anywhere;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-source strong{
  color:var(--kyre-sem-text-primary);
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-method{
  margin-top:8px;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-method summary{
  min-height:44px;
  display:flex;
  align-items:center;
  cursor:pointer;
  color:var(--kyre-sem-text-accent-soft);
  font-size:.62rem;
  font-weight:900;
}
[data-passing-yards-detail-cleanup="v69"] .ks-py69-method p{
  margin:4px 0 0;
  color:var(--kyre-sem-text-muted);
  font-size:.61rem;
  line-height:1.5;
}

@media(max-width:1100px){
  [data-passing-yards-detail-cleanup="v69"] .ks-py69-hero,
  [data-passing-yards-detail-cleanup="v69"] .ks-py69-grid{
    grid-template-columns:repeat(2,minmax(0,1fr));
  }
  [data-passing-yards-detail-cleanup="v69"] .ks-py69-hero>[data-clean-field]:first-child{
    grid-column:1/-1;
  }
}
@media(max-width:560px){
  [data-passing-yards-detail-cleanup="v69"] .ks-py69-head{
    flex-direction:column;
    align-items:flex-start;
  }
  [data-passing-yards-detail-cleanup="v69"] .ks-py69-hero,
  [data-passing-yards-detail-cleanup="v69"] .ks-py69-grid{
    grid-template-columns:1fr!important;
  }
  [data-passing-yards-detail-cleanup="v69"] .ks-py69-hero>[data-clean-field]:first-child{
    grid-column:auto;
  }
  [data-passing-yards-detail-cleanup="v69"] [data-clean-field]{
    min-height:0;
  }
}
</style>
"""


def _plain(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = unescape(text)
    return " ".join(text.split()).strip()


def _safe_text(value: str, *, limit: int = 120, fallback: str = "—") -> str:
    text = _plain(value)
    if not text or len(text) > limit:
        return fallback
    if any(token in text for token in _RAW_DUMP_TOKENS):
        return fallback
    return text


def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""


_B_VALUE = r"((?:(?!</b>).){0,240})"


def _extract_b_span(source: str, label: str) -> str:
    pattern = (
        rf"<b(?:\s[^>]*)?>{_B_VALUE}</b>\s*"
        rf"<span(?:\s[^>]*)?>\s*{re.escape(label)}\s*</span>"
    )
    match = re.search(pattern, str(source or ""), flags=re.S | re.I)
    return _safe_text(match.group(1)) if match else "—"


def _extract_b_label(source: str, label: str) -> str:
    pattern = rf"<b(?:\s[^>]*)?>{_B_VALUE}</b>\s*{re.escape(label)}"
    match = re.search(pattern, str(source or ""), flags=re.S | re.I)
    return _safe_text(match.group(1)) if match else "—"


def _extract_div_html(source: str, class_name: str) -> str:
    pattern = rf'<div[^>]*class="[^"]*{re.escape(class_name)}[^"]*"[^>]*>(.*?)</div>'
    match = re.search(pattern, str(source or ""), flags=re.S | re.I)
    return match.group(1) if match else ""


def _extract_div_text(source: str, class_name: str, fallback: str) -> str:
    return _safe_text(
        _extract_div_html(source, class_name),
        limit=180,
        fallback=fallback,
    )


def _extract_named_b(chunk: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*<b(?:\s[^>]*)?>{_B_VALUE}</b>"
    match = re.search(pattern, str(chunk or ""), flags=re.S | re.I)
    return _safe_text(match.group(1)) if match else "—"


def _clean_basis(value: str, fallback: str) -> str:
    return _safe_text(value, limit=220, fallback=fallback)


def _field(kind: str, label: str, value: str) -> str:
    clean = _safe_text(value)
    return (
        f'<div data-clean-field="{escape(kind, quote=True)}">'
        f'<b>{escape(clean)}</b><span>{escape(label)}</span></div>'
    )


def _panel(
    kind: str,
    kicker: str,
    title: str,
    badge: str,
    hero: tuple[tuple[str, str, str], ...],
    grid: tuple[tuple[str, str, str], ...],
    source_label: str,
    source_text: str,
    method_text: str,
) -> str:
    hero_html = "".join(_field(*item) for item in hero)
    grid_html = "".join(_field(*item) for item in grid)
    return (
        f'<section class="ks-py69-clean-detail" data-passing-yards-clean-detail="{escape(kind, quote=True)}" '
        'data-passing-yards-detail-cleanup-panel="v69">'
        '<div class="ks-py69-head"><div>'
        f'<div class="ks-py69-kicker">{escape(kicker)}</div>'
        f'<div class="ks-py69-title">{escape(title)}</div>'
        f'</div><div class="ks-py69-badge">{escape(badge)}</div></div>'
        f'<div class="ks-py69-hero">{hero_html}</div>'
        f'<div class="ks-py69-grid">{grid_html}</div>'
        f'<div class="ks-py69-source"><strong>{escape(source_label)}:</strong> '
        f'{escape(_clean_basis(source_text, "Frozen certified source card"))}</div>'
        '<details class="ks-py69-method"><summary>How to read this clean detail</summary>'
        f'<p>{escape(method_text)}</p></details>'
        '</section>'
    )


def build_market_cleanup(source: str) -> str:
    source_text = _extract_div_text(
        source,
        "kpy10-sub",
        "Frozen certified market card",
    )
    if " • projection influence" in source_text:
        source_text = source_text.split(" • projection influence", 1)[0].strip()
    return _panel(
        "market",
        "Post-model market read",
        "Market Decision Detail",
        "MODEL INDEPENDENT",
        (
            ("lean", "Final Lean", _extract_b_span(source, "Final Lean")),
            ("line", "Market Line", _extract_b_span(source, "Market Line")),
            ("confidence", "Model Confidence", _extract_b_span(source, "Model Confidence")),
        ),
        (
            ("model-probability", "Model Over / Under", _extract_b_label(source, "Model Over / Under")),
            ("fair-odds", "Model Fair Odds", _extract_b_label(source, "Model fair Over / Under")),
            ("offered-odds", "Offered Odds", _extract_b_label(source, "Offered Over / Under")),
            ("no-vig", "No-Vig Market", _extract_b_label(source, "No-vig Over / Under")),
            ("edge", "Model Edge", _extract_b_label(source, "Model edge Over / Under")),
            ("ev", "EV per $1", _extract_b_label(source, "EV per $1 Over / Under")),
        ),
        "Source",
        source_text + " • sportsbook projection influence 0.0% • stake sizing OFF",
        "Values are copied from the isolated frozen market payload. This cleanup changes presentation only and does not recalculate market probability, fair odds, edge, EV, projection, or stake sizing.",
    )


def build_projection_cleanup(source: str) -> str:
    ctx = _extract_div_html(source, "kpy-projctx")
    basis = ""
    if "<br>" in ctx:
        basis = ctx.split("<br>", 1)[1]
    basis = _clean_basis(basis, "Frozen certified projection evidence")
    sub = _extract_div_text(source, "kpy-projsub", "Certified volume × efficiency baseline")
    grade = _extract_div_text(source, "kpy-projgrade", "CHECK")
    return _panel(
        "projection",
        "Frozen baseline decomposition",
        "Projection Detail",
        grade,
        (
            ("baseline-yards", "Baseline Pass Yards", _extract_b_span(source, "Baseline Pass Yards")),
            ("expected-attempts", "Expected Attempts", _extract_b_span(source, "Expected Attempts")),
            ("expected-ypa", "Expected YPA", _extract_b_span(source, "Expected YPA")),
        ),
        (
            ("attempt-coverage", "Attempt Coverage", _extract_b_label(source, "Attempt-source coverage")),
            ("ypa-coverage", "Efficiency Coverage", _extract_b_label(source, "Efficiency-source coverage")),
            ("pressure-context", "Pressure Context", _extract_b_label(source, "Pressure context • not numerically adjusted")),
            ("personnel-context", "Personnel Context", _extract_b_label(source, "Personnel context • not numerically adjusted")),
            ("environment-context", "Environment Context", _extract_named_b(ctx, "Environment:")),
            ("weather-context", "Weather Context", _extract_named_b(ctx, "weather:")),
        ),
        "Projection basis",
        sub + " • " + basis + " • sportsbook projection influence 0.0%",
        "Baseline yards, expected attempts, expected YPA, coverage, and context come from the isolated frozen projection payload. No model value or adjustment is recomputed here.",
    )


def build_context_cleanup(source: str) -> str:
    note = _extract_div_html(source, "kpy8-note")
    basis = note.split("<br>", 1)[1] if "<br>" in note else ""
    basis = _clean_basis(basis, "Frozen certified context evidence")
    sub = _extract_div_text(source, "kpy8-sub", "Certified bounded context + visible uncertainty")
    grade = _extract_div_text(source, "kpy8-grade", "CHECK")
    return _panel(
        "context",
        "Bounded context decomposition",
        "Context + Uncertainty Detail",
        grade,
        (
            ("context-yards", "Context Pass Yards", _extract_b_span(source, "Context Pass Yards")),
            ("baseline-yards", "Baseline Pass Yards", _extract_b_span(source, "Step 7 Baseline")),
            ("pressure-adjustment", "Pressure Adjustment", _extract_b_span(source, "Pressure Adjustment")),
        ),
        (
            ("context-attempts", "Context Attempts", _extract_b_label(source, "Context attempts")),
            ("held-ypa", "Held Expected YPA", _extract_b_label(source, "YPA held at Step 7 value")),
            ("uncertainty-envelope", "Uncertainty Envelope", _extract_b_label(source, "Descriptive uncertainty envelope")),
            ("bounded-sack-delta", "Bounded Sack-Rate Delta", _extract_b_label(source, "Bounded sack-rate delta")),
            ("personnel-context", "Personnel Context", _extract_b_label(source, "Personnel • numerical effect 0.0")),
            ("weather-context", "Weather Context", _extract_b_label(source, "Weather • numerical effect 0.0")),
            ("rest-context", "Rest Context", _extract_named_b(note, "Rest:")),
            ("pressure-cap", "Pressure Cap Hit", _extract_named_b(note, "pressure cap hit:")),
        ),
        "Context basis",
        sub + " • " + basis + " • sportsbook projection influence 0.0%",
        "Every displayed value comes from the isolated frozen context payload. This cleanup does not change pressure bounds, personnel, weather, rest, uncertainty, probability, or projection math.",
    )


def build_distribution_cleanup(source: str) -> str:
    note = _extract_div_html(source, "kpy9-note")
    basis = note.split("<br>", 1)[0] if note else ""
    basis = _clean_basis(basis, "Frozen certified probability evidence")
    sub = _extract_div_text(source, "kpy9-sub", "Certified analytic distribution")
    grade = _extract_div_text(source, "kpy9-grade", "CHECK")
    return _panel(
        "distribution",
        "Frozen outcome distribution read",
        "Distribution + Probability Detail",
        grade,
        (
            ("location-yards", "Distribution Location", _extract_b_span(source, "Step 8 Location")),
            ("sigma-yards", "Observed Recent SD", _extract_b_span(source, "Observed Recent SD")),
            ("recent-games", "Recent Games", _extract_b_span(source, "Recent Games")),
        ),
        (
            ("p10", "P10", _extract_b_span(source, "P10")),
            ("p25", "P25", _extract_b_span(source, "P25")),
            ("p50", "P50 Median", _extract_b_span(source, "P50 Median")),
            ("p75", "P75", _extract_b_span(source, "P75")),
            ("p90", "P90", _extract_b_span(source, "P90")),
            ("sampling-error", "Sampling Error", _extract_named_b(note, "Monte Carlo sampling error:")),
        ),
        "Distribution basis",
        sub + " • " + basis + " • engine analytic • sportsbook influence 0.0%",
        "Location, recent standard deviation, sample size, quantiles, and sampling error come from the isolated frozen distribution payload. No probability or distribution value is recalculated.",
    )


def _inject_detail_cleanup(
    body: str,
    captured: dict[str, list[str]],
    slot: int,
) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-navigation-mobile="v68"' not in text
        or 'data-passing-yards-detail-cleanup="v69"' in text
    ):
        return text

    index = slot - 1
    panels = (
        (
            '<strong>Current Market + Edge</strong>',
            build_market_cleanup(_piece(captured, "market", index)),
        ),
        (
            '<strong>Baseline Projection</strong>',
            build_projection_cleanup(_piece(captured, "projection", index)),
        ),
        (
            '<strong>Context + Uncertainty</strong>',
            build_context_cleanup(_piece(captured, "context", index)),
        ),
        (
            '<strong>Distribution + Probability</strong>',
            build_distribution_cleanup(_piece(captured, "distribution", index)),
        ),
    )
    for anchor, panel in panels:
        if anchor not in text:
            return text
        text = text.replace(anchor, anchor + panel, 1)

    root_anchor = '<section class="ks-py59" data-passing-yards-qb-detail="v59"'
    text = text.replace(
        root_anchor,
        root_anchor + ' data-passing-yards-detail-cleanup="v69"',
        1,
    )

    ready = 'data-passing-yards-navigation-mobile-ready="v68"'
    if ready in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-detail-cleanup-ready="v69"',
            1,
        )

    return _DETAIL_CLEANUP_CSS + text


def _selected_analysis_v69(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_detail_cleanup(
        _FROZEN_SELECTED_ANALYSIS(captured, slot),
        captured,
        slot,
    )


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v68
    prior._selected_analysis_v68 = _selected_analysis_v69
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v68 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V69 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DETAIL_CLEANUP_VERSION",
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_inject_detail_cleanup",
    "_selected_analysis_v69",
    "build_context_cleanup",
    "build_distribution_cleanup",
    "build_market_cleanup",
    "build_projection_cleanup",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
