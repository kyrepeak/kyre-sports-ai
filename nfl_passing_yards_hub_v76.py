"""NFL Passing Yards V76 — UX / Presentation Step 7.

Additive presentation-only wrapper over frozen V75. Step 7 improves wayfinding,
responsive spacing, touch targets, section anchors, and visual hierarchy for the
already-certified selected-quarterback detail page.

No projection, context math, probability, market math, personnel math,
environment math, provider behavior, widget keys, or navigation state changes.
Sportsbook projection influence remains 0.0%. Stake sizing stays OFF.
"""
from __future__ import annotations

import nfl_passing_yards_hub_v75 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v75

MODEL_VERSION = "NFL PASSING YARDS V76 • UX / PRESENTATION STEP 7"
FROZEN_PRIOR = "nfl_passing_yards_hub_v75"
UX_PRESENTATION_VERSION = "v76"
NEW_PHASE_STEP = 7
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_PERSONNEL_MATH = False
MAY_MODIFY_ENVIRONMENT_MATH = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_UX_CSS = r"""
<style data-passing-yards-ux-presentation-css="v76">
[data-passing-yards-ux-presentation="v76"],
[data-passing-yards-ux-presentation="v76"] *{box-sizing:border-box}

[data-passing-yards-ux-presentation="v76"]{
  width:100%;
  max-width:100%;
  min-width:0;
  overflow-x:clip;
}

.ks-py76-guide{
  position:sticky;
  top:0;
  z-index:8;
  margin:8px 0 12px;
  padding:8px;
  border:1px solid var(--kyre-sem-border-medium);
  border-radius:12px;
  background:color-mix(in srgb,var(--kyre-sem-surface-panel) 94%,transparent);
  backdrop-filter:blur(10px);
  -webkit-backdrop-filter:blur(10px);
}

.ks-py76-guide-title{
  margin:0 0 7px 2px;
  font-size:.48rem;
  font-weight:950;
  letter-spacing:.1em;
  text-transform:uppercase;
  color:var(--kyre-sem-text-muted);
}

.ks-py76-links{
  display:flex;
  gap:7px;
  max-width:100%;
  overflow-x:auto;
  overflow-y:hidden;
  padding:1px 1px 3px;
  scrollbar-width:none;
  -webkit-overflow-scrolling:touch;
  overscroll-behavior-inline:contain;
}

.ks-py76-links::-webkit-scrollbar{display:none}

.ks-py76-link{
  flex:0 0 auto;
  min-height:42px;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding:8px 10px;
  border:1px solid var(--kyre-sem-border-soft);
  border-radius:999px;
  background:rgba(255,255,255,.012);
  color:var(--kyre-sem-text-primary);
  font-size:.52rem;
  font-weight:900;
  line-height:1;
  text-decoration:none;
  white-space:nowrap;
  touch-action:manipulation;
  scroll-snap-align:start;
}

.ks-py76-link:hover{border-color:var(--kyre-sem-border-medium)}
.ks-py76-link:focus-visible{
  outline:2px solid var(--kyre-sem-text-accent);
  outline-offset:2px;
}

#ks-py76-overview,
#ks-py76-why,
#ks-py76-matchup,
#ks-py76-market,
#ks-py76-gameday,
#ks-py76-reliability{scroll-margin-top:78px}

[data-passing-yards-ux-presentation="v76"] .ks-py71-explain,
[data-passing-yards-ux-presentation="v76"] .ks-py72-matchup,
[data-passing-yards-ux-presentation="v76"] .ks-py73-market,
[data-passing-yards-ux-presentation="v76"] .ks-py74,
[data-passing-yards-ux-presentation="v76"] .ks-py75{
  width:100%;
  max-width:100%;
  min-width:0;
  overflow-wrap:anywhere;
}

[data-passing-yards-ux-presentation="v76"] .ks-py71-explain,
[data-passing-yards-ux-presentation="v76"] .ks-py72-matchup,
[data-passing-yards-ux-presentation="v76"] .ks-py73-market,
[data-passing-yards-ux-presentation="v76"] .ks-py74{
  box-shadow:0 1px 0 rgba(255,255,255,.025) inset;
}

[data-passing-yards-ux-presentation="v76"] .ks-py75{
  opacity:.96;
}

@media(max-width:760px){
  .ks-py76-guide{top:0;padding:7px}
  .ks-py76-links{scroll-snap-type:x proximity}
  .ks-py76-link{min-height:46px;padding:9px 12px}

  [data-passing-yards-ux-presentation="v76"] .ks-py71-explain,
  [data-passing-yards-ux-presentation="v76"] .ks-py72-matchup,
  [data-passing-yards-ux-presentation="v76"] .ks-py73-market,
  [data-passing-yards-ux-presentation="v76"] .ks-py74,
  [data-passing-yards-ux-presentation="v76"] .ks-py75{
    margin-left:0!important;
    margin-right:0!important;
  }

  [data-passing-yards-ux-presentation="v76"] .ks-py71-head,
  [data-passing-yards-ux-presentation="v76"] .ks-py72-head,
  [data-passing-yards-ux-presentation="v76"] .ks-py73-head,
  [data-passing-yards-ux-presentation="v76"] .ks-py74-head{
    gap:8px!important;
  }
}

@media(max-width:520px){
  .ks-py76-guide-title{font-size:.46rem}
  .ks-py76-link{font-size:.5rem}

  [data-passing-yards-ux-presentation="v76"] .ks-py71-explain,
  [data-passing-yards-ux-presentation="v76"] .ks-py72-matchup,
  [data-passing-yards-ux-presentation="v76"] .ks-py73-market,
  [data-passing-yards-ux-presentation="v76"] .ks-py74{
    padding:10px!important;
    border-radius:12px!important;
  }

  [data-passing-yards-ux-presentation="v76"] .ks-py71-title,
  [data-passing-yards-ux-presentation="v76"] .ks-py72-title,
  [data-passing-yards-ux-presentation="v76"] .ks-py73-title,
  [data-passing-yards-ux-presentation="v76"] .ks-py74-title{
    font-size:.9rem!important;
    line-height:1.25!important;
  }

  [data-passing-yards-ux-presentation="v76"] .ks-py71-hero,
  [data-passing-yards-ux-presentation="v76"] .ks-py72-hero,
  [data-passing-yards-ux-presentation="v76"] .ks-py73-grid,
  [data-passing-yards-ux-presentation="v76"] .ks-py74-grid{
    grid-template-columns:1fr!important;
  }
}
</style>
"""

_GUIDE = """
<nav class="ks-py76-guide" data-passing-yards-ux-guide="v76" aria-label="Passing yards analysis sections">
  <div class="ks-py76-guide-title">Analysis guide</div>
  <div class="ks-py76-links">
    <a class="ks-py76-link" href="#ks-py76-overview">Overview</a>
    <a class="ks-py76-link" href="#ks-py76-why">Why</a>
    <a class="ks-py76-link" href="#ks-py76-matchup">Matchup</a>
    <a class="ks-py76-link" href="#ks-py76-market">Market</a>
    <a class="ks-py76-link" href="#ks-py76-gameday">Game Day</a>
    <a class="ks-py76-link" href="#ks-py76-reliability">Reliability</a>
  </div>
</nav>
"""


def _add_id_once(text: str, token: str, element_id: str) -> str:
    if token not in text or f'id="{element_id}"' in text:
        return text
    replacement = (
        token[:-1] + f' id="{element_id}">'
        if token.endswith(">")
        else token + f' id="{element_id}"'
    )
    return text.replace(token, replacement, 1)


def _inject_ux_presentation(body: str) -> str:
    text = str(body or "")
    required = (
        'data-passing-yards-qb-detail="v59"',
        'data-passing-yards-projection-explainability="v71"',
        'data-passing-yards-matchup-intelligence="v72"',
        'data-passing-yards-live-market="v73"',
        'data-passing-yards-availability-game-day="v74"',
        'data-passing-yards-failure-proofing="v75"',
    )
    if any(token not in text for token in required):
        return text
    if 'data-passing-yards-ux-presentation="v76"' in text:
        return text

    root_anchor = '<section class="ks-py59" data-passing-yards-qb-detail="v59"'
    if root_anchor not in text:
        return text
    text = text.replace(
        root_anchor,
        root_anchor + ' data-passing-yards-ux-presentation="v76"',
        1,
    )

    # Stable in-page anchors only; no Streamlit/query/session navigation state changes.
    text = _add_id_once(
        text,
        '<section class="ks-py59-player">',
        "ks-py76-overview",
    )
    text = _add_id_once(
        text,
        '<section class="ks-py71-explain" data-passing-yards-projection-explainability="v71">',
        "ks-py76-why",
    )
    text = _add_id_once(
        text,
        '<section class="ks-py72-matchup" data-passing-yards-matchup-intelligence="v72">',
        "ks-py76-matchup",
    )
    text = _add_id_once(
        text,
        '<section class="ks-py73-market" data-passing-yards-live-market="v73"',
        "ks-py76-market",
    )
    text = _add_id_once(
        text,
        '<section class="ks-py74" data-passing-yards-availability-game-day="v74"',
        "ks-py76-gameday",
    )
    text = _add_id_once(
        text,
        '<section class="ks-py75" data-passing-yards-failure-proofing="v75"',
        "ks-py76-reliability",
    )

    player_start = text.find('<section class="ks-py59-player"')
    if player_start >= 0:
        player_end = text.find("</section>", player_start)
        if player_end >= 0:
            player_end += len("</section>")
            text = text[:player_end] + _GUIDE + text[player_end:]

    ready = 'data-passing-yards-failure-proofing-ready="v75"'
    if ready in text and 'data-passing-yards-ux-presentation-ready="v76"' not in text:
        text = text.replace(
            ready,
            ready + ' data-passing-yards-ux-presentation-ready="v76"',
            1,
        )

    return _UX_CSS + text


def _selected_analysis_v76(captured: dict[str, list[str]], slot: int) -> str:
    return _inject_ux_presentation(
        _FROZEN_SELECTED_ANALYSIS(captured, slot)
    )


def _render_step7_locked() -> None:
    original = prior._selected_analysis_v75
    prior._selected_analysis_v75 = _selected_analysis_v76
    try:
        return prior._render_step6_locked()
    finally:
        prior._selected_analysis_v75 = original


def render_nfl_passing_yards_hub() -> None:
    # Reuse Step 6's certified global render lock so this new monkeypatch cannot
    # race across overlapping Streamlit sessions.
    return prior._run_serialized(_render_step7_locked)


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V76 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR",
    "MAY_MODIFY_ENVIRONMENT_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PERSONNEL_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NEW_PHASE_STEP",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "UX_PRESENTATION_VERSION",
    "_inject_ux_presentation",
    "_selected_analysis_v76",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
