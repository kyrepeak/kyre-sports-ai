"""Compatibility route for the frozen PRA V3.6.12 import boundary.

The preserved application imports this historical module name. It now forwards
that presentation boundary to V3.6.17, the Kyre Sports API-only WNBA PRA market
routing successor. Production projection/probability/selection math remains
frozen and Universal Runtime V5 is unchanged.
"""
from __future__ import annotations

import wnba_pra_hub_v3617 as active
import wnba_pra_api_market_bridge_upcoming_only_r1 as _upcoming_only
import wnba_pra_page1_final_polish_v1 as _page1_final_polish

# Install the pregame-only schedule gate after the active hub imports its frozen
# Kyre Sports API market bridge. The existing bridge module object is patched in
# place, so all active consumers share the same upcoming-games-only contract.
_upcoming_only.install()

active.render_page_snapshot = _page1_final_polish.render_page_snapshot

# V3 preserves the V2 S-tier layout while making the upstream upcoming-game gate
# authoritative for the bottom Certified PRA Pick section as well.
import wnba_pra_page1_ultra_stier_v3 as _page1_ultra_stier_v3
active.render_page_snapshot = _page1_ultra_stier_v3.render_page_snapshot

import wnba_pra_hub_v3618 as refresh_handoff

MODEL_VERSION = active.MODEL_VERSION
MLB_FROZEN_BASELINE = active.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = active.MLB_FROZEN_BRANCH
STEP5_FROZEN_BASELINE = active.STEP5_FROZEN_BASELINE
PRECISION_STEP1_CONTRACT = active.PRECISION_STEP1_CONTRACT


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return refresh_handoff.render_wnba_pra_hub(section_header, status_info, team_logo, h)


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
