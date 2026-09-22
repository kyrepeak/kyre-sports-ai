"""WNBA Daily Picks common-schema adapter V2 — add Assists read-only rows.

Uses the V1.1 source-contract repair for PRA, Points and Rebounds, then adds only
completed same-day WNBA Assists V20 Step-20 production rows through the verified
read-only connector.

This module performs schema mapping only. It does NOT import an Assists production
module, run/restore simulations, request sportsbook/injury/roster data, change a
projection, requalify a source pick, run Daily Picks safety/ranking/selection, or
write to any production-model session-state key.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import wnba_daily_picks_standardizer_v11 as v1
import wnba_daily_picks_assists_connector_v1 as assists_feed

MODEL_VERSION = "WNBA DAILY PICKS STANDARDIZER V2 • ASSISTS SCHEMA STEP 2 • V1.1 SOURCE CONTRACT • READ ONLY"
STANDARD_SIMS = 5_000_000
COMMON_COLUMNS = list(v1.COMMON_COLUMNS)


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COMMON_COLUMNS)


def normalize_assists(day: Any) -> pd.DataFrame:
    """Return only verified same-day Assists Step-20 production rows."""
    day_str = _day(day)
    if not day_str:
        return _empty()

    status = assists_feed.status(day_str)
    if not bool(status.get("connected")):
        return _empty()

    rows = assists_feed.preview_rows(day_str, limit=100)
    if rows is None or rows.empty:
        # A valid Step-20 0/5 result is connected but contributes zero schema rows.
        return _empty()

    out = rows.copy()
    for col in COMMON_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    out = out[COMMON_COLUMNS].copy()

    # Schema insertion is fail-closed. We do not repair or infer source-model
    # values here; malformed rows stay out of the common table.
    slate_ok = out["Slate day"].map(_day).eq(day_str)
    market_ok = out["Market"].astype(str).str.strip().str.upper().eq("ASSISTS")
    sims = pd.to_numeric(out["Simulation count"], errors="coerce").fillna(0)
    conv = out["Converged"].fillna(False).astype(bool)
    qstate = out["Qualification state"].astype(str).str.strip().str.upper()
    source = out["Source"].astype(str).str.upper()

    valid = (
        slate_ok
        & market_ok
        & sims.ge(STANDARD_SIMS)
        & conv
        & qstate.eq("PRODUCTION READY")
        & source.str.contains("ASSISTS", na=False)
    )
    out = out.loc[valid].copy()
    if out.empty:
        return _empty()

    out["Market"] = "ASSISTS"
    return out.drop_duplicates(
        ["Market", "Player", "Team", "Side", "Line", "Book"], keep="first"
    ).reset_index(drop=True)


def normalize_all(day: Any) -> pd.DataFrame:
    """PRA + Points + Rebounds from repaired V1.1, then append verified Assists."""
    base = v1.normalize_all(day)
    assists = normalize_assists(day)
    frames = [f for f in (base, assists) if isinstance(f, pd.DataFrame) and not f.empty]
    if not frames:
        return _empty()
    out = pd.concat(frames, ignore_index=True, sort=False)
    for col in COMMON_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    return out[COMMON_COLUMNS].reset_index(drop=True)


def diagnostics(day: Any) -> dict[str, Any]:
    day_str = _day(day)
    frame = normalize_all(day_str)
    markets = ("PRA", "POINTS", "REBOUNDS", "ASSISTS")
    counts = {
        m: int(frame["Market"].astype(str).str.upper().eq(m).sum()) if not frame.empty else 0
        for m in markets
    }

    required = (
        "Slate day", "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
        "Posted odds", "Projection", "Model probability", "Simulation count", "Converged",
        "Qualification state", "Source",
    )
    missing = 0
    if not frame.empty:
        for col in required:
            s = frame[col]
            if col in {"Line", "Posted odds", "Projection", "Model probability", "Simulation count"}:
                missing += int(pd.to_numeric(s, errors="coerce").isna().sum())
            else:
                bad = s.isna()
                if s.dtype == object:
                    bad = bad | s.astype(str).str.strip().isin({"", "—", "nan", "None", "N/A"})
                missing += int(bad.sum())

    assists_status = assists_feed.status(day_str)
    assists_rows = counts.get("ASSISTS", 0)
    assists_connected = bool(assists_status.get("connected"))
    # A connected 0/5 source is a valid schema PASS with zero rows.
    assists_schema_ready = bool(assists_connected and (
        assists_rows == int(assists_status.get("production_picks") or 0)
    ))

    return {
        "day": day_str,
        "rows": int(len(frame)),
        "schema_columns": len(COMMON_COLUMNS),
        "feeds_with_rows": sum(1 for x in counts.values() if x > 0),
        "market_counts": counts,
        "missing_required_cells": int(missing),
        "assists_connected": assists_connected,
        "assists_source_picks": int(assists_status.get("production_picks") or 0),
        "assists_schema_rows": assists_rows,
        "assists_schema_ready": assists_schema_ready,
        "safety_enabled_for_assists": False,
        "ranking_enabled_for_assists": False,
        "selection_enabled_for_assists": False,
        "guard_enabled_for_assists": False,
        "writes": 0,
        "simulations": 0,
        "network_requests": 0,
    }


__all__ = [
    "MODEL_VERSION", "COMMON_COLUMNS", "normalize_assists", "normalize_all", "diagnostics",
]
