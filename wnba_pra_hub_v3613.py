"""WNBA PRA V3.6.13 — Precision Step 1 inside V2.8 Top-5 player cards.

Additive presentation layer over the frozen V3.6.12 checkpoint. Production PRA
projection, market, Monte Carlo, qualification and ranking behavior remains on
the frozen V3.6.11/V3.6.2/V3.6.1 stack.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v3611 as frozen
import wnba_pra_opportunity_v3613 as opportunity


MODEL_VERSION = "PRA V3.6.13 • PRECISION STEP 1 • CARD-INTEGRATED OPPORTUNITY"
MLB_FROZEN_BASELINE = frozen.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = frozen.MLB_FROZEN_BRANCH

STEP5_FROZEN_BASELINE = {
    "behavior_version": "PRA V3.6.11",
    "production_route_commit": "b13c376583ab846fc55fec33595fe75463420d89",
    "v3611_hub_blob": "0d3c6883888a7613835cf44f2fb670364e2b9e20",
    "scope": "Step-5 presentation baseline + card-integrated opportunity audit",
    "model_math_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
    "monte_carlo_changed": False,
}

PRECISION_STEP1_CONTRACT = {
    "name": "Opportunity Decomposition",
    "placement": "inside each V2.8 Top-5 player card after Projection Path",
    "read_only": True,
    "new_provider": False,
    "projection_input_changed": False,
    "sportsbook_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
}


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # V3.6.11 owns the frozen fail-safe Top-5 renderer and deliberately restores
    # it each render. Let it restore first. Then patch only the renderer's stable
    # Projection-Path subcomponent so Step 1 lives inside every card and cannot
    # alter the selection/ranking/identity/defense/H2H renderer chain.
    frozen.step5_failsafe.begin_render()
    opportunity.begin_render()

    st.caption(
        "🔬 PRA UI V3.6.13 • Step 1 Opportunity Decomposition is embedded inside "
        "each V2.8 Top-5 player card • V3.6.12 production checkpoint preserved • "
        "model/market/MC/ranking unchanged"
    )
    return frozen.base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(frozen, name)


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "STEP5_FROZEN_BASELINE",
    "PRECISION_STEP1_CONTRACT",
    "render_wnba_pra_hub",
]
