"""NFL Prop Analytics Page 3 Fun Polish Step 4 — premium data panels.

Presentation-only visual layer for the frozen historical stats, game chart,
supporting stats, and market/insight surfaces. No data ownership or analysis
semantics change.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 FUN POLISH STEP 4 • DATA PANELS V1"
PAGE3_FUN_POLISH_STEP = 4
PAGE3_DATA_PANELS_POLISH_VERSION = "v1"
PRESENTATION_ONLY = True
FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED = True
FROZEN_POLISH_STEPS_1_TO_3_PROTECTED = True
PROJECTION_LOGIC = False
PROBABILITY_LOGIC = False
RECOMMENDATION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS = False
CERTIFIED_VIEWPORTS = (390, 768, 1440)


def render_data_panels_polish() -> dict[str, Any]:
    """Apply presentation-only premium styling to frozen Page 3 data surfaces."""
    st.markdown(
        f"""
<div class="ks-pa3-fun-polish-step4-marker"
     data-prop-page3-fun-polish-step4="{PAGE3_DATA_PANELS_POLISH_VERSION}"
     data-prop-page3-fun-polish-step4-state="ready"
     data-prop-page3-fun-polish-step4-presentation-only="true"
     data-prop-page3-fun-polish-step4-frozen-steps-1-8="true"
     data-prop-page3-fun-polish-step4-frozen-polish-steps-1-3="true"
     data-prop-page3-fun-polish-step4-projection-weight="0.0"></div>

<style data-prop-page3-fun-polish-step4-css="{PAGE3_DATA_PANELS_POLISH_VERSION}">
.ks-pa3-fun-polish-step4-marker{{display:none!important}}

.ks-pa3-stats,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi{{
  position:relative;
  border-color:rgba(125,211,252,.22)!important;
  background:
    radial-gradient(circle at 92% -12%,rgba(56,189,248,.12),transparent 21rem),
    linear-gradient(180deg,rgba(5,15,27,.985),rgba(2,8,15,.995))!important;
  box-shadow:
    0 16px 38px rgba(0,0,0,.20),
    inset 0 1px 0 rgba(255,255,255,.035)!important;
}}
.ks-pa3-stats::before,.ks-pa5-chart::before,.ks-pa6-support::before,.ks-pa7mi::before{{
  content:"";position:absolute;left:14px;right:14px;top:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(125,211,252,.60),transparent);
  opacity:.72;pointer-events:none;
}}

.ks-pa3-stat-grid article,.ks-pa6-grid article,.ks-pa7mi-grid article,.ks-pa7mi-insights article{{
  border-color:rgba(125,211,252,.13)!important;
  background:
    linear-gradient(180deg,rgba(15,28,43,.76),rgba(6,15,25,.86))!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.028);
}}
.ks-pa3-stat-grid article strong,.ks-pa6-grid article strong,.ks-pa7mi-grid article strong{{
  color:#f2fbff!important;
  text-shadow:0 0 16px rgba(125,211,252,.08);
}}
.ks-pa3-stat-grid article span,.ks-pa6-grid article span,.ks-pa7mi-grid article span{{
  color:#86b9d2!important;
}}

.ks-pa5-head,.ks-pa6-head,.ks-pa7mi-head{{
  padding-bottom:8px;
  border-bottom:1px solid rgba(125,211,252,.075);
}}
.ks-pa5-legend{{
  padding:7px 9px;margin-top:8px!important;border-radius:10px;
  border:1px solid rgba(125,211,252,.08);
  background:rgba(8,19,31,.62);
}}
.ks-pa5-scroll{{
  margin-top:5px;border-radius:12px;
  border:1px solid rgba(125,211,252,.07);
  background:rgba(2,8,15,.28);
}}
.ks-pa5-plot{{
  background:
    repeating-linear-gradient(to top,transparent 0,transparent 49px,rgba(125,211,252,.055) 50px),
    linear-gradient(180deg,rgba(8,20,34,.36),rgba(3,9,16,.18))!important;
}}
.ks-pa5-over{{
  box-shadow:0 0 15px rgba(56,189,248,.24)!important;
}}
.ks-pa5-game:hover .ks-pa5-value{{color:#e5f7ff}}
.ks-pa5-foot span{{
  background:rgba(14,165,233,.045);
  border-color:rgba(125,211,252,.14)!important;
}}

.ks-pa6-note,.ks-pa7mi-foot,.ks-pa7mi-notes{{
  border-color:rgba(125,211,252,.08)!important;
  background:rgba(8,18,29,.48)!important;
}}
.ks-pa7mi-section{{
  border-color:rgba(125,211,252,.09)!important;
}}
.ks-pa7mi-selected{{
  border-color:rgba(56,189,248,.34)!important;
  background:linear-gradient(180deg,rgba(14,165,233,.12),rgba(14,165,233,.045))!important;
  box-shadow:0 0 20px rgba(14,165,233,.07),inset 0 1px 0 rgba(255,255,255,.025)!important;
}}
.ks-pa7mi-market{{
  border-radius:12px!important;
}}
.ks-pa7mi-insights article{{
  border-radius:13px!important;
}}

@media(hover:hover){{
  .ks-pa3-stat-grid article,.ks-pa6-grid article,.ks-pa7mi-grid article,.ks-pa7mi-insights article{{
    transition:transform .14s ease,border-color .14s ease,box-shadow .14s ease;
  }}
  .ks-pa3-stat-grid article:hover,.ks-pa6-grid article:hover,.ks-pa7mi-grid article:hover,.ks-pa7mi-insights article:hover{{
    transform:translateY(-1px);
    border-color:rgba(125,211,252,.26)!important;
    box-shadow:0 10px 24px rgba(0,0,0,.14),inset 0 1px 0 rgba(255,255,255,.035);
  }}
}}

@media(max-width:760px){{
  .ks-pa3-stats,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi{{
    padding:12px!important;
  }}
  .ks-pa5-legend{{gap:8px!important;flex-wrap:wrap}}
}}
@media(max-width:560px){{
  .ks-pa3-stats,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi{{
    max-width:100%!important;min-width:0!important;border-radius:14px!important;
  }}
  .ks-pa5-head,.ks-pa6-head,.ks-pa7mi-head{{gap:5px!important}}
  .ks-pa5-foot em{{width:100%;margin-left:0!important}}
}}
@media(prefers-reduced-motion:reduce){{
  .ks-pa3-stat-grid article,.ks-pa6-grid article,.ks-pa7mi-grid article,.ks-pa7mi-insights article{{
    transition:none!important;transform:none!important;
  }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return {
        "ready": True,
        "state": "ready",
        "version": PAGE3_DATA_PANELS_POLISH_VERSION,
        "presentation_only": True,
        "frozen_steps_1_to_8": True,
        "frozen_polish_steps_1_to_3": True,
        "certified_viewports": CERTIFIED_VIEWPORTS,
        "projection_weight": 0.0,
    }


__all__ = [
    "CERTIFIED_VIEWPORTS",
    "FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED",
    "FROZEN_POLISH_STEPS_1_TO_3_PROTECTED",
    "MODEL_VERSION",
    "PAGE3_DATA_PANELS_POLISH_VERSION",
    "PAGE3_FUN_POLISH_STEP",
    "PRESENTATION_ONLY",
    "PROBABILITY_LOGIC",
    "PROJECTION_LOGIC",
    "RECOMMENDATION_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS",
    "render_data_panels_polish",
]
