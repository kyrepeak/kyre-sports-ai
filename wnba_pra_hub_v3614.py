"""WNBA PRA V3.6.14 — clean production presentation.

Step 2 presentation wrapper over the frozen V3.6.13 API-owned PRA route.
The WNBA API ownership/provider boundary and all model/market/Monte Carlo math
remain frozen.  This wrapper changes only what the user sees.
"""
from __future__ import annotations

import wnba_pra_hub_v3613 as previous
import wnba_pra_page_cleanup_v1 as cleanup


MODEL_VERSION = "PRA V3.6.14 • PAGE CLEANUP"
MLB_FROZEN_BASELINE = previous.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = previous.MLB_FROZEN_BRANCH
STEP5_FROZEN_BASELINE = previous.STEP5_FROZEN_BASELINE
PRECISION_STEP1_CONTRACT = previous.PRECISION_STEP1_CONTRACT
PAGE_CLEANUP_CONTRACT = cleanup.CLEANUP_CONTRACT


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Preserve the exact Step-1 API ownership and frozen card renderer setup.
    previous.api_market.install()
    previous.frozen.step5_failsafe.begin_render()
    previous.opportunity.begin_render()

    # Presentation-only patch is deliberately last so API ownership stays the
    # provider owner while user-facing labels/panels are cleaned.
    cleanup.begin_render()
    with cleanup.presentation_scope():
        return previous.frozen.base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(previous, name)


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "STEP5_FROZEN_BASELINE",
    "PRECISION_STEP1_CONTRACT",
    "PAGE_CLEANUP_CONTRACT",
    "render_wnba_pra_hub",
]
