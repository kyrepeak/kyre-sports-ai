"""WNBA Points V1.9.2 — uncertainty-calibrated decision layer + status fix.

Projection and Monte Carlo math remain V1.9. This wrapper adds a conservative
post-simulation calibration guard for ranking/decision purposes only:
  conservative P(over) = raw MC P(over) - max(1.96*MC_SE, 0.5*max_batch_diff)
  conservative edge    = conservative P(over) - same-book no-vig P(over)

This is deliberately NOT described as historical frequency calibration. A true
Platt/isotonic calibration requires archived out-of-sample pregame projections,
closing lines and realized outcomes. Until that archive exists, the model keeps
raw MC probability visible and uses a transparent uncertainty floor to prevent
borderline simulation noise from being promoted.

Also replaces stale post-run UI prompts with dynamic 5M/10M completion status.
Frozen WNBA PRA V3.2.1 and MLB V2.1.7 remain untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v191 as clean
import wnba_points_hub_v19 as v19

MODEL_VERSION = "WNBA POINTS V1.9.2 • UNCERTAINTY CALIBRATED"
PRA_FROZEN_BRANCH = clean.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = clean.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = clean.MLB_FROZEN_BRANCH


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _current_day():
    value = st.session_state.get("wnba_points_date") or st.session_state.get("wnba_points_date_control")
    if value is None:
        return None
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return None


def _stability_buffer(row) -> float:
    """Conservative probability haircut from simulation uncertainty/stability."""
    se = max(0.0, _num(row.get("mc_se"), 0.0))
    batch = max(0.0, _num(row.get("max_batch_diff"), 0.0))
    return float(np.clip(max(1.96 * se, 0.50 * batch), 0.0, 0.05))


def _calibrated_values(row):
    raw_p = float(np.clip(_num(row.get("model_over"), 0.5), 0.0, 1.0))
    buffer = _stability_buffer(row)
    floor_p = float(np.clip(raw_p - buffer, 0.0, 1.0))
    nv = _num(row.get("no_vig_over"), np.nan)
    cedge = floor_p - nv if pd.notna(nv) else np.nan
    return raw_p, buffer, floor_p, cedge


def _calibrated_decision_tier(row):
    fresh = str(row.get("freshness") or "").upper()
    role = str(row.get("role_label") or "").upper()
    converged = bool(row.get("converged"))
    lineup = bool(row.get("lineup_ready"))
    data_q = _num(row.get("data_quality"), 0.0)
    pass_source = str(row.get("pass_source") or "5M").upper()
    raw_p, _, floor_p, cedge = _calibrated_values(row)

    if fresh == "STALE" or role == "OUT" or not converged or pd.isna(cedge):
        return "⛔ AVOID"

    # The calibrated gate is intentionally at least as strict as the production
    # raw gate. Borderline rows can fall out; calibration never promotes a row.
    calibrated_qualified = bool(
        bool(row.get("model_qualified"))
        and floor_p >= 0.55
        and cedge >= 0.030
        and _num(row.get("proj_min"), 0.0) >= 10.0
    )
    if not calibrated_qualified:
        return "⛔ AVOID"
    if not lineup:
        return "⚠️ MONITOR"
    if pass_source == "10M" and floor_p >= 0.60 and cedge >= 0.080 and data_q >= 0.75:
        return "🔥 BEST BET"
    return "✅ STRONG"


# Patch only V1.9's post-simulation hierarchy. Projection/simulation math stays V1.9.
v19._decision_tier = _calibrated_decision_tier


def _completion_state(day):
    if not day:
        return {"rows": pd.DataFrame(), "units": 0, "final_units": 0, "has_5m": False, "has_10m": False}
    try:
        rows = v19.points.combined_rows(day)
    except Exception:
        rows = pd.DataFrame()
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return {"rows": pd.DataFrame(), "units": 0, "final_units": 0, "has_5m": False, "has_10m": False}
    work = rows.copy()
    sims = pd.to_numeric(work.get("sims"), errors="coerce").fillna(0)
    work["_sims_num"] = sims
    key_cols = [c for c in ("game_id", "player_key", "line") if c in work.columns]
    if len(key_cols) == 3:
        units = work.sort_values("_sims_num", ascending=False).drop_duplicates(key_cols, keep="first")
    else:
        units = work.copy()
    final_units = int((pd.to_numeric(units.get("_sims_num"), errors="coerce").fillna(0) >= 10_000_000).sum())
    total_units = int(len(units))
    has_5m = bool(total_units > 0 and (pd.to_numeric(units.get("_sims_num"), errors="coerce").fillna(0) >= 5_000_000).all())
    has_10m = bool(final_units > 0)
    return {"rows": rows, "units": total_units, "final_units": final_units, "has_5m": has_5m, "has_10m": has_10m}


def _is_old_run_prompt(text: str) -> bool:
    t = str(text or "").upper()
    return (
        "POINTS PREFLIGHT PASSED" in t
        or "PREFLIGHT PASSED. RUN THE 5M PASS" in t
        or "RUN THE 5,000,000 STANDARD SIMULATION ONCE" in t
    )


def _replacement_prompt(day):
    state = _completion_state(day)
    if state["has_10m"]:
        return (
            f"✅ 5M STANDARD PASS COMPLETE • 🎯 10M FINALIST PASS COMPLETE • "
            f"{state['units']} unique distributions protected • {state['final_units']} finalist distributions upgraded to 10M."
        )
    if state["has_5m"]:
        return (
            f"✅ 5M STANDARD PASS COMPLETE • {state['units']} unique distributions protected • "
            "10M finalist pass is available for qualified/close-call units only."
        )
    return None


def _render_calibration_audit(day):
    state = _completion_state(day)
    rows = state["rows"]
    if rows.empty:
        return

    work = rows.copy()
    vals = work.apply(_calibrated_values, axis=1, result_type="expand")
    vals.columns = ["raw_p", "stability_buffer", "cal_p_floor", "conservative_edge"]
    for col in vals.columns:
        work[col] = vals[col].values
    work["Decision (cal)"] = work.apply(_calibrated_decision_tier, axis=1)

    key_cols = [c for c in ("game_id", "player_key", "line", "book") if c in work.columns]
    if key_cols:
        work = work.sort_values(["cal_p_floor", "conservative_edge"], ascending=[False, False]).drop_duplicates(key_cols, keep="first")

    st.markdown("### 🎛️ Probability Calibration & Run Status")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("5M standard", "COMPLETE" if state["has_5m"] else "WAITING")
    c2.metric("10M finalists", f"{state['final_units']} COMPLETE" if state["has_10m"] else "WAITING")
    c3.metric("Unique distributions", state["units"])
    max_buf = float(pd.to_numeric(work["stability_buffer"], errors="coerce").fillna(0).max()) if len(work) else 0.0
    c4.metric("Max stability buffer", f"{max_buf*100:.2f} pp")

    if state["has_10m"]:
        st.success("✅ SIMULATION CALIBRATION STATUS CURRENT • 5M base + selective 10M finalist results are active; stale run prompts are suppressed.")
    else:
        st.info("5M results are active. The selective 10M finalist pass has not completed yet.")

    candidates = work[work["Decision (cal)"].isin(["🔥 BEST BET", "✅ STRONG", "⚠️ MONITOR"])].copy()
    if not candidates.empty:
        candidates = candidates.sort_values(["cal_p_floor", "conservative_edge"], ascending=[False, False]).head(8)
        candidates["Raw MC"] = (candidates["raw_p"] * 100).round(1).astype(str) + "%"
        candidates["Buffer"] = (candidates["stability_buffer"] * 100).round(2).astype(str) + " pp"
        candidates["Cal floor"] = (candidates["cal_p_floor"] * 100).round(1).astype(str) + "%"
        candidates["No-vig"] = (pd.to_numeric(candidates.get("no_vig_over"), errors="coerce") * 100).round(1).astype(str) + "%"
        candidates["Cal edge"] = (candidates["conservative_edge"] * 100).round(1).map(lambda x: f"{x:+.1f} pp")
        candidates["Pass"] = candidates.get("pass_source", "").astype(str)
        candidates["Player"] = candidates.get("player", "").astype(str)
        candidates["Book"] = candidates.get("book", "").astype(str)
        candidates["Line"] = pd.to_numeric(candidates.get("line"), errors="coerce")
        st.dataframe(
            candidates[["Decision (cal)", "Player", "Book", "Line", "Raw MC", "Buffer", "Cal floor", "No-vig", "Cal edge", "Pass"]],
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "Calibration rule: conservative P(over) = raw Monte Carlo P(over) − max(1.96×MC SE, ½×max batch spread). "
        "This is an uncertainty/stability calibration guard, not historical frequency calibration. A future out-of-sample calibrator will require archived pregame projections + closing lines + final outcomes."
    )


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    original_success = st.success
    original_info = st.info

    def _success_dynamic(body, *args, **kwargs):
        if _is_old_run_prompt(body):
            replacement = _replacement_prompt(_current_day())
            if replacement:
                return original_success(replacement, *args, **kwargs)
        return original_success(body, *args, **kwargs)

    def _info_dynamic(body, *args, **kwargs):
        if _is_old_run_prompt(body):
            replacement = _replacement_prompt(_current_day())
            if replacement:
                return original_success(replacement)
        return original_info(body, *args, **kwargs)

    st.success = _success_dynamic
    st.info = _info_dynamic
    try:
        result = clean.render_wnba_points_hub(section_header, status_info, team_logo, h)
    finally:
        st.success = original_success
        st.info = original_info

    day = _current_day()
    if day:
        _render_calibration_audit(day)
    return result


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT",
    "MLB_FROZEN_BRANCH", "render_wnba_points_hub",
]
