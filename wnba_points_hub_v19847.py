"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The live frozen shell still imports this historical filename. This shim now
forwards that boundary to V1.9.8.4.8, which preserves the V1.9.8.4.6 Top-5 H2H
evidence and adds Step 3 Minutes + Role + Usage for the same five candidates.

No Points projection, SportsGameOdds transport, 5M/10M Monte Carlo,
calibration, candidate hierarchy, persistence, readiness, sanity quarantine,
PRA, Rebounds, Assists, MLB or NFL model math is changed.
"""
from __future__ import annotations

import wnba_points_hub_v19848 as presentation

# V1.9.8.4.8 exposes the genuine V1.9.8.4.5 production runtime object.
base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.8 • STEP 3 VIA HOT-RELOAD-SAFE ROUTE"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

v171 = base.v171
ui = base.ui
points = base.points


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return presentation.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(presentation, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
