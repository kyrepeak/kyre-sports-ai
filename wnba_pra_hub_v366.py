"""WNBA PRA V3.6.6 — Step-5 opponent defensive context wrapper.

Preserves the PRA V3.6.2/V3.6.1 production model, V3.6.5 Step-5 identity
reliability and the existing Step-9 Final Top-5 identity presentation. Adds only
cached opponent defensive context to the V2.8 Minutes + Role Top-5 cards.

No projection, availability, minutes/usage, sportsbook, qualification,
Monte Carlo, final-ready, ranking or selection logic is changed.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v362 as base
import wnba_pra_step5_defense_v366 as step5_defense

MODEL_VERSION = "PRA V3.6.6 • STEP-5 OPPONENT DEFENSE CONTEXT • MODEL PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    step5_defense.begin_render()
    st.caption(
        "🛡️ PRA UI V3.6.6 • Step-5 opponent defensive context ACTIVE • "
        "cached ESPN team context • presentation only • PRA model/ranking unchanged"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
