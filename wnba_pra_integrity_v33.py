"""WNBA PRA V3.3 — upstream basketball-state integrity guard.

This module makes injury/availability changes first-class model state.  It does
not change the proven P/R/A formulas.  Instead it:
- installs the V3.3 availability provider into the existing Step-5/7/8 stack;
- carries verified designation/source fields through the role frame;
- prevents OUT/INACTIVE/DOUBTFUL, uncertain, or unverified players from becoming
  production PRA candidates;
- fingerprints roster/status/minutes/role/matchup/lineup state so stale 5M/10M
  summaries are invalidated whenever basketball inputs change.
"""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np
import pandas as pd
import streamlit as st

import wnba_availability_v33 as availability
import wnba_role_v28 as role28
import wnba_role_v282 as role282
import wnba_pra_matchup_v30 as matchup
import wnba_pra_monte_carlo_v31 as monte31
import wnba_pra_final_v32 as final32

OUT_STATUSES = set(availability.OUT_STATUSES)
UNCERTAIN_STATUSES = set(availability.UNCERTAIN_STATUSES)
UNVERIFIED = "STATUS UNVERIFIED"


def _day(day) -> str:
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value) -> str:
    text = str(value or "").strip().lower()
    return "".join(ch for ch in text if ch.isalnum())


def _merge_availability_v33(pool: pd.DataFrame, av_frame: pd.DataFrame):
    """Keep the proven merge but preserve V3.3 verification metadata."""
    original = getattr(role28, "_v33_original_merge_availability", None)
    if original is None:
        original = role28._merge_availability
    out = original(pool, av_frame)
    if out is None or out.empty:
        return out
    out = out.copy()
    out["AVAILABILITY_VERIFIED"] = False
    out["PROVIDER_COVERED"] = False
    out["STATUS_SOURCE"] = ""
    if av_frame is None or av_frame.empty:
        out["DESIGNATION"] = UNVERIFIED
        return out
    amap = {}
    for _, r in av_frame.iterrows():
        key = (int(r.get("TEAM_ID") or 0), availability._norm_name(r.get("PLAYER_NAME")))
        amap[key] = r
    for idx, p in out.iterrows():
        key = (int(p.get("TEAM_ID") or 0), availability._norm_name(p.get("PLAYER_NAME")))
        r = amap.get(key)
        if r is None:
            out.at[idx, "DESIGNATION"] = UNVERIFIED
            continue
        out.at[idx, "AVAILABILITY_VERIFIED"] = bool(r.get("AVAILABILITY_VERIFIED"))
        out.at[idx, "PROVIDER_COVERED"] = bool(r.get("PROVIDER_COVERED"))
        out.at[idx, "STATUS_SOURCE"] = str(r.get("STATUS_SOURCE") or "")
        # The original merge already copied designation/detail/starter; assign
        # again so V3.3 status precedence cannot be lost to an older binding.
        out.at[idx, "DESIGNATION"] = str(r.get("DESIGNATION") or UNVERIFIED)
        out.at[idx, "DETAIL"] = str(r.get("DETAIL") or "")
        out.at[idx, "STARTER_CONFIRMED"] = bool(r.get("STARTER_CONFIRMED"))
    return out


def install_runtime_guards():
    """Idempotently wire V3.3 availability into every PRA layer."""
    if getattr(role28, "_v33_integrity_installed", False):
        return

    # Step 5 functions resolve the availability module dynamically.
    role28.availability = availability
    role28.OUT_STATUSES = set(OUT_STATUSES)
    role28.UNCERTAIN_STATUSES = set(role28.UNCERTAIN_STATUSES) | {UNVERIFIED}
    if not hasattr(role28, "_v33_original_merge_availability"):
        role28._v33_original_merge_availability = role28._merge_availability
    role28._merge_availability = _merge_availability_v33

    # V2.8.2 exports were bound at import time; repoint the public interfaces.
    role282.availability = availability
    role282.OUT_STATUSES = set(OUT_STATUSES)
    role282.UNCERTAIN_STATUSES = set(role28.UNCERTAIN_STATUSES)
    role282.player_form_table = availability.player_form_table
    role282.slate_player_pool = availability.slate_player_pool
    role282.team_player_pool = availability.team_player_pool
    role282.availability_for_game = availability.availability_for_game
    role282.availability_diagnostics = availability.availability_diagnostics
    role282.schedule_for_date = availability.schedule_for_date

    # Patch Step 7 grading so a stale sportsbook market can never resurrect a
    # player whom the basketball layer says is unavailable or unresolved.
    if not hasattr(matchup, "_v33_original_grade_matchup_pra"):
        matchup._v33_original_grade_matchup_pra = matchup.grade_matchup_pra
    original_grade = matchup._v33_original_grade_matchup_pra

    def safe_grade_matchup_pra(day):
        rows, meta = original_grade(day)
        if rows is None or rows.empty:
            return rows, meta
        return apply_availability_gate_to_rows(day, rows, stage="STEP7"), meta

    matchup.grade_matchup_pra = safe_grade_matchup_pra

    # Step 8 standard/final runs both resolve _market_rows dynamically.
    if not hasattr(monte31, "_v33_original_market_rows"):
        monte31._v33_original_market_rows = monte31._market_rows
    original_market_rows = monte31._v33_original_market_rows

    def safe_market_rows(day, sim_count=monte31.STANDARD_SIMS, progress=None):
        rows, meta = original_market_rows(day, sim_count=sim_count, progress=progress)
        if rows is None or rows.empty:
            return rows, meta
        gated = apply_availability_gate_to_rows(day, rows, stage="STEP8")
        if isinstance(meta, dict):
            meta = dict(meta)
            meta["availability_v33_gate"] = True
        return gated, meta

    monte31._market_rows = safe_market_rows

    # Final decision receives one more independent gate.  This is intentionally
    # redundant: an OUT player must fail even if a future UI refactor bypasses
    # one earlier eligibility flag.
    if not hasattr(final32, "_v33_original_critical_reasons"):
        final32._v33_original_critical_reasons = final32._critical_reasons
    if not hasattr(final32, "_v33_original_monitor_reasons"):
        final32._v33_original_monitor_reasons = final32._monitor_reasons
    original_critical = final32._v33_original_critical_reasons
    original_monitor = final32._v33_original_monitor_reasons

    def critical_reasons_v33(row):
        reasons = list(original_critical(row))
        designation = str(row.get("designation") or row.get("DESIGNATION") or "").upper()
        verified = row.get("availability_verified")
        if designation in OUT_STATUSES and "player status is OUT" not in reasons:
            reasons.append(f"player availability is {designation}")
        if _num(row.get("proj_min"), 0.0) <= 0 and "projected minutes are zero" not in reasons:
            reasons.append("projected minutes are zero")
        if verified is False:
            reasons.append("live availability is not verified")
        return list(dict.fromkeys(reasons))

    def monitor_reasons_v33(row):
        reasons = list(original_monitor(row))
        designation = str(row.get("designation") or row.get("DESIGNATION") or "").upper()
        if designation in UNCERTAIN_STATUSES or designation == UNVERIFIED:
            reasons.append(f"player availability is {designation}")
        return list(dict.fromkeys(reasons))

    final32._critical_reasons = critical_reasons_v33
    final32._monitor_reasons = monitor_reasons_v33
    role28._v33_integrity_installed = True


def _projection_map(day):
    projections, meta = matchup.matchup_projection_frame(day)
    lookup = {}
    if projections is not None and not projections.empty:
        for _, p in projections.iterrows():
            key = (str(p.get("game_id") or ""), str(p.get("player_key") or _norm(p.get("PLAYER_NAME"))))
            lookup[key] = p
    return projections if isinstance(projections, pd.DataFrame) else pd.DataFrame(), meta or {}, lookup


def _availability_gate(proj):
    if proj is None:
        return {
            "designation": UNVERIFIED, "verified": False, "state": "HOLD",
            "reason": "player missing from current verified projection pool",
        }
    designation = str(proj.get("DESIGNATION") or UNVERIFIED).upper()
    verified = bool(proj.get("AVAILABILITY_VERIFIED", designation != UNVERIFIED))
    proj_min = _num(proj.get("PROJ_MIN"), 0.0)
    if designation in OUT_STATUSES or proj_min <= 0:
        return {
            "designation": designation, "verified": verified, "state": "OUT",
            "reason": f"{designation} / projected minutes {proj_min:.1f}",
        }
    if not verified or designation == UNVERIFIED:
        return {
            "designation": designation, "verified": False, "state": "HOLD",
            "reason": "live availability not verified",
        }
    if designation in UNCERTAIN_STATUSES:
        return {
            "designation": designation, "verified": True, "state": "MONITOR",
            "reason": f"{designation} requires status confirmation",
        }
    return {"designation": designation, "verified": True, "state": "ACTIVE", "reason": ""}


def apply_availability_gate_to_rows(day, rows: pd.DataFrame, stage="") -> pd.DataFrame:
    if rows is None or rows.empty:
        return rows
    _projections, _meta, pmap = _projection_map(day)
    out = rows.copy()
    states = []; designations = []; verifieds = []; reasons = []
    for _, r in out.iterrows():
        key = (str(r.get("game_id") or ""), str(r.get("player_key") or _norm(r.get("player"))))
        gate = _availability_gate(pmap.get(key))
        states.append(gate["state"]); designations.append(gate["designation"])
        verifieds.append(bool(gate["verified"])); reasons.append(gate["reason"])
    out["availability_gate"] = states
    out["designation"] = designations
    out["availability_verified"] = verifieds
    out["availability_reason"] = reasons

    hard = out["availability_gate"].isin(["OUT", "HOLD"])
    monitor = out["availability_gate"].eq("MONITOR")
    if "eligible" in out.columns:
        out.loc[hard | monitor, "eligible"] = False
    if "model_qualified" in out.columns:
        out.loc[hard | monitor, "model_qualified"] = False
    if "final_ready" in out.columns:
        out.loc[hard | monitor, "final_ready"] = False
    if "status" in out.columns:
        out.loc[out["availability_gate"].eq("OUT"), "status"] = "AVOID • OUT"
        out.loc[out["availability_gate"].eq("HOLD"), "status"] = "HOLD • AVAILABILITY"
        out.loc[out["availability_gate"].eq("MONITOR"), "status"] = "MONITOR • STATUS"
    return out


def _roundish(value):
    x = _num(value, np.nan)
    return None if not np.isfinite(x) else round(float(x), 4)


def current_basketball_state(day):
    """Build stable digest of every input that can change the PRA distribution."""
    install_runtime_guards()
    day_str = _day(day)
    projections, meta, _lookup = _projection_map(day_str)
    schedule = meta.get("schedule") if isinstance(meta, dict) else pd.DataFrame()
    try:
        diag = availability.availability_diagnostics(day_str)
    except Exception as exc:
        diag = {"state": "CHECK", "reason": type(exc).__name__}

    stats = role282.player_form_table()
    try:
        lineups = monte31._lineup_map(day_str, schedule, stats) if isinstance(schedule, pd.DataFrame) else {}
    except Exception:
        lineups = {}

    player_rows = []
    hard_out = uncertain = unverified = 0
    if projections is not None and not projections.empty:
        sort_cols = [c for c in ["game_id", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME"] if c in projections.columns]
        pframe = projections.sort_values(sort_cols, kind="mergesort") if sort_cols else projections
        for _, p in pframe.iterrows():
            designation = str(p.get("DESIGNATION") or UNVERIFIED).upper()
            verified = bool(p.get("AVAILABILITY_VERIFIED", designation != UNVERIFIED))
            if designation in OUT_STATUSES:
                hard_out += 1
            if designation in UNCERTAIN_STATUSES:
                uncertain += 1
            if not verified or designation == UNVERIFIED:
                unverified += 1
            player_rows.append({
                "game": str(p.get("game_id") or ""),
                "pid": str(p.get("PLAYER_ID") or ""),
                "player": str(p.get("PLAYER_NAME") or ""),
                "team": int(_num(p.get("TEAM_ID"), 0)),
                "designation": designation,
                "verified": verified,
                "starter": bool(p.get("STARTER_CONFIRMED")),
                "min": _roundish(p.get("PROJ_MIN")),
                "usg": _roundish(p.get("PROJ_USG")),
                "pts": _roundish(p.get("PROJ_PTS")),
                "reb": _roundish(p.get("PROJ_REB")),
                "ast": _roundish(p.get("PROJ_AST")),
                "pra": _roundish(p.get("PROJ_PRA")),
                "pace": _roundish(p.get("pace_factor")),
                "def": _roundish(p.get("defense_factor")),
                "ctx": _roundish(p.get("context_quality")),
            })

    schedule_rows = []
    if isinstance(schedule, pd.DataFrame) and not schedule.empty:
        for _, g in schedule.sort_values("game_id", kind="mergesort").iterrows():
            schedule_rows.append({
                "game": str(g.get("game_id") or ""),
                "status": str(g.get("status") or g.get("status_text") or ""),
                "away": int(_num(g.get("away_team_id"), 0)),
                "home": int(_num(g.get("home_team_id"), 0)),
                "lineup_ready": bool(lineups.get(str(g.get("game_id") or ""), False)),
            })

    canonical = {
        "schema": "PRA-V3.3-BASKETBALL-STATE",
        "day": day_str,
        "players": player_rows,
        "schedule": schedule_rows,
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    diag_state = str((diag or {}).get("state") or "CHECK").upper()
    safe = bool(diag_state == "VERIFIED" and unverified == 0 and len(player_rows) > 0)
    return {
        "day": day_str,
        "fingerprint": fingerprint,
        "short_fingerprint": fingerprint[:12],
        "safe": safe,
        "availability_state": diag_state,
        "players": len(player_rows),
        "hard_out": hard_out,
        "uncertain": uncertain,
        "unverified": unverified,
        "covered_teams": int((diag or {}).get("covered_teams") or 0),
        "teams": int((diag or {}).get("teams") or 0),
        "confirmed_starters": int((diag or {}).get("confirmed_starters") or 0),
        "diag": diag,
    }


def _std_key(day):
    return f"wnba_pra_v31_standard::{_day(day)}"


def _final_key(day):
    return f"wnba_pra_v31_final::{_day(day)}"


def invalidate_stale_session(day, state):
    """Drop 5M/10M rows if their upstream basketball fingerprint is missing/stale."""
    std_key, final_key = _std_key(day), _final_key(day)
    stored = st.session_state.get(std_key) or {}
    rows = stored.get("rows")
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return False
    meta = stored.get("meta") if isinstance(stored.get("meta"), dict) else {}
    saved_fp = str(meta.get("basketball_fingerprint") or "")
    current_fp = str((state or {}).get("fingerprint") or "")
    safe = bool((state or {}).get("safe"))
    if safe and saved_fp and saved_fp == current_fp:
        return False

    reason = "availability provider not fully verified" if not safe else (
        "legacy simulation snapshot has no injury/minutes fingerprint" if not saved_fp
        else "roster / injury / minutes / role / matchup / lineup state changed"
    )
    st.session_state.pop(std_key, None)
    st.session_state.pop(final_key, None)
    st.session_state[f"wnba_pra_v33_invalidated::{_day(day)}"] = reason
    return True


def attach_fingerprint(day, state):
    for key in (_std_key(day), _final_key(day)):
        obj = st.session_state.get(key)
        if not isinstance(obj, dict):
            continue
        rows = obj.get("rows")
        if not isinstance(rows, pd.DataFrame) or rows.empty:
            continue
        obj = dict(obj)
        obj["rows"] = apply_availability_gate_to_rows(day, rows, stage="PERSIST")
        meta = dict(obj.get("meta") or {})
        meta["basketball_fingerprint"] = str((state or {}).get("fingerprint") or "")
        meta["availability_state"] = str((state or {}).get("availability_state") or "CHECK")
        meta["pra_v33_integrity"] = True
        obj["meta"] = meta
        st.session_state[key] = obj


def clear_live_input_caches():
    availability.clear_availability_cache()
    for fn in (getattr(role28, "clear_role_cache", None), getattr(role282, "clear_role_cache", None)):
        if callable(fn):
            try:
                fn()
            except Exception:
                pass
    # Context/market caches are deliberately left intact: this button is for
    # injury/minutes/role verification, not odds refresh.


def render_integrity_panel(day, state):
    day_str = _day(day)
    state = state or current_basketball_state(day_str)
    st.markdown("### 🩺 PRA Availability + Projection Integrity")
    st.caption(
        "V3.3 checks current roster identity, injury designations, projected minutes, role/usage, matchup inputs and "
        "lineup state before allowing a saved 5M/10M PRA distribution to remain valid."
    )
    a, b, c, d = st.columns(4)
    a.metric("Availability", "VERIFIED" if state.get("safe") else "CHECK")
    b.metric("Hard OUT applied", int(state.get("hard_out") or 0))
    c.metric("Status uncertain", int(state.get("uncertain") or 0))
    d.metric("Team coverage", f"{int(state.get('covered_teams') or 0)}/{int(state.get('teams') or 0)}")
    st.caption(
        f"Basketball-state fingerprint: {state.get('short_fingerprint','—')} • "
        f"players modeled: {int(state.get('players') or 0)} • unverified: {int(state.get('unverified') or 0)}"
    )
    invalidated = st.session_state.get(f"wnba_pra_v33_invalidated::{day_str}")
    if invalidated:
        st.warning(f"🔁 Previous PRA simulation invalidated: {invalidated}. Run a fresh 5M pass before using the Final Card.")
    if state.get("safe"):
        st.success("✅ Injury/minutes/role integrity gate passed. OUT players are zeroed before team-minute and usage redistribution.")
    else:
        st.error("⛔ PRA production HOLD — live availability coverage is incomplete. Projections may be displayed for diagnosis, but no Final Card should be trusted until verification passes.")
    if st.button("🔄 RECHECK PRA INJURIES + MINUTES + ROLE", use_container_width=True, key=f"pra_v33_recheck_{day_str}"):
        clear_live_input_caches()
        st.rerun()


__all__ = [
    "install_runtime_guards", "current_basketball_state", "invalidate_stale_session",
    "attach_fingerprint", "apply_availability_gate_to_rows", "render_integrity_panel",
    "clear_live_input_caches",
]
