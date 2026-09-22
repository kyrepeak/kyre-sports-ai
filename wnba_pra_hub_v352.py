"""WNBA PRA V3.5.2 — visual Step-6 cards on the hardened V3.5.1 model.

Keeps the entire V3.5.1 availability, Eastern-slate, projection, matchup,
SportsGameOdds, 5M/10M Monte Carlo and strict Final Ready chain unchanged. This
wrapper installs only the presentation patch that turns the Preliminary PRA Over
Board into responsive player/headshot/team-logo cards.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v351 as base
import wnba_pra_visual_v352 as visual

MODEL_VERSION = "PRA V3.5.2 • VISUAL PRELIMINARY PRA BOARD • V3.5.1 MODEL PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    visual.install()
    st.caption(
        "🎨 PRA V3.5.2 • visual Preliminary PRA cards ACTIVE • player headshots + verified slate team logos • "
        "V3.5.1 injury/lineup/5M/10M/finalization math unchanged • Rebounds untouched"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
