"""Frozen WNBA PRA V3.2.1 route preserved before V3.3 integrity upgrade."""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v311 as core
import wnba_pra_final_v32 as final
import wnba_pra_persist_v321 as persist

MODEL_VERSION = "PRA V3.2.1"
MLB_FROZEN_BASELINE = core.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = core.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "💾 PRA V3.2.1 • Step 9 + reload-safe Monte Carlo persistence ACTIVE • "
        "PRA production connector live • SportsGameOdds WNBA • MLB V2.1.7 frozen"
    )
    result = core.render_wnba_pra_hub(section_header, status_info, team_logo, h)
    day = st.session_state.get("wnba_pra_v2_date")
    if not day:
        st.caption("💾 Select a WNBA slate date. Completed Step-8 summaries will be protected automatically.")
        return result
    if persist.restore_if_missing(day):
        st.toast("💾 Restored completed WNBA Monte Carlo snapshot — no 5M rerun required.")
        st.rerun()
    persist.persist_if_ready(day)
    persist.render_persistence_status(day)
    final.render_final_decision(day)
    return result


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
