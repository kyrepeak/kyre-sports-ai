"""WNBA Daily Picks safety adapter V2 — Assists Connector Step 3.

Preserves the existing Step-6 Daily Picks safety engine exactly for PRA, Points
and Rebounds, while allowing verified standardized Assists rows to be evaluated
through the same gate logic without editing the frozen V1 implementation.

Implementation detail: V1's exact-market gate predates Assists and accepts only
PRA/POINTS/REBOUNDS. For Assists rows only, this adapter temporarily labels the
market as POINTS solely while V1 evaluates the shared safety contract, then
restores Market=ASSISTS in the returned audit. No source value, projection,
probability, price, simulation result, availability evidence, game-state evidence
or freshness evidence is changed.

This module is read-only. It runs no simulations, performs no network requests,
changes no source-model state, and performs no ranking or selection.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

import wnba_daily_picks_safety_v1 as v1
import wnba_daily_picks_assists_connector_v1 as assists_feed

MODEL_VERSION = "WNBA DAILY PICKS SAFETY V2 • ASSISTS CONNECTOR STEP 3"
STANDARD_SIMS = v1.STANDARD_SIMS
MAX_QUOTE_AGE_MIN = v1.MAX_QUOTE_AGE_MIN
SAFETY_COLUMNS = list(v1.SAFETY_COLUMNS)


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def evaluate_assists(
    frame: pd.DataFrame,
    slate_day: Any,
    *,
    now_et: datetime | None = None,
) -> pd.DataFrame:
    """Evaluate only Assists rows through the frozen V1 safety contract."""
    day_str = _day(slate_day)
    if frame is None or frame.empty:
        cols = list(frame.columns) if isinstance(frame, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in SAFETY_COLUMNS if c not in cols])

    assists = frame.loc[
        frame.get("Market", pd.Series("", index=frame.index))
        .astype(str).str.strip().str.upper().eq("ASSISTS")
    ].copy()
    if assists.empty:
        return pd.DataFrame(columns=list(frame.columns) + [c for c in SAFETY_COLUMNS if c not in frame.columns])

    # Compatibility shim only. V1's market gate is otherwise identical for all
    # player-prop rows. Restore ASSISTS immediately after V1 returns.
    shim = assists.copy()
    shim["Market"] = "POINTS"
    feed = assists_feed.status(day_str)
    audited = v1.evaluate(
        shim,
        day_str,
        feeds={"POINTS": feed},
        now_et=now_et,
    )
    if not audited.empty:
        audited["Market"] = "ASSISTS"
    return audited.reset_index(drop=True)


def diagnostics(audit: pd.DataFrame) -> dict[str, Any]:
    diag = dict(v1.diagnostics(audit))
    diag.update({
        "market": "ASSISTS",
        "compatibility_adapter": True,
        "ranking_enabled": False,
        "selection_enabled": False,
        "guard_enabled": False,
        "writes": 0,
        "simulations": 0,
        "network_requests": 0,
    })
    return diag


__all__ = [
    "MODEL_VERSION", "STANDARD_SIMS", "MAX_QUOTE_AGE_MIN", "SAFETY_COLUMNS",
    "evaluate_assists", "diagnostics",
]
