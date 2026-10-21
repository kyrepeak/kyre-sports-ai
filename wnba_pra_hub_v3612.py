"""Compatibility route for the frozen PRA V3.6.12 import boundary.

The preserved application imports this historical module name. It now forwards
that presentation boundary to V3.6.17, the Kyre Sports API-only WNBA PRA market
routing successor. Production projection/probability/selection math remains
frozen and Universal Runtime V5 is unchanged.
"""
from __future__ import annotations

import wnba_pra_hub_v3617 as active
import wnba_pra_page1_final_polish_v1 as _page1_final_polish

active.render_page_snapshot = _page1_final_polish.render_page_snapshot

MODEL_VERSION = active.MODEL_VERSION
MLB_FROZEN_BASELINE = active.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = active.MLB_FROZEN_BRANCH
STEP5_FROZEN_BASELINE = active.STEP5_FROZEN_BASELINE
PRECISION_STEP1_CONTRACT = active.PRECISION_STEP1_CONTRACT


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return active.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(active, name)


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "STEP5_FROZEN_BASELINE",
    "PRECISION_STEP1_CONTRACT",
    "render_wnba_pra_hub",
]
