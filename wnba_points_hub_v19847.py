"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The live frozen shell still imports this historical filename. This shim now
forwards that boundary to V1.9.8.4.24, preserving the Top-5 Step 2–9 card stack.

V1.9.8.4.24 keeps the V1.9.8.4.23 late-install Step-9 render repair and also
fixes Step 8's RECENT USAGE DELTA presentation so a percentage-point difference
is not multiplied by 100 a second time. Example: Season 21.3% vs L5 21.5% now
renders approximately +0.2 pp rather than an inflated double-scaled percentage.

No Points formulas, opportunity grading, Monte Carlo distribution, calibration,
sportsbook transport, readiness, sanity quarantine or Top-5 ranking are changed.
PRA, Rebounds, Assists, MLB and NFL continue using their existing modules.
"""
from __future__ import annotations

import wnba_points_hub_v198424 as presentation

base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.24 • STEP 8 USAGE DELTA + STEP 9 RENDER REPAIRS VIA HOT-RELOAD-SAFE ROUTE"
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
