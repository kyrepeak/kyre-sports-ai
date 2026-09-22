"""WNBA PRA V3.6.3 — Step-5 Top-5 identity presentation wrapper.

Preserves the complete PRA V3.6.2 route, including the V3.6.1 production model
and Step-9 Final Card identity layer. Adds only player headshots plus team and
opponent logos to the inherited V2.8 Minutes + Role PRA Top 5.

No projection, availability, minutes/usage, matchup, sportsbook, qualification,
Monte Carlo, final-ready or ranking logic is changed.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v362 as base
import wnba_pra_step5_identity_v363 as step5_identity

MODEL_VERSION = "PRA V3.6.3 • STEP-5 TOP-5 IDENTITY • V3.6.2 PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    step5_identity.begin_render()
    st.caption(
        "🖼️ PRA UI V3.6.3 • Step 1 V2.8 Minutes + Role Top-5 player headshots + team/opponent logos ACTIVE • "
        "presentation only • PRA model/ranking unchanged"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
