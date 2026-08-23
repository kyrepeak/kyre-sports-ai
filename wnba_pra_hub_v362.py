"""WNBA PRA V3.6.2 — Step 1 Final Top-5 player/team identity wrapper.

Preserves the complete PRA V3.6.1 speed/cache path and all V3.6 basketball,
market, qualification, Monte Carlo, final-ready and ranking logic. Adds only a
presentation patch to the Step-9 Final Card so each displayed Top-5 PRA pick can
show the player headshot and verified team logo.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v361 as base
import wnba_pra_final_visual_v362 as identity

MODEL_VERSION = "PRA V3.6.2 • STEP 1 FINAL TOP-5 IDENTITY • V3.6.1 MODEL PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    identity.begin_render()
    st.caption(
        "🖼️ PRA UI V3.6.2 • Step 1 Final Top-5 player headshots + team logos ACTIVE • "
        "presentation only • PRA projection/qualification/Monte Carlo/ranking unchanged"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
