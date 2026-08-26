"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The frozen shell still imports this historical filename. This shim now forwards
that boundary to V1.9.8.4.34.

V1.9.8.4.34 preserves the completed Top-5 Step 2–12 card stack, the pre-market
card repair, and the single protected 5M control. It repairs the current-line
transport by resolving today's WNBA Events first and then re-fetching the exact
SportsGameOdds eventIDs for player Points O/U markets.

For PRE-MARKET display only, it can read the current line from an available
byBookmaker overUnder field or from SportsGameOdds consensus fields. A unique
normalized player-name fallback is allowed only for display if sportsbook and
projection game IDs use different namespaces.

Display-only lines cannot unlock 5M, create sportsbook prices/no-vig/EV, qualify
a pick, or alter production Top-5 ordering. Exact same-player + same-book +
same-line Over/Under pairs and every inherited readiness/integrity gate remain
mandatory for production simulation.

No Points projection formulas, minutes, matchup factors, Monte Carlo distribution,
calibration, no-vig math, sanity quarantine or production ranking are changed.
PRA, Rebounds, Assists, Spread, MLB and NFL remain untouched.
"""
from __future__ import annotations

import wnba_points_hub_v198434 as presentation

base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.34 • TWO-STAGE CURRENT-LINE TRANSPORT REPAIR VIA HOT-RELOAD-SAFE ROUTE"
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
