"""NFL Prop Analytics Page 3 Fun Polish Step 1 — cleanup + visual bugs.

Presentation-only cleanup layered on top of the frozen Page 3 Steps 1-8 build.
This module does not own player identity, history, lines, chart values,
supporting stats, market data, availability, projections, or recommendations.

Step 1 fixes:
- suppress leaked raw chart markup from the Step 5 markdown container;
- give the Step 7 LOCKED state the same premium card treatment as ready state;
- preserve the black + glacier-blue universal theme and all frozen data logic.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 FUN POLISH STEP 1 • CLEANUP V1"
PAGE3_FUN_POLISH_STEP = 1
PAGE3_FUN_POLISH_VERSION = "v1"
PRESENTATION_ONLY = True
FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED = True
PROJECTION_LOGIC = False
PROBABILITY_LOGIC = False
RECOMMENDATION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS = False


def render_cleanup_polish() -> dict[str, Any]:
    """Inject additive cleanup CSS and a deterministic certification marker."""
    st.markdown(
        f"""
<div class="ks-pa3-fun-polish-step1-marker"
     data-prop-page3-fun-polish-step1="{PAGE3_FUN_POLISH_VERSION}"
     data-prop-page3-fun-polish-step1-state="ready"
     data-prop-page3-fun-polish-step1-presentation-only="true"
     data-prop-page3-fun-polish-step1-frozen-steps-1-8="true"
     data-prop-page3-fun-polish-step1-projection-weight="0.0"></div>

<style data-prop-page3-fun-polish-step1-css="{PAGE3_FUN_POLISH_VERSION}">
.ks-pa3-fun-polish-step1-marker{{display:none!important}}

/* Screenshot cleanup: the Step 5 markdown renderer can surface a raw closing
   tag as a code/pre fragment. Hide only code/pre descendants belonging to the
   markdown block that contains the certified Step 5 chart. */
[data-testid="stMarkdown"]:has(.ks-pa5-chart) pre,
[data-testid="stMarkdown"]:has(.ks-pa5-chart) code{{
  display:none!important;
}}

/* Step 7 returns early while availability is PENDING, so its locked markup
   does not receive the ready-state CSS block. Restore the same premium visual
   language additively without touching the frozen Step 7 data/gate contract. */
.ks-pa7mi-locked{{
  width:100%;max-width:100%;min-width:0;overflow:hidden;
  margin:10px 0 14px;padding:14px 16px;
  border:1px solid rgba(56,189,248,.22);border-radius:16px;
  background:
    radial-gradient(circle at 92% 0%,rgba(14,165,233,.10),transparent 18rem),
    linear-gradient(180deg,rgba(6,16,28,.98),rgba(3,10,18,.99));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.03),0 10px 30px rgba(0,0,0,.12);
}}
.ks-pa7mi-locked .ks-pa7mi-head{{
  display:flex;align-items:flex-end;justify-content:space-between;gap:12px;
  margin:0 0 8px;
}}
.ks-pa7mi-locked .ks-pa7mi-head>div{{
  min-width:0;display:flex;flex-direction:column;gap:3px;
}}
.ks-pa7mi-locked .ks-pa7mi-head span{{
  color:#38bdf8;font-size:.54rem;font-weight:950;letter-spacing:.12em;
}}
.ks-pa7mi-locked .ks-pa7mi-head strong{{
  display:block;color:#eef8ff;font-size:.88rem;line-height:1.15;
}}
.ks-pa7mi-locked .ks-pa7mi-head em{{
  padding:4px 7px;border:1px solid rgba(56,189,248,.16);border-radius:999px;
  color:#8fb4cd;background:rgba(14,165,233,.05);
  font-size:.47rem;font-style:normal;font-weight:900;letter-spacing:.06em;
  white-space:nowrap;
}}
.ks-pa7mi-locked>p{{
  margin:0;padding-top:8px;border-top:1px solid rgba(148,163,184,.08);
  color:#8da2b8;font-size:.66rem;line-height:1.5;
}}

@media(max-width:560px){{
  .ks-pa7mi-locked{{padding:13px 12px;border-radius:14px}}
  .ks-pa7mi-locked .ks-pa7mi-head{{
    align-items:flex-start;flex-direction:column;gap:6px;
  }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return {
        "ready": True,
        "state": "ready",
        "version": PAGE3_FUN_POLISH_VERSION,
        "presentation_only": True,
        "frozen_steps_1_to_8": True,
        "projection_weight": 0.0,
    }


__all__ = [
    "FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED",
    "MODEL_VERSION",
    "PAGE3_FUN_POLISH_STEP",
    "PAGE3_FUN_POLISH_VERSION",
    "PRESENTATION_ONLY",
    "PROBABILITY_LOGIC",
    "PROJECTION_LOGIC",
    "RECOMMENDATION_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS",
    "render_cleanup_polish",
]
