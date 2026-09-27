"""NFL Prop Analytics Page 3 Redesign Step 1 — protected layout shell.

Presentation-only foundation for the six-step Page 3 redesign. This layer owns
only page composition, spacing, surface hierarchy, and responsive shell styling.
All frozen Page 3 behavior and Fun Polish Steps 1-5 remain untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 REDESIGN STEP 1 • PROTECTED LAYOUT SHELL V1"
PAGE3_REDESIGN_STEP = 1
PAGE3_REDESIGN_STEP1_VERSION = "v1"
PRESENTATION_ONLY = True
FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED = True
FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED = True
INTERACTION_BEHAVIOR_CHANGED = False
DATA_OWNERSHIP_CHANGED = False
PROJECTION_LOGIC = False
PROBABILITY_LOGIC = False
RECOMMENDATION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS = False
MIN_TOUCH_TARGET_PX = 44
CERTIFIED_VIEWPORTS = (390, 768, 1440)


def render_redesign_step1_shell() -> dict[str, Any]:
    """Install the redesign shell without changing frozen controls or data."""
    st.markdown(
        f"""
<div class="ks-pa3-redesign-step1-marker"
     data-prop-page3-redesign-step1="{PAGE3_REDESIGN_STEP1_VERSION}"
     data-prop-page3-redesign-step1-state="ready"
     data-prop-page3-redesign-step1-presentation-only="true"
     data-prop-page3-redesign-step1-frozen-page3-steps="1-8"
     data-prop-page3-redesign-step1-frozen-fun-polish="1-5"
     data-prop-page3-redesign-step1-interaction-change="false"
     data-prop-page3-redesign-step1-data-owner-change="false"
     data-prop-page3-redesign-step1-projection-weight="0.0"></div>

<style data-prop-page3-redesign-step1-css="{PAGE3_REDESIGN_STEP1_VERSION}">
.ks-pa3-redesign-step1-marker{{display:none!important}}

/* Page-shell tokens. Scoped to the Page 3 surface via the marker. */
[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker){{
  --ks-r1-glacier:#38bdf8;
  --ks-r1-ice:#7dd3fc;
  --ks-r1-ink:#020812;
  --ks-r1-panel:#071321;
  --ks-r1-line:rgba(125,211,252,.18);
  --ks-r1-soft:rgba(56,189,248,.08);
  position:relative;
  isolation:isolate;
  max-width:1180px!important;
  margin-inline:auto!important;
  padding-top:1.0rem!important;
  padding-bottom:3rem!important;
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker)::before{{
  content:"";
  position:absolute;
  inset:0;
  z-index:-1;
  pointer-events:none;
  background:
    radial-gradient(circle at 18% 8%,rgba(14,165,233,.09),transparent 28rem),
    radial-gradient(circle at 88% 18%,rgba(56,189,248,.055),transparent 24rem),
    linear-gradient(180deg,rgba(2,8,18,.02),rgba(2,8,18,.18));
}}

/* One coherent vertical rhythm for every existing frozen Page 3 surface. */
.ks-pa3-hero,
.ks-pa3-stats,
.ks-pa4-line,
.ks-pa5-chart,
.ks-pa6-support,
.ks-pa7mi,
.ks-pa8-page{{
  width:100%!important;
  max-width:100%!important;
  min-width:0!important;
  box-sizing:border-box!important;
}}

.ks-pa3-hero{{
  margin-top:2px!important;
  margin-bottom:12px!important;
}}

.ks-pa3-stats,
.ks-pa4-line,
.ks-pa5-chart,
.ks-pa6-support,
.ks-pa7mi,
.ks-pa8-page{{
  margin-top:12px!important;
  margin-bottom:12px!important;
}}

/* Shared premium frame. Later redesign steps may enrich individual sections. */
.ks-pa3-hero,
.ks-pa3-stats,
.ks-pa4-line,
.ks-pa5-chart,
.ks-pa6-support,
.ks-pa7mi{{
  position:relative;
  overflow:clip;
  border-color:var(--ks-r1-line)!important;
  box-shadow:
    0 18px 42px rgba(0,0,0,.18),
    inset 0 1px 0 rgba(255,255,255,.025)!important;
}}

.ks-pa3-hero::after,
.ks-pa3-stats::after,
.ks-pa4-line::after,
.ks-pa5-chart::after,
.ks-pa6-support::after,
.ks-pa7mi::after{{
  content:"";
  position:absolute;
  left:16px;
  right:16px;
  top:0;
  height:1px;
  pointer-events:none;
  background:linear-gradient(90deg,transparent,rgba(125,211,252,.42),transparent);
  opacity:.74;
}}

/* Keep native controls physically comfortable and visually aligned. */
[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker)
[data-testid="stSegmentedControl"] button,
[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker)
[data-testid="stButton"] button{{
  min-height:{MIN_TOUCH_TARGET_PX}px!important;
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker)
[data-testid="stSegmentedControl"]{{
  margin-block:.18rem .42rem!important;
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker)
[data-testid="stSlider"]{{
  margin-block:.2rem .5rem!important;
}}

/* Prevent text/card blowout as the redesign becomes denser. */
.ks-pa3-hero *,
.ks-pa3-stats *,
.ks-pa4-line *,
.ks-pa5-chart *,
.ks-pa6-support *,
.ks-pa7mi *,
.ks-pa8-page *{{
  min-width:0;
}}

@media(max-width:900px){{
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker){{
    padding-left:1rem!important;
    padding-right:1rem!important;
  }}
}}

@media(max-width:560px){{
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker){{
    padding-left:.72rem!important;
    padding-right:.72rem!important;
    padding-top:.7rem!important;
  }}
  .ks-pa3-hero,
  .ks-pa3-stats,
  .ks-pa4-line,
  .ks-pa5-chart,
  .ks-pa6-support,
  .ks-pa7mi{{
    border-radius:14px!important;
    margin-top:9px!important;
    margin-bottom:9px!important;
  }}
}}

@media(prefers-reduced-motion:reduce){{
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker) *,
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker) *::before,
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step1-marker) *::after{{
    animation:none!important;
    transition:none!important;
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
        "version": PAGE3_REDESIGN_STEP1_VERSION,
        "presentation_only": True,
        "frozen_page3_steps_1_to_8": True,
        "frozen_fun_polish_steps_1_to_5": True,
        "interaction_behavior_changed": False,
        "data_ownership_changed": False,
        "min_touch_target_px": MIN_TOUCH_TARGET_PX,
        "certified_viewports": CERTIFIED_VIEWPORTS,
        "projection_weight": 0.0,
    }


__all__ = [
    "CERTIFIED_VIEWPORTS",
    "DATA_OWNERSHIP_CHANGED",
    "FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED",
    "FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED",
    "INTERACTION_BEHAVIOR_CHANGED",
    "MIN_TOUCH_TARGET_PX",
    "MODEL_VERSION",
    "PAGE3_REDESIGN_STEP",
    "PAGE3_REDESIGN_STEP1_VERSION",
    "PRESENTATION_ONLY",
    "PROBABILITY_LOGIC",
    "PROJECTION_LOGIC",
    "RECOMMENDATION_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS",
    "render_redesign_step1_shell",
]
