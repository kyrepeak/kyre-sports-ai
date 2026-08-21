"""WNBA PRA production route wrapper.

The historical V3.2.1 implementation remains preserved in
wnba_pra_hub_v321_frozen.py and the frozen branch. Main now routes PRA to
V3.6.1, which preserves the full V3.6 / V3.5.3 hardened stack (visual
Preliminary PRA cards, empirical variance repair, lineup-aware targeted 5M/10M
finalization, strict 10M Final Ready gate, Eastern-date slate reconciliation,
current injury/minutes/role integrity, and V3.6 matchup/pace calibration).

V3.6.1 is performance-only: duplicate Step-5 game projections and per-player
variance calculations are reused within a single Streamlit render, then cleared
before the next rerun. SportsGameOdds refresh behavior and every PRA model/grading
formula remain unchanged.

Rebounds and MLB are untouched.
"""
from __future__ import annotations

import wnba_pra_hub_v361 as _impl

MODEL_VERSION = getattr(_impl, "MODEL_VERSION", "PRA V3.6.1 • STEP-6 SPEED CACHE")
MLB_FROZEN_BASELINE = _impl.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = _impl.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _impl.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(_impl, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
