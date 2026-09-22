"""WNBA Daily Picks — Step 2 PRA read-only connector.

This connector is intentionally passive. It reads only the same-day PRA Step-8
payloads already present in Streamlit session state. It does NOT import PRA
production modules, run/restore/regrade Monte Carlo, call sportsbooks, refresh
injuries, mutate PRA session keys, or select Daily Picks.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

MODEL_VERSION = "WNBA DAILY PICKS PRA CONNECTOR V1 • READ ONLY"
STANDARD_SIMS = 5_000_000
FINAL_SIMS = 10_000_000


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _std_key(day: Any) -> str:
    return f"wnba_pra_v31_standard::{_day(day)}"


def _final_key(day: Any) -> str:
    return f"wnba_pra_v31_final::{_day(day)}"


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


def _unique_distributions(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    keys = [c for c in ("game_id", "player_key", "line") if c in frame.columns]
    if len(keys) == 3:
        return int(frame[keys].drop_duplicates().shape[0])
    return 0


def _completed_sims(frame: pd.DataFrame) -> int:
    if frame.empty or "sims" not in frame.columns:
        return 0
    keys = [c for c in ("game_id", "player_key", "line") if c in frame.columns]
    sims = pd.to_numeric(frame["sims"], errors="coerce").fillna(0)
    if len(keys) == 3:
        temp = frame[keys].copy()
        temp["sims"] = sims
        return int(temp.groupby(keys, dropna=False)["sims"].first().sum())
    return int(sims.sum())


def _converged(frame: pd.DataFrame) -> int:
    if frame.empty or "converged" not in frame.columns:
        return 0
    keys = [c for c in ("game_id", "player_key", "line") if c in frame.columns]
    if len(keys) == 3:
        temp = frame[keys + ["converged"]].drop_duplicates(subset=keys, keep="first")
        return int(temp["converged"].fillna(False).astype(bool).sum())
    return _bool_count(frame, "converged")


def status(day: Any) -> dict[str, Any]:
    """Return a read-only health snapshot for the requested ET slate day."""
    day_str = _day(day)
    if not day_str:
        return {
            "day": "",
            "state": "NEXT",
            "connected": False,
            "detail": "No valid Daily Picks slate day.",
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

    # READS ONLY. Do not use setdefault/pop/update or assign to session_state here.
    standard = st.session_state.get(_std_key(day_str))
    final = st.session_state.get(_final_key(day_str))

    std_rows = _frame((standard or {}).get("rows") if isinstance(standard, dict) else None)
    fin_rows = _frame((final or {}).get("rows") if isinstance(final, dict) else None)

    if std_rows.empty:
        return {
            "day": day_str,
            "state": "⏳ NOT RUN",
            "connected": False,
            "detail": "No completed same-day PRA 5M payload is present in this Streamlit session.",
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

    unique = _unique_distributions(std_rows)
    sims = _completed_sims(std_rows)
    converged = _converged(std_rows)
    qualified = _bool_count(std_rows, "model_qualified")
    final_ready = _bool_count(std_rows, "final_ready")
    monitor = 0
    if "model_qualified" in std_rows.columns and "final_ready" in std_rows.columns:
        try:
            monitor = int(
                (
                    std_rows["model_qualified"].fillna(False).astype(bool)
                    & ~std_rows["final_ready"].fillna(False).astype(bool)
                ).sum()
            )
        except Exception:
            monitor = 0

    expected_min = unique * STANDARD_SIMS
    fully_completed = unique > 0 and sims >= expected_min
    fully_converged = unique > 0 and converged == unique
    connected = bool(fully_completed and fully_converged)
    state = "✅ CONNECTED" if connected else "⚠ CHECK"
    source = "5M + 10M finalists" if not fin_rows.empty else "5M"
    detail = (
        f"Read-only PRA payload • {unique} distributions • {sims:,} completed sims • "
        f"{qualified} qualified • {final_ready} final ready"
    )
    if not connected:
        detail += " • completion/convergence validation did not fully pass"

    return {
        "day": day_str,
        "state": state,
        "connected": connected,
        "detail": detail,
        "source": source,
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
    """Return display-only PRA rows. No ranking or qualification is performed here."""
    day_str = _day(day)
    if not day_str:
        return pd.DataFrame()
    standard = st.session_state.get(_std_key(day_str))
    rows = _frame((standard or {}).get("rows") if isinstance(standard, dict) else None)
    if rows.empty:
        return pd.DataFrame()

    cols = [
        c for c in (
            "player", "team", "opponent", "book", "line", "projection",
            "model_over", "no_vig_over", "edge", "freshness", "converged",
            "model_qualified", "final_ready", "status", "sims",
        ) if c in rows.columns
    ]
    out = rows[cols].copy()
    if "player" in out.columns:
        out = out.drop_duplicates(subset=[c for c in ("player", "book", "line") if c in out.columns], keep="first")
    return out.head(max(1, int(limit))).reset_index(drop=True)


__all__ = ["MODEL_VERSION", "status", "preview_rows"]
