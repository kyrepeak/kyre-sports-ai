"""WNBA Daily Picks — Step 3 Points read-only connector.

Passive state inspector for the current WNBA Points V1.9 production payload.
It reads only already-completed same-day Points 5M/10M rows from Streamlit
session state. It does NOT import any Points production module, restore a saved
snapshot, run Monte Carlo, call SportsGameOdds, refresh injuries/lineups,
regrade rows, change projections, mutate Points state, or select Daily Picks.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

MODEL_VERSION = "WNBA DAILY PICKS POINTS CONNECTOR V1 • READ ONLY"
STANDARD_SIMS = 5_000_000
FINAL_SIMS = 10_000_000


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _std_key(day: Any) -> str:
    return f"wnba_points_v19_standard::{_day(day)}"


def _final_key(day: Any) -> str:
    return f"wnba_points_v19_final::{_day(day)}"


def _source_key(day: Any) -> str:
    return f"wnba_points_v19_restore_source::{_day(day)}"


def _frame(value: Any) -> pd.DataFrame:
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _timestamp(value: Any) -> str:
    if value is None:
        return "—"
    try:
        ts = pd.to_datetime(value)
        if getattr(ts, "tzinfo", None) is not None:
            return ts.strftime("%Y-%m-%d %I:%M:%S %p %Z")
        return ts.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception:
        return str(value)


def _bool_count(frame: pd.DataFrame, column: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    try:
        return int(frame[column].fillna(False).astype(bool).sum())
    except Exception:
        return 0


def _unit_keys(frame: pd.DataFrame) -> list[str]:
    keys = [c for c in ("game_id", "player_key", "line") if c in frame.columns]
    return keys if len(keys) == 3 else []


def _unique_distributions(frame: pd.DataFrame) -> int:
    keys = _unit_keys(frame)
    if frame.empty or not keys:
        return 0
    return int(frame[keys].drop_duplicates().shape[0])


def _completed_sims(frame: pd.DataFrame) -> int:
    keys = _unit_keys(frame)
    if frame.empty or "sims" not in frame.columns or not keys:
        return 0
    temp = frame[keys].copy()
    temp["sims"] = pd.to_numeric(frame["sims"], errors="coerce").fillna(0)
    return int(temp.groupby(keys, dropna=False)["sims"].first().sum())


def _converged(frame: pd.DataFrame) -> int:
    keys = _unit_keys(frame)
    if frame.empty or "converged" not in frame.columns or not keys:
        return 0
    temp = frame[keys + ["converged"]].drop_duplicates(subset=keys, keep="first")
    return int(temp["converged"].fillna(False).astype(bool).sum())


def _unique_true_rows(frame: pd.DataFrame, column: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    subset = frame.loc[frame[column].fillna(False).astype(bool)].copy()
    if subset.empty:
        return 0
    keys = [c for c in ("game_id", "player_key", "line", "book") if c in subset.columns]
    if keys:
        subset = subset.drop_duplicates(subset=keys, keep="first")
    return int(len(subset))


def status(day: Any) -> dict[str, Any]:
    """Return a read-only health snapshot for the requested ET slate day."""
    day_str = _day(day)
    empty = {
        "day": day_str,
        "state": "⏳ NOT RUN" if day_str else "NEXT",
        "connected": False,
        "detail": "No completed same-day Points 5M payload is present in this Streamlit session." if day_str else "No valid Daily Picks slate day.",
        "source": "NONE",
        "rows": 0,
        "unique_distributions": 0,
        "completed_sims": 0,
        "converged": 0,
        "qualified": 0,
        "final_ready": 0,
        "monitor": 0,
        "finalist_rows": 0,
        "ran_at": "—",
        "final_ran_at": "—",
    }
    if not day_str:
        return empty

    # READS ONLY. No setdefault/pop/update/assignment to session_state is allowed.
    standard = st.session_state.get(_std_key(day_str))
    final = st.session_state.get(_final_key(day_str))
    source = st.session_state.get(_source_key(day_str))

    std_rows = _frame((standard or {}).get("rows") if isinstance(standard, dict) else None)
    fin_rows = _frame((final or {}).get("rows") if isinstance(final, dict) else None)
    if std_rows.empty:
        return empty

    unique = _unique_distributions(std_rows)
    sims = _completed_sims(std_rows)
    converged = _converged(std_rows)
    qualified = _unique_true_rows(std_rows, "model_qualified")
    final_ready = _unique_true_rows(std_rows, "final_ready")
    monitor = 0
    if "model_qualified" in std_rows.columns and "final_ready" in std_rows.columns:
        try:
            mon = std_rows.loc[
                std_rows["model_qualified"].fillna(False).astype(bool)
                & ~std_rows["final_ready"].fillna(False).astype(bool)
            ].copy()
            keys = [c for c in ("game_id", "player_key", "line", "book") if c in mon.columns]
            if keys:
                mon = mon.drop_duplicates(subset=keys, keep="first")
            monitor = int(len(mon))
        except Exception:
            monitor = 0

    expected_min = unique * STANDARD_SIMS
    fully_completed = unique > 0 and sims >= expected_min
    fully_converged = unique > 0 and converged == unique
    connected = bool(fully_completed and fully_converged)
    state = "✅ CONNECTED" if connected else "⚠ CHECK"
    pass_source = "5M + 10M finalists" if not fin_rows.empty else "5M"
    persisted_source = str(source or "active session")
    detail = (
        f"Read-only Points payload • {unique} distributions • {sims:,} completed sims • "
        f"{qualified} qualified rows • {final_ready} final-ready rows"
    )
    if not connected:
        detail += " • completion/convergence validation did not fully pass"

    return {
        "day": day_str,
        "state": state,
        "connected": connected,
        "detail": detail,
        "source": pass_source,
        "persistence_source": persisted_source,
        "rows": int(len(std_rows)),
        "unique_distributions": unique,
        "completed_sims": sims,
        "converged": converged,
        "qualified": qualified,
        "final_ready": final_ready,
        "monitor": monitor,
        "finalist_rows": int(len(fin_rows)),
        "ran_at": _timestamp((standard or {}).get("ran_at") if isinstance(standard, dict) else None),
        "final_ran_at": _timestamp((final or {}).get("ran_at") if isinstance(final, dict) else None),
    }


def preview_rows(day: Any, limit: int = 12) -> pd.DataFrame:
    """Return display-only Points rows. No ranking or qualification is performed."""
    day_str = _day(day)
    if not day_str:
        return pd.DataFrame()
    standard = st.session_state.get(_std_key(day_str))
    rows = _frame((standard or {}).get("rows") if isinstance(standard, dict) else None)
    if rows.empty:
        return pd.DataFrame()

    cols = [
        c for c in (
            "market", "player", "team", "opponent", "book", "line", "projection",
            "sim_mean", "sim_median", "model_over", "no_vig_over", "edge", "ev100",
            "freshness", "lineup_ready", "converged", "model_qualified", "final_ready",
            "status", "sims", "pass_source",
        ) if c in rows.columns
    ]
    out = rows[cols].copy()
    keys = [c for c in ("player", "book", "line") if c in out.columns]
    if keys:
        out = out.drop_duplicates(subset=keys, keep="first")
    return out.head(max(1, int(limit))).reset_index(drop=True)


__all__ = ["MODEL_VERSION", "status", "preview_rows"]
