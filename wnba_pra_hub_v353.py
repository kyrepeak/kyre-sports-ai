"""WNBA PRA V3.5.3 — empirical variance repair on visual V3.5.2.

Keeps the full V3.5.2 presentation, V3.5.1 lineup-aware finalization, V3.4.1
Eastern slate reconciliation, injury/minutes/role integrity, exact market math and
5M/10M Monte Carlo rules unchanged. Installs only the Step-6 historical-variance
handoff repair so verified ESPN completed-game logs can replace misleading
FALLBACK • 0 GP states when a real >=5-game sample exists.

Rebounds and MLB are untouched.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v352 as base
import wnba_pra_variance_v353 as variance

MODEL_VERSION = "PRA V3.5.3 • EMPIRICAL VARIANCE REPAIR • V3.5.2 VISUALS PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    variance.install()
    st.caption(
        "📊 PRA V3.5.3 • empirical variance repair ACTIVE • verified completed-game history only • "
        "no same-day look-ahead • V3.5.2 visuals + V3.5.1 injury/lineup/5M/10M/finalization preserved • Rebounds untouched"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
