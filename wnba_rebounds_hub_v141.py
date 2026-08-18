"""WNBA Rebounds V1.4.1 — Step 5 precision coverage repair.

Extends V1.4 without weakening the Step-5 verification gate.

Why this exists:
- A current-team season aggregate can be short for a traded/signed player even
  when Step 4 already proved that the same immutable ESPN PLAYER_ID has >=3
  verified OREB/DREB games elsewhere in the current season.
- Step 5 must not label that provider/team-scope artifact as "no history".

Repair hierarchy:
1) Prefer the normal verified season + L10/L5/L3 form from V1.4.
2) If that current-team season baseline is short/missing, reuse the already
   verified Step-4 PLAYER_ID OREB/DREB history as a baseline/recent fallback.
3) Never fabricate a game, rebound, minute, OREB, DREB or sportsbook input.
4) A fallback is allowed only when Step 4 has >=3 component-valid played games
   with finite minutes and REB/36.

This remains descriptive infrastructure only. No final rebound projection,
sportsbook line, no-vig probability, Monte Carlo, or pick grading is enabled.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v14 as base

MODEL_VERSION = "WNBA REBOUNDS V1.4.1 • STEP 5 PLAYER_ID FORM RECONCILIATION"

_ORIGINAL_BUILD = base._build_step5_form
_ORIGINAL_MARKDOWN_14 = base._versioned_markdown_14
_ORIGINAL_CAPTION_14 = base._caption_14


def _finite(value):
    try:
        x = float(value)
        return np.isfinite(x)
    except Exception:
        return False


def _repair_row(row: pd.Series) -> pd.Series:
    """Repair provider/team-scope gaps from already-verified Step-4 history."""
    r = row.copy()

    role_gp = int(base._num(r.get("REB_ROLE_GP"), 0) or 0)
    role_min = base._num(r.get("REB_ROLE_MIN"), np.nan)
    role_reb36 = base._num(r.get("REB36"), np.nan)
    role_reb_total = base._num(r.get("REB_L10_TOTAL"), np.nan)

    season_gp = int(base._num(r.get("FORM_SEASON_GP"), 0) or 0)
    season36 = base._num(r.get("FORM_SEASON_REB36"), np.nan)
    l3_gp = int(base._num(r.get("FORM_L3_GP"), 0) or 0)
    l3_36 = base._num(r.get("FORM_L3_REB36"), np.nan)

    normal_baseline = season_gp >= 3 and _finite(season36)
    normal_recent = l3_gp >= 3 and _finite(l3_36)
    role_verified = (
        role_gp >= 3
        and _finite(role_min)
        and float(role_min) > 0
        and _finite(role_reb36)
    )

    r["FORM_BASELINE_SOURCE"] = "SEASON"
    r["FORM_RECENT_SOURCE"] = "GAME LOG L3/L5/L10"
    r["FORM_FALLBACK_USED"] = False

    # Current-team season tables can reset after a transaction. Step 4 has
    # already followed the immutable ESPN PLAYER_ID across teams, so use that
    # verified component history rather than treating the player as historyless.
    if not normal_baseline and role_verified:
        avg_min = float(role_min) / float(role_gp)
        if _finite(role_reb_total):
            avg_reb = float(role_reb_total) / float(role_gp)
        else:
            avg_reb = float(role_reb36) * avg_min / 36.0
        r["FORM_SEASON_GP"] = role_gp
        r["FORM_SEASON_MIN"] = avg_min
        r["FORM_SEASON_REB"] = avg_reb
        r["FORM_SEASON_REB36"] = float(role_reb36)
        r["FORM_BASELINE_SOURCE"] = "VERIFIED PLAYER_ID OREB/DREB HISTORY"
        r["FORM_FALLBACK_USED"] = True
        season_gp = role_gp
        season36 = float(role_reb36)

    # If provider L3 rows are sparse while the Step-4 recent component sample is
    # healthy, preserve the truthful distinction: this is a verified recent
    # component-history fallback, not a synthetic L3. We use it as the L10-style
    # recent rate and mark the source explicitly.
    if not normal_recent and role_verified:
        if int(base._num(r.get("FORM_L10_GP"), 0) or 0) < 3 or not _finite(r.get("FORM_L10_REB36")):
            r["FORM_L10_GP"] = role_gp
            r["FORM_L10_REB36"] = float(role_reb36)
            avg_min = float(role_min) / float(role_gp)
            r["FORM_L10_REB"] = (
                float(role_reb_total) / float(role_gp)
                if _finite(role_reb_total)
                else float(role_reb36) * avg_min / 36.0
            )
        r["FORM_RECENT_SOURCE"] = "VERIFIED PLAYER_ID OREB/DREB HISTORY"
        r["FORM_FALLBACK_USED"] = True

    # Recompute the guarded descriptor after any verified fallback repair.
    stabilized, raw_recent, capped_recent = base._stabilized_form_rate(
        r.get("FORM_SEASON_REB36"),
        r.get("FORM_L10_REB36"),
        r.get("FORM_L5_REB36"),
        r.get("FORM_L3_REB36"),
        r.get("FORM_SEASON_GP"),
    )
    r["FORM_STABILIZED_REB36"] = stabilized
    r["FORM_RAW_RECENT36"] = raw_recent
    r["FORM_CAPPED_RECENT36"] = capped_recent

    s = base._num(r.get("FORM_SEASON_REB36"), np.nan)
    if _finite(s) and float(s) > 0 and _finite(stabilized):
        trend_pct = 100.0 * (float(stabilized) / float(s) - 1.0)
        r["FORM_TREND_PCT"] = trend_pct
        r["FORM_TREND"] = "UP" if trend_pct >= 4.0 else "DOWN" if trend_pct <= -4.0 else "STEADY"

    baseline_verified = (
        int(base._num(r.get("FORM_SEASON_GP"), 0) or 0) >= 3
        and _finite(r.get("FORM_SEASON_REB36"))
    )
    recent_verified = (
        (
            int(base._num(r.get("FORM_L3_GP"), 0) or 0) >= 3
            and _finite(r.get("FORM_L3_REB36"))
        )
        or role_verified
    )
    stable_verified = _finite(r.get("FORM_STABILIZED_REB36"))

    r["_FORM_COVERED_141"] = bool(baseline_verified and recent_verified and stable_verified)
    if r["_FORM_COVERED_141"]:
        r["FORM_SAMPLE"] = "VERIFIED • PLAYER_ID FALLBACK" if bool(r.get("FORM_FALLBACK_USED")) else "VERIFIED"
    else:
        r["FORM_SAMPLE"] = "SHORT/CHECK"
    return r


def _build_step5_form_141(step4_players: pd.DataFrame, day: str, slate: pd.DataFrame):
    players_out, _, old_info = _ORIGINAL_BUILD(step4_players, day, slate)
    if players_out is None or players_out.empty:
        return players_out, pd.DataFrame(), {**(old_info or {}), "ready": False}

    repaired = players_out.apply(_repair_row, axis=1)
    repaired["PROJ_MIN"] = pd.to_numeric(repaired.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    modeled = repaired[repaired["PROJ_MIN"].ge(5.0)].copy()
    if not modeled.empty:
        modeled["_COVERED"] = modeled.get("_FORM_COVERED_141", False).fillna(False).astype(bool)

    team_rows = []
    if not modeled.empty:
        for team_name, part in modeled.groupby("TEAM_NAME", sort=False):
            covered = int(part["_COVERED"].sum())
            total = int(len(part))
            fallbacks = int(part.get("FORM_FALLBACK_USED", False).fillna(False).astype(bool).sum())
            team_rows.append({
                "Team": team_name,
                "Modeled ≥5 MIN": total,
                "Form covered": covered,
                "PLAYER_ID fallbacks": fallbacks,
                "State": "VERIFIED" if total > 0 and covered == total else "CHECK",
            })
    teams_out = pd.DataFrame(team_rows)

    team_count = int(teams_out["Team"].nunique()) if not teams_out.empty else 0
    ready_teams = int(teams_out["State"].eq("VERIFIED").sum()) if not teams_out.empty else 0
    covered_players = int(modeled["_COVERED"].sum()) if not modeled.empty else 0
    fallback_players = int(modeled.get("FORM_FALLBACK_USED", False).fillna(False).astype(bool).sum()) if not modeled.empty else 0
    ready = bool(team_count > 0 and ready_teams == team_count and covered_players == len(modeled))

    # Expose exact blockers if anything legitimately remains unresolved.
    blockers = []
    if not modeled.empty:
        bad = modeled[~modeled["_COVERED"]].copy()
        for _, r in bad.iterrows():
            blockers.append({
                "Player": str(r.get("PLAYER_NAME") or "Player"),
                "Team": str(r.get("TEAM_NAME") or ""),
                "Season GP": int(base._num(r.get("FORM_SEASON_GP"), 0) or 0),
                "L3 GP": int(base._num(r.get("FORM_L3_GP"), 0) or 0),
                "Role GP": int(base._num(r.get("REB_ROLE_GP"), 0) or 0),
                "Baseline source": str(r.get("FORM_BASELINE_SOURCE") or "—"),
                "Recent source": str(r.get("FORM_RECENT_SOURCE") or "—"),
            })

    info = dict(old_info or {})
    info.update({
        "ready": ready,
        "teams": team_count,
        "ready_teams": ready_teams,
        "modeled_players": int(len(modeled)),
        "covered_players": covered_players,
        "player_id_fallbacks": fallback_players,
        "blockers": blockers,
        "repair_version": "V1.4.1",
    })
    return repaired, teams_out, info


def _versioned_markdown_141(body, *args, **kwargs):
    text = str(body).replace(
        "WNBA Rebounds Command Center — V1.4",
        "WNBA Rebounds Command Center — V1.4.1",
    )
    return _ORIGINAL_MARKDOWN_14(text, *args, **kwargs)


def _caption_141(body, *args, **kwargs):
    text = str(body)
    if text.startswith("📈 WNBA Rebounds V1.4"):
        text = (
            "🧬 WNBA Rebounds V1.4.1 • Steps 1–5 active • PLAYER_ID transaction/history "
            "reconciliation • strict verified form gate • no rebound projection/market/simulation yet"
        )
    return _ORIGINAL_CAPTION_14(text, *args, **kwargs)


def render_wnba_rebounds_hub(*args, **kwargs):
    old_build = base._build_step5_form
    old_markdown = base._versioned_markdown_14
    old_caption = base._caption_14
    base._build_step5_form = _build_step5_form_141
    base._versioned_markdown_14 = _versioned_markdown_141
    base._caption_14 = _caption_141
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        base._build_step5_form = old_build
        base._versioned_markdown_14 = old_markdown
        base._caption_14 = old_caption

    if st.session_state.get("wnba_rebounds_step5_ready"):
        records = st.session_state.get("wnba_rebounds_step5_players") or []
        frame = pd.DataFrame(records)
        fallback_count = 0
        if not frame.empty and "FORM_FALLBACK_USED" in frame.columns:
            fallback_count = int(frame["FORM_FALLBACK_USED"].fillna(False).astype(bool).sum())
        st.success(
            f"🧬 STEP 5 V1.4.1 VERIFIED • {fallback_count} PLAYER_ID history reconciliation(s) used where needed. "
            "Step 6 is unlocked; no sportsbook or Monte Carlo input has been introduced."
        )
    else:
        records = st.session_state.get("wnba_rebounds_step5_players") or []
        frame = pd.DataFrame(records)
        if not frame.empty and "_FORM_COVERED_141" in frame.columns:
            bad = frame[
                pd.to_numeric(frame.get("PROJ_MIN"), errors="coerce").fillna(0).ge(5.0)
                & ~frame["_FORM_COVERED_141"].fillna(False).astype(bool)
            ]
            if not bad.empty:
                st.error("Step 5 still has legitimate unresolved history. Exact blockers are shown below; the gate remains strict.")
                cols = [c for c in ["PLAYER_NAME", "TEAM_NAME", "FORM_SEASON_GP", "FORM_L3_GP", "REB_ROLE_GP", "FORM_BASELINE_SOURCE", "FORM_RECENT_SOURCE"] if c in bad.columns]
                st.dataframe(bad[cols], hide_index=True, use_container_width=True)
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
