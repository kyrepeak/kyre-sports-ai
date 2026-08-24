"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The live frozen shell still imports this historical filename. This shim now
forwards that boundary to V1.9.8.4.27, preserving the Top-5 Step 2–11 card stack.

V1.9.8.4.27 keeps the Step-8 percentage-point display repair, Step-9 final-render
repair, Step-10 rest/schedule audit and Step-11 market/game-script audit. It only
repairs Step-11 negative grade labels so true blowout risk is distinguished from
a low-scoring market environment.

No Points formulas, Monte Carlo distribution, calibration, sportsbook prop
transport, readiness, sanity quarantine or Top-5 ranking are changed. PRA,
Rebounds, Assists, MLB and NFL continue using their existing modules.
"""
from __future__ import annotations

import wnba_points_hub_v198427 as presentation

base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.27 • STEP 11 CONTEXT-AWARE SCRIPT LABELS VIA HOT-RELOAD-SAFE ROUTE"
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
