"""WNBA PRA V2.8.4 isolated Step-5 + SportsGameOdds bridge.

WNBA-only patch. MLB production/model files are intentionally untouched.
The frozen MLB baseline is commit 6f439a251329c588a097abc9281f0a528c3053be.

V2.8.4 keeps the hardened V2.8.3 minutes/usage compatibility layer and adds a
read-only SportsGameOdds WNBA market bridge for full-game lines plus Points,
Rebounds, Assists and PRA props. Sportsbook data is verification/transport only
at this step and does not change WNBA projection math yet.
"""
import streamlit as st
import wnba_pra_hub_v28 as v28
import wnba_role_v282 as role282
import wnba_sportsgameodds_v1 as wnba_sgo

MODEL_VERSION = "PRA V2.8.4"
MLB_FROZEN_BASELINE = "6f439a251329c588a097abc9281f0a528c3053be"
MLB_FROZEN_BRANCH = "mlb-v217-frozen-20260818"

_original_role = v28.role
for _helper in ("_num", "_day_str"):
    if not hasattr(role282, _helper) and hasattr(_original_role, _helper):
        setattr(role282, _helper, getattr(_original_role, _helper))

if not hasattr(role282, "availability"):
    role282.availability = _original_role.availability
if not hasattr(role282.availability, "_norm_name") and hasattr(_original_role.availability, "_norm_name"):
    role282.availability._norm_name = _original_role.availability._norm_name

v28.role = role282
v28.MODEL_VERSION = MODEL_VERSION


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🧠 PRA V2.8.4 • WNBA-only development active • SportsGameOdds bridge added • "
        "MLB V2.1.7 baseline frozen and untouched"
    )
    result = v28.render_wnba_pra_hub(section_header, status_info, team_logo, h)

    # The inherited PRA shell owns the selected-date control. Render the market
    # bridge after the shell so we always query the exact WNBA date the user chose.
    day = st.session_state.get("wnba_pra_v2_date")
    if day:
        wnba_sgo.render_market_panel(day)
    else:
        st.caption("🎯 SportsGameOdds WNBA bridge ready — select a WNBA slate date to verify markets.")
    return result


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "render_wnba_pra_hub",
]
