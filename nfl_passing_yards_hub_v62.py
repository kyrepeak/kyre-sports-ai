"""NFL Passing Yards V62 — New Phase Step 1 Category Navigation.

Additive presentation-only wrapper over frozen V61. The certified QB picker,
QB detail content, analytics, data, projection, probability, market math,
sportsbook influence, date/matchup state, and Back to Quarterbacks behavior
remain frozen. V62 only adds six in-page category navigation controls to the
selected-quarterback detail view.
"""
from __future__ import annotations

from html import escape

import nfl_passing_yards_hub_v58 as navigation
import nfl_passing_yards_hub_v59 as detail
import nfl_passing_yards_hub_v61 as prior

_FROZEN_SELECTED_ANALYSIS = detail._selected_analysis

MODEL_VERSION = "NFL PASSING YARDS V62 • NEW PHASE STEP 1 CATEGORY NAVIGATION"
FROZEN_PRIOR = "nfl_passing_yards_hub_v61"
CATEGORY_NAV_VERSION = "v62"
NEW_PHASE_STEP = 1
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

CATEGORY_NAV_ITEMS = (
    ("market", "Current Market + Edge", "ks-py-category-market"),
    ("projection", "Baseline Projection", "ks-py-category-projection"),
    ("context", "Context + Uncertainty", "ks-py-category-context"),
    ("distribution", "Distribution + Probability", "ks-py-category-distribution"),
    ("matchup", "Matchup Drivers", "ks-py-category-matchup"),
    ("conditions", "Conditions + Personnel", "ks-py-category-conditions"),
)

_CATEGORY_NAV_CSS = r"""
<style data-passing-yards-category-nav-css="v62">
.ks-py62-category-nav,.ks-py62-category-nav *{box-sizing:border-box}
.ks-py62-category-nav{
  width:100%;max-width:100%;margin:0 0 12px;padding:10px;
  border:1px solid var(--kyre-sem-border-soft);
  border-radius:var(--kyre-sem-radius-section);
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.02);
}
.ks-py62-category-label{
  display:block;margin:0 0 8px;color:var(--kyre-sem-text-muted);
  font-size:.56rem;font-weight:950;letter-spacing:.12em;text-transform:uppercase
}
.ks-py62-category-links{
  display:flex;flex-wrap:wrap;gap:7px;width:100%;max-width:100%
}
.ks-py62-category-link{
  display:inline-flex;align-items:center;justify-content:center;min-height:44px;
  max-width:100%;padding:8px 11px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:999px;background:var(--kyre-sem-surface-column);
  color:var(--kyre-sem-text-primary);font-size:.64rem;font-weight:900;
  line-height:1.2;text-decoration:none!important;overflow-wrap:anywhere;
  touch-action:manipulation
}
.ks-py62-category-link:hover,
.ks-py62-category-link:focus-visible{
  border-color:var(--kyre-sem-border-strong);
  background:var(--kyre-sem-accent-wash-soft);
  color:var(--kyre-sem-text-accent-soft);
  outline:none
}
[id^="ks-py-category-"]{scroll-margin-top:18px}
@media(max-width:760px){
  .ks-py62-category-nav{padding:9px}
  .ks-py62-category-links{
    flex-wrap:nowrap;overflow-x:auto;overscroll-behavior-inline:contain;
    scroll-snap-type:x proximity;padding-bottom:2px
  }
  .ks-py62-category-link{
    flex:0 0 auto;white-space:nowrap;scroll-snap-align:start
  }
}
</style>
"""

def _category_context_url(slot: int) -> str:
    # Reuse the frozen V58 date/matchup/QB navigation helper as the preserved
    # context source. The actual category click is fragment-only so the current
    # selected-QB page never reloads or changes navigation state.
    return escape(navigation._current_nav_url(slot), quote=True)


def _category_href(target_id: str) -> str:
    return escape(f"#{target_id}", quote=True)


def build_category_nav(slot: int) -> str:
    preserved_context = _category_context_url(slot)
    links = "".join(
        f'<a class="ks-py62-category-link" data-category-target="{kind}" '
        f'data-preserved-nav="{preserved_context}" href="{_category_href(target_id)}">{label}</a>'
        for kind, label, target_id in CATEGORY_NAV_ITEMS
    )
    return (
        '<nav class="ks-py62-category-nav" data-passing-yards-category-nav="v62" '
        'aria-label="Quarterback analysis categories">'
        '<span class="ks-py62-category-label">Jump to analysis</span>'
        f'<div class="ks-py62-category-links">{links}</div>'
        '</nav>'
    )


def _inject_category_navigation(body: str, slot: int) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-category-nav="v62"' in text
    ):
        return text

    replacements = (
        (
            '<section class="ks-py59-section" data-qb-analysis-section="market"',
            '<section id="ks-py-category-market" class="ks-py59-section" data-qb-analysis-section="market"',
        ),
        (
            '<section class="ks-py59-section" data-qb-analysis-section="projection"',
            '<section id="ks-py-category-projection" class="ks-py59-section" data-qb-analysis-section="projection"',
        ),
        (
            '<section class="ks-py59-section" data-qb-analysis-section="context"',
            '<section id="ks-py-category-context" class="ks-py59-section" data-qb-analysis-section="context"',
        ),
        (
            '<section class="ks-py59-section" data-qb-analysis-section="distribution"',
            '<section id="ks-py-category-distribution" class="ks-py59-section" data-qb-analysis-section="distribution"',
        ),
        (
            '<details data-qb-analysis-support="matchup"',
            '<details id="ks-py-category-matchup" data-qb-analysis-support="matchup"',
        ),
        (
            '<details data-qb-analysis-support="conditions"',
            '<details id="ks-py-category-conditions" data-qb-analysis-support="conditions"',
        ),
    )
    for old, new in replacements:
        text = text.replace(old, new, 1)

    # Category fragment navigation stays inside the current document. The
    # frozen Back URL is query-relative, but public Streamlit renders the app
    # inside a hosted frame. Promote that query to the app root before using
    # target="_top" so Back changes the real top-level query state.
    text = text.replace(
        'data-qb-back="true" href="?',
        'data-qb-back="true" target="_top" href="/?',
        1,
    )

    root_token = f'data-qb-analysis-slot="{slot}"'
    text = text.replace(
        root_token,
        root_token + ' data-passing-yards-category-nav-ready="v62"',
        1,
    )

    anchor = '<header class="ks-py59-head"'
    if anchor not in text:
        return text
    text = text.replace(anchor, build_category_nav(slot) + anchor, 1)
    return _CATEGORY_NAV_CSS + text


def _selected_analysis_v62(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_category_navigation(_FROZEN_SELECTED_ANALYSIS(captured, slot), slot)


def render_nfl_passing_yards_hub() -> None:
    original = detail._selected_analysis
    detail._selected_analysis = _selected_analysis_v62
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        detail._selected_analysis = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V62 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "CATEGORY_NAV_ITEMS",
    "CATEGORY_NAV_VERSION",
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
    "_inject_category_navigation",
    "build_category_nav",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
