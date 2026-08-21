"""WNBA Points V1.9.8.4.5 — player-level sanity quarantine.

Safety/readiness-only wrapper over V1.9.8.4.4. Projection formulas,
SportsGameOdds transport, Monte Carlo distribution math, grading, calibration,
persistence, PRA, Rebounds, Assists, Spread and MLB are unchanged.

V1.9.8.4.4 correctly exposed the final remaining blocker: one matched Points
projection can fail the strict unexplained >35% projection-vs-history sanity
check. The inherited design then deadlocked the entire 5M slate, including every
other fully verified player/game.

V1.9.8.4.5 changes the failure scope, not the safety rule:
- a truly unexplained sanity-fail player is QUARANTINED before simulation;
- that player's sportsbook rows are removed from the execution frame and can
  never be simulated, graded, ranked, persisted as a pick, or sent to Daily Picks;
- every other player keeps the exact same projection and Monte Carlo math;
- all upcoming games must STILL retain at least one safe exact projection+market
  pair after quarantine, otherwise the 5M button remains locked;
- missing empirical history remains a hard blocker and is never auto-quarantined.

This is the same fail-closed pattern already used for raw sportsbook quotes that
have no current projection: unsafe rows are excluded instead of poisoning every
valid distribution on the slate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v19844 as prior

MODEL_VERSION = "WNBA POINTS V1.9.8.4.5 • PLAYER-LEVEL SANITY QUARANTINE"
PRA_FROZEN_BRANCH = prior.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = prior.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = prior.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = prior.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = prior.POINTS_FROZEN_COMMIT

v171 = prior.v171
ui = prior.ui
points = ui.points

# Save the genuine V1.9 prepare before installing the quarantine wrapper.
_ORIGINAL_PREPARE = points._prepare

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


def _key(game_id, player_key):
    return str(game_id or ""), str(player_key or "")


def _sanity_quarantine(day: str, projections=None, pairs=None) -> list[dict]:
    """Return only strict unexplained sanity failures using the frozen rule."""
    if projections is None or pairs is None:
        try:
            projections, pairs, _snap, _meta, _lineups = _ORIGINAL_PREPARE(day)
        except Exception:
            return []
    projections = projections if isinstance(projections, pd.DataFrame) else pd.DataFrame()
    pairs = pairs if isinstance(pairs, pd.DataFrame) else pd.DataFrame()
    if projections.empty or pairs.empty:
        return []
    if not {"game_id", "player_key"}.issubset(projections.columns) or not {"game_id", "player_key"}.issubset(pairs.columns):
        return []

    q = pairs[["game_id", "player_key"]].drop_duplicates().copy()
    p = projections.copy()
    q["game_id"] = q["game_id"].astype(str)
    q["player_key"] = q["player_key"].astype(str)
    p["game_id"] = p["game_id"].astype(str)
    p["player_key"] = p["player_key"].astype(str)
    matched = q.merge(p, on=["game_id", "player_key"], how="inner").drop_duplicates(["game_id", "player_key"])

    blocked = []
    for _, row in matched.iterrows():
        pid = str(row.get("PLAYER_ID") or "")
        pname = str(row.get("PLAYER_NAME") or "Player")
        team_id = int(_num(row.get("TEAM_ID"), 0))
        profile = points.points_empirical_profile(day, pid, pname, team_id) or {}
        hist_games = int(profile.get("games") or 0)
        hist_mean = _num(profile.get("pts"), np.nan)
        hist_min = _num(profile.get("minutes"), np.nan)
        proj = _num(row.get("PROJ_PTS"), np.nan)
        proj_min = _num(row.get("PROJ_MIN"), np.nan)
        role = str(row.get("ROLE_LABEL") or "ACTIVE")

        # Missing/short history is NOT quarantined here. The inherited history
        # gate must continue to block the slate until that evidence is complete.
        if not (hist_games >= 5 and pd.notna(hist_mean) and hist_mean >= 6.0 and pd.notna(proj)):
            continue
        pts_ratio = proj / max(hist_mean, 1.0)
        if 0.65 <= pts_ratio <= 1.35:
            continue

        min_ratio = proj_min / hist_min if pd.notna(proj_min) and pd.notna(hist_min) and hist_min > 0 else np.nan
        hist_rate = hist_mean / hist_min if pd.notna(hist_min) and hist_min > 0 else np.nan
        proj_rate = proj / proj_min if pd.notna(proj_min) and proj_min > 0 else np.nan
        rate_ratio = proj_rate / hist_rate if pd.notna(proj_rate) and pd.notna(hist_rate) and hist_rate > 0 else np.nan
        minute_shift = bool(pd.notna(min_ratio) and (min_ratio < MINUTE_SHIFT_LOW or min_ratio > MINUTE_SHIFT_HIGH))
        rate_stable = bool(pd.notna(rate_ratio) and RATE_RATIO_LOW <= rate_ratio <= RATE_RATIO_HIGH)

        # V1.9.8.4.3 already established that a material minutes shift with a
        # stable per-minute rate is explainable and remains non-blocking.
        if minute_shift and rate_stable:
            continue

        if minute_shift and pd.notna(rate_ratio):
            reason = "minutes changed but scoring-rate also left ±30% history band"
        elif "UNCERTAIN" in role.upper():
            reason = "status uncertainty without minutes/rate explanation"
        else:
            reason = "unexplained >35% projection-vs-history deviation"
        blocked.append({
            "game_id": str(row.get("game_id") or ""),
            "player_key": str(row.get("player_key") or ""),
            "Player": pname,
            "Team": str(row.get("team_name") or ""),
            "Proj PTS": round(proj, 2),
            "Hist PTS": round(hist_mean, 2),
            "PTS ratio": round(pts_ratio, 2),
            "Proj MIN": round(proj_min, 1) if pd.notna(proj_min) else np.nan,
            "Hist MIN": round(hist_min, 1) if pd.notna(hist_min) else np.nan,
            "MIN ratio": round(min_ratio, 2) if pd.notna(min_ratio) else np.nan,
            "PTS/min ratio": round(rate_ratio, 2) if pd.notna(rate_ratio) else np.nan,
            "Role": role,
            "Quarantine reason": reason,
        })
    return blocked


def _prepare_quarantined(day):
    projections, pairs, snap, pmeta, lineups = _ORIGINAL_PREPARE(day)
    projections = projections if isinstance(projections, pd.DataFrame) else pd.DataFrame()
    pairs = pairs if isinstance(pairs, pd.DataFrame) else pd.DataFrame()
    blocked = _sanity_quarantine(str(day), projections, pairs)
    keys = {_key(r.get("game_id"), r.get("player_key")) for r in blocked}

    if keys and not projections.empty and {"game_id", "player_key"}.issubset(projections.columns):
        mask = projections.apply(lambda r: _key(r.get("game_id"), r.get("player_key")) not in keys, axis=1)
        projections = projections.loc[mask].copy()
    if keys and not pairs.empty and {"game_id", "player_key"}.issubset(pairs.columns):
        mask = pairs.apply(lambda r: _key(r.get("game_id"), r.get("player_key")) not in keys, axis=1)
        pairs = pairs.loc[mask].copy()

    pmeta = dict(pmeta or {})
    pmeta["sanity_quarantine"] = blocked
    pmeta["sanity_quarantine_count"] = len(blocked)
    return projections, pairs, snap, pmeta, lineups


def _install():
    # Patch BOTH the public V1.9 execution module and the V1.0 base whose
    # run_standard() resolves _prepare dynamically. This guarantees a quarantined
    # player cannot sneak back into the actual simulation after preflight passes.
    points._prepare = _prepare_quarantined
    points.base._prepare = _prepare_quarantined
    prior._install()


def _quarantine_view(day: str) -> list[dict]:
    try:
        projections, pairs, _snap, _meta, _lineups = _ORIGINAL_PREPARE(day)
        return _sanity_quarantine(day, projections, pairs)
    except Exception:
        return []


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption("🛡️ Points V1.9.8.4.5 • player-level sanity quarantine ACTIVE • unsafe projection rows can never enter 5M")
    result = prior.render_wnba_points_hub(section_header, status_info, team_logo, h)

    day = st.session_state.get("wnba_points_date") or st.session_state.get("wnba_points_date_control")
    if day is not None:
        try:
            day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
            quarantined = _quarantine_view(day_str)
        except Exception:
            quarantined = []
        with st.expander("🚧 Points sanity quarantine audit", expanded=False):
            if quarantined:
                st.warning(
                    f"⚠️ {len(quarantined)} player projection(s) failed the strict unexplained sanity rule and are QUARANTINED. "
                    "They are excluded from the execution frame and cannot be simulated, graded, ranked or published."
                )
                st.dataframe(pd.DataFrame(quarantined), use_container_width=True, hide_index=True)
                st.caption(
                    "The rest of the slate may run only if every upcoming game still has safe exact projection+market coverage. Missing empirical history still blocks globally."
                )
            else:
                st.success("✅ No strict sanity-fail projection is quarantined on this slate.")
    return result


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "render_wnba_points_hub",
]
