"""WNBA Rebounds + Assists V5.1 — Step-5 mobile run-control placement repair.

Presentation-only wrapper over V5. The V5 statistical projection and 5,000,000-
draw correlated Monte Carlo engine are unchanged.

Root cause repaired:
V5 rendered its native Monte Carlo button *above the entire player card*. On
mobile the player card contains Steps 1-5 and is very tall, so a user who reaches
the Step-5 pending panel sees "5M MONTE CARLO NOT RUN YET" but no nearby run
button. The button existed; it was simply far above the visible Step-5 section.

V5.1 keeps the original control and additionally places a second, equivalent
native Streamlit control immediately below the player card / Step-5 panel. Both
controls write to the same V5 simulation-state key and call the exact same
``run_standard`` engine. No projection, variance, correlation, market-line,
probability, fair-odds or convergence formula changes.
"""
from __future__ import annotations

import numpy as np
import streamlit as st

import wnba_ra_hub_v5 as prior

v3 = prior.v3
model = prior.model

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V5.1 • STEP-5 MOBILE RUN-CONTROL REPAIR"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _player_token(row) -> str:
    return str(
        row.get("ESPN_PLAYER_ID")
        or row.get("PLAYER_ID")
        or row.get("PLAYER_NAME")
        or "player"
    )


def _render_bottom_mc_control(day_str, row, markets):
    """Render the same V5 5M action directly underneath the long player card."""
    try:
        _logs, _ctx, projection = prior._projection_payload(day_str, row)
    except Exception as exc:
        projection = {"state": "ERROR", "error": type(exc).__name__}

    try:
        line_info = v3._line_basis(row, markets)
        line = _num(line_info.get("line"), np.nan)
    except Exception:
        line = np.nan

    sim_key = prior._sim_key(day_str, row, line)
    sim_result = st.session_state.get(sim_key)
    complete = isinstance(sim_result, dict) and str(sim_result.get("state") or "").upper() == "COMPLETE"
    ready = str((projection or {}).get("state") or "").upper() == "READY"
    can_run = bool(ready and np.isfinite(line))

    st.markdown("#### 🎲 Step 5 • Run the 5M R+A Monte Carlo")
    st.caption("Mobile placement repair • this control is intentionally directly below the Step-5 card. It calls the exact same V5 simulation engine.")

    if complete:
        conv = "PASS" if bool(sim_result.get("converged")) else "FAIL"
        sims = int(sim_result.get("sims", 0) or 0)
        st.success(f"✅ {sims:,} simulations already complete • convergence {conv}. The Step-5 card above now contains the results.")
        return

    if not ready:
        state = str((projection or {}).get("state") or "CHECK")
        st.warning(f"Step-5 projection is not simulation-ready: {state}.")
    elif not np.isfinite(line):
        st.warning("Step-5 projection is ready, but there is no verified exact R+A line to simulate.")
    else:
        st.info(
            f"Ready • projected {prior._fmt(projection.get('proj_ra'))} R+A • "
            f"exact market line {float(line):.1f}."
        )

    run = st.button(
        "▶️ Run 5,000,000 R+A Monte Carlo",
        use_container_width=True,
        disabled=not can_run,
        key=f"wnba_ra_v51_run_bottom::{day_str}::{_player_token(row)}",
    )
    if run:
        with st.spinner("🎲 Running 5,000,000 correlated R+A simulations…"):
            result = model.run_standard(day_str, row, float(line), projection)
            st.session_state[sim_key] = result
        # Rerun so the already-rendered Step-5 HTML above is immediately replaced
        # by the completed probability/convergence result rather than staying stale.
        st.rerun()


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    original_player_card = v3._player_card
    original_step5_block = prior._step5_block

    def _step5_with_mobile_hint(day_str, row, markets, projection, sim_result):
        html = original_step5_block(day_str, row, markets, projection, sim_result)
        return html.replace(
            "Use the Step-5 run control above the player card to execute the exact-line 5,000,000-draw simulation.",
            "Use the Run 5,000,000 R+A Monte Carlo control directly below this card to execute the exact-line simulation.",
        )

    def _player_card_then_control(day_str, row, markets, market_meta):
        out = original_player_card(day_str, row, markets, market_meta)
        _render_bottom_mc_control(day_str, row, markets)
        return out

    # V5 patches Step 3 only for the duration of its own player-card render. We
    # patch only the card boundary and Step-5 pending copy, then restore both.
    v3._player_card = _player_card_then_control
    prior._step5_block = _step5_with_mobile_hint
    try:
        return prior.render_wnba_ra_hub(section_header, status_info, team_logo, h)
    finally:
        v3._player_card = original_player_card
        prior._step5_block = original_step5_block


def __getattr__(name):
    return getattr(prior, name)


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]
