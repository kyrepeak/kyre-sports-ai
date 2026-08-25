"""WNBA PRA V3.6.13 — Precision Step 1 Opportunity Decomposition.

Additive presentation layer over the frozen V3.6.12 checkpoint. The production
PRA stack remains V3.6.11/V3.6.2/V3.6.1. This version installs one read-only hook
under the existing V2.8 Minutes + Role Top-5 so opportunity inputs can be audited
without changing any model or market output.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v3611 as frozen
import wnba_pra_opportunity_v3613 as opportunity

MODEL_VERSION = "PRA V3.6.13 • PRECISION STEP 1 • OPPORTUNITY DECOMPOSITION"
MLB_FROZEN_BASELINE = frozen.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = frozen.MLB_FROZEN_BRANCH

STEP5_FROZEN_BASELINE = {
    "behavior_version": "PRA V3.6.11",
    "production_route_commit": "b13c376583ab846fc55fec33595fe75463420d89",
    "v3611_hub_blob": "0d3c6883888a7613835cf44f2fb670364e2b9e20",
    "scope": "Step-5 presentation baseline + additive opportunity audit",
    "model_math_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
    "monte_carlo_changed": False,
}

PRECISION_STEP1_CONTRACT = {
    "name": "Opportunity Decomposition",
    "read_only": True,
    "new_provider": False,
    "projection_input_changed": False,
    "sportsbook_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
}


def _bind_precision_top5_aliases():
    """Mirror the active wrapper onto every alias used by the Step-5 stack."""
    fs = frozen.step5_failsafe
    wrapped = fs.v28._render_top5

    # The Step-5 presentation stack carries the same renderer through several
    # module aliases. V3.6.11 resets all of them together, so the precision hook
    # must be mirrored to the same aliases after it is installed.
    fs.cards._render_top5 = wrapped
    fs.cards.v28._render_top5 = wrapped
    fs.defense_layer.cards._render_top5 = wrapped
    fs.defense_layer.cards.v28._render_top5 = wrapped

    # Keep the direct V2.8 module binding explicit as the source of truth.
    fs.v28._render_top5 = wrapped


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # V3.6.11 intentionally reinstalls its fail-safe renderer at the start of
    # every Streamlit render. Run that exact baseline setup first, then attach
    # the read-only Step-1 wrapper so the baseline cannot overwrite our hook.
    frozen.step5_failsafe.begin_render()
    opportunity.install()
    _bind_precision_top5_aliases()

    st.caption(
        "🔬 PRA UI V3.6.13 • Precision Step 1 Opportunity Decomposition ACTIVE • "
        "V3.6.12 production checkpoint preserved • model/market/MC/ranking unchanged"
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
