"""WNBA PRA production route wrapper.

The historical V3.2.1 implementation remains preserved in
wnba_pra_hub_v321_frozen.py and the frozen branch. Main now routes PRA to V3.3,
which keeps the V3.2.1 projection/Monte Carlo/market formulas while repairing
injury, roster, projected-minute and persistence integrity.
"""
from __future__ import annotations

import wnba_pra_hub_v33 as _impl

MODEL_VERSION = getattr(_impl, "MODEL_VERSION", "PRA V3.3 • AVAILABILITY + PROJECTION INTEGRITY")
MLB_FROZEN_BASELINE = _impl.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = _impl.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _impl.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(_impl, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
