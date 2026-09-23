"""NFL Passing Yards V68 — New Phase Step 7 Navigation + Mobile Polish.

Additive presentation-only wrapper over frozen V67. Step 7 changes only
navigation ergonomics and responsive presentation for the already-certified
selected-quarterback detail page. It preserves the exact six-category contract,
all Step 1-6 content, query state, Back behavior, analytics, data, model values,
market math, sportsbook logic, and providers.
"""
from __future__ import annotations

import nfl_passing_yards_hub_v67 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v67

MODEL_VERSION = "NFL PASSING YARDS V68 • NEW PHASE STEP 7 NAVIGATION + MOBILE POLISH"
FROZEN_PRIOR = "nfl_passing_yards_hub_v67"
NAVIGATION_MOBILE_VERSION = "v68"
NEW_PHASE_STEP = 7
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

_NAVIGATION_MOBILE_CSS = r"""
<style data-passing-yards-navigation-mobile-css="v68">
[data-passing-yards-navigation-mobile="v68"],
[data-passing-yards-navigation-mobile="v68"] *{box-sizing:border-box}

[data-passing-yards-navigation-mobile="v68"]{
  width:100%;
  max-width:100%;
  min-width:0;
  overflow-x:clip;
}

[data-passing-yards-navigation-mobile="v68"] .ks-py59-player,
[data-passing-yards-navigation-mobile="v68"] .ks-py59-section,
[data-passing-yards-navigation-mobile="v68"] .ks-py63-market-detail,
[data-passing-yards-navigation-mobile="v68"] .ks-py64-projection-detail,
[data-passing-yards-navigation-mobile="v68"] .ks-py65-context-detail,
[data-passing-yards-navigation-mobile="v68"] .ks-py66-distribution-detail,
[data-passing-yards-navigation-mobile="v68"] .ks-py67-deep{
  width:100%;
  max-width:100%;
  min-width:0;
  overflow-wrap:anywhere;
}

[data-passing-yards-navigation-mobile="v68"] .ks-py62-category-nav{
  width:100%;
  max-width:100%;
  min-width:0;
  overflow:hidden;
}

[data-passing-yards-navigation-mobile="v68"] .ks-py62-category-links{
  max-width:100%;
  scrollbar-width:none;
  -webkit-overflow-scrolling:touch;
  overscroll-behavior-inline:contain;
}

[data-passing-yards-navigation-mobile="v68"] .ks-py62-category-links::-webkit-scrollbar{
  display:none;
}

[data-passing-yards-navigation-mobile="v68"] .ks-py62-category-link{
  min-height:48px;
  padding:10px 13px;
  touch-action:manipulation;
  scroll-snap-align:start;
}

[data-passing-yards-navigation-mobile="v68"] .ks-py62-category-link:focus-visible{
  outline:2px solid var(--kyre-sem-text-accent);
  outline-offset:2px;
}

[data-passing-yards-navigation-mobile="v68"] #ks-py-category-market,
[data-passing-yards-navigation-mobile="v68"] #ks-py-category-projection,
[data-passing-yards-navigation-mobile="v68"] #ks-py-category-context,
[data-passing-yards-navigation-mobile="v68"] #ks-py-category-distribution,
[data-passing-yards-navigation-mobile="v68"] #ks-py-category-matchup,
[data-passing-yards-navigation-mobile="v68"] #ks-py-category-conditions,
[data-passing-yards-navigation-mobile="v68"] #ks-py-deep-evidence{
  scroll-margin-top:16px;
}

.st-key-ks_py62_back_to_quarterbacks button{
  min-height:48px!important;
  touch-action:manipulation;
}

@media(max-width:760px){
  [data-passing-yards-navigation-mobile="v68"] .ks-py62-category-links{
    display:flex!important;
    flex-wrap:nowrap!important;
    gap:8px!important;
    overflow-x:auto!important;
    overflow-y:hidden!important;
    scroll-snap-type:x proximity;
    padding:1px 1px 4px;
  }

  [data-passing-yards-navigation-mobile="v68"] .ks-py62-category-link{
    flex:0 0 auto!important;
    white-space:nowrap!important;
  }

  [data-passing-yards-navigation-mobile="v68"] .ks-py59-player,
  [data-passing-yards-navigation-mobile="v68"] .ks-py59-section,
  [data-passing-yards-navigation-mobile="v68"] .ks-py63-market-detail,
  [data-passing-yards-navigation-mobile="v68"] .ks-py64-projection-detail,
  [data-passing-yards-navigation-mobile="v68"] .ks-py65-context-detail,
  [data-passing-yards-navigation-mobile="v68"] .ks-py66-distribution-detail,
  [data-passing-yards-navigation-mobile="v68"] .ks-py67-deep{
    padding-left:10px!important;
    padding-right:10px!important;
  }

  [data-passing-yards-navigation-mobile="v68"] .ks-py67-head{
    gap:8px!important;
  }

  .st-key-ks_py62_back_to_quarterbacks button{
    width:100%!important;
  }
}

@media(max-width:560px){
  [data-passing-yards-navigation-mobile="v68"] .ks-py63-market-head,
  [data-passing-yards-navigation-mobile="v68"] .ks-py64-projection-head,
  [data-passing-yards-navigation-mobile="v68"] .ks-py65-context-head,
  [data-passing-yards-navigation-mobile="v68"] .ks-py66-distribution-head,
  [data-passing-yards-navigation-mobile="v68"] .ks-py67-head{
    flex-direction:column!important;
    align-items:flex-start!important;
  }

  [data-passing-yards-navigation-mobile="v68"] .ks-py63-market-hero,
  [data-passing-yards-navigation-mobile="v68"] .ks-py63-market-grid,
  [data-passing-yards-navigation-mobile="v68"] .ks-py64-projection-hero,
  [data-passing-yards-navigation-mobile="v68"] .ks-py64-projection-grid,
  [data-passing-yards-navigation-mobile="v68"] .ks-py65-context-hero,
  [data-passing-yards-navigation-mobile="v68"] .ks-py65-context-grid,
  [data-passing-yards-navigation-mobile="v68"] .ks-py66-distribution-hero,
  [data-passing-yards-navigation-mobile="v68"] .ks-py66-distribution-grid,
  [data-passing-yards-navigation-mobile="v68"] .ks-py67-grid{
    grid-template-columns:1fr!important;
  }

  [data-passing-yards-navigation-mobile="v68"] .ks-py63-market-hero>div:first-child,
  [data-passing-yards-navigation-mobile="v68"] .ks-py64-projection-hero>div:first-child,
  [data-passing-yards-navigation-mobile="v68"] .ks-py65-context-hero>div:first-child,
  [data-passing-yards-navigation-mobile="v68"] .ks-py66-distribution-hero>div:first-child,
  [data-passing-yards-navigation-mobile="v68"] .ks-py67-card[data-deep-evidence-kind="recent"]{
    grid-column:auto!important;
  }
}
</style>
"""


def _inject_navigation_mobile_polish(body: str) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-deep-evidence="v67"' not in text
        or 'data-passing-yards-navigation-mobile="v68"' in text
    ):
        return text

    root_anchor = '<section class="ks-py59" data-passing-yards-qb-detail="v59"'
    if root_anchor not in text:
        return text
    text = text.replace(
        root_anchor,
        root_anchor + ' data-passing-yards-navigation-mobile="v68"',
        1,
    )

    text = text.replace(
        '<section class="ks-py67-deep" data-passing-yards-deep-evidence="v67">',
        '<section id="ks-py-deep-evidence" class="ks-py67-deep" data-passing-yards-deep-evidence="v67">',
        1,
    )

    ready = 'data-passing-yards-deep-evidence-ready="v67"'
    if ready in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-navigation-mobile-ready="v68"',
            1,
        )

    return _NAVIGATION_MOBILE_CSS + text


def _selected_analysis_v68(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_navigation_mobile_polish(
        _FROZEN_SELECTED_ANALYSIS(captured, slot)
    )


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v67
    prior._selected_analysis_v67 = _selected_analysis_v68
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v67 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V68 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
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
    "NAVIGATION_MOBILE_VERSION",
    "NEW_PHASE_STEP",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_inject_navigation_mobile_polish",
    "_selected_analysis_v68",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
