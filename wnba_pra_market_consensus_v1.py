"""Read-only multi-book market summary for WNBA PRA presentation."""
from __future__ import annotations

import math
from typing import Any
import pandas as pd

COLUMNS = [
    "player_key", "player", "book_count", "books", "consensus_line",
    "min_line", "max_line", "best_over_odds", "evidence_state", "current_quote_count",
]


def _current(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    freshness = frame.get("freshness", pd.Series([""] * len(frame), index=frame.index)).astype(str).str.upper()
    return frame.loc[~freshness.eq("STALE")].copy()


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def build_market_consensus(graded: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(graded, pd.DataFrame) or graded.empty:
        return pd.DataFrame(columns=COLUMNS)

    src = graded.copy(deep=True)
    if "player_key" not in src.columns:
        src["player_key"] = src.get("player", pd.Series([""] * len(src), index=src.index)).astype(str).str.strip().str.lower()
    if "player" not in src.columns:
        src["player"] = src["player_key"]
    if "book" not in src.columns:
        src["book"] = ""

    rows: list[dict[str, Any]] = []
    for player_key, group in src.groupby("player_key", sort=False, dropna=False):
        group = group.copy()
        books = tuple(dict.fromkeys(str(v) for v in group["book"].tolist() if str(v).strip()))
        current = _current(group)
        current_books = tuple(dict.fromkeys(str(v) for v in current["book"].tolist() if str(v).strip()))
        lines = _num(current.get("line", pd.Series(dtype=float))).dropna()
        odds = _num(current.get("over_odds", pd.Series(dtype=float))).dropna()
        if len(current_books) >= 2:
            evidence = "VERIFIED_MULTI_SOURCE"
        elif len(current_books) == 1:
            evidence = "SINGLE_SOURCE"
        else:
            evidence = "STALE"
        consensus = float(lines.median()) if not lines.empty else math.nan
        min_line = float(lines.min()) if not lines.empty else math.nan
        max_line = float(lines.max()) if not lines.empty else math.nan
        best_odds = float(odds.max()) if not odds.empty else math.nan
        if not math.isnan(best_odds) and best_odds.is_integer():
            best_odds = int(best_odds)
        rows.append({
            "player_key": str(player_key),
            "player": str(group.iloc[0].get("player") or player_key),
            "book_count": len(books),
            "books": books,
            "consensus_line": consensus,
            "min_line": min_line,
            "max_line": max_line,
            "best_over_odds": best_odds,
            "evidence_state": evidence,
            "current_quote_count": len(current_books),
        })
    return pd.DataFrame(rows, columns=COLUMNS)


__all__ = ["build_market_consensus"]
