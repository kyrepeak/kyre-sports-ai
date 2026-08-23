"""WNBA PRA V3.6.12 — frozen Step-5 presentation production baseline.

This wrapper freezes the verified V3.6.11 PRA stack as the safe production
baseline before any later PRA changes. It delegates rendering unchanged to
V3.6.11 and adds no calculation, provider call, cache, patch, renderer, model
feature or selection behavior.

Frozen Step-5 stack:
- V3.6.5 normalized player headshot reliability
- V3.6.6 cached opponent defensive context
- V3.6.7 current-season matchup history
- V3.6.8 existing-field projection path
- V3.6.9 compact tablet/mobile layout
- V3.6.10 presentation performance repair
- V3.6.11 optional-enrichment fail-safe firewall

Underlying production model remains the preserved V3.6.2/V3.6.1 stack.
No projection, availability, minutes/usage math, sportsbook, qualification,
Monte Carlo, final-ready, ranking, selection, provider or cache-TTL logic changes.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v3611 as frozen

MODEL_VERSION = "PRA V3.6.12 • STEP-5 PRESENTATION BASELINE FROZEN • MODEL PRESERVED"
MLB_FROZEN_BASELINE = frozen.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = frozen.MLB_FROZEN_BRANCH

# Audit anchors for the exact baseline we intentionally froze.
STEP5_FROZEN_BASELINE = {
    "behavior_version": "PRA V3.6.11",
    "production_route_commit": "b13c376583ab846fc55fec33595fe75463420d89",
    "v3611_hub_blob": "0d3c6883888a7613835cf44f2fb670364e2b9e20",
    "scope": "Step-5 presentation only",
    "model_math_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
    "monte_carlo_changed": False,
}


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🔒 PRA UI V3.6.12 • Step-5 presentation baseline FROZEN • verified V3.6.11 behavior • "
        "future PRA work should branch after this checkpoint • model/ranking unchanged"
    )
    return frozen.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(frozen, name)


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "STEP5_FROZEN_BASELINE",
    "render_wnba_pra_hub",
]
