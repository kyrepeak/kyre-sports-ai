"""NFL Prop Analytics Page 3 Fun Polish Step 3 — premium controls upgrade.

Presentation-only control styling layered after frozen Page 3 Steps 1-8 and
Fun Polish Steps 1-2. It changes no navigation, query, history, market, line,
chart, market-data, availability, or analytical semantics.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 FUN POLISH STEP 3 • CONTROLS V1"
PAGE3_FUN_POLISH_STEP = 3
PAGE3_CONTROLS_POLISH_VERSION = "v1"
PRESENTATION_ONLY = True
FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED = True
FROZEN_POLISH_STEPS_1_TO_2_PROTECTED = True
PROJECTION_LOGIC = False
PROBABILITY_LOGIC = False
RECOMMENDATION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS = False
MIN_TOUCH_TARGET_PX = 44


def render_controls_polish() -> dict[str, Any]:
    """Apply additive premium control styling and emit deterministic proof marker."""
    st.markdown(
        f"""
<div class="ks-pa3-fun-polish-step3-marker"
     data-prop-page3-fun-polish-step3="{PAGE3_CONTROLS_POLISH_VERSION}"
     data-prop-page3-fun-polish-step3-state="ready"
     data-prop-page3-fun-polish-step3-presentation-only="true"
     data-prop-page3-fun-polish-step3-frozen-steps-1-8="true"
     data-prop-page3-fun-polish-step3-frozen-polish-steps-1-2="true"
     data-prop-page3-fun-polish-step3-min-touch-target="{MIN_TOUCH_TARGET_PX}"
     data-prop-page3-fun-polish-step3-projection-weight="0.0"></div>

<style data-prop-page3-fun-polish-step3-css="{PAGE3_CONTROLS_POLISH_VERSION}">
.ks-pa3-fun-polish-step3-marker{{display:none!important}}

/* History + prop segmented navigation — richer sports-dashboard control shell. */
[data-testid="stSegmentedControl"]{{
  margin:.16rem 0 .42rem!important;
}}
[data-testid="stSegmentedControl"] [role="group"],
[data-testid="stSegmentedControl"] [role="radiogroup"]{{
  gap:5px!important;
  padding:4px!important;
  border:1px solid rgba(125,211,252,.12)!important;
  border-radius:14px!important;
  background:
    linear-gradient(180deg,rgba(6,16,28,.92),rgba(3,10,18,.96))!important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,.025),
    0 8px 24px rgba(0,0,0,.08)!important;
}}
[data-testid="stSegmentedControl"] button,
button[aria-pressed],
button[aria-checked]{{
  min-height:44px!important;
  border:1px solid transparent!important;
  border-radius:10px!important;
  color:#8399af!important;
  background:transparent!important;
  font-weight:850!important;
  letter-spacing:.025em!important;
  transition:
    color .16s ease,
    border-color .16s ease,
    background-color .16s ease,
    box-shadow .16s ease,
    transform .12s ease!important;
}}
[data-testid="stSegmentedControl"] button[aria-pressed="true"],
[data-testid="stSegmentedControl"] button[aria-selected="true"],
[data-testid="stSegmentedControl"] button[data-active="true"],
button[aria-pressed="true"],
button[aria-checked="true"]{{
  color:#e9f9ff!important;
  border-color:rgba(125,211,252,.36)!important;
  background:
    linear-gradient(180deg,rgba(14,165,233,.20),rgba(14,165,233,.09))!important;
  box-shadow:
    0 0 0 1px rgba(56,189,248,.05),
    0 0 18px rgba(56,189,248,.12),
    inset 0 1px 0 rgba(255,255,255,.05)!important;
}}
[data-testid="stSegmentedControl"] button:focus-visible,
button[aria-pressed]:focus-visible,
button[aria-checked]:focus-visible{{
  outline:2px solid rgba(125,211,252,.95)!important;
  outline-offset:2px!important;
  border-color:rgba(125,211,252,.48)!important;
  box-shadow:0 0 0 4px rgba(56,189,248,.16),0 0 20px rgba(56,189,248,.10)!important;
}}

/* Streamlit Line Lab slider — preserve value behavior, upgrade visual affordance. */
[data-testid="stSlider"]{{
  margin:.22rem 0 .55rem!important;
  padding:7px 10px 8px!important;
  border:1px solid rgba(125,211,252,.11)!important;
  border-radius:13px!important;
  background:
    radial-gradient(circle at 12% 0%,rgba(14,165,233,.08),transparent 12rem),
    rgba(4,12,22,.72)!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025)!important;
}}
[data-testid="stSlider"] label{{
  color:#9bc7dd!important;
  font-size:.62rem!important;
  font-weight:900!important;
  letter-spacing:.075em!important;
  text-transform:uppercase!important;
}}
[data-testid="stSlider"] [data-rac]:has(> div > input[type="range"]){{
  width:44px!important;
  height:44px!important;
  min-width:44px!important;
  min-height:44px!important;
  box-sizing:border-box!important;
  border-radius:999px!important;
  background:
    radial-gradient(circle at center,#38bdf8 0 9px,#d9f6ff 10px 11px,rgba(56,189,248,.14) 12px,transparent 13px)!important;
  box-shadow:inset 0 0 0 1px rgba(125,211,252,.08)!important;
  filter:drop-shadow(0 0 8px rgba(56,189,248,.32))!important;
  transition:filter .16s ease,transform .12s ease!important;
}}
[data-testid="stSlider"] [data-rac]:has(> div > input[type="range"]):focus-within{{
  outline:2px solid rgba(186,230,253,.95)!important;
  outline-offset:4px!important;
  box-shadow:inset 0 0 0 2px rgba(125,211,252,.18)!important;
  filter:drop-shadow(0 0 11px rgba(56,189,248,.42))!important;
}}

/* Line Lab information surface gets a slightly clearer active-analysis cue. */
.ks-pa4-line-intro{{
  border-color:rgba(56,189,248,.24)!important;
  box-shadow:inset 3px 0 0 rgba(56,189,248,.50),inset 0 1px 0 rgba(255,255,255,.025)!important;
}}
.ks-pa4-line-grid .ks-pa4-line-value{{
  border-color:rgba(56,189,248,.34)!important;
  box-shadow:0 0 18px rgba(56,189,248,.06)!important;
}}

@media(hover:hover){{
  [data-testid="stSegmentedControl"] button:hover{{
    color:#d8edf8!important;
    border-color:rgba(125,211,252,.22)!important;
    background:rgba(14,165,233,.065)!important;
    transform:translateY(-1px);
  }}
  [data-testid="stSlider"] [data-rac]:has(> div > input[type="range"]):hover{{
    transform:scale(1.07);
    box-shadow:inset 0 0 0 2px rgba(125,211,252,.12)!important;
    filter:drop-shadow(0 0 10px rgba(56,189,248,.40))!important;
  }}
}}

@media(max-width:560px){{
  [data-testid="stSegmentedControl"] [role="group"],
  [data-testid="stSegmentedControl"] [role="radiogroup"]{{
    gap:4px!important;padding:3px!important;border-radius:12px!important;
  }}
  [data-testid="stSegmentedControl"] button{{
    min-height:46px!important;
    padding-left:.52rem!important;
    padding-right:.52rem!important;
    border-radius:9px!important;
  }}
  [data-testid="stSlider"]{{padding:7px 8px 8px!important}}
}}

@media(prefers-reduced-motion:reduce){{
  [data-testid="stSegmentedControl"] button,
  [data-testid="stSlider"] [data-rac]:has(> div > input[type="range"]){{
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
        "version": PAGE3_CONTROLS_POLISH_VERSION,
        "presentation_only": True,
        "frozen_steps_1_to_8": True,
        "frozen_polish_steps_1_to_2": True,
        "min_touch_target_px": MIN_TOUCH_TARGET_PX,
        "projection_weight": 0.0,
    }


__all__ = [
    "FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED",
    "FROZEN_POLISH_STEPS_1_TO_2_PROTECTED",
    "MIN_TOUCH_TARGET_PX",
    "MODEL_VERSION",
    "PAGE3_CONTROLS_POLISH_VERSION",
    "PAGE3_FUN_POLISH_STEP",
    "PRESENTATION_ONLY",
    "PROBABILITY_LOGIC",
    "PROJECTION_LOGIC",
    "RECOMMENDATION_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS",
    "render_controls_polish",
]
