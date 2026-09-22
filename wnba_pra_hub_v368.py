"""WNBA PRA V3.6.8 — Step-5 projection path presentation wrapper.

Preserves the PRA V3.6.2/V3.6.1 production model, Step-5 identity reliability,
opponent defensive context, matchup history and the existing Step-9 Final Top-5
identity presentation. Adds only an explanatory Step-5 projection path made from
already-existing V2.8 fields.

No projection, availability, minutes/usage math, sportsbook, qualification,
Monte Carlo, final-ready, ranking or selection logic is changed.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v362 as base
import wnba_pra_step5_path_v368 as step5_path

MODEL_VERSION = "PRA V3.6.8 • STEP-5 PROJECTION PATH • MODEL PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    step5_path.begin_render()
    st.caption(
        "🧭 PRA UI V3.6.8 • Step-5 projection path ACTIVE • existing V2.8 fields only • "
        "no synthetic intermediate PRA/probability • presentation only • model/ranking unchanged"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
