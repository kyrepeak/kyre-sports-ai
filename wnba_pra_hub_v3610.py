"""WNBA PRA V3.6.10 — Step-5 presentation performance repair wrapper.

Preserves the PRA V3.6.2/V3.6.1 production model, Step-5 identity reliability,
cached opponent defense, matchup history, existing-field projection path, compact
V3.6.9 layout and the existing Step-9 Final Top-5 identity presentation.

V3.6.10 removes one redundant presentation-side Step-6 projection-frame rebuild
used only to recover headshot IDs. Step-5/slate IDs are reused directly instead.
No projection, availability, minutes/usage math, sportsbook, qualification,
Monte Carlo, final-ready, ranking, selection or provider/cache TTL logic changes.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v362 as base
import wnba_pra_step5_perf_v3610 as step5_perf

MODEL_VERSION = "PRA V3.6.10 • STEP-5 PERFORMANCE REPAIR • MODEL PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    step5_perf.begin_render()
    st.caption(
        "⚡ PRA UI V3.6.10 • Step-5 performance repair ACTIVE • identity reuses existing Step-5/slate IDs • "
        "no duplicate Step-6 identity projection rebuild • model/ranking unchanged"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
