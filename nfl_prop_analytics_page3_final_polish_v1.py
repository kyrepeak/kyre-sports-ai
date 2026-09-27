"""NFL Prop Analytics Page 3 Step 8 — final professional polish + freeze marker.

This final Page 3 layer is presentation-only. It does not change any frozen
Steps 1-7 data ownership, identity, history, line, chart, supporting-stat,
market, availability, or safety semantics.

Contract:
- preserve black + glacier-blue universal visual system;
- preserve real team colors/logos already rendered by frozen Step 1;
- tighten Page 3 spacing without hiding information;
- minimum 44px touch targets for interactive controls;
- clear focus-visible states and reduced-motion support;
- no horizontal document overflow at 390/768/1440;
- expose a deterministic final-polish DOM marker for end-to-end certification;
- no projection/probability/recommendation/staking/wager logic.
"""
from __future__ import annotations

import html as html_lib
from typing import Any

import streamlit as st

from nfl_prop_analytics_page3_cleanup_polish_v1 import render_cleanup_polish
from nfl_prop_analytics_page3_hero_polish_v1 import render_hero_polish
from nfl_prop_analytics_page3_controls_polish_v1 import render_controls_polish
from nfl_prop_analytics_page3_data_panels_polish_v1 import render_data_panels_polish
from nfl_prop_analytics_page3_final_coherence_polish_v1 import render_final_coherence_polish
from nfl_prop_analytics_page3_redesign_step1_shell_v1 import render_redesign_step1_shell

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 STEP 8 • FINAL PROFESSIONAL POLISH V1"
PAGE3_FINAL_POLISH_STEP = 8
PAGE3_FINAL_POLISH_VERSION = "v1"

PRESENTATION_ONLY = True
FROZEN_STEPS_1_TO_7_PROTECTED = True
PROJECTION_LOGIC = False
PROBABILITY_LOGIC = False
RECOMMENDATION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS = False
MIN_TOUCH_TARGET_PX = 44
CERTIFIED_VIEWPORTS = (390, 768, 1440)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def render_final_polish(
    *,
    player_id: Any,
    market_key: Any,
    history_key: Any,
    gate_open: bool,
    history_state: Any,
    step7_state: Any,
) -> dict[str, Any]:
    """Apply additive Page 3 visual polish and emit the final certification marker."""
    player = _text(player_id)
    market = _text(market_key)
    history = _text(history_key)
    gate = "OPEN" if bool(gate_open) else "CLOSED"
    history_state_text = _text(history_state).lower() or "unknown"
    step7_state_text = _text(step7_state).lower() or "unknown"

    st.markdown(
        f"""
<div class="ks-pa3-final-marker"
     data-prop-page3-step8-final-polish="{PAGE3_FINAL_POLISH_VERSION}"
     data-prop-page3-step8-state="ready"
     data-prop-page3-step8-player-id="{html_lib.escape(player)}"
     data-prop-page3-step8-market="{html_lib.escape(market)}"
     data-prop-page3-step8-history="{html_lib.escape(history)}"
     data-prop-page3-step8-gate="{gate}"
     data-prop-page3-step8-history-state="{html_lib.escape(history_state_text)}"
     data-prop-page3-step8-step7-state="{html_lib.escape(step7_state_text)}"
     data-prop-page3-step8-presentation-only="true"
     data-prop-page3-step8-frozen-steps-1-7="true"
     data-prop-page3-step8-min-touch-target="{MIN_TOUCH_TARGET_PX}"
     data-prop-page3-step8-projection-weight="0.0"
     data-prop-page3-step8-recommendations="0"
     data-prop-page3-step8-wager-actions="0"></div>

<style data-prop-page3-step8-final-polish-css="{PAGE3_FINAL_POLISH_VERSION}">
/* Final Page 3 polish is additive and presentation-only. */
.ks-pa3-final-marker{{display:none!important}}

/* Streamlit's current segmented controls expose 32px live <button> elements
   without a stable wrapper tag. Step 8 owns presentation only, so apply the
   accessibility floor directly to buttons while Page 3 is rendered. */
button{{
  min-height:44px!important;
}}
button:focus-visible{{
  outline:2px solid rgba(125,211,252,.95)!important;
  outline-offset:2px!important;
  box-shadow:0 0 0 4px rgba(56,189,248,.16)!important;
}}

[data-testid="stSegmentedControl"] button,
[data-testid="stButton"] button,
button[data-testid="stBaseButton-secondary"],
button[data-testid="stBaseButton-primary"]{{
  min-height:44px!important;
  transition:border-color .16s ease,background-color .16s ease,box-shadow .16s ease,transform .12s ease;
}}

[data-testid="stSegmentedControl"] button:focus-visible,
[data-testid="stButton"] button:focus-visible,
[data-testid="stSlider"] [role="slider"]:focus-visible{{
  outline:2px solid rgba(125,211,252,.95)!important;
  outline-offset:2px!important;
  box-shadow:0 0 0 4px rgba(56,189,248,.16)!important;
}}

.ks-pa3-hero,
.ks-pa3-stats,
.ks-pa4-line,
.ks-pa5-chart,
.ks-pa6-support,
.ks-pa7mi,
.ks-pa8-page{{
  scroll-margin-top:14px;
}}

.ks-pa3-stats,
.ks-pa4-line,
.ks-pa5-chart,
.ks-pa6-support,
.ks-pa7mi{{
  margin-top:8px!important;
  margin-bottom:10px!important;
}}

.ks-pa3-stat-grid article,
.ks-pa4-line-grid article,
.ks-pa6-grid article,
.ks-pa7mi-grid article,
.ks-pa7mi-insights article{{
  transition:border-color .16s ease,background-color .16s ease,transform .12s ease;
}}

@media(hover:hover){{
  .ks-pa3-stat-grid article:hover,
  .ks-pa4-line-grid article:hover,
  .ks-pa6-grid article:hover,
  .ks-pa7mi-grid article:hover,
  .ks-pa7mi-insights article:hover{{
    border-color:rgba(125,211,252,.24);
    transform:translateY(-1px);
  }}
}}

@media(max-width:760px){{
  .ks-pa3-hero{{margin-bottom:10px!important}}
  .ks-pa3-stats,.ks-pa4-line,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi{{border-radius:14px!important}}
}}

@media(max-width:560px){{
  div[data-testid="stSegmentedControl"] button{{
    min-height:46px!important;
    padding-left:.55rem!important;
    padding-right:.55rem!important;
  }}
  .ks-pa3-hero,.ks-pa3-stats,.ks-pa4-line,.ks-pa5-chart,.ks-pa6-support,.ks-pa7mi,.ks-pa8-page{{
    max-width:100%!important;
    min-width:0!important;
  }}
}}

@media(prefers-reduced-motion:reduce){{
  *,*::before,*::after{{
    scroll-behavior:auto!important;
    transition:none!important;
    animation:none!important;
  }}
}}
</style>
""",
        unsafe_allow_html=True,
    )

    cleanup_polish = render_cleanup_polish()
    hero_polish = render_hero_polish()
    controls_polish = render_controls_polish()
    data_panels_polish = render_data_panels_polish()
    final_coherence_polish = render_final_coherence_polish()
    redesign_step1_shell = render_redesign_step1_shell()

    return {
        "ready": True,
        "state": "ready",
        "version": PAGE3_FINAL_POLISH_VERSION,
        "presentation_only": True,
        "frozen_steps_1_to_7": True,
        "player_id": player,
        "market_key": market,
        "history_key": history,
        "gate": gate,
        "history_state": history_state_text,
        "step7_state": step7_state_text,
        "min_touch_target_px": MIN_TOUCH_TARGET_PX,
        "certified_viewports": CERTIFIED_VIEWPORTS,
        "projection_weight": 0.0,
        "recommendations": False,
        "wager_actions": False,
        "cleanup_polish": cleanup_polish,
        "hero_polish": hero_polish,
        "controls_polish": controls_polish,
        "data_panels_polish": data_panels_polish,
        "final_coherence_polish": final_coherence_polish,
        "redesign_step1_shell": redesign_step1_shell,
    }


__all__ = [
    "CERTIFIED_VIEWPORTS",
    "FROZEN_STEPS_1_TO_7_PROTECTED",
    "MIN_TOUCH_TARGET_PX",
    "MODEL_VERSION",
    "PAGE3_FINAL_POLISH_STEP",
    "PAGE3_FINAL_POLISH_VERSION",
    "PRESENTATION_ONLY",
    "PROBABILITY_LOGIC",
    "PROJECTION_LOGIC",
    "RECOMMENDATION_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS",
    "render_final_polish",
]
