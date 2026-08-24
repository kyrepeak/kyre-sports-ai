"""WNBA Points V1.9.8.4.7 — hot-reload-safe compatibility shim.

The live frozen shell still imports this historical filename. This shim now
forwards that boundary to V1.9.8.4.14, which keeps the same Top-5 Step 2
Player-vs-Team History, Step 3 Minutes + Role + Usage, Step 4 Recent Scoring
Form, Step 5 Opponent Defense + Positional Matchup and Step 6 Pace + Game
Scoring Environment cards, with both the pace-baseline display separation and
the Markdown-safe HTML rendering repair.

No Points projection, SportsGameOdds transport, 5M/10M Monte Carlo,
calibration, candidate hierarchy, persistence, readiness, sanity quarantine,
PRA, Rebounds, Assists, MLB or NFL model math is changed.
"""
from __future__ import annotations

import wnba_points_hub_v198414 as presentation

# V1.9.8.4.14 exposes the genuine V1.9.8.4.5 production runtime object.
base = presentation.base

MODEL_VERSION = "WNBA POINTS V1.9.8.4.14 • STEP 6 HTML RENDER REPAIR VIA HOT-RELOAD-SAFE ROUTE"
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
