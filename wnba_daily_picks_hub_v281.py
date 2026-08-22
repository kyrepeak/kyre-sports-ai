"""WNBA Daily Picks V28.1 — Spread controller module-chain repair.

Preserves Daily Picks V28 and every source-model calculation. This wrapper repairs
only the Step-7 controller's native Spread Step-5 module traversal.

V28 incorrectly treated `wnba_spread_hub_v161.base` as the V1.5 module. In the
actual source chain V1.6.1.base is V1.6, while V1.6's own local `base` is
V1.5 (via V1.5.2). Therefore `V1.6.1.base.prior` does not exist and raised the
observed AttributeError before any simulation began.

The repaired chain exactly mirrors the working Spread V1.6 renderer:
V1.6.1 -> V1.6 -> V1.5.2 -> V1.5 -> V1.4._render_step5.
No projection, probability, Monte Carlo, grading, connector, ranking, threshold,
or simulation-count logic is changed.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v28 as base
import wnba_spread_hub_v161 as spread_v161

MODEL_VERSION = "WNBA DAILY PICKS V28.1 • STEP 7 SPREAD MODULE-CHAIN REPAIR"


def _build_native_step6(day_str: str):
    """Build the current Spread Steps 1-6 using the exact native module ownership."""
    foundation = spread_v161.foundation
    clock = spread_v161.clock
    ui = spread_v161.ui

    # Native ownership trace:
    # spread_v161.base = wnba_spread_hub_v16
    # spread_v161.step6_ui = wnba_spread_hub_v151
    # spread_v161.step6_ui.base = wnba_spread_hub_v15
    # spread_v161.step6_ui.base.prior = wnba_spread_hub_v14
    step6_ui = spread_v161.step6_ui
    spread_v15 = step6_ui.base
    step5_owner = spread_v15.prior

    now_et = pd.Timestamp.now(tz=spread_v161.ET)
    schedule = foundation._schedule(day_str)
    if not isinstance(schedule, pd.DataFrame):
        schedule = pd.DataFrame()

    pregame = clock._pregame_schedule(schedule, now_et=now_et) if not schedule.empty else pd.DataFrame()
    if not isinstance(pregame, pd.DataFrame):
        pregame = pd.DataFrame()

    if pregame.empty:
        return pd.DataFrame(), {
            "ready": False,
            "reason": "No clock-safe pregame Spread games remain for the current ET slate.",
            "games": 0,
        }

    try:
        contexts, cdiag = foundation.context.slate_context(day_str)
    except Exception as exc:
        contexts, cdiag = {}, {"state": "CHECK", "reason": type(exc).__name__}
    contexts = contexts if isinstance(contexts, dict) else {}
    cdiag = cdiag if isinstance(cdiag, dict) else {}
    context_state = str(cdiag.get("state") or "CHECK").upper()

    try:
        av = foundation._availability_snapshot(day_str, pregame)
    except Exception as exc:
        av = pd.DataFrame()
        availability_reason = type(exc).__name__
    else:
        availability_reason = ""
    if not isinstance(av, pd.DataFrame):
        av = pd.DataFrame()

    covered = int(
        pd.to_numeric(av.get("covered_teams", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    ) if not av.empty else 0
    expected_coverage = int(2 * len(pregame))
    unverified = int(
        pd.to_numeric(av.get("unverified", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    ) if not av.empty else 0
    availability_ready = bool(expected_coverage > 0 and covered == expected_coverage and unverified == 0)
    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)

    # Execute the source-owned Step-4/5/6 functions inside a disposable container.
    # The functions and their math are untouched; only the controller's reference
    # to the Step-5 owner is corrected.
    slot = st.empty()
    try:
        with slot.container():
            ready_lines, step4 = ui._render_step4(day_str, pregame, foundation_ready)
            step4 = dict(step4 or {})
            market_ready = bool(step4.get("market_ready", False))

            projected, step5 = step5_owner._render_step5(
                day_str, pregame, contexts, market_ready
            )
            step5 = dict(step5 or {})
            margin_ready = bool(step5.get("model_ready", False))

            probability_board, step6 = step6_ui._render_step6(
                day_str, pregame, projected, ready_lines, margin_ready
            )
            step6 = dict(step6 or {})
            probability_ready = bool(step6.get("model_ready", False))
    finally:
        slot.empty()

    if not isinstance(probability_board, pd.DataFrame):
        probability_board = pd.DataFrame()

    ready = bool(
        foundation_ready
        and market_ready
        and margin_ready
        and probability_ready
        and not probability_board.empty
    )

    reasons = []
    if context_state != "VERIFIED":
        reasons.append("team context not VERIFIED")
    if not availability_ready:
        reasons.append(
            f"availability {covered}/{expected_coverage} covered teams; {unverified} unverified"
            + (f" ({availability_reason})" if availability_reason else "")
        )
    if not market_ready:
        reasons.append("exact sportsbook spread Step 4 not READY")
    if not margin_ready:
        reasons.append("independent projected margin Step 5 not READY")
    if not probability_ready:
        reasons.append("cover probability/fair spread Step 6 not READY")
    if probability_board.empty:
        reasons.append("Step-6 probability board is empty")

    return probability_board, {
        "ready": ready,
        "reason": "; ".join(reasons),
        "games": int(len(pregame)),
        "context_state": context_state,
        "availability_ready": availability_ready,
        "market_ready": market_ready,
        "margin_ready": margin_ready,
        "probability_ready": probability_ready,
    }


# V28's _run_spread_standard_5m resolves this symbol from its own module globals.
# Rebinding the helper repairs only the broken traversal while retaining all V28
# execution, persistence, convergence and UI behavior.
base._build_native_step6 = _build_native_step6


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🛠️ Daily Picks V28.1 • Spread Step-5 module-chain repair ACTIVE")
    return base.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub", "_build_native_step6"]
