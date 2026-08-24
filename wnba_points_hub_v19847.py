"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The live frozen shell still imports this historical filename. This shim now
forwards that boundary to V1.9.8.4.28, preserving the Top-5 Step 2–12 card stack.

V1.9.8.4.28 keeps every prior Points repair through Step 11 and adds Step 12 — a
final evidence synthesis that summarizes weighted agreement + verified coverage
across Steps 2–11. It does not create a second probability model and cannot
change the protected projection, Monte Carlo probability, calibration, sportsbook
line, pick side or Top-5 ordering.

No Points formulas, Monte Carlo distribution, calibration, sportsbook prop
transport, readiness, sanity quarantine or Top-5 ranking are changed. PRA,
Rebounds, Assists, MLB and NFL continue using their existing modules.
"""
from __future__ import annotations

import wnba_points_hub_v198428 as presentation

base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.28 • STEP 12 FINAL EVIDENCE SYNTHESIS VIA HOT-RELOAD-SAFE ROUTE"
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
