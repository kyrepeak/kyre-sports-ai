"""WNBA Points V1.9.8.4.23 — Step 9 late-install render-chain repair.

Builds on V1.9.8.4.22. The Step-9 code/data layer was loading, but the card did
not render because the nested historical render chain later invoked
wnba_points_hub_v198418._install(), which reset the shared V1.9.8.4.16
_step7_block seam back to Step 7 + Step 8 after V1.9.8.4.22 had already attached
Step 9.

This wrapper fixes installer order only. It patches the V1.9.8.4.18 installer so
that every time that late historical installer runs, it first performs its
original Step-8 setup and then re-attaches the V1.9.8.4.22 Step-7+8+9 combiner.
That places Step 9 at the actual final render boundary used by the Top-5 cards.

No model math, projection, Monte Carlo, calibration, sportsbook transport,
usage, injuries, ranking, or Step-9 grading logic is changed.
"""
from __future__ import annotations

import streamlit as st

import wnba_points_hub_v198422 as prior
import wnba_points_hub_v198418 as step8mod

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points
v416 = prior.v416

MODEL_VERSION = "WNBA POINTS V1.9.8.4.23 • STEP 9 LATE-INSTALL RENDER REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

# Capture the genuine Step-8 installer once. Streamlit reruns must not wrap an
# already wrapped installer or the call chain can recurse/grow indefinitely.
_BASE_STEP8_INSTALL = getattr(
    step8mod,
    "_kyre_v198423_base_install",
    step8mod._install,
)
setattr(step8mod, "_kyre_v198423_base_install", _BASE_STEP8_INSTALL)


def _step8_install_then_step9() -> None:
    """Run the historical Step-8 install, then restore the Step-9 card seam."""
    _BASE_STEP8_INSTALL()
    v416._step7_block = prior._step7_plus_step8_plus_step9


def _install() -> None:
    # Patch the late installer BEFORE entering V1.9.8.4.22's nested render chain.
    # V1.9.8.4.22/V1.9.8.4.21 can then run all of their normal setup safely;
    # when V1.9.8.4.18 installs later, this wrapper reasserts Step 9 last.
    step8mod._install = _step8_install_then_step9
    prior._install()
    # Also assert the seam here for direct calls/tests that do not traverse the
    # full historical render chain.
    v416._step7_block = prior._step7_plus_step8_plus_step9


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🧷 Points V1.9.8.4.23 • Step 9 late-install render repair ACTIVE • "
        "Step 7 → Step 8 → Step 9 preserved inside each Top-5 card • model/ranking unchanged"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
