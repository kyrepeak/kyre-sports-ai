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

Final Decision Step 2 installs the verified Points card-feed connector. When the
same-day Points payload disappeared from Streamlit session state after a deploy,
this route may recover the already-completed persisted Points V1.9 snapshot using
the Points engine's existing restore path. Restore never reruns Monte Carlo or
changes the Points projection; the existing completed 5M/10M distributions are
reused and their sportsbook grading is refreshed against the current exact market
before they are exposed to Final Decision. Rebounds remains paused/untouched.

Sportsbook price never changes the projection. Rebounds and MLB are untouched.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v353 as base
import wnba_pra_matchup_v36 as step7
import wnba_final_points_connector_v2 as points_final_connector
import wnba_points_v19 as points_engine

MODEL_VERSION = "PRA V3.6 • STEP 7 MATCHUP CALIBRATION • V3.5.3 STACK PRESERVED"
MLB_FROZEN_BASELINE = base.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def _restore_points_for_final_decision() -> bool:
    """Recover a completed same-day Points snapshot if session state lost it.

    This deliberately calls the Points engine's existing persistence restore,
    which reuses completed Monte Carlo rows and regrades only the sportsbook
    fields against the current exact market. No simulation is executed here.
    """
    day = st.session_state.get("wnba_pra_v2_date")
    if day is None:
        return False

    try:
        current = points_engine.combined_rows(day)
        if current is not None and not current.empty:
            return False
    except Exception:
        pass

    try:
        restored = bool(points_engine.restore_if_missing(day))
    except Exception as exc:
        # Fail closed. Final Decision will simply show Points NEXT/CHECK rather
        # than inventing or partially reconstructing a production payload.
        st.session_state["_wnba_final_points_restore_error"] = f"{type(exc).__name__}: {exc}"
        return False

    if restored:
        st.session_state.pop("_wnba_final_points_restore_error", None)
        st.session_state["_wnba_final_points_restore_source"] = "persisted same-day Points snapshot"
    return restored


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Install before V3.3/V3.5 integrity preflight so basketball fingerprints,
    # Step 7 grading and the downstream 5M/10M Monte Carlo all see the same
    # calibrated matchup-adjusted P/R/A means.
    step7.install()

    # Recovery bridge for deploy/reboot session loss. This can restore an
    # already-completed Points snapshot but can never launch a new 5M/10M pass.
    restored_points = _restore_points_for_final_decision()

    # Final Decision Step 2. This patches only stored-output read/selection/UI
    # hooks; Points projection math and PRA projection math remain untouched.
    points_final_connector.install()

    st.caption(
        "🧭 PRA V3.6 • Step-7 matchup calibration ACTIVE • team-relative pace + offense/defense efficiency blend • "
        "quality shrinkage • V3.5.3 injury/variance/visual/5M/10M/finalization protections preserved • Rebounds untouched"
    )
    if restored_points:
        st.caption(
            "💾 Final Decision recovery • completed same-day Points snapshot restored • existing 5M/10M simulations reused • "
            "current sportsbook grading refreshed • zero Monte Carlo rerun"
        )
    else:
        st.caption(
            "🔌 Final Decision Step 2 • verified Points card feed ACTIVE • completed same-day Points rows may compete only if already model-qualified • "
            "no Points Monte Carlo is launched here • Rebounds still NEXT"
        )
    return base.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
