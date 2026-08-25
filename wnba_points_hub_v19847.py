"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The frozen shell still imports this historical filename. This shim now forwards
that boundary to V1.9.8.4.30.

V1.9.8.4.30 preserves the V1.9.8.4.29 market-aware readiness repair and the
completed Top-5 Step 2–12 evidence stack, then repairs presentation order:
Top-5 Player-vs-Team History cards render first and the one real protected 5M
control renders immediately below them. The inherited later production-widget
call is suppressed so Streamlit never receives a duplicate button key.

The actual 5M readiness contract remains fail-closed. Exact sportsbook pairs,
matched projections, empirical history, positional verification, sanity checks
and all inherited production gates are still required before simulation.

No Points projection formulas, minutes, matchup factors, Monte Carlo distribution,
calibration, sportsbook transport, no-vig math, sanity quarantine, ranking or
Top-5 ordering are changed. PRA, Rebounds, Assists, Spread, MLB and NFL remain
untouched.
"""
from __future__ import annotations

import wnba_points_hub_v198430 as presentation

base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.30 • CARDS FIRST + SINGLE 5M CONTROL VIA HOT-RELOAD-SAFE ROUTE"
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
