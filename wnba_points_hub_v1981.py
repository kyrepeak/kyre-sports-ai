"""WNBA Points V1.9.8.1 — forced deployment-route wrapper.

This tiny wrapper gives Streamlit a new import path so the V1.9.8.1 opponent-name
and usage display handoff cannot remain hidden behind an already-loaded V1.9.8
module in a long-lived app process. It delegates directly to the updated
`wnba_points_hub_v198` implementation.

No projection, SportsGameOdds, Monte Carlo, calibration, persistence, H2H, PRA,
or MLB math is changed. Existing protected 5M/10M summaries are reused.
"""
from __future__ import annotations

import wnba_points_hub_v198 as prior

MODEL_VERSION = prior.MODEL_VERSION
PRA_FROZEN_BRANCH = prior.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = prior.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = prior.MLB_FROZEN_BRANCH


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "render_wnba_points_hub",
]
