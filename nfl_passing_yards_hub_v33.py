"""NFL Passing Yards V33 — visual parity Step 6 final polish + certification.

Additive presentation-only wrapper over certified V32. V33 completes the six-step
Passing Yards visual-parity build without changing any frozen analytical value,
formula, probability, fair odds, no-vig output, EV, market input, grade, identity
contract, or fail-closed rule.

Sportsbook projection influence remains exactly 0.0% and stake sizing remains OFF.
"""
from __future__ import annotations

import nfl_passing_yards_hub_v32 as prior

MODEL_VERSION = "NFL PASSING YARDS V33 • VISUAL PARITY STEP 6 • FINAL POLISH + CERTIFICATION"
FROZEN_PRIOR = "nfl_passing_yards_hub_v32"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
VISUAL_BUILD_STEP = 6
VISUAL_BUILD_TOTAL = 6
DISPLAY_ONLY = True
FINAL_PAGE_COMPLETE = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_ORIGINAL_STEP5_ANALYTICS_CSS_V32 = prior._STEP5_ANALYTICS_CSS
_ORIGINAL_VISUAL_BANNER_V32 = prior._visual_build_banner_v32

_STEP6_FINAL_CSS = r'''
<style>
/* Step 6 final polish: completion state only; no analytical ownership. */
.kpass29-build{border-color:#3d7651!important;box-shadow:inset 0 0 0 1px rgba(139,226,172,.035)!important}
.kpass29-fill{width:100%!important}
.kpass29-buildchip.final{border-color:#4c8d61!important;background:#12301e!important;color:#a8efbc!important}
.kpass33-finalnote{position:relative;z-index:1;margin-top:8px;padding:7px 9px;border:1px solid #294b36;border-radius:10px;background:#0a1710;color:#789083;font-size:.46rem;line-height:1.45}
.kpass33-finalnote strong{color:#9ce6b0}
</style>
'''


def _visual_build_banner_v33() -> str:
    return (
        '<section class="kpass29-build">'
        '<div class="kpass29-buildtop"><div>'
        '<div class="kpass29-buildtitle">🎨 Passing Yards • Visual Parity Build</div>'
        '<div class="kpass29-buildsub">Final certified Passing Yards presentation • player identity, matchup context, analytical readouts, and market evaluation now share the certified compact green/black family.</div>'
        '</div><div class="kpass29-buildchips">'
        '<span class="kpass29-buildchip final">VISUAL STEP 6 / 6</span>'
        '<span class="kpass29-buildchip final">✅ FINAL CERTIFIED</span>'
        '<span class="kpass29-buildchip blue">V32 + V28 FROZEN</span>'
        '<span class="kpass29-buildchip gold">SPORTSBOOK 0%</span>'
        '</div></div><div class="kpass29-track"><div class="kpass29-fill" style="width:100%"></div></div>'
        '<div class="kpass33-finalnote"><strong>Final visual layer only.</strong> Frozen Passing projection, uncertainty, distribution, probability, fair-odds, no-vig, edge, EV, market behavior, and exact-ID rules remain unchanged • stake sizing OFF.</div>'
        '</section>'
    )


def render_nfl_passing_yards_hub() -> None:
    """Render frozen V32 with completion-only Step 6 presentation state."""
    original_css = prior._STEP5_ANALYTICS_CSS
    original_banner = prior._visual_build_banner_v32
    prior._STEP5_ANALYTICS_CSS = original_css + _STEP6_FINAL_CSS
    prior._visual_build_banner_v32 = _visual_build_banner_v33
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._STEP5_ANALYTICS_CSS = original_css
        prior._visual_build_banner_v32 = original_banner


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V33 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FINAL_PAGE_COMPLETE",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_BUILD_STEP",
    "VISUAL_BUILD_TOTAL",
    "_STEP6_FINAL_CSS",
    "_visual_build_banner_v33",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
