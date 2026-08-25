"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The frozen shell still imports this historical filename. This shim now forwards
that boundary to V1.9.8.4.31.

V1.9.8.4.31 preserves the V1.9.8.4.30 cards-first page, completed Top-5 Step
2–12 evidence stack and single authoritative 5M control, then repairs the actual
upstream failure that left those cards empty: the isolated Points SportsGameOdds
request no longer forces subscription-restricted bookmaker IDs at the provider
boundary. Returned odds are filtered locally to the same configured books and
must still form exact same-player + same-book + same-line Over/Under pairs.

The actual 5M readiness contract remains fail-closed. Exact sportsbook pairs,
matched projections, empirical history, positional verification, sanity checks
and all inherited production gates are still required before simulation.

No Points projection formulas, minutes, matchup factors, Monte Carlo distribution,
calibration, no-vig math, sanity quarantine, ranking or Top-5 ordering are changed.
PRA, Rebounds, Assists, Spread, MLB and NFL remain untouched.
"""
from __future__ import annotations

import wnba_points_hub_v198431 as presentation

base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.31 • EXACT MARKET HANDOFF REPAIR VIA HOT-RELOAD-SAFE ROUTE"
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
