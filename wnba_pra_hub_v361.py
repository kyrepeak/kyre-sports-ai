"""WNBA PRA V3.6.1 — Step-6 performance-only wrapper.

Preserves the complete PRA V3.6 basketball model, V3.5.3 empirical variance
repair, Step-7 calibration, injury/lineup integrity, exact SportsGameOdds grading,
and 5M/10M Monte Carlo rules.

V3.6.1 changes execution efficiency only: repeated Step-5 game projections and
per-player variance calculations are reused inside the same Streamlit render.
The cache is reset every rerun, while the sportsbook market refresh path remains
unchanged.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v36 as base
import wnba_pra_perf_v361 as perf

MODEL_VERSION = "PRA V3.6.1 • STEP-6 SPEED CACHE • V3.6 MATH PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    perf.begin_render()

    st.caption(
        "⚡ PRA V3.6.1 • Step-6 speed cache ACTIVE • same-render Step-5 game projections + "
        "per-player empirical variance reused • SportsGameOdds refresh unchanged • "
        "projection/no-vig/edge/EV/qualification/5M/10M math unchanged"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
