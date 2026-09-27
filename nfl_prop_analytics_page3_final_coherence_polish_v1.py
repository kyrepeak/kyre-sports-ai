"""NFL Prop Analytics Page 3 Fun Polish Step 5 — final page coherence.

Presentation-only closeout layer after frozen Page 3 Steps 1-8 and Fun Polish
Steps 1-4. It standardizes spacing, section rhythm, responsive gutters, and
visual hierarchy without changing data, navigation, line, chart, market, or
availability semantics.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 FUN POLISH STEP 5 • FINAL COHERENCE V1"
PAGE3_FUN_POLISH_STEP = 5
PAGE3_FINAL_COHERENCE_VERSION = "v1"
PRESENTATION_ONLY = True
FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED = True
FROZEN_POLISH_STEPS_1_TO_4_PROTECTED = True
PROJECTION_LOGIC = False
PROBABILITY_LOGIC = False
RECOMMENDATION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS = False
CERTIFIED_VIEWPORTS = (390, 768, 1440)


def render_final_coherence_polish() -> dict[str, Any]:
    """Apply final presentation-only page coherence and emit closeout marker."""
    st.markdown(
        f"""
<div class="ks-pa3-fun-polish-step5-marker"
     data-prop-page3-fun-polish-step5="{PAGE3_FINAL_COHERENCE_VERSION}"
     data-prop-page3-fun-polish-step5-state="ready"
     data-prop-page3-fun-polish-step5-presentation-only="true"
     data-prop-page3-fun-polish-step5-frozen-steps-1-8="true"
     data-prop-page3-fun-polish-step5-frozen-polish-steps-1-4="true"
     data-prop-page3-fun-polish-step5-projection-weight="0.0"></div>

<style data-prop-page3-fun-polish-step5-css="{PAGE3_FINAL_COHERENCE_VERSION}">
.ks-pa3-fun-polish-step5-marker{{display:none!important}}

.ks-pa3-hero,.ks-pa3-stats,.ks-pa4-line,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi,.ks-pa8-page{{
  width:100%;max-width:100%;min-width:0;
}}

.ks-pa3-hero{{margin-bottom:10px!important;}}
.ks-pa3-stats,.ks-pa4-line,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi{{
  margin-top:10px!important;
  margin-bottom:10px!important;
  border-radius:16px!important;
}}

.ks-pa3-head,.ks-pa5-head,.ks-pa6-head,.ks-pa7mi-head{{min-width:0;}}
.ks-pa3-head strong,.ks-pa5-head strong,.ks-pa6-head strong,.ks-pa7mi-head strong{{
  letter-spacing:-.01em;
}}
.ks-pa3-head span,.ks-pa5-head span,.ks-pa6-head span,.ks-pa7mi-head span{{
  letter-spacing:.10em!important;
}}

.ks-pa3-stat-grid,.ks-pa4-line-grid,.ks-pa6-grid,.ks-pa7mi-grid,.ks-pa7mi-insights{{
  gap:8px!important;
}}
.ks-pa3-stat-grid article,.ks-pa4-line-grid article,.ks-pa6-grid article,.ks-pa7mi-grid article,.ks-pa7mi-insights article{{
  min-width:0;
  border-radius:13px!important;
}}

.ks-pa4-line-intro{{gap:10px!important;}}
.ks-pa4-line-grid .ks-pa4-line-value{{letter-spacing:-.02em;}}

.ks-pa5-scroll{{
  scrollbar-width:thin;
  scrollbar-color:rgba(125,211,252,.30) rgba(15,23,42,.35);
}}
.ks-pa5-scroll::-webkit-scrollbar{{height:7px}}
.ks-pa5-scroll::-webkit-scrollbar-thumb{{
  background:rgba(125,211,252,.28);border-radius:999px;
}}
.ks-pa5-scroll::-webkit-scrollbar-track{{
  background:rgba(15,23,42,.30);border-radius:999px;
}}

.ks-pa7mi-section{{margin-top:8px!important;}}
.ks-pa7mi-notes,.ks-pa7mi-foot{{margin-top:8px!important;}}

[data-testid="stSegmentedControl"]{{margin-bottom:2px}}
[data-testid="stSlider"]{{margin-top:2px;margin-bottom:2px}}

@media(max-width:760px){{
  .ks-pa3-hero,.ks-pa3-stats,.ks-pa4-line,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi{{
    border-radius:14px!important;
  }}
  .ks-pa3-stat-grid,.ks-pa4-line-grid,.ks-pa6-grid,.ks-pa7mi-grid,.ks-pa7mi-insights{{
    gap:7px!important;
  }}
}}

@media(max-width:560px){{
  .ks-pa3-hero,.ks-pa3-stats,.ks-pa4-line,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi,.ks-pa8-page{{
    max-width:100%!important;min-width:0!important;
  }}
  .ks-pa3-stats,.ks-pa4-line,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi{{
    margin-top:8px!important;margin-bottom:8px!important;
  }}
  .ks-pa3-stat-grid,.ks-pa4-line-grid,.ks-pa6-grid,.ks-pa7mi-grid,.ks-pa7mi-insights{{
    grid-template-columns:repeat(auto-fit,minmax(min(132px,100%),1fr))!important;
  }}
  .ks-pa5-scroll{{
    -webkit-overflow-scrolling:touch;
    overscroll-behavior-inline:contain;
  }}
}}

@media(prefers-reduced-motion:reduce){{
  .ks-pa3-hero,.ks-pa3-stats,.ks-pa4-line,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi{{
    scroll-behavior:auto!important;
  }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return {
        "ready": True,
        "state": "ready",
        "version": PAGE3_FINAL_COHERENCE_VERSION,
        "presentation_only": True,
        "frozen_steps_1_to_8": True,
        "frozen_polish_steps_1_to_4": True,
        "certified_viewports": CERTIFIED_VIEWPORTS,
        "projection_weight": 0.0,
    }


__all__ = [
    "CERTIFIED_VIEWPORTS",
    "FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED",
    "FROZEN_POLISH_STEPS_1_TO_4_PROTECTED",
    "MODEL_VERSION",
    "PAGE3_FINAL_COHERENCE_VERSION",
    "PAGE3_FUN_POLISH_STEP",
    "PRESENTATION_ONLY",
    "PROBABILITY_LOGIC",
    "PROJECTION_LOGIC",
    "RECOMMENDATION_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS",
    "render_final_coherence_polish",
]
