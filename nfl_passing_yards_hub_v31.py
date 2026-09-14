"""NFL Passing Yards V31 — visual parity Step 4 matchup + context cards.

Additive presentation-only wrapper over certified V30. V31 moves the frozen
Passing Yards matchup/context stack into the same green/black card family used
by certified Receiving Yards and Rushing Yards:
- opponent pass-defense cards;
- protection vs defensive-pressure cards;
- weapons + availability / injury cards;
- game-environment cards.

V31 does not recompute, replace, or reinterpret any context value. V1-V30,
including certified V28 model/market behavior, remain frozen. Sportsbook
projection influence remains exactly 0.0%.
"""
from __future__ import annotations

import nfl_passing_yards_hub_v30 as prior

MODEL_VERSION = "NFL PASSING YARDS V31 • VISUAL PARITY STEP 4 • MATCHUP + CONTEXT CARDS"
FROZEN_PRIOR = "nfl_passing_yards_hub_v30"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
VISUAL_BUILD_STEP = 4
VISUAL_BUILD_TOTAL = 6
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_STEP3_VISUAL_CSS_V30 = prior._STEP3_VISUAL_CSS
_ORIGINAL_VISUAL_BANNER_V30 = prior._visual_build_banner_v30

_STEP4_CONTEXT_CSS = r'''
<style>
/* Step 4: presentation-only green/black reskin of frozen matchup/context cards. */
.kpy-dgrid,.kpy-xgrid,.kpy-igrid{gap:9px!important;margin:8px 0 12px!important}
.kpy-defense,.kpy-pressure,.kpy-personnel,.kpy-env{
  position:relative!important;overflow:hidden!important;
  border:1px solid #2b4b39!important;border-radius:16px!important;
  background:linear-gradient(145deg,#0b1712 0%,#09140f 72%,#0d1a14 100%)!important;
  padding:10px 11px!important;box-shadow:none!important;
}
/* Frozen context styles render later in the legacy stack. Keep the Step 4 outer
   card radius authoritative with element+class specificity across every family. */
section.kpy-defense,section.kpy-pressure,section.kpy-personnel,section.kpy-env{border-radius:16px!important}
.kpy-defense:after,.kpy-pressure:after,.kpy-personnel:after,.kpy-env:after{
  content:"";position:absolute;right:-38px;bottom:-62px;width:145px;height:145px;
  border:1px solid rgba(139,226,172,.045);border-radius:50%;
  box-shadow:0 0 0 18px rgba(139,226,172,.014);pointer-events:none;
}
.kpy-dhead,.kpy-xhead,.kpy-ihead,.kpy-envtop{position:relative;z-index:1!important;padding-bottom:7px!important;border-bottom:1px solid #1b3024!important;margin-bottom:8px!important}
.kpy-dname,.kpy-xname,.kpy-iname,.kpy-envtitle{color:#f5faf7!important;font-size:.84rem!important;font-weight:950!important;line-height:1.18!important}
.kpy-dsub,.kpy-xsub,.kpy-isub,.kpy-envsub{color:#73877a!important;font-size:.47rem!important;line-height:1.45!important;margin-top:3px!important}

.kpy-grade,.kpy-xgrade,.kpy-ilabel,.kpy-envlabel{position:relative;z-index:1!important;border-radius:999px!important;padding:4px 7px!important;font-size:.42rem!important;font-weight:950!important;letter-spacing:.035em!important}
.kpy-grade.check,.kpy-xgrade.check,.kpy-ilabel.check,.kpy-envlabel.check{border-color:#3c6a4d!important;background:#0f2418!important;color:#8be2ac!important}
.kpy-grade.balanced,.kpy-xgrade.moderate,.kpy-ilabel.mixed,.kpy-ilabel.watch,.kpy-envlabel.watch{border-color:#6d613a!important;background:#241f12!important;color:#dcc06d!important}
.kpy-grade.favorable,.kpy-xgrade.low-pressure,.kpy-ilabel.help,.kpy-envlabel.controlled{border-color:#3c6a4d!important;background:#0f2418!important;color:#8be2ac!important}
.kpy-grade.tough,.kpy-xgrade.high-pressure,.kpy-ilabel.hurt{border-color:#77443f!important;background:#271412!important;color:#f2a19a!important}
.kpy-ilabel.neutral,.kpy-envlabel.neutral,.kpy-envlabel.normal{border-color:#435e76!important;background:#111e29!important;color:#a9c5df!important}

.kpy-dmetrics,.kpy-xmetrics,.kpy-imetrics,.kpy-envmetrics{position:relative;z-index:1!important;gap:5px!important}
.kpy-dmetric,.kpy-xmetric,.kpy-imetric,.kpy-envmetric{
  border:1px solid #1d3527!important;border-radius:9px!important;
  background:#09140f!important;padding:7px 7px!important;min-width:0!important;
}
.kpy-dmetric b,.kpy-xmetric b,.kpy-imetric b,.kpy-envmetric b{color:#edf6f0!important;font-size:.70rem!important;font-weight:900!important}
.kpy-dmetric span,.kpy-xmetric span,.kpy-imetric span,.kpy-envmetric span{color:#607366!important;font-size:.39rem!important;font-weight:900!important;letter-spacing:.025em!important}

.kpy-drecent,.kpy-xrecent,.kpy-inote,.kpy28-weapons{
  position:relative;z-index:1!important;margin-top:7px!important;padding-top:7px!important;
  border-top:1px solid #1a2e22!important;color:#6c8174!important;font-size:.43rem!important;line-height:1.55!important;
}
.kpy-drecent b,.kpy-xrecent b,.kpy-inote b,.kpy28-weapons b{color:#91cda4!important}
.kpy-blitz,.kpy28-source{position:relative;z-index:1!important;color:#667b6e!important;font-size:.42rem!important}
.kpy28-weapon-pill{border-color:#315940!important;background:#0f2418!important;color:#a6e8b8!important;border-radius:999px!important;padding:3px 6px!important}

.kpy-envteams{position:relative;z-index:1!important;gap:6px!important}
.kpy-envteam{border:1px solid #1d3527!important;border-radius:10px!important;background:#09140f!important;padding:8px!important}
.kpy-envteam h4{color:#eef7f1!important;font-size:.72rem!important}
.kpy-envcell{color:#65796c!important;font-size:.43rem!important}.kpy-envcell b{color:#edf6f0!important;font-size:.65rem!important}

/* Keep all contextual tables visually subordinate and mobile-safe. */
div[data-testid="stDataFrame"]{border-radius:11px!important;overflow:hidden!important}
@media(max-width:820px){
  .kpy-dgrid,.kpy-xgrid,.kpy-igrid{grid-template-columns:1fr!important}
  .kpy-dmetrics,.kpy-xmetrics,.kpy-imetrics,.kpy-envmetrics{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .kpy-envteams{grid-template-columns:1fr!important}
}
</style>
'''


def _visual_build_banner_v31() -> str:
    return (
        '<section class="kpass29-build">'
        '<div class="kpass29-buildtop"><div>'
        '<div class="kpass29-buildtitle">🎨 Passing Yards • Visual Parity Build</div>'
        '<div class="kpass29-buildsub">Opponent defense, pressure, weapons/injuries, and game environment now share the certified Receiving/Rushing green card language • underlying Passing model remains frozen.</div>'
        '</div><div class="kpass29-buildchips">'
        '<span class="kpass29-buildchip">VISUAL STEP 4 / 6</span>'
        '<span class="kpass29-buildchip blue">V30 + V28 FROZEN</span>'
        '<span class="kpass29-buildchip gold">SPORTSBOOK 0%</span>'
        '</div></div><div class="kpass29-track"><div class="kpass29-fill" style="width:66.666%"></div></div>'
        '</section>'
    )


def render_nfl_passing_yards_hub() -> None:
    """Render frozen V30 with presentation-only Step 4 context styling."""
    original_css = prior._STEP3_VISUAL_CSS
    original_banner = prior._visual_build_banner_v30
    prior._STEP3_VISUAL_CSS = original_css + _STEP4_CONTEXT_CSS
    prior._visual_build_banner_v30 = _visual_build_banner_v31
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._STEP3_VISUAL_CSS = original_css
        prior._visual_build_banner_v30 = original_banner


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V31 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VISUAL_BUILD_STEP",
    "VISUAL_BUILD_TOTAL",
    "_STEP4_CONTEXT_CSS",
    "_visual_build_banner_v31",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
