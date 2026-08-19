"""WNBA Daily Picks Step 5 — read-only common-schema adapter.

Reads already-completed same-day PRA, Points and Rebounds session payloads and
maps them into one common Daily Picks table. No production modules are imported;
no simulations, restores, sportsbook calls, injury refreshes, regrades, rankings
or production-state writes occur here.
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd
import streamlit as st

MODEL_VERSION = "WNBA DAILY PICKS STANDARDIZER V1 • STEP 5 READ ONLY"
STANDARD_SIMS = 5_000_000

COMMON_COLUMNS = [
    "Slate day", "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
    "Posted odds", "Projection", "Model probability", "Fair odds",
    "No-vig probability", "Edge", "EV / $100", "Confidence", "Simulation count",
    "Converged", "Qualification state", "Freshness", "Source timestamp", "Source",
]


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, (list, tuple)):
        try:
            return pd.DataFrame(list(value))
        except Exception:
            return pd.DataFrame()
    if isinstance(value, dict):
        try:
            return pd.DataFrame([value])
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _nested_rows(value: Any) -> pd.DataFrame:
    return _frame(value.get("rows")) if isinstance(value, dict) else pd.DataFrame()


def _first(row: pd.Series, aliases: Iterable[str], default: Any = np.nan) -> Any:
    lower = {str(c).strip().lower(): c for c in row.index}
    for name in aliases:
        actual = name if name in row.index else lower.get(str(name).strip().lower())
        if actual is None:
            continue
        value = row.get(actual)
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except Exception:
            pass
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return default


def _num(value: Any) -> float:
    try:
        x = float(value)
        return float(x) if np.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _int_num(value: Any) -> int:
    x = _num(value)
    return int(round(x)) if np.isfinite(x) else 0


def _bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None:
        return False
    return str(value).strip().upper() in {
        "TRUE", "1", "YES", "Y", "PASS", "VERIFIED", "READY", "CONNECTED"
    }


def _american(value: Any) -> Any:
    x = _num(value)
    if np.isfinite(x):
        return int(round(x))
    return value if isinstance(value, str) and value.strip() else np.nan


def _qualification(row: pd.Series) -> str:
    explicit = _first(
        row,
        (
            "Production pick state", "Final card state", "qualification_state",
            "Qualification state", "Decision", "status", "Status",
        ),
        "",
    )
    if str(explicit).strip():
        return str(explicit).strip()
    if _bool(_first(row, ("final_ready", "Final ready"), False)):
        return "FINAL READY"
    if _bool(_first(row, ("model_qualified", "Qualified"), False)):
        return "QUALIFIED"
    return "SOURCE ROW"


def _converged(row: pd.Series) -> bool:
    direct = _first(row, ("converged", "Converged"), None)
    if direct is not None and not (isinstance(direct, float) and np.isnan(direct)):
        return _bool(direct)
    state = str(_first(row, ("MC convergence", "Step17 state"), "")).strip().upper()
    return state in {"PASS", "VERIFIED", "READY"}


def _source_timestamp(payload: Any) -> str:
    value = payload.get("ran_at") if isinstance(payload, dict) else None
    if value is None:
        return "—"
    try:
        return pd.to_datetime(value).isoformat()
    except Exception:
        return str(value)


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COMMON_COLUMNS)


def _normalize_prop_rows(
    rows: pd.DataFrame, *, day: str, market: str, timestamp: str, source: str
) -> pd.DataFrame:
    if rows.empty:
        return _empty()
    records = []
    for _, row in rows.iterrows():
        # PRA/Points production rows expose model_over/no_vig_over; when they do
        # not carry an explicit side they are OVER-side source rows by contract.
        side = str(_first(row, ("side", "Side", "direction", "Direction"), "OVER")).strip().upper() or "OVER"
        if side not in {"OVER", "UNDER"}:
            side = "OVER"
        records.append({
            "Slate day": day,
            "Market": market,
            "Player": _first(row, ("player", "Player", "PLAYER_NAME"), "—"),
            "Team": _first(row, ("team", "Team", "team_name"), "—"),
            "Opponent": _first(row, ("opponent", "Opponent"), "—"),
            "Side": side,
            "Line": _num(_first(row, ("line", "Line"))),
            "Book": _first(row, ("book", "Book"), "—"),
            "Posted odds": _american(_first(row, ("posted_odds", "Posted odds", "odds", "price", "Price"))),
            "Projection": _num(_first(row, ("projection", "Projection", "adj_projection", "Adj PRA", "proj"))),
            "Model probability": _num(_first(row, ("model_probability", "decision_probability", "model_prob", "model_over", "P(Over)"))),
            "Fair odds": _american(_first(row, ("fair_odds", "Fair odds", "model_fair_american", "Model fair American", "fair"))),
            "No-vig probability": _num(_first(row, ("no_vig_probability", "no_vig_over", "no_vig", "No-vig over", "No-vig probability"))),
            "Edge": _num(_first(row, ("edge", "Edge", "no_vig_edge", "No-vig edge"))),
            "EV / $100": _num(_first(row, ("ev100", "EV / $100", "expected_value_100", "Expected value / $100"))),
            "Confidence": _first(row, ("confidence", "Confidence", "confidence_grade", "Confidence grade", "data_quality"), "—"),
            "Simulation count": _int_num(_first(row, ("sims", "Simulation count", "MC simulations"))),
            "Converged": _converged(row),
            "Qualification state": _qualification(row),
            "Freshness": _first(row, ("freshness", "Freshness", "market_age", "Quote freshness"), "—"),
            "Source timestamp": timestamp,
            "Source": source,
        })
    out = pd.DataFrame(records, columns=COMMON_COLUMNS)
    return out.drop_duplicates(["Market", "Player", "Book", "Line", "Side"], keep="first").reset_index(drop=True)


def normalize_pra(day: Any) -> pd.DataFrame:
    day_str = _day(day)
    if not day_str:
        return _empty()
    payload = st.session_state.get(f"wnba_pra_v31_standard::{day_str}")
    return _normalize_prop_rows(
        _nested_rows(payload), day=day_str, market="PRA",
        timestamp=_source_timestamp(payload), source="PRA Step-8 5M",
    )


def normalize_points(day: Any) -> pd.DataFrame:
    day_str = _day(day)
    if not day_str:
        return _empty()
    payload = st.session_state.get(f"wnba_points_v19_standard::{day_str}")
    return _normalize_prop_rows(
        _nested_rows(payload), day=day_str, market="POINTS",
        timestamp=_source_timestamp(payload), source="Points 5M",
    )


def normalize_rebounds(day: Any) -> pd.DataFrame:
    day_str = _day(day)
    if not day_str or _day(st.session_state.get("wnba_rebounds_step1_day")) != day_str:
        return _empty()

    prod = _frame(st.session_state.get("wnba_rebounds_prod_guard_card"))
    final = _frame(st.session_state.get("wnba_rebounds_step20_final_card"))
    qualified = _frame(st.session_state.get("wnba_rebounds_step20_qualified"))
    step17 = _frame(st.session_state.get("wnba_rebounds_step17_players"))
    rows = prod if not prod.empty else (final if not final.empty else qualified)
    if rows.empty:
        rows = step17.copy()
    elif not step17.empty and "Player" in rows.columns and "Player" in step17.columns:
        extra_cols = [c for c in (
            "Player", "Team", "Expected REB", "MC mean REB", "MC median REB",
            "MC simulations", "MC convergence", "Step17 state",
        ) if c in step17.columns]
        extra = step17[extra_cols].copy()
        keys = [c for c in ("Player", "Team") if c in extra.columns]
        if keys:
            extra = extra.drop_duplicates(keys, keep="first")
            on = [c for c in keys if c in rows.columns]
            if on:
                rows = rows.merge(extra, on=on, how="left", suffixes=("", "_step17"))
    if rows.empty:
        return _empty()

    source = "Rebounds production guard" if not prod.empty else (
        "Rebounds Step-20 final card" if not final.empty else (
            "Rebounds Step-20 qualified" if not qualified.empty else "Rebounds Step-17 5M"
        )
    )
    records = []
    for _, row in rows.iterrows():
        sims = _num(_first(row, ("MC simulations", "Simulation count", "sims")))
        if not np.isfinite(sims) and _bool(st.session_state.get("wnba_rebounds_step17_ready")):
            sims = STANDARD_SIMS
        ev = _num(_first(row, ("EV / $100", "ev100", "Expected value / $100")))
        if not np.isfinite(ev):
            roi = _num(_first(row, ("Expected ROI", "expected_roi")))
            ev = roi * 100.0 if np.isfinite(roi) else np.nan
        records.append({
            "Slate day": day_str,
            "Market": "REBOUNDS",
            "Player": _first(row, ("Player", "player"), "—"),
            "Team": _first(row, ("Team", "team"), "—"),
            "Opponent": _first(row, ("Opponent", "opponent"), "—"),
            "Side": str(_first(row, ("Side", "side"), "—")).strip().upper() or "—",
            "Line": _num(_first(row, ("Line", "line"))),
            "Book": _first(row, ("Book", "book"), "—"),
            "Posted odds": _american(_first(row, ("Posted odds", "posted_odds", "Price", "price"))),
            "Projection": _num(_first(row, ("Expected REB", "projection", "Projection", "MC mean REB"))),
            "Model probability": _num(_first(row, ("Model decision probability", "model_probability", "decision_probability"))),
            "Fair odds": _american(_first(row, ("Model fair American", "fair_odds", "Fair odds"))),
            "No-vig probability": _num(_first(row, ("No-vig probability", "no_vig_probability", "No-vig over", "no_vig_over"))),
            "Edge": _num(_first(row, ("No-vig edge", "edge", "Edge"))),
            "EV / $100": ev,
            "Confidence": _first(row, ("Confidence grade", "confidence_grade", "Confidence"), "—"),
            "Simulation count": int(sims) if np.isfinite(sims) else 0,
            "Converged": _converged(row),
            "Qualification state": _qualification(row),
            "Freshness": _first(row, ("Quote freshness", "freshness", "Freshness"), "—"),
            "Source timestamp": "—",
            "Source": source,
        })
    out = pd.DataFrame(records, columns=COMMON_COLUMNS)
    return out.drop_duplicates(["Market", "Player", "Book", "Line", "Side"], keep="first").reset_index(drop=True)


def normalize_all(day: Any) -> pd.DataFrame:
    frames = [normalize_pra(day), normalize_points(day), normalize_rebounds(day)]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return _empty()
    out = pd.concat(frames, ignore_index=True, sort=False)
    for col in COMMON_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    return out[COMMON_COLUMNS].reset_index(drop=True)


def diagnostics(day: Any) -> dict[str, Any]:
    frame = normalize_all(day)
    counts = {m: int((frame["Market"] == m).sum()) for m in ("PRA", "POINTS", "REBOUNDS")}
    missing = 0
    if not frame.empty:
        for col in ("Slate day", "Market", "Player", "Team", "Opponent"):
            s = frame[col]
            bad = s.isna()
            if s.dtype == object:
                bad = bad | s.astype(str).str.strip().isin({"", "—", "nan", "None"})
            missing += int(bad.sum())
    return {
        "day": _day(day), "rows": int(len(frame)), "schema_columns": len(COMMON_COLUMNS),
        "feeds_with_rows": sum(1 for x in counts.values() if x > 0),
        "market_counts": counts, "missing_required_cells": int(missing),
        "ranking_enabled": False, "writes": 0, "simulations": 0,
    }


__all__ = [
    "MODEL_VERSION", "COMMON_COLUMNS", "normalize_pra", "normalize_points",
    "normalize_rebounds", "normalize_all", "diagnostics",
]
