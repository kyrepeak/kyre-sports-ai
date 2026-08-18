"""WNBA V3.3 — PRA + Points production route with unified Master Card.

WNBA-only. MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.
Keeps the proven PRA Steps 1-8 + reload-safe persistence, adds the independent
Points V1.0 production connector, and replaces the PRA-only Step-9 card with a
multi-market WNBA Daily Master Card.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v311 as core
import wnba_pra_persist_v321 as pra_persist
import wnba_points_v10 as points
import wnba_master_card_v33 as master

MODEL_VERSION = "WNBA V3.3 • PRA + POINTS"
MLB_FROZEN_BASELINE = core.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = core.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🏀 WNBA V3.3 • PRA + Points production connectors • unified Daily Master Card • "
        "SportsGameOdds WNBA • MLB V2.1.7 frozen"
    )

    # Render the proven WNBA Steps 1-8 shell and PRA Monte Carlo first.
    result = core.render_wnba_pra_hub(section_header, status_info, team_logo, h)
    day = st.session_state.get("wnba_pra_v2_date")
    if not day:
        st.caption("🏀 Select a WNBA slate date to arm PRA + Points production connectors.")
        return result

    # Restore/protect PRA summaries exactly as V3.2.1 did, without rendering the
    # old PRA-only card. One rerun lets the Step-8 panel above display restored rows.
    if pra_persist.restore_if_missing(day):
        st.toast("💾 Restored completed PRA Monte Carlo snapshot — no 5M rerun required.")
        st.rerun()
    pra_persist.persist_if_ready(day)
    pra_persist.render_persistence_status(day)

    # Independent Points connector. It owns its own exact Points market pairing,
    # empirical scoring variance, 5M/10M simulation and persistence contract.
    points.render_points_connector(day)

    # One slate-wide card for every completed WNBA production connector.
    master.render_master_card(day)
    return result


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "render_wnba_pra_hub",
]
