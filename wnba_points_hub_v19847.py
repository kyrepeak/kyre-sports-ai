"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The live frozen shell still imports this historical filename. This shim now
forwards that boundary to V1.9.8.4.21, preserving the Top-5 Step 2–8 card stack
while repairing the underlying Points-only usage identity handoff.

V1.9.8.4.21 fixes the cross-provider identity mismatch at the role boundary:
ESPN player-pool IDs and preferred WNBA/NBA Stats usage IDs are not assumed to
share a namespace. The isolated Points role facade now uses exact ID first,
normalized full name second, and the existing date-scoped verified ESPN usage
fallback only for fields still missing for that player. Provenance is carried
in USG_SOURCE and Step 8 displays it.

Only the WNBA Points module's role reference is replaced. PRA, Rebounds,
Assists, MLB and NFL continue using their existing modules unchanged. The
existing Points role formulas, Monte Carlo distribution, calibration,
sportsbook transport, readiness, sanity quarantine and ranking rules are not
reweighted or replaced; this is a provider-identity/data-handoff correction.
"""
from __future__ import annotations

import wnba_points_hub_v198421 as presentation

base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.21 • POINTS-ONLY USAGE IDENTITY BRIDGE VIA HOT-RELOAD-SAFE ROUTE"
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
