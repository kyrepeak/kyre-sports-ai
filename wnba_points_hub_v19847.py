"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The frozen shell still imports this historical filename. This shim now forwards
that boundary to V1.9.8.4.32.

V1.9.8.4.32 preserves the completed Top-5 Step 2–12 card stack and single
protected 5M control, then fixes the actual display gate: the Top-5 audit cards
no longer disappear just because exact sportsbook Points pairs are unavailable.
When markets are pending, the cards use a verified projection-only PRE-MARKET
preview with no fabricated line/odds/edge. When exact markets exist, the original
market-backed candidate order takes over unchanged.

The Points-only SportsGameOdds request is also hardened to verify that a 200
response actually contains player Points odds before accepting it, while the
actual 5M readiness contract remains fail-closed. Exact same-player + same-book +
same-line O/U pairs, matched projections, empirical history, positional checks,
sanity checks and all inherited production gates are still required to simulate.

No Points projection formulas, minutes, matchup factors, Monte Carlo distribution,
calibration, no-vig math, sanity quarantine or production ranking are changed.
PRA, Rebounds, Assists, Spread, MLB and NFL remain untouched.
"""
from __future__ import annotations

import wnba_points_hub_v198432 as presentation

base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.32 • PRE-MARKET TOP-5 CARD HANDOFF REPAIR VIA HOT-RELOAD-SAFE ROUTE"
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
