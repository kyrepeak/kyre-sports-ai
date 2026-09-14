"""NFL Passing Yards V32 — visual parity Step 5 analytical readouts.

Additive presentation-only wrapper over certified V31. V32 moves the frozen
Passing Yards analytical stack into the same compact green/black visual family
used by certified Receiving Yards, Rushing Yards, and Passing visual Steps 2–4:
- Step 7 baseline projection cards;
- Step 8 bounded context + uncertainty cards;
- Step 9 outcome distribution + probability cards;
- Step 10 post-model market evaluation cards.

V32 does not recompute, replace, or reinterpret any projection, uncertainty,
distribution, probability, fair-odds, no-vig, edge, EV, grade, or market value.
V1–V31, including certified V28 model/market behavior, remain frozen.
Sportsbook projection influence remains exactly 0.0% and stake sizing remains OFF.
"""
from __future__ import annotations

import nfl_passing_yards_hub_v31 as prior

MODEL_VERSION = "NFL PASSING YARDS V32 • VISUAL PARITY STEP 5 • ANALYTICAL READOUTS"
FROZEN_PRIOR = "nfl_passing_yards_hub_v31"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
VISUAL_BUILD_STEP = 5
VISUAL_BUILD_TOTAL = 6
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_STEP4_CONTEXT_CSS_V31 = prior._STEP4_CONTEXT_CSS
_ORIGINAL_VISUAL_BANNER_V31 = prior._visual_build_banner_v31

_STEP5_ANALYTICS_CSS = r'''
<style>
/* Step 5: presentation-only reskin of frozen Steps 7–10 analytical cards. */
.kpy-projgrid,.kpy8-grid,.kpy9-grid,.kpy10-grid{
  gap:8px!important;margin:8px 0 11px!important;
}
section.kpy-proj,section.kpy8-card,section.kpy9-card,section.kpy10-card{
  position:relative!important;overflow:hidden!important;
  border:1px solid #2b4b39!important;border-radius:16px!important;
  background:linear-gradient(145deg,#0b1712 0%,#09140f 72%,#0d1a14 100%)!important;
  padding:10px 11px!important;box-shadow:none!important;
}
section.kpy-proj:after,section.kpy8-card:after,section.kpy9-card:after,section.kpy10-card:after{
  content:"";position:absolute;right:-42px;bottom:-68px;width:150px;height:150px;
  border:1px solid rgba(139,226,172,.045);border-radius:50%;
  box-shadow:0 0 0 18px rgba(139,226,172,.014);pointer-events:none;
}
.kpy-projtop,.kpy8-top,.kpy9-top,.kpy10-top{
  position:relative;z-index:1!important;align-items:center!important;gap:8px!important;
  margin-bottom:9px!important;padding-bottom:7px!important;border-bottom:1px solid #1b3024!important;
}
.kpy-projname,.kpy8-name,.kpy9-name,.kpy10-name{
  color:#f5faf7!important;font-size:.90rem!important;font-weight:950!important;line-height:1.16!important;
}
.kpy-projsub,.kpy8-sub,.kpy9-sub,.kpy10-sub{
  color:#73877a!important;font-size:.47rem!important;line-height:1.42!important;margin-top:3px!important;
}

.kpy-projgrade,.kpy8-grade,.kpy9-grade,.kpy10-grade{
  position:relative;z-index:1!important;border-radius:999px!important;padding:4px 7px!important;
  font-size:.42rem!important;font-weight:950!important;letter-spacing:.035em!important;
}
.kpy-projgrade.green,.kpy8-grade.high,.kpy9-grade.high,.kpy10-grade.a,.kpy10-grade.b{
  border-color:#3c6a4d!important;background:#0f2418!important;color:#8be2ac!important;
}
.kpy-projgrade.watch,.kpy8-grade.medium,.kpy8-grade.low,.kpy9-grade.medium,.kpy9-grade.low,.kpy10-grade.c{
  border-color:#6d613a!important;background:#241f12!important;color:#dcc06d!important;
}
.kpy-projgrade.check,.kpy8-grade.check,.kpy9-grade.check,.kpy10-grade.check,.kpy10-grade.pass{
  border-color:#435e76!important;background:#111e29!important;color:#a9c5df!important;
}

.kpy-projhero,.kpy8-hero,.kpy9-hero,.kpy10-hero{position:relative;z-index:1!important;gap:5px!important;margin-bottom:7px!important}
.kpy-projhero>div,.kpy8-hero>div,.kpy9-hero>div,.kpy10-hero>div{
  border:1px solid #1d3527!important;border-radius:10px!important;background:#09140f!important;padding:8px!important;
}
.kpy-projhero b,.kpy8-hero b,.kpy9-hero b,.kpy10-hero b{
  color:#edf6f0!important;font-size:1.02rem!important;font-weight:950!important;
}
.kpy-projhero span,.kpy8-hero span,.kpy9-hero span,.kpy10-hero span{
  color:#607366!important;font-size:.40rem!important;font-weight:900!important;letter-spacing:.025em!important;
}

.kpy-projmeta,.kpy8-meta,.kpy10-metrics,.kpy9-q{position:relative;z-index:1!important;gap:5px!important}
.kpy-projmeta>div,.kpy8-meta>div,.kpy10-metrics>div,.kpy9-q>div{
  border:1px solid #1d3527!important;border-radius:9px!important;background:#09140f!important;
  color:#65796c!important;padding:7px 6px!important;
}
.kpy-projmeta b,.kpy8-meta b,.kpy10-metrics b,.kpy9-q b{
  color:#edf6f0!important;font-weight:900!important;
}
.kpy9-q span{color:#607366!important;font-weight:850!important}

.kpy-projctx,.kpy8-note,.kpy9-note,.kpy10-note{
  position:relative;z-index:1!important;margin-top:7px!important;padding-top:7px!important;
  border-top:1px solid #1a2e22!important;color:#6c8174!important;font-size:.45rem!important;line-height:1.55!important;
}
.kpy-projctx b,.kpy8-note b,.kpy9-note b,.kpy10-note b{color:#91cda4!important}

.kpy8-active,.kpy9-active,.kpy10-active{
  border:1px solid #2b4b39!important;border-radius:12px!important;
  background:linear-gradient(135deg,#0b1712 0%,#0d1d15 100%)!important;
  padding:9px 11px!important;box-shadow:none!important;
}
.kpy8-active b,.kpy9-active b,.kpy10-active b{color:#8be2ac!important;font-size:.72rem!important}
.kpy8-active span,.kpy9-active span,.kpy10-active span{color:#718579!important;font-size:.46rem!important;line-height:1.45!important}

@media(max-width:820px){
  .kpy-projgrid,.kpy8-grid,.kpy9-grid,.kpy10-grid{grid-template-columns:1fr!important}
  .kpy-projhero,.kpy8-hero,.kpy9-hero,.kpy10-hero{grid-template-columns:1fr 1fr!important}
  .kpy-projhero>div:first-child,.kpy8-hero>div:first-child,.kpy9-hero>div:first-child,.kpy10-hero>div:first-child{grid-column:1/-1!important}
  .kpy9-q{grid-template-columns:repeat(3,minmax(0,1fr))!important}
}
</style>
'''


def _visual_build_banner_v32() -> str:
    return (
        '<section class="kpass29-build">'
        '<div class="kpass29-buildtop"><div>'
        '<div class="kpass29-buildtitle">🎨 Passing Yards • Visual Parity Build</div>'
        '<div class="kpass29-buildsub">Projection, uncertainty, probability, and final market readouts now share the certified Receiving/Rushing compact green card language • all analytical values remain frozen.</div>'
        '</div><div class="kpass29-buildchips">'
        '<span class="kpass29-buildchip">VISUAL STEP 5 / 6</span>'
        '<span class="kpass29-buildchip blue">V31 + V28 FROZEN</span>'
        '<span class="kpass29-buildchip gold">SPORTSBOOK 0%</span>'
        '</div></div><div class="kpass29-track"><div class="kpass29-fill" style="width:83.333%"></div></div>'
        '</section>'
    )


def render_nfl_passing_yards_hub() -> None:
    """Render frozen V31 with presentation-only Step 5 analytical styling."""
    original_css = prior._STEP4_CONTEXT_CSS
    original_banner = prior._visual_build_banner_v31
    prior._STEP4_CONTEXT_CSS = original_css + _STEP5_ANALYTICS_CSS
    prior._visual_build_banner_v31 = _visual_build_banner_v32
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._STEP4_CONTEXT_CSS = original_css
        prior._visual_build_banner_v31 = original_banner


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V32 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VISUAL_BUILD_STEP",
    "VISUAL_BUILD_TOTAL",
    "_STEP5_ANALYTICS_CSS",
    "_visual_build_banner_v32",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
