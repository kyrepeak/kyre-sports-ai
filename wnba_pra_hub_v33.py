"""WNBA PRA V3.3 — injury-aware projection integrity production route.

Built from the frozen V3.2.1 basketball model.  Projection formulas, matchup
weights, Monte Carlo counts and market math stay unchanged.  V3.3 repairs the
state plumbing around them: stronger availability precedence, current roster
status fallback, fail-closed provider coverage, downstream OUT/uncertain gates,
and fingerprint-aware 5M/10M persistence.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_pra_hub_v311 as core
import wnba_pra_final_v32 as final
import wnba_pra_integrity_v33 as integrity
import wnba_pra_persist_v33 as persist

MODEL_VERSION = "PRA V3.3 • AVAILABILITY + PROJECTION INTEGRITY"
MLB_FROZEN_BASELINE = core.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = core.MLB_FROZEN_BRANCH


def _day_key(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def _has_valid_mc(day, state):
    obj = st.session_state.get(persist.std_key(day)) or {}
    rows = obj.get("rows")
    meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
    return bool(
        state.get("safe")
        and isinstance(rows, pd.DataFrame) and not rows.empty
        and str(meta.get("basketball_fingerprint") or "") == str(state.get("fingerprint") or "")
    )


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    integrity.install_runtime_guards()
    st.caption(
        "🩺 PRA V3.3 • injury/roster/minutes/role integrity ACTIVE • fingerprint-safe 5M/10M persistence • "
        "SportsGameOdds market math preserved • Rebounds/Points/MLB untouched"
    )

    # Preflight BEFORE Step 8 renders. Any V3.2.1 same-day rows that lack the new
    # basketball-state fingerprint are removed rather than being shown as current.
    pre_day = st.session_state.get("wnba_pra_v2_date")
    pre_state = None
    if pre_day:
        try:
            pre_state = integrity.current_basketball_state(pre_day)
            integrity.invalidate_stale_session(pre_day, pre_state)
        except Exception as exc:
            st.session_state[f"wnba_pra_v33_preflight_error::{_day_key(pre_day)}"] = type(exc).__name__

    # Render the proven Steps 1-8 / actual Monte Carlo engine with V3.3 runtime
    # availability guards installed underneath it.
    result = core.render_wnba_pra_hub(section_header, status_info, team_logo, h)

    day = st.session_state.get("wnba_pra_v2_date")
    if not day:
        st.caption("🩺 Select a WNBA slate date. Availability integrity will be verified before any saved Monte Carlo result can load.")
        return result

    state = integrity.current_basketball_state(day)

    # If basketball state changed while this render was running, never stamp a
    # just-completed simulation with the wrong fingerprint.
    if pre_state and str(pre_state.get("fingerprint")) != str(state.get("fingerprint")):
        if integrity.invalidate_stale_session(day, state):
            st.toast("🩺 PRA basketball state changed during refresh — stale simulations removed.")
            st.rerun()

    # Preflight already removed legacy/stale rows. Any rows now present were
    # generated under this current render/state, so attach the exact fingerprint
    # before persistence evaluates them.
    integrity.attach_fingerprint(day, state)

    # Restore only a V3.3 snapshot whose full basketball fingerprint matches.
    if not _has_valid_mc(day, state) and persist.restore_if_missing(day, state):
        st.toast("💾 Restored fingerprint-matched PRA Monte Carlo snapshot — no unnecessary 5M rerun.")
        st.rerun()

    persist.persist_if_ready(day, state)
    integrity.render_integrity_panel(day, state)
    persist.render_persistence_status(day, state)

    # Final Card is explicitly fail-closed. Diagnostic Steps 1-8 may remain
    # visible during provider trouble, but stale/unverified rows cannot become a
    # production recommendation.
    if _has_valid_mc(day, state):
        final.render_final_decision(day)
    else:
        st.markdown("### 🏁 Step 9 — Final Decision / Daily Master Card")
        if not state.get("safe"):
            st.error("⛔ FINAL CARD LOCKED • live injury/availability verification is incomplete. Recheck availability before using PRA picks.")
        else:
            invalidated = st.session_state.get(f"wnba_pra_v33_invalidated::{_day_key(day)}")
            if invalidated:
                st.warning(f"🔁 FINAL CARD NEEDS A FRESH 5M PASS • {invalidated}.")
            else:
                st.info("Run the 5,000,000 standard PRA simulations after the verified injury/minutes/role check to unlock the Final Card.")

    st.caption(
        "⚡ V3.3 integrity repair • OUT/INACTIVE/DOUBTFUL zeroed before 200 team-minute redistribution • "
        "QUESTIONABLE/DAY-TO-DAY/PROBABLE held from production qualification • same-day injury/minutes/role changes "
        "invalidate old Monte Carlo summaries • V3.2.1 projection/market formulas otherwise preserved."
    )
    return result


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
