"""WNBA PRA V3.6.9 — compact Step-5 card layout wrapper.

Preserves the PRA V3.6.2/V3.6.1 production model, Step-5 identity reliability,
cached opponent defensive context, matchup history, V3.6.8 existing-field
projection path and the existing Step-9 Final Top-5 identity presentation.
V3.6.9 changes only the Step-5 HTML layout for scanability on tablet/mobile.

No projection, availability, minutes/usage math, data-provider, sportsbook,
qualification, Monte Carlo, final-ready, ranking or selection logic is changed.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v362 as base
import wnba_pra_step5_layout_v369 as step5_layout

MODEL_VERSION = "PRA V3.6.9 • STEP-5 COMPACT LAYOUT • MODEL PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    step5_layout.begin_render()
    st.caption(
        "📱 PRA UI V3.6.9 • Step-5 compact layout ACTIVE • same V2.8 metrics/data • "
        "no new calls or math • presentation only • model/ranking unchanged"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
