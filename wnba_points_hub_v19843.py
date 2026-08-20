"""WNBA Points V1.9.8.4.3 — explainable sanity-gate repair.

Preflight-only wrapper over V1.9.8.4.2. Projection, SportsGameOdds transport,
Monte Carlo, grading, calibration, persistence, PRA, Rebounds and MLB math are
unchanged.

V1.7.1 correctly flagged >35% projection-vs-history deviations, but every flag
was treated as a hard blocker even when the same row already proved that the
deviation was caused by a material minutes change. That made "review reason"
diagnostics indistinguishable from true unexplained model failures.

This wrapper separates:
- BLOCKING deviations: unexplained scoring-rate changes / missing explanation.
- EXPLAINED deviations: projected minutes materially changed and projected
  points-per-minute remains within +/-30% of verified historical points/minute.

Explained deviations stay visible as MONITOR rows but no longer deadlock the 5M
button. Status uncertainty is still surfaced and the inherited Monte Carlo
uncertainty multipliers remain unchanged.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v19842 as prior

MODEL_VERSION = "WNBA POINTS V1.9.8.4.3 • EXPLAINABLE SANITY-GATE REPAIR"
PRA_FROZEN_BRANCH = prior.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = prior.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = prior.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = prior.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = prior.POINTS_FROZEN_COMMIT

v171 = prior.v171
ui = prior.ui
points = ui.points

MINUTE_SHIFT_LOW = 0.82
MINUTE_SHIFT_HIGH = 1.18
RATE_RATIO_LOW = 0.70
RATE_RATIO_HIGH = 1.30


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _history_gate_explainable(day):
    matched, _lineups = v171.base._matched_unique(day)
    if matched.empty:
        return {
            "expected": 0, "verified": 0, "short_sample": 0, "missing": 0,
            "ready": False, "sanity": [], "sanity_count": 0,
            "explained_sanity": [], "explained_count": 0,
        }

    expected = verified = short_sample = missing = 0
    blocking = []
    explained = []

    for _, row in matched.iterrows():
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

        if not (
            hist_games >= 5
            and pd.notna(hist_mean)
            and hist_mean >= 6.0
            and pd.notna(proj)
        ):
            continue

        pts_ratio = proj / max(hist_mean, 1.0)
        if 0.65 <= pts_ratio <= 1.35:
            continue

        min_ratio = (
            proj_min / hist_min
            if pd.notna(proj_min) and pd.notna(hist_min) and hist_min > 0
            else np.nan
        )
        hist_rate = (
            hist_mean / hist_min
            if pd.notna(hist_min) and hist_min > 0
            else np.nan
        )
        proj_rate = (
            proj / proj_min
            if pd.notna(proj_min) and proj_min > 0
            else np.nan
        )
        rate_ratio = (
            proj_rate / hist_rate
            if pd.notna(proj_rate) and pd.notna(hist_rate) and hist_rate > 0
            else np.nan
        )

        minute_shift = bool(
            pd.notna(min_ratio)
            and (min_ratio < MINUTE_SHIFT_LOW or min_ratio > MINUTE_SHIFT_HIGH)
        )
        rate_stable = bool(
            pd.notna(rate_ratio)
            and RATE_RATIO_LOW <= rate_ratio <= RATE_RATIO_HIGH
        )
        minute_explained = minute_shift and rate_stable

        row_out = {
            "Player": pname,
            "Proj PTS": round(proj, 2),
            "Hist PTS": round(hist_mean, 2),
            "PTS ratio": round(pts_ratio, 2),
            "Proj MIN": round(proj_min, 1) if pd.notna(proj_min) else np.nan,
            "Hist MIN": round(hist_min, 1) if pd.notna(hist_min) else np.nan,
            "MIN ratio": round(min_ratio, 2) if pd.notna(min_ratio) else np.nan,
            "PTS/min ratio": round(rate_ratio, 2) if pd.notna(rate_ratio) else np.nan,
            "Role": role,
        }

        if minute_explained:
            direction = "below" if min_ratio < 1.0 else "above"
            row_out["Review reason"] = (
                f"EXPLAINED — projected minutes materially {direction} history; "
                "per-minute scoring remains inside ±30% sanity band"
            )
            row_out["Disposition"] = "MONITOR • NON-BLOCKING"
            explained.append(row_out)
            continue

        if minute_shift and pd.notna(rate_ratio):
            reason = (
                "BLOCK — minutes changed, but projected points/minute also moved "
                "outside the ±30% verified-history band"
            )
        elif "UNCERTAIN" in role.upper():
            reason = "BLOCK — status uncertainty without a minutes/rate explanation"
        else:
            reason = "BLOCK — unexplained projection-vs-history deviation"
        row_out["Review reason"] = reason
        row_out["Disposition"] = "BLOCK"
        blocking.append(row_out)

    return {
        "expected": expected,
        "verified": verified,
        "short_sample": short_sample,
        "missing": missing,
        "sanity": blocking,
        "sanity_count": len(blocking),
        "explained_sanity": explained,
        "explained_count": len(explained),
        "ready": bool(expected > 0 and missing == 0 and len(blocking) == 0),
    }


def _render_readiness_explainable(info):
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
        st.error(
            f"⛔ HISTORY NOT READY • {h.get('missing',0)} established matched "
            "player(s) still lack verified ≥5-game scoring logs."
        )
    elif h.get("sanity_count", 0):
        st.warning(
            f"⚠️ REVIEW REQUIRED • {h.get('sanity_count',0)} unexplained extreme "
            "projection deviation(s) still block 5M."
        )
    elif info.get("ready"):
        confirmed = int(info.get("lineups_confirmed", 0))
        games = int(info.get("active_games", 0))
        if confirmed < games:
            st.warning(
                f"⚠️ PRE-LINEUP READY • {confirmed}/{games} upcoming starting fives "
                "confirmed. 5M may run; qualified plays remain MONITOR until explicit "
                "starters publish."
            )
        else:
            st.success(
                "✅ PRODUCTION READY • schedule, roster, projections, exact markets, "
                "empirical history and explainable-sanity checks passed."
            )
    else:
        st.warning("⚠️ NOT READY FOR 5M • one or more production gates remain unresolved.")

    if h.get("explained_count", 0):
        st.info(
            f"ℹ️ {h.get('explained_count',0)} extreme projection deviation(s) are "
            "fully explained by material minutes changes while projected scoring "
            "rate remains inside the verified ±30% band. They stay MONITOR and do "
            "not deadlock valid 5M distributions."
        )

    preview = info.get("preview")
    if isinstance(preview, pd.DataFrame) and not preview.empty:
        with st.expander("📋 Exact Points line + projection preview", expanded=False):
            cols = [c for c in preview.columns if c != "Hist GP"]
            st.dataframe(preview[cols], use_container_width=True, hide_index=True)


def _render_integrity_explainable(info):
    h = info.get("history_gate") or {}
    st.markdown("### 🧬 Points History Integrity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Established players", h.get("expected", 0))
    c2.metric("Verified ≥5 GP logs", f"{h.get('verified',0)}/{h.get('expected',0)}")
    c3.metric("Legit short samples", h.get("short_sample", 0))
    c4.metric("History misses", h.get("missing", 0))

    if h.get("missing", 0):
        st.error("⛔ EMPIRICAL HISTORY GATE NOT READY • do not run 5M.")
        return

    st.success(
        "✅ EMPIRICAL HISTORY GATE PASSED • all established matched players have "
        "verified prior-game scoring logs."
    )

    if h.get("sanity_count", 0):
        st.warning(
            f"⚠️ PROJECTION SANITY BLOCK: {h.get('sanity_count',0)} unexplained "
            "player deviation(s) remain. 5M stays locked."
        )
        with st.expander("🔎 Blocking projection sanity review — REQUIRED", expanded=True):
            st.dataframe(
                pd.DataFrame(h.get("sanity") or []),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.success("✅ EXPLAINABLE PROJECTION SANITY GATE PASSED • no unexplained extreme scoring deviations.")

    if h.get("explained_count", 0):
        st.info(
            f"🧠 {h.get('explained_count',0)} extreme raw PTS deviation(s) were "
            "minute-explained, not scoring-rate failures. These rows remain visible "
            "for review but are non-blocking."
        )
        with st.expander("🔎 Minute-explained projection monitors", expanded=True):
            st.dataframe(
                pd.DataFrame(h.get("explained_sanity") or []),
                use_container_width=True,
                hide_index=True,
            )
    elif not h.get("sanity_count", 0):
        st.caption("✅ No extreme >35% projection-vs-verified-history deviations detected.")


def _install():
    # V1.7.1 installs these globals dynamically during render. Replace only the
    # sanity classification/renderers; projection and simulation functions remain
    # untouched.
    v171._history_gate = _history_gate_explainable
    v171._render_readiness = _render_readiness_explainable
    v171._render_integrity = _render_integrity_explainable


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "render_wnba_points_hub",
]
