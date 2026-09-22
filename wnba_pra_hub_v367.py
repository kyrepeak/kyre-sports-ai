"""WNBA PRA V3.6.7 — Step-5 matchup history presentation wrapper.

Preserves the PRA V3.6.2/V3.6.1 production model, V3.6.5 Step-5 identity
reliability, V3.6.6 opponent defensive context and the existing Step-9 Final
Top-5 identity presentation. Adds only cached current-season matchup history to
the V2.8 Minutes + Role Top-5 cards.

No projection, availability, minutes/usage, sportsbook, qualification,
Monte Carlo, final-ready, ranking or selection logic is changed.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v362 as base
import wnba_pra_step5_history_v367 as step5_history

MODEL_VERSION = "PRA V3.6.7 • STEP-5 MATCHUP HISTORY • MODEL PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    step5_history.begin_render()
    st.caption(
        "📚 PRA UI V3.6.7 • Step-5 matchup history ACTIVE • cached ESPN game summaries • "
        "current-season/current-team scope • presentation only • PRA model/ranking unchanged"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
