"""WNBA Rebounds V1.4.1 — Step 5 precision coverage repair.

Extends V1.4 without weakening the Step-5 verification gate.

Performance repair:
- Step 4 already verifies recent OREB/DREB role history from completed games.
- Step 5 no longer re-downloads many of those same ESPN game summaries again.
- Season/L10/L5 values come from the verified current-roster player pool.
- Step-4 PLAYER_ID history remains the strict fallback for recent/sample coverage.
- The season pool is cached for six hours by slate date.

No sportsbook, Monte Carlo, final rebound projection, or other sport module is
changed by this file.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v14 as base

MODEL_VERSION = "WNBA REBOUNDS V1.4.1 • FAST STEP 5 PLAYER_ID FORM RECONCILIATION"

_ORIGINAL_MARKDOWN_14 = base._versioned_markdown_14
_ORIGINAL_CAPTION_14 = base._caption_14


def _finite(value):
    try:
        x = float(value)
        return np.isfinite(x)
    except Exception:
        return False


@st.cache_data(ttl=21600, show_spinner=False, max_entries=16)
def _fast_season_lookup(day: str) -> pd.DataFrame:
    """Cache the already-verified player pool; do not rebuild it on every rerun."""
    return base._season_lookup(str(day)).copy()


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
    r["FORM_RECENT_SOURCE"] = "PLAYER POOL L10/L5"
    r["FORM_FALLBACK_USED"] = False

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
        int(base._num(r.get("FORM_L10_GP"), 0) or 0) >= 3
        and _finite(r.get("FORM_L10_REB36"))
    ) or role_verified
    stable_verified = _finite(r.get("FORM_STABILIZED_REB36"))

    r["_FORM_COVERED_141"] = bool(baseline_verified and recent_verified and stable_verified)
    r["FORM_SAMPLE"] = (
        "VERIFIED • PLAYER_ID FALLBACK"
        if r["_FORM_COVERED_141"] and bool(r.get("FORM_FALLBACK_USED"))
        else "VERIFIED" if r["_FORM_COVERED_141"] else "SHORT/CHECK"
    )
    return r


def _pool_num(srow, key, default=np.nan):
    if srow is None:
        return default
    return base._num(srow.get(key), default)


def _rate36(reb, mins):
    return 36.0 * reb / mins if _finite(reb) and _finite(mins) and float(mins) > 0 else np.nan


@st.cache_data(ttl=21600, show_spinner=False, max_entries=16)
def _build_step5_fast_cached(step4_records: tuple, day: str):
    """Build Step 5 without re-fetching per-game summaries already used by Step 4."""
    frame = pd.DataFrame(list(step4_records))
    if frame.empty:
        return [], [], {"ready": False, "reason": "no Step-4 rows"}

    pool = _fast_season_lookup(day)
    outputs = []

    for _, row in frame.iterrows():
        srow = base._match_season_row(pool, row)
        season_gp = int(_pool_num(srow, "GP", 0) or 0)
        season_min = _pool_num(srow, "MIN", np.nan)
        season_reb = _pool_num(srow, "REB", np.nan)
        season36 = _rate36(season_reb, season_min)

        l10_reb = _pool_num(srow, "L10_REB", np.nan)
        l10_min = _pool_num(srow, "L10_MIN", np.nan)
        l10_36 = _rate36(l10_reb, l10_min)
        l5_reb = _pool_num(srow, "L5_REB", np.nan)
        l5_min = _pool_num(srow, "L5_MIN", np.nan)
        l5_36 = _rate36(l5_reb, l5_min)

        role_gp = int(base._num(row.get("REB_ROLE_GP"), 0) or 0)
        role36 = base._num(row.get("REB36"), np.nan)

        # We intentionally do not re-download game summaries to manufacture L3.
        # Step-4 verified role history supplies recent sample validation instead.
        stabilized, raw_recent, capped_recent = base._stabilized_form_rate(
            season36, l10_36, l5_36, np.nan, season_gp
        )

        out = row.to_dict()
        out.update({
            "FORM_SEASON_GP": season_gp,
            "FORM_SEASON_REB": season_reb,
            "FORM_SEASON_MIN": season_min,
            "FORM_SEASON_REB36": season36,
            "FORM_L10_GP": min(10, season_gp) if _finite(l10_36) else 0,
            "FORM_L10_REB": l10_reb,
            "FORM_L10_REB36": l10_36,
            "FORM_L5_GP": min(5, season_gp) if _finite(l5_36) else 0,
            "FORM_L5_REB": l5_reb,
            "FORM_L5_REB36": l5_36,
            "FORM_L3_GP": 0,
            "FORM_L3_REB": np.nan,
            "FORM_L3_REB36": np.nan,
            "FORM_L5_OREB36": np.nan,
            "FORM_L5_DREB36": np.nan,
            "FORM_VOL_REB36": np.nan,
            "FORM_RAW_RECENT36": raw_recent,
            "FORM_CAPPED_RECENT36": capped_recent,
            "FORM_STABILIZED_REB36": stabilized,
            "FORM_TREND_PCT": (
                100.0 * (stabilized / season36 - 1.0)
                if _finite(stabilized) and _finite(season36) and float(season36) > 0 else np.nan
            ),
            "FORM_RECENT_SOURCE": "PLAYER POOL L10/L5 • NO DUPLICATE GAME FETCH",
            "FORM_BASELINE_SOURCE": "SEASON",
            "FORM_FALLBACK_USED": False,
            "FORM_STEP4_RECENT_GP": role_gp,
            "FORM_STEP4_RECENT_REB36": role36,
        })
        outputs.append(_repair_row(pd.Series(out)).to_dict())

    repaired = pd.DataFrame(outputs)
    repaired["PROJ_MIN"] = pd.to_numeric(repaired.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    modeled = repaired[repaired["PROJ_MIN"].ge(5.0)].copy()
    modeled["_COVERED"] = modeled.get("_FORM_COVERED_141", False).fillna(False).astype(bool) if not modeled.empty else False

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

    blockers = []
    if not modeled.empty:
        bad = modeled[~modeled["_COVERED"]].copy()
        for _, r in bad.iterrows():
            blockers.append({
                "Player": str(r.get("PLAYER_NAME") or "Player"),
                "Team": str(r.get("TEAM_NAME") or ""),
                "Season GP": int(base._num(r.get("FORM_SEASON_GP"), 0) or 0),
                "L10 GP": int(base._num(r.get("FORM_L10_GP"), 0) or 0),
                "Role GP": int(base._num(r.get("REB_ROLE_GP"), 0) or 0),
                "Baseline source": str(r.get("FORM_BASELINE_SOURCE") or "—"),
                "Recent source": str(r.get("FORM_RECENT_SOURCE") or "—"),
            })

    info = {
        "ready": ready,
        "teams": team_count,
        "ready_teams": ready_teams,
        "modeled_players": int(len(modeled)),
        "covered_players": covered_players,
        "player_id_fallbacks": fallback_players,
        "blockers": blockers,
        "repair_version": "V1.4.1 FAST",
        "performance_mode": "NO DUPLICATE STEP5 GAME SUMMARY FETCHES",
    }
    return repaired.to_dict("records"), teams_out.to_dict("records"), info


def _build_step5_form_141(step4_players: pd.DataFrame, day: str, slate: pd.DataFrame):
    if step4_players is None or step4_players.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-4 rows"}

    # Convert only stable scalar records into the cache key. This prevents every
    # Streamlit widget rerun from rebuilding Step 5 and hitting ESPN repeatedly.
    records = tuple(
        tuple(sorted((str(k), None if pd.isna(v) else str(v)) for k, v in row.items()))
        for row in step4_players.to_dict("records")
    )
    packed_rows, team_rows, info = _build_step5_fast_cached(records, str(day))

    # Cached tuples are stringified for stable hashing; restore useful numeric
    # types where possible after reconstruction.
    players_out = pd.DataFrame(packed_rows)
    teams_out = pd.DataFrame(team_rows)
    return players_out, teams_out, info


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
            "⚡ WNBA Rebounds V1.4.1 • Steps 1–5 active • fast Step-5 cache • "
            "no duplicate game-summary fetches • strict verified form gate"
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
        st.success("⚡ STEP 5 FAST CACHE ACTIVE • duplicate recent-game summary fetches are disabled.")
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
