"""WNBA Points V1.7.1 — synchronized empirical-history + projection sanity preflight.

UI/preflight-only refinement over V1.7. It does not change Points projection or
Monte Carlo math. It fixes the legacy readiness widget that dropped player/team
identity before checking empirical history, and blocks 5M while an extreme
projection-vs-own-history deviation still needs review.

Frozen WNBA PRA V3.2.1 and MLB V2.1.7 are not modified.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


def _load_base():
    path = Path(__file__).with_name("wnba_points_hub_v17.py")
    spec = importlib.util.spec_from_file_location("_kyre_wnba_points_v17_base_for_v171", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load WNBA Points V1.7 base.")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


base = _load_base()
points = base.points
ui = base.ui
MODEL_VERSION = "WNBA POINTS V1.7.1 • SYNCHRONIZED HISTORY + SANITY GATE"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _history_gate(day):
    matched, lineups = base._matched_unique(day)
    if matched.empty:
        return {
            "expected": 0, "verified": 0, "short_sample": 0, "missing": 0,
            "ready": False, "sanity": [], "sanity_count": 0,
        }

    expected = verified = short_sample = missing = 0
    sanity = []
    for _, row in matched.iterrows():
        gid = str(row.get("game_id") or "")
        pid = str(row.get("PLAYER_ID") or "")
        pname = str(row.get("PLAYER_NAME") or "Player")
        team_id = int(_num(row.get("TEAM_ID"), 0))

        profile = points.points_empirical_profile(day, pid, pname, team_id) or {}
        hist_games = int(profile.get("games") or 0)
        gp = _num(row.get("GP"), np.nan)
        established = bool(pd.isna(gp) or gp >= 5.0)

        if established:
            expected += 1
            if hist_games >= 5:
                verified += 1
            else:
                missing += 1
        else:
            short_sample += 1

        hist_mean = _num(profile.get("pts"), np.nan)
        hist_min = _num(profile.get("minutes"), np.nan)
        proj = _num(row.get("PROJ_PTS"), np.nan)
        proj_min = _num(row.get("PROJ_MIN"), np.nan)
        role = str(row.get("ROLE_LABEL") or "ACTIVE")

        if hist_games >= 5 and pd.notna(hist_mean) and hist_mean >= 6.0 and pd.notna(proj):
            ratio = proj / max(hist_mean, 1.0)
            if ratio < 0.65 or ratio > 1.35:
                min_ratio = proj_min / hist_min if pd.notna(proj_min) and pd.notna(hist_min) and hist_min > 0 else np.nan
                if pd.notna(min_ratio) and min_ratio < 0.82:
                    reason = "Projected minutes materially below verified history"
                elif pd.notna(min_ratio) and min_ratio > 1.18:
                    reason = "Projected minutes materially above verified history"
                elif "UNCERTAIN" in role.upper():
                    reason = "Current role/status uncertainty"
                else:
                    reason = "UNEXPLAINED — inspect minutes/role inputs"
                sanity.append({
                    "Player": pname,
                    "Proj PTS": round(proj, 2),
                    "Hist PTS": round(hist_mean, 2),
                    "PTS ratio": round(ratio, 2),
                    "Proj MIN": round(proj_min, 1) if pd.notna(proj_min) else np.nan,
                    "Hist MIN": round(hist_min, 1) if pd.notna(hist_min) else np.nan,
                    "MIN ratio": round(min_ratio, 2) if pd.notna(min_ratio) else np.nan,
                    "Role": role,
                    "Review reason": reason,
                })

    # Extreme projection deviations are a review gate, not an automatic model
    # correction. The sportsbook line is never used here.
    return {
        "expected": expected,
        "verified": verified,
        "short_sample": short_sample,
        "missing": missing,
        "sanity": sanity,
        "sanity_count": len(sanity),
        "ready": bool(expected > 0 and missing == 0 and len(sanity) == 0),
    }


def _render_readiness(info):
    st.markdown("### 🧪 Pre-Simulation Readiness")
    h = info.get("history_gate") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Eligible games", info.get("active_games", 0))
    c2.metric("Projection coverage", f"{info.get('matched_players',0)}/{info.get('market_players',0)}")
    c3.metric("Exact eligible pairs", info.get("eligible_pairs", 0))
    c4.metric("Verified history", f"{h.get('verified',0)}/{h.get('expected',0)} established")

    if info.get("error"):
        st.error(f"Preflight could not complete: {info['error']}")
        return

    if h.get("missing", 0):
        st.error(f"⛔ HISTORY NOT READY • {h.get('missing',0)} established matched player(s) still lack verified ≥5-game scoring logs.")
    elif h.get("sanity_count", 0):
        st.warning(f"⚠️ REVIEW REQUIRED • empirical history is complete, but {h.get('sanity_count',0)} extreme projection deviation(s) must be inspected before 5M unlocks.")
    elif info.get("ready"):
        confirmed = int(info.get("lineups_confirmed", 0))
        games = int(info.get("active_games", 0))
        if confirmed < games:
            st.warning(f"⚠️ PRE-LINEUP READY • {confirmed}/{games} upcoming starting fives confirmed. 5M may run after sanity clearance; qualified plays remain MONITOR until explicit starters publish.")
        else:
            st.success("✅ PRODUCTION READY • schedule, roster, projections, exact markets, empirical history and lineup checks passed.")
    else:
        st.warning("⚠️ NOT READY FOR 5M • one or more production gates remain unresolved.")

    preview = info.get("preview")
    if isinstance(preview, pd.DataFrame) and not preview.empty:
        with st.expander("📋 Exact Points line + projection preview", expanded=False):
            # Hist GP in this legacy preview is intentionally omitted because it
            # was calculated after identity columns had been stripped in V1.3.
            cols = [c for c in preview.columns if c != "Hist GP"]
            st.dataframe(preview[cols], use_container_width=True, hide_index=True)


def _render_integrity(info):
    h = info.get("history_gate") or {}
    st.markdown("### 🧬 Points History Integrity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Established players", h.get("expected", 0))
    c2.metric("Verified ≥5 GP logs", f"{h.get('verified',0)}/{h.get('expected',0)}")
    c3.metric("Legit short samples", h.get("short_sample", 0))
    c4.metric("History misses", h.get("missing", 0))

    if h.get("missing", 0):
        st.error("⛔ EMPIRICAL HISTORY GATE NOT READY • do not run 5M.")
    elif h.get("sanity_count", 0):
        st.success("✅ EMPIRICAL HISTORY GATE PASSED • all established matched players have verified prior-game scoring logs.")
        st.warning(
            f"⚠️ PROJECTION SANITY GATE: {h.get('sanity_count',0)} player(s) are >35% away from their own verified scoring history. "
            "The sportsbook line is not used. 5M stays locked until these rows are reviewed."
        )
        with st.expander("🔎 Projection sanity review — REQUIRED", expanded=True):
            st.dataframe(pd.DataFrame(h.get("sanity") or []), use_container_width=True, hide_index=True)
    else:
        st.success("✅ EMPIRICAL HISTORY + PROJECTION SANITY GATES PASSED.")
        st.caption("No unresolved >35% projection-vs-own-history deviations detected.")


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Replace only V1.7's preflight helpers. Model/simulation code remains V1.4.
    base._history_gate = _history_gate
    base.ui._render_readiness = _render_readiness
    base._render_integrity = _render_integrity
    st.caption("🏀 WNBA Points V1.7.1 • synchronized history + sanity gate • PRA V3.2.1 frozen • MLB V2.1.7 frozen")
    return base.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = ["MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH", "render_wnba_points_hub"]
