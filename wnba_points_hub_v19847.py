"""WNBA Points V1.9.8.4.7 — hot-reload-safe Top-5 H2H route shim.

This is a routing/compatibility wrapper over V1.9.8.4.6. It exists because the
frozen Streamlit shell intentionally aliases historical WNBA Points module names
between reruns. A long-lived Streamlit process can therefore leave an old wrapper
object behind under a base-module name and break the V1.9.8.4.x import chain on
the next deploy.

V1.9.8.4.7 does not change Points projections, SportsGameOdds transport,
5M/10M Monte Carlo, calibration, candidate hierarchy, persistence, readiness,
H2H calculations, PRA, Rebounds, Assists, MLB or NFL math. It delegates the
V1.9.8.4.6 Top-5 player-vs-team history presentation and exposes the genuine
V1.9.8.4.5 runtime surface for compatibility with the frozen shell.
"""
from __future__ import annotations

import wnba_points_hub_v19846 as presentation

# V1.9.8.4.6 binds `prior` to the genuine V1.9.8.4.5 module before app.py installs
# any historical aliases. Keep that object as the compatibility source of truth.
base = presentation.prior

MODEL_VERSION = "WNBA POINTS V1.9.8.4.7 • HOT-RELOAD-SAFE H2H ROUTE"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

# Re-export the runtime objects the frozen V1.9.8.4.1/V1.9.8.4.5 compatibility
# boundary has historically exposed. This keeps aliases transparent.
v171 = base.v171
ui = base.ui
points = base.points


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return presentation.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    """Transparent fallback to presentation first, then the genuine base module."""
    try:
        return getattr(presentation, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
