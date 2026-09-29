"""WNBA Navigation V2 — Step 6 responsive three-page integration.

Presentation/integration-only shell over frozen Step 5. It adds one shared
responsive/touch/focus contract for Slate, Game Center, and Player Intelligence
without changing any frozen page logic, data source, model, market, probability,
ranking, qualification, or Monte Carlo behavior.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_performance_v2_step5 as performance


MODEL_VERSION = "WNBA PRA NAVIGATION V2 • STEP 6 RESPONSIVE INTEGRATION"
CERTIFIED_VIEWPORTS = (390, 768, 1440)
MIN_TOUCH_TARGET_PX = 44

RESPONSIVE_CONTRACT = {
    "project": "WNBA Navigation V2",
    "step": "6/7",
    "scope": "three_page_ux_responsive_integration_only",
    "certified_viewports": list(CERTIFIED_VIEWPORTS),
    "zero_horizontal_overflow_required": True,
    "fresh_browser_session_per_viewport": True,
    "back_navigation_preserved": True,
    "query_state_persistence_preserved": True,
    "session_state_persistence_preserved": True,
    "single_rerun_transport_preserved": True,
    "min_touch_target_px": MIN_TOUCH_TARGET_PX,
    "keyboard_focus_visible": True,
    "reduced_motion_supported": True,
    "frozen_steps_1_through_5_modified": False,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
}


def render_responsive_shell(state: navigation.NavigationState) -> None:
    """Inject the shared three-page responsive contract before frozen Step 5."""
    st.html(
        f"""
<div data-wnba-nav-v2-step6="responsive-integration"
     data-wnba-nav-page="{state.page}"
     data-wnba-nav-depth="{state.depth}"
     data-wnba-nav-game-selected="{'true' if bool(state.game_id) else 'false'}"
     data-wnba-nav-player-selected="{'true' if bool(state.player_id) else 'false'}"
     data-wnba-nav-responsive-targets="390,768,1440"
     data-wnba-nav-zero-overflow="required"
     data-wnba-nav-state-persistence="query+session"
     style="height:0;min-height:0;overflow:hidden;padding:0;margin:0;border:0"
     aria-hidden="true"></div>
<style data-wnba-nav-v2-step6-css="responsive-integration">
*,*::before,*::after{{box-sizing:border-box}}
html,body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"]{{
  max-width:100%;
  min-width:0;
}}
[data-testid="stMainBlockContainer"] > div,
[data-testid="stVerticalBlock"],
[data-testid="stElementContainer"],
[data-testid="stMarkdownContainer"]{{
  min-width:0;
  max-width:100%;
}}
.wn2-hero,.wn2-health,.wn2-card,.wn2-team,.wn2-mid,
.wn3-hero,.wn3-health,.wn3-teamhead,.wn3-player,.wn3-metrics,.wn3-team,
.wn4-hero,.wn4-chips,.wn4-strip,.wn4-grid,.wn4-games,.wn4-panel,.wn4-decision,
.wn4-metric,.wn4-game{{
  min-width:0 !important;
  max-width:100% !important;
}}
.wn2-name,.wn2-code,.wn2-venue,
.wn3-name,.wn3-role,.wn3-detail,.wn3-teamname,.wn3-teammeta,
.wn4-title,.wn4-sub,.wn4-pick,.wn4-row,.wn4-row span,.wn4-row b{{
  overflow-wrap:anywhere;
  word-break:normal;
}}
.wn2-logo,.wn3-logo,.wn3-teamlogo,.wn3-headshot,.wn4-headshot{{
  max-width:100%;
}}
div[data-testid="stButton"] button,
button[data-testid^="stBaseButton"]{{
  min-height:{MIN_TOUCH_TARGET_PX}px !important;
  max-width:100%;
  white-space:normal !important;
  overflow-wrap:anywhere;
  line-height:1.2;
}}
div[data-testid="stButton"] button:focus-visible,
button[data-testid^="stBaseButton"]:focus-visible{{
  outline:2px solid currentColor !important;
  outline-offset:2px !important;
}}
@media (max-width:900px){{
  .wn4-strip{{grid-template-columns:repeat(3,minmax(0,1fr)) !important}}
  .wn4-grid{{grid-template-columns:repeat(2,minmax(0,1fr)) !important}}
  .wn4-games{{grid-template-columns:repeat(3,minmax(0,1fr)) !important}}
}}
@media (max-width:760px){{
  [data-testid="stMainBlockContainer"]{{
    padding-left:.72rem !important;
    padding-right:.72rem !important;
  }}
  .wn2-card{{
    grid-template-columns:minmax(0,1fr) !important;
    text-align:center !important;
  }}
  .wn2-team,.wn2-team.home{{
    justify-content:center !important;
    text-align:center !important;
  }}
  .wn2-mid{{min-width:0 !important}}
  .wn3-player{{
    grid-template-columns:52px minmax(0,1fr) !important;
  }}
  .wn3-metrics{{
    grid-column:1/-1 !important;
    grid-template-columns:repeat(5,minmax(0,1fr)) !important;
  }}
  .wn4-hero{{
    grid-template-columns:64px minmax(0,1fr) !important;
  }}
  .wn4-strip{{grid-template-columns:repeat(2,minmax(0,1fr)) !important}}
  .wn4-grid{{grid-template-columns:repeat(2,minmax(0,1fr)) !important}}
  .wn4-games{{grid-template-columns:repeat(2,minmax(0,1fr)) !important}}
}}
@media (max-width:430px){{
  [data-testid="stMainBlockContainer"]{{
    padding-left:.55rem !important;
    padding-right:.55rem !important;
  }}
  .wn3-metrics{{grid-template-columns:repeat(3,minmax(0,1fr)) !important}}
  .wn4-strip,.wn4-grid,.wn4-games{{
    grid-template-columns:minmax(0,1fr) !important;
  }}
  .wn4-row{{
    align-items:flex-start;
    flex-direction:column;
    gap:.15rem !important;
  }}
  .wn4-row b{{text-align:left !important}}
}}
@media (prefers-reduced-motion:reduce){{
  *,*::before,*::after{{
    animation-duration:0.001ms !important;
    animation-iteration-count:1 !important;
    transition-duration:0.001ms !important;
    scroll-behavior:auto !important;
  }}
}}
</style>
"""
    )


def render_step6_route():
    state = navigation.current_state()
    render_responsive_shell(state)
    return performance.render_step5_route()


__all__ = [
    "CERTIFIED_VIEWPORTS",
    "MIN_TOUCH_TARGET_PX",
    "MODEL_VERSION",
    "RESPONSIVE_CONTRACT",
    "render_responsive_shell",
    "render_step6_route",
]
