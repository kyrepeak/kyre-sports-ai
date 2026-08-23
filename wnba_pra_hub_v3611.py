"""WNBA PRA V3.6.11 — Step-5 presentation fail-safe firewall wrapper.

Preserves the PRA V3.6.2/V3.6.1 production model, V3.6.10 Step-5 performance
repair, compact layout, identity, cached opponent defense, matchup history,
existing-field projection path and the existing Step-9 Final Top-5 presentation.

V3.6.11 adds only final exception isolation around OPTIONAL Step-5 display
enrichment. Missing/broken headshot, logo, defense, H2H or path presentation can
no longer prevent the already-computed Step-5 Top-5 from rendering.

No projection, availability, minutes/usage math, sportsbook, qualification,
Monte Carlo, final-ready, ranking, selection, provider, cache or TTL logic changes.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v362 as base
import wnba_pra_step5_failsafe_v3611 as step5_failsafe

MODEL_VERSION = "PRA V3.6.11 • STEP-5 FAIL-SAFE FIREWALL • MODEL PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    step5_failsafe.begin_render()
    st.caption(
        "🛡️ PRA UI V3.6.11 • Step-5 fail-safe firewall ACTIVE • optional display layers fail independently • "
        "core Top-5 model output preserved • model/ranking unchanged"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
