"""WNBA PRA V3.6.5 — Step-5 normalized headshot reliability wrapper.

Preserves PRA V3.6.2/V3.6.1 production behavior and the existing Step-9 Final
Top-5 identity presentation. Adds the V3.6.5 display-only Step-5 verified ESPN ID
fallback under the exact renderer normalization key.

No projection, availability, minutes/usage, matchup, sportsbook, qualification,
Monte Carlo, final-ready or ranking logic is changed.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v362 as base
import wnba_pra_step5_identity_v365 as step5_identity

MODEL_VERSION = "PRA V3.6.5 • STEP-5 NORMALIZED HEADSHOT RELIABILITY • MODEL PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    step5_identity.begin_render()
    st.caption(
        "🖼️ PRA UI V3.6.5 • Step-5 normalized headshot fallback ACTIVE • "
        "verified ESPN identity • presentation only • PRA model/ranking unchanged"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
