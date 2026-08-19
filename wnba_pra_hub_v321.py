"""WNBA PRA production route wrapper.

The historical V3.2.1 implementation remains preserved in
wnba_pra_hub_v321_frozen.py and the frozen branch. Main now routes PRA to
V3.5.2, which preserves the V3.5.1 Eastern-date slate, multi-source availability,
lineup-aware targeted 5M/10M finalization and strict 10M Final Ready gate, while
adding presentation-only player/headshot/team-logo cards to the Preliminary PRA
Over Board. Rebounds and MLB are untouched.
"""
from __future__ import annotations

import wnba_pra_hub_v352 as _impl

MODEL_VERSION = getattr(_impl, "MODEL_VERSION", "PRA V3.5.2 • VISUAL PRELIMINARY PRA BOARD")
MLB_FROZEN_BASELINE = _impl.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = _impl.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _impl.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(_impl, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
