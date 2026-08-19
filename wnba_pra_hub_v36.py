"""WNBA PRA V3.6 — strengthened Step 7 matchup/pace calibration.

Preserves V3.5.3 empirical variance repair, V3.5.2 visual Preliminary PRA cards,
V3.5.1 lineup-aware targeted 5M/10M finalization + strict 10M Final Ready gate,
V3.4.1 Eastern-date slate reconciliation, and V3.3 injury/minutes/role integrity.

V3.6 changes only the Step-7 matchup multipliers:
- team-relative pace instead of slate-relative pace;
- team offense vs opponent defense efficiency blend;
- low-sample context shrinkage toward neutral;
- PTS/REB/AST remain separate;
- rebound matchup adjustment no longer uses an unsupported positive defense
  multiplier without a verified missed-shot/rebound-opportunity feed.

Final Decision Step 1 also installs a read-only Points connection-status strip.
That connector only inspects an already-completed same-day Points V1.9 session
payload. It cannot run/restore Points, request sportsbook data, alter PRA, or add
Points selections to the Daily Master Card. Rebounds remains paused/untouched.

Sportsbook price never changes the projection. Rebounds and MLB are untouched.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v353 as base
import wnba_pra_matchup_v36 as step7
import wnba_final_points_connector_v1 as points_final_connector

MODEL_VERSION = "PRA V3.6 • STEP 7 MATCHUP CALIBRATION • V3.5.3 STACK PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Install before V3.3/V3.5 integrity preflight so basketball fingerprints,
    # Step 7 grading and the downstream 5M/10M Monte Carlo all see the same
    # calibrated matchup-adjusted P/R/A means.
    step7.install()

    # Presentation-only Step-1 connector. It replaces only the hard-coded Final
    # Decision connector strip. PRA selection/model functions remain untouched.
    points_final_connector.install()

    st.caption(
        "🧭 PRA V3.6 • Step-7 matchup calibration ACTIVE • team-relative pace + offense/defense efficiency blend • "
        "quality shrinkage • V3.5.3 injury/variance/visual/5M/10M/finalization protections preserved • Rebounds untouched"
    )
    st.caption(
        "🔌 Final Decision Step 1 • Points read-only connection check ACTIVE • Points is NOT feeding the Daily Master Card yet • "
        "no Points simulation/restore/sportsbook request is triggered here"
    )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
