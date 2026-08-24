"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The live frozen shell still imports this historical filename. This shim now
forwards that boundary to V1.9.8.4.22, preserving the Top-5 Step 2–8 card stack
and adding Step 9 Opponent Shot-Profile Defense + Scoring Method Matchup.

V1.9.8.4.22 keeps the V1.9.8.4.21 Points-only provider-safe usage identity
bridge, then adds an audit-only comparison between each Top-5 player's verified
recent 3PA/FTA/efficiency profile and the opponent's verified season/L10
shooting profile allowed from ESPN WNBA final box scores before the slate date.
Rim/midrange location defense is not inferred when the connected verified feed
does not expose it.

No new Step-9 multiplier is fed into the protected Points projection. Existing
Points formulas, Monte Carlo distribution, calibration, sportsbook transport,
readiness, sanity quarantine and Top-5 ranking remain unchanged. PRA, Rebounds,
Assists, MLB and NFL continue using their existing modules.
"""
from __future__ import annotations

import wnba_points_hub_v198422 as presentation

base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.22 • STEP 9 SHOT-PROFILE DEFENSE AUDIT VIA HOT-RELOAD-SAFE ROUTE"
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
