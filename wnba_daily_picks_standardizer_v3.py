"""WNBA Daily Picks common-schema adapter V3 — add Spread read-only rows.

Preserves V2 PRA/Points/Rebounds/Assists normalization and appends only completed
same-day QUALIFIED Spread Step-7 rows from the passive Spread connector.
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

import wnba_daily_picks_standardizer_v2 as v2
import wnba_daily_picks_spread_connector_v1 as spread_feed

MODEL_VERSION = "WNBA DAILY PICKS STANDARDIZER V3 • SPREAD SCHEMA • READ ONLY"
COMMON_COLUMNS = list(v2.COMMON_COLUMNS)
STANDARD_SIMS = 5_000_000


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _empty():
    return pd.DataFrame(columns=COMMON_COLUMNS)


def normalize_spread(day: Any) -> pd.DataFrame:
    day_str = _day(day)
    if not day_str or not spread_feed.status(day_str).get("connected"):
        return _empty()
    rows = spread_feed.preview_rows(day_str, limit=50)
    if rows is None or rows.empty:
        return _empty()
    out = rows.copy()
    for col in COMMON_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    out = out[COMMON_COLUMNS].copy()
    valid = (
        out["Slate day"].map(_day).eq(day_str)
        & out["Market"].astype(str).str.upper().eq("SPREAD")
        & out["Side"].astype(str).str.upper().eq("SPREAD")
        & pd.to_numeric(out["Simulation count"], errors="coerce").fillna(0).ge(STANDARD_SIMS)
        & out["Converged"].fillna(False).astype(bool)
        & out["Qualification state"].astype(str).str.upper().eq("PRODUCTION READY")
    )
    out = out.loc[valid].copy()
    if out.empty:
        return _empty()
    return out.drop_duplicates(["Market","Team","Opponent","Line","Book"], keep="first").reset_index(drop=True)


def normalize_all(day: Any) -> pd.DataFrame:
    base = v2.normalize_all(day)
    spread = normalize_spread(day)
    frames = [f for f in (base, spread) if isinstance(f, pd.DataFrame) and not f.empty]
    if not frames:
        return _empty()
    out = pd.concat(frames, ignore_index=True, sort=False)
    for col in COMMON_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    return out[COMMON_COLUMNS].reset_index(drop=True)


def diagnostics(day: Any) -> dict:
    day_str = _day(day)
    frame = normalize_all(day_str)
    markets = ("PRA","POINTS","REBOUNDS","ASSISTS","SPREAD")
    counts = {m: int(frame["Market"].astype(str).str.upper().eq(m).sum()) if not frame.empty else 0 for m in markets}
    s = spread_feed.status(day_str)
    return {
        "day": day_str,
        "rows": int(len(frame)),
        "market_counts": counts,
        "spread_connected": bool(s.get("connected")),
        "spread_source_picks": int(s.get("production_picks") or 0),
        "spread_schema_rows": counts["SPREAD"],
        "spread_schema_ready": bool(s.get("connected") and counts["SPREAD"] == int(s.get("production_picks") or 0)),
        "simulations": 0, "network_requests": 0, "writes": 0,
    }


__all__ = ["MODEL_VERSION","COMMON_COLUMNS","normalize_spread","normalize_all","diagnostics"]
