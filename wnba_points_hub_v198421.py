"""WNBA Points V1.9.8.4.21 — Points-only usage identity bridge repair.

Builds on V1.9.8.4.20 and fixes the deeper source of the missing Step-8 usage
values without touching PRA/Rebounds/Assists or any non-Points model.

Root cause:
- the selected Points player pool can carry ESPN PLAYER_ID values;
- the preferred WNBA/NBA Stats advanced-usage table can carry another provider
  PLAYER_ID namespace;
- the shared role engine's original _attach_usage() joins strictly on
  TEAM_ID + PLAYER_ID, so legitimate usage rows can be missed even when the
  player is present under the same verified full name.

This wrapper replaces only the role facade referenced by the isolated
wnba_points_v19 module. It does NOT patch wnba_role_v282 globally. The Points
facade joins usage by exact team+id first, then exact normalized full name, and
uses the existing day-aware ESPN WNBA box-score usage fallback only for fields
still missing for that player. All provenance is retained in USG_SOURCE.

This is an identity/data-handoff correction, not a new feature weight. Absolute
usage still affects Points exactly where the existing role engine already used
it (primarily verified teammate-absence redistribution). The projection formula,
Monte Carlo distribution, calibration, sportsbook transport and ranking rules
are unchanged.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198420 as prior
import wnba_role_v282 as role

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.21 • POINTS-ONLY USAGE IDENTITY BRIDGE"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_USAGE_COLS = ("USG_PCT", "L10_USG_PCT", "L5_USG_PCT")
_ORIGINAL_POINTS_ROLE = getattr(points, "_kyre_v198421_original_role", getattr(points, "role", role))
setattr(points, "_kyre_v198421_original_role", _ORIGINAL_POINTS_ROLE)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _id_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _norm_name(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _valid_usage(value) -> bool:
    x = _num(value, np.nan)
    return bool(pd.notna(x) and x > 0)


def _source_label(source: str) -> str:
    text = str(source or "").strip()
    upper = text.upper()
    if not text:
        return "UNAVAILABLE"
    if "PRODUCTION-ROLE PROXY" in upper:
        return "ROLE PROXY • ESTIMATED"
    if "ESPN" in upper:
        return "ESPN BOX-SCORE ESTIMATED USG%"
    return text


def _match_row(table: pd.DataFrame, player_row):
    if table is None or table.empty:
        return None, ""

    pid = _id_int(player_row.get("PLAYER_ID"))
    tid = _id_int(player_row.get("TEAM_ID"))
    name_key = _norm_name(player_row.get("PLAYER_NAME"))

    if pid and "PLAYER_ID" in table.columns:
        ids = pd.to_numeric(table["PLAYER_ID"], errors="coerce").fillna(-1).astype(int)
        exact = table.loc[ids.eq(pid)].copy()
        if tid and not exact.empty and "TEAM_ID" in exact.columns:
            tids = pd.to_numeric(exact["TEAM_ID"], errors="coerce").fillna(-1).astype(int)
            same_team = exact.loc[tids.eq(tid)]
            if not same_team.empty:
                return same_team.iloc[0], "TEAM+PLAYER ID"
        if len(exact) == 1:
            return exact.iloc[0], "PLAYER ID"

    if name_key and "PLAYER_NAME" in table.columns:
        names = table["PLAYER_NAME"].map(_norm_name)
        named = table.loc[names.eq(name_key)].copy()
        if not named.empty:
            if tid and "TEAM_ID" in named.columns:
                tids = pd.to_numeric(named["TEAM_ID"], errors="coerce").fillna(-1).astype(int)
                same_team = named.loc[tids.eq(tid)]
                if not same_team.empty:
                    return same_team.iloc[0], "TEAM+NAME • CROSS-PROVIDER ID"
            if len(named) == 1:
                return named.iloc[0], "NAME • CROSS-PROVIDER ID"

    return None, ""


def _attach_usage_points(pool: pd.DataFrame, primary: pd.DataFrame, primary_source: str,
                         espn: pd.DataFrame) -> pd.DataFrame:
    out = pool.copy()
    for col in _USAGE_COLS:
        out[col] = np.nan
    out["USG_SOURCE"] = "UNAVAILABLE"

    if out.empty:
        return out

    for idx, player_row in out.iterrows():
        notes = []
        prow, pmethod = _match_row(primary, player_row)
        if prow is not None:
            filled = 0
            for col in _USAGE_COLS:
                if col in prow.index and _valid_usage(prow.get(col)):
                    out.at[idx, col] = _num(prow.get(col), np.nan)
                    filled += 1
            if filled:
                notes.append(f"{_source_label(primary_source)} • {pmethod}")

        # A healthy league table can still omit an individual player. Fill only
        # missing fields from the existing date-scoped verified ESPN fallback.
        if any(not _valid_usage(out.at[idx, col]) for col in _USAGE_COLS):
            erow, emethod = _match_row(espn, player_row)
            if erow is not None:
                efilled = 0
                for col in _USAGE_COLS:
                    if not _valid_usage(out.at[idx, col]) and col in erow.index and _valid_usage(erow.get(col)):
                        out.at[idx, col] = _num(erow.get(col), np.nan)
                        efilled += 1
                if efilled:
                    notes.append(f"ESPN BOX-SCORE ESTIMATED USG% • {emethod}")

        if notes:
            out.at[idx, "USG_SOURCE"] = " + ".join(notes)
        else:
            out.at[idx, "USG_SOURCE"] = "NO VERIFIED USAGE IDENTITY MATCH"

    return out


def _role_projection_for_game_points(row, stats: pd.DataFrame | None = None) -> dict:
    """Points-isolated copy of the existing role pipeline with safer identity join."""
    rb = role.base  # wnba_role_v28, already carrying V2.8.2 safety patches
    if stats is None:
        stats = rb.availability.player_form_table()

    av = rb.availability.availability_for_game(row, stats)
    av_frame = av.get("players") if isinstance(av, dict) else pd.DataFrame()
    game_pool = rb.availability.slate_player_pool(pd.DataFrame([row]), stats)

    try:
        day_str = rb._day_str(row.get("game_date"))
        season = int(pd.to_datetime(day_str).year)
    except Exception:
        day_str = pd.to_datetime(row.get("game_date"), errors="coerce").strftime("%Y-%m-%d")
        season = int(pd.to_datetime(row.get("game_date"), errors="coerce").year)

    try:
        primary, primary_source = role.advanced_usage_table(season)
    except Exception:
        primary, primary_source = pd.DataFrame(), "unavailable"
    try:
        espn = role.prior._espn_usage_fallback(season, day_str)
    except Exception:
        espn = pd.DataFrame()

    merged = rb._merge_availability(game_pool, av_frame)
    pool = _attach_usage_points(merged, primary, primary_source, espn)

    teams = {}
    for tid in (int(row.get("away_team_id") or 0), int(row.get("home_team_id") or 0)):
        part = pool[pd.to_numeric(pool["TEAM_ID"], errors="coerce").eq(tid)].copy()
        if part.empty:
            teams[tid] = part
            continue
        # These are the same existing V2.8.2 role functions and formulas.
        part = rb._redistribute_team_minutes(part)
        part = rb._apply_role(part)
        part = rb._project_stats(part)
        teams[tid] = part.sort_values(["PROJ_MIN", "PROJ_PRA"], ascending=False).reset_index(drop=True)

    source_values = []
    if "USG_SOURCE" in pool.columns:
        source_values = [str(x) for x in pool["USG_SOURCE"].dropna().unique().tolist() if str(x).strip()]
    usage_source = " + ".join(source_values[:4]) if source_values else _source_label(primary_source)
    return {
        "teams": teams,
        "usage_source": usage_source,
        "availability_source": av.get("source") if isinstance(av, dict) else "—",
    }


class _PointsRoleFacade:
    role_projection_for_game = staticmethod(_role_projection_for_game_points)


def _usage_handoff_from_projection(day: str, data: dict):
    # V1.9.8.4.20 already has the correct display fallback. If the repaired
    # protected Points row now carries usage, expose its exact provenance.
    out = dict(data or {})
    if all(_valid_usage(out.get(col)) for col in _USAGE_COLS):
        source = str(out.get("USG_SOURCE") or "PROTECTED POINTS ROLE PIPELINE")
        return out, f"PROTECTED POINTS ROLE PIPELINE • {source}"
    return prior._usage_handoff_identity(day, out)


def _install() -> None:
    # Install prior presentation fixes first, then patch only the isolated Points
    # module's role reference. PRA/Rebounds/Assists continue using wnba_role_v282.
    prior._install()
    points.role = _PointsRoleFacade()
    prior.prior._usage_handoff = _usage_handoff_from_projection


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🧬 Points V1.9.8.4.21 • provider-safe usage identity bridge ACTIVE in Points only • "
        "exact ID → normalized full name → verified ESPN per-player fallback • PRA/other markets untouched"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
