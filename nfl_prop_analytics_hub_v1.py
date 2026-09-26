"""NFL Prop Analytics V1 — route owner with lazy Page 2/Page 3 imports.

The route foundation stays lightweight so a fresh Streamlit interpreter can
always enter NFL -> Prop Analytics. Heavy roster, availability, player, and
Page 3 modules are imported only when their page is actually opened.

No truth engine, eligibility rule, projection behavior, market behavior,
Passing Yards owner, or frozen data module is changed here.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from nfl_prop_analytics_schedule_v1 import render_schedule_truth_layer
from nfl_prop_analytics_game_select_v1 import render_game_selection_handoff
from nfl_prop_analytics_matchup_shell_v1 import (
    is_matchup_page,
    render_matchup_open_control,
    render_matchup_shell,
)

MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 1 ROUTE OWNERSHIP"
PROP_ANALYTICS_VERSION = "v1"
MARKET = "Prop Analytics"
STEP = 1
PAGE = 1
ROUTE_ONLY = True
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

PAGE_QUERY_KEY = "ks_pa_page"
PROP_PAGE_QUERY_VALUE = "props"


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key, "")
    except Exception:
        return ""
    if isinstance(raw, list):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _prop_page_requested() -> bool:
    return _query_value(PAGE_QUERY_KEY) == PROP_PAGE_QUERY_VALUE


# Lazy wrappers preserve the hub's public API while keeping fresh-route import
# ownership lightweight. The underlying modules and functions remain frozen.

def render_verified_roster_truth(*args, **kwargs):
    from nfl_prop_analytics_roster_truth_v1 import render_verified_roster_truth as impl
    return impl(*args, **kwargs)


def load_verified_roster_truth(*args, **kwargs):
    from nfl_prop_analytics_roster_truth_v1 import load_verified_roster_truth as impl
    return impl(*args, **kwargs)


def render_availability_depth_truth(*args, **kwargs):
    from nfl_prop_analytics_availability_depth_v1 import render_availability_depth_truth as impl
    return impl(*args, **kwargs)


def load_availability_depth_truth(*args, **kwargs):
    from nfl_prop_analytics_availability_depth_v1 import load_availability_depth_truth as impl
    return impl(*args, **kwargs)


def render_unified_roster_availability(*args, **kwargs):
    from nfl_prop_analytics_page2_unified_roster_v1 import render_unified_roster_availability as impl
    return impl(*args, **kwargs)


def render_player_selection_handoff(*args, **kwargs):
    from nfl_prop_analytics_player_select_v1 import render_player_selection_handoff as impl
    return impl(*args, **kwargs)


def render_tap_player_handoff(*args, **kwargs):
    from nfl_prop_analytics_page2_tap_player_v1 import render_tap_player_handoff as impl
    return impl(*args, **kwargs)


def render_page2_responsive_polish(*args, **kwargs):
    from nfl_prop_analytics_page2_responsive_polish_v1 import render_page2_responsive_polish as impl
    return impl(*args, **kwargs)


def is_prop_page() -> bool:
    if not _prop_page_requested():
        return False
    from nfl_prop_analytics_prop_page_v1 import is_prop_page as impl
    return bool(impl())


def render_prop_page_open_control(*args, **kwargs):
    from nfl_prop_analytics_prop_page_v1 import render_prop_page_open_control as impl
    return impl(*args, **kwargs)


def render_prop_page_shell(*args, **kwargs):
    from nfl_prop_analytics_prop_page_v1 import render_prop_page_shell as impl
    return impl(*args, **kwargs)


def render_prop_analytics_page() -> None:
    st.markdown(
        """
<section class="ks-prop-analytics-v1"
         data-nfl-prop-analytics-route="v1"
         data-prop-analytics-owner="nfl_prop_analytics_hub_v1"
         data-prop-analytics-step="1"
         data-prop-analytics-page="1">
  <div class="ks-pa1-eyebrow">NFL • PROP ANALYTICS</div>
  <h1 class="ks-pa1-title">Prop Analytics</h1>
  <p class="ks-pa1-copy">
    Verified game context, roster truth, availability, and player navigation.
  </p>
  <div class="ks-pa1-state" role="status">
    <span>Page 1</span>
    <span>Route + ownership certified foundation</span>
  </div>
</section>
<style data-nfl-prop-analytics-step1-css="v1">
.ks-prop-analytics-v1{
  width:100%;
  max-width:100%;
  min-width:0;
  overflow-x:clip;
  margin:8px 0 18px;
  padding:clamp(18px,3vw,30px);
  border:1px solid rgba(125,211,252,.22);
  border-radius:18px;
  background:
    radial-gradient(circle at 92% 8%,rgba(14,165,233,.12),transparent 18rem),
    linear-gradient(145deg,rgba(7,14,24,.98),rgba(10,22,38,.96));
}
.ks-pa1-eyebrow{color:#7dd3fc;font-size:.72rem;font-weight:900;letter-spacing:.16em}
.ks-pa1-title{margin:.35rem 0 .45rem;color:#f8fafc;font-size:clamp(1.8rem,5vw,3rem);line-height:1;letter-spacing:-.04em}
.ks-pa1-copy{max-width:720px;margin:0;color:#a9bad0;font-size:.92rem;line-height:1.55}
.ks-pa1-state{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
.ks-pa1-state span{min-height:40px;display:inline-flex;align-items:center;padding:8px 12px;border:1px solid rgba(125,211,252,.18);border-radius:999px;color:#dbeafe;background:rgba(14,165,233,.06);font-size:.74rem;font-weight:800}
@media(max-width:520px){
  .ks-prop-analytics-v1{padding:16px 14px;border-radius:15px}
  .ks-pa1-state{display:grid;grid-template-columns:1fr}
  .ks-pa1-state span{width:100%}
}
</style>
""",
        unsafe_allow_html=True,
    )

    # Avoid importing the heavy Page 3 graph unless Page 3 was requested.
    if _prop_page_requested():
        render_prop_page_shell()
        return

    # Matchup shell is intentionally rendered before any Page 2 heavy imports.
    # This keeps Page 2 identity/navigation available even if a downstream
    # truth provider must fail closed.
    if is_matchup_page():
        handoff = render_matchup_shell()
        if handoff:
            render_page2_responsive_polish()
            roster_truth = load_verified_roster_truth(handoff)
            if roster_truth and roster_truth.get("state") == "live":
                availability_truth = load_availability_depth_truth(handoff, roster_truth)
                if availability_truth and availability_truth.get("state") == "live":
                    render_unified_roster_availability(
                        handoff,
                        roster_truth,
                        availability_truth,
                    )
                    player_handoff = render_tap_player_handoff(
                        handoff,
                        availability_truth,
                    )
                    render_prop_page_open_control(player_handoff)
        return

    render_schedule_truth_layer()
    handoff = render_game_selection_handoff()
    render_matchup_open_control(handoff)


def render_nfl_hub(market: str = MARKET) -> None:
    if str(market or "").strip() != MARKET:
        raise ValueError("NFL Prop Analytics V1 only renders Prop Analytics.")
    return render_prop_analytics_page()


__all__ = [
    "MARKET",
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "PROP_ANALYTICS_VERSION",
    "ROUTE_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP",
    "is_prop_page",
    "render_nfl_hub",
    "render_game_selection_handoff",
    "render_matchup_open_control",
    "render_matchup_shell",
    "render_verified_roster_truth",
    "render_availability_depth_truth",
    "render_unified_roster_availability",
    "render_player_selection_handoff",
    "render_tap_player_handoff",
    "render_page2_responsive_polish",
    "render_prop_page_open_control",
    "render_prop_page_shell",
    "render_schedule_truth_layer",
    "render_prop_analytics_page",
]
