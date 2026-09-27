"""NFL Prop Analytics Page 3 Redesign Step 3 — Analysis Settings.

Presentation-only redesign of the frozen History Window + Prop Category controls.
No query, navigation, market, history, slider, chart, data-owner, projection,
probability, recommendation, staking, or wagering behavior changes.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 REDESIGN STEP 3 • ANALYSIS SETTINGS V1"
PAGE3_REDESIGN_STEP = 3
PAGE3_REDESIGN_STEP3_VERSION = "v1"
PRESENTATION_ONLY = True
FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED = True
FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED = True
FROZEN_REDESIGN_STEPS_1_TO_2_PROTECTED = True
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


def render_redesign_step3_analysis_settings() -> dict[str, Any]:
    """Style frozen analysis controls and emit deterministic proof marker."""
    st.markdown(
        f"""
<div class="ks-pa3-redesign-step3-marker"
     data-prop-page3-redesign-step3="{PAGE3_REDESIGN_STEP3_VERSION}"
     data-prop-page3-redesign-step3-state="ready"
     data-prop-page3-redesign-step3-presentation-only="true"
     data-prop-page3-redesign-step3-frozen-page3-steps="1-8"
     data-prop-page3-redesign-step3-frozen-fun-polish="1-5"
     data-prop-page3-redesign-step3-frozen-redesign="1-2"
     data-prop-page3-redesign-step3-interaction-change="false"
     data-prop-page3-redesign-step3-data-owner-change="false"
     data-prop-page3-redesign-step3-min-touch-target="{MIN_TOUCH_TARGET_PX}"
     data-prop-page3-redesign-step3-projection-weight="0.0"></div>

<style data-prop-page3-redesign-step3-css="{PAGE3_REDESIGN_STEP3_VERSION}">
.ks-pa3-redesign-step3-marker{{display:none!important}}

/* Turn the existing frozen navigation marker into a visual section heading. */
.ks-pa3-nav-marker{{
  display:block!important;
  position:relative;
  min-height:68px;
  margin:14px 0 8px!important;
  padding:13px 15px 12px 48px;
  border:1px solid rgba(125,211,252,.18);
  border-radius:16px;
  background:
    radial-gradient(circle at 3% 20%,rgba(56,189,248,.16),transparent 9rem),
    linear-gradient(180deg,rgba(6,18,31,.94),rgba(3,10,19,.98));
  box-shadow:
    0 16px 36px rgba(0,0,0,.18),
    inset 0 1px 0 rgba(255,255,255,.028);
}}

.ks-pa3-nav-marker::before{{
  content:"STEP 3  •  ANALYSIS SETTINGS";
  display:block;
  color:#dff6ff;
  font-size:.82rem;
  line-height:1.1;
  font-weight:950;
  letter-spacing:.08em;
}}

.ks-pa3-nav-marker::after{{
  content:"Customize historical context and prop category. Every control below remains fully interactive.";
  display:block;
  margin-top:7px;
  color:#7992ac;
  font-size:.59rem;
  line-height:1.35;
  font-weight:700;
  letter-spacing:.015em;
}}

.ks-pa3-nav-marker{{
  background-image:
    radial-gradient(circle at 3% 20%,rgba(56,189,248,.16),transparent 9rem),
    linear-gradient(180deg,rgba(6,18,31,.94),rgba(3,10,19,.98));
}}

.ks-pa3-nav-marker > *{{display:none!important}}

.ks-pa3-nav-marker::selection{{background:rgba(56,189,248,.25)}}

/* Glacier icon tile without changing frozen HTML. */
[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
.ks-pa3-nav-marker{{
  background-color:#04101c;
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
.ks-pa3-nav-marker{{
  box-sizing:border-box;
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
.ks-pa3-nav-marker::marker{{content:""}}

/* Each existing segmented control becomes a premium settings card. */
[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
[data-testid="stSegmentedControl"]{{
  position:relative;
  margin:.38rem 0 .62rem!important;
  padding:12px 12px 11px!important;
  border:1px solid rgba(125,211,252,.14)!important;
  border-radius:16px!important;
  background:
    radial-gradient(circle at 4% 0%,rgba(14,165,233,.075),transparent 13rem),
    linear-gradient(180deg,rgba(7,18,31,.88),rgba(4,11,20,.95))!important;
  box-shadow:
    0 12px 30px rgba(0,0,0,.13),
    inset 0 1px 0 rgba(255,255,255,.025)!important;
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
[data-testid="stSegmentedControl"] label{{
  display:flex!important;
  align-items:center!important;
  gap:8px!important;
  margin-bottom:8px!important;
  color:#bdeaff!important;
  font-size:.66rem!important;
  font-weight:950!important;
  letter-spacing:.10em!important;
  text-transform:uppercase!important;
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
[data-testid="stSegmentedControl"] label::before{{
  content:"";
  display:inline-block;
  width:7px;
  height:7px;
  flex:0 0 7px;
  border-radius:999px;
  background:#38bdf8;
  box-shadow:0 0 12px rgba(56,189,248,.65);
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
[data-testid="stSegmentedControl"] [role="group"],
[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
[data-testid="stSegmentedControl"] [role="radiogroup"]{{
  display:flex!important;
  width:100%!important;
  gap:6px!important;
  padding:5px!important;
  border:1px solid rgba(125,211,252,.10)!important;
  border-radius:13px!important;
  background:rgba(2,8,18,.68)!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.018)!important;
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
[data-testid="stSegmentedControl"] button{{
  min-height:{MIN_TOUCH_TARGET_PX}px!important;
  flex:1 1 0!important;
  border-radius:10px!important;
  border:1px solid transparent!important;
  color:#8398ae!important;
  background:transparent!important;
  font-size:.67rem!important;
  font-weight:900!important;
  letter-spacing:.03em!important;
  box-shadow:none!important;
  transition:
    transform .12s ease,
    color .16s ease,
    border-color .16s ease,
    background-color .16s ease,
    box-shadow .16s ease!important;
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
[data-testid="stSegmentedControl"] button[aria-checked="true"],
[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
[data-testid="stSegmentedControl"] button[aria-pressed="true"],
[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
[data-testid="stSegmentedControl"] button[aria-selected="true"]{{
  color:#eefbff!important;
  border-color:rgba(125,211,252,.42)!important;
  background:
    linear-gradient(180deg,rgba(14,165,233,.23),rgba(2,132,199,.10))!important;
  box-shadow:
    0 0 0 1px rgba(56,189,248,.055),
    0 0 20px rgba(56,189,248,.12),
    inset 0 1px 0 rgba(255,255,255,.045)!important;
}}

[data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
[data-testid="stSegmentedControl"] button:focus-visible{{
  outline:2px solid rgba(186,230,253,.96)!important;
  outline-offset:2px!important;
  box-shadow:0 0 0 4px rgba(56,189,248,.15)!important;
}}

@media(hover:hover){{
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
  [data-testid="stSegmentedControl"] button:hover{{
    transform:translateY(-1px);
    color:#dff5ff!important;
    border-color:rgba(125,211,252,.22)!important;
    background:rgba(14,165,233,.06)!important;
  }}
}}

@media(max-width:760px){{
  .ks-pa3-nav-marker{{
    min-height:64px;
    padding:12px 13px 11px 16px;
  }}
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
  [data-testid="stSegmentedControl"]{{
    padding:10px!important;
  }}
}}

@media(max-width:560px){{
  .ks-pa3-nav-marker{{
    border-radius:14px;
    margin-top:10px!important;
  }}
  .ks-pa3-nav-marker::before{{
    font-size:.72rem;
  }}
  .ks-pa3-nav-marker::after{{
    font-size:.55rem;
  }}
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
  [data-testid="stSegmentedControl"] [role="group"],
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
  [data-testid="stSegmentedControl"] [role="radiogroup"]{{
    overflow-x:auto!important;
    justify-content:flex-start!important;
    overscroll-behavior-inline:contain;
    scrollbar-width:none;
    scroll-snap-type:x proximity;
  }}
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
  [data-testid="stSegmentedControl"] [role="group"]::-webkit-scrollbar,
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
  [data-testid="stSegmentedControl"] [role="radiogroup"]::-webkit-scrollbar{{
    display:none;
  }}
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
  [data-testid="stSegmentedControl"] button{{
    min-width:64px!important;
    min-height:46px!important;
    flex:0 0 auto!important;
    scroll-snap-align:start;
  }}
}}

@media(prefers-reduced-motion:reduce){{
  [data-testid="stMainBlockContainer"]:has(.ks-pa3-redesign-step3-marker)
  [data-testid="stSegmentedControl"] button{{
    transition:none!important;
    transform:none!important;
  }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return {
        "ready": True,
        "state": "ready",
        "version": PAGE3_REDESIGN_STEP3_VERSION,
        "presentation_only": True,
        "frozen_page3_steps_1_to_8": True,
        "frozen_fun_polish_steps_1_to_5": True,
        "frozen_redesign_steps_1_to_2": True,
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
    "FROZEN_REDESIGN_STEPS_1_TO_2_PROTECTED",
    "INTERACTION_BEHAVIOR_CHANGED",
    "MIN_TOUCH_TARGET_PX",
    "MODEL_VERSION",
    "PAGE3_REDESIGN_STEP",
    "PAGE3_REDESIGN_STEP3_VERSION",
    "PRESENTATION_ONLY",
    "PROBABILITY_LOGIC",
    "PROJECTION_LOGIC",
    "RECOMMENDATION_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS",
    "render_redesign_step3_analysis_settings",
]
