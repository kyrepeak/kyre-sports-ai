"""WNBA Daily Picks protection adapter V2 — Assists Connector Step 4.

Preserves the existing Daily Picks duplicate/correlation protection engine and
feeds it only same-day Assists rows that already cleared Connector Step 3 with
Safety state=SAFE.

This adapter does not rank, select, choose a best quote, run simulations, request
sportsbook/injury data, refresh source models, or write to production state. It
only annotates duplicate quote families and exposure/correlation structure using
the frozen Step-7 protection contract.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

import wnba_daily_picks_protection_v1 as v1

MODEL_VERSION = "WNBA DAILY PICKS PROTECTION V2 • ASSISTS CONNECTOR STEP 4"
PROTECTION_COLUMNS = list(v1.PROTECTION_COLUMNS)


def protect_assists(safety_audit: pd.DataFrame) -> pd.DataFrame:
    """Annotate only SAFE Assists rows with the frozen V1 protection engine."""
    if safety_audit is None or safety_audit.empty:
        cols = list(safety_audit.columns) if isinstance(safety_audit, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in PROTECTION_COLUMNS if c not in cols])

    market = safety_audit.get("Market", pd.Series("", index=safety_audit.index)).astype(str).str.strip().str.upper()
    state = safety_audit.get("Safety state", pd.Series("", index=safety_audit.index)).astype(str).str.strip().str.upper()
    safe = safety_audit.loc[market.eq("ASSISTS") & state.eq("SAFE")].copy()
    if safe.empty:
        return pd.DataFrame(columns=list(safety_audit.columns) + [c for c in PROTECTION_COLUMNS if c not in safety_audit.columns])

    # V1 is already market-agnostic. No compatibility relabeling is required.
    protected = v1.annotate(safe)
    return protected.reset_index(drop=True)


def diagnostics(protected: pd.DataFrame, safety_audit: pd.DataFrame | None = None) -> dict[str, Any]:
    diag = dict(v1.diagnostics(protected))
    input_rows = 0 if safety_audit is None else int(len(safety_audit))
    safe_input = 0
    if isinstance(safety_audit, pd.DataFrame) and not safety_audit.empty:
        market = safety_audit.get("Market", pd.Series("", index=safety_audit.index)).astype(str).str.strip().str.upper()
        state = safety_audit.get("Safety state", pd.Series("", index=safety_audit.index)).astype(str).str.strip().str.upper()
        safe_input = int((market.eq("ASSISTS") & state.eq("SAFE")).sum())
    diag.update({
        "market": "ASSISTS",
        "safety_rows_received": input_rows,
        "safe_rows_received": safe_input,
        "protected_rows": 0 if protected is None else int(len(protected)),
        "coverage_pass": bool((0 if protected is None else len(protected)) == safe_input),
        "ranking_enabled": False,
        "selection_enabled": False,
        "guard_enabled": False,
        "writes": 0,
        "simulations": 0,
        "network_requests": 0,
    })
    return diag


__all__ = ["MODEL_VERSION", "PROTECTION_COLUMNS", "protect_assists", "diagnostics"]
