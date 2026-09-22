"""WNBA Daily Picks common-schema adapter V1.1 — source-contract repair.

This is a read-only repair layer over V1. It does not change any source-model
projection, probability, qualification threshold, Monte Carlo result, ranking,
or sportsbook data. It fixes only source-to-common-schema handoff details:

- PRA / Points source rows publish ``over_odds`` and ``fair_over``; map those
  exact fields into ``Posted odds`` and ``Fair odds`` instead of dropping them.
- Preserve source qualification when a qualified row also carries a presentation
  state such as MONITOR LINEUP, READY or HOLD.
- Rebounds Step-20 publishes ``Market no-vig probability``; map that exact field
  into the common ``No-vig probability`` column.
- Rebounds production-guard/final-card rows remain source-qualified even when the
  later production-readiness guard labels them READY or HOLD.

No values are inferred when the source did not provide them.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

import wnba_daily_picks_standardizer_v1 as base

MODEL_VERSION = "WNBA DAILY PICKS STANDARDIZER V1.1 • SOURCE CONTRACT REPAIR • READ ONLY"
STANDARD_SIMS = base.STANDARD_SIMS
COMMON_COLUMNS = list(base.COMMON_COLUMNS)


def _day(value: Any) -> str:
    return base._day(value)


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COMMON_COLUMNS)


def _source_qualification(row: pd.Series) -> str:
    """Preserve qualification evidence without erasing later readiness states."""
    production = str(base._first(row, ("Production pick state",), "") or "").strip()
    final_card = str(base._first(row, ("Final card state",), "") or "").strip()
    qualification = str(base._first(row, ("qualification_state", "Qualification state"), "") or "").strip()
    decision = str(base._first(row, ("Decision", "status", "Status"), "") or "").strip()

    final_ready = base._bool(base._first(row, ("final_ready", "Final ready"), False))
    model_qualified = base._bool(base._first(row, ("model_qualified", "Qualified"), False))

    evidence = " | ".join(x.upper() for x in (final_card, qualification) if x)
    source_qualified = bool(
        final_ready
        or model_qualified
        or "QUALIFIED" in evidence
        or "PRODUCTION READY" in evidence
    )

    if final_ready:
        return "FINAL READY"

    if source_qualified:
        modifiers = []
        for value in (production, decision):
            upper = value.upper()
            if value and any(token in upper for token in ("HOLD", "MONITOR", "CHECK", "READY")):
                if value not in modifiers:
                    modifiers.append(value)
        return "QUALIFIED" + (" • " + " • ".join(modifiers) if modifiers else "")

    return production or final_card or qualification or decision or "SOURCE ROW"


def _normalize_prop_rows(
    rows: pd.DataFrame, *, day: str, market: str, timestamp: str, source: str
) -> pd.DataFrame:
    if rows is None or rows.empty:
        return _empty()

    records = []
    for _, row in rows.iterrows():
        side = str(base._first(row, ("side", "Side", "direction", "Direction"), "OVER")).strip().upper() or "OVER"
        if side not in {"OVER", "UNDER"}:
            side = "OVER"

        records.append({
            "Slate day": day,
            "Market": market,
            "Player": base._first(row, ("player", "Player", "PLAYER_NAME"), "—"),
            "Team": base._first(row, ("team", "Team", "team_name"), "—"),
            "Opponent": base._first(row, ("opponent", "Opponent"), "—"),
            "Side": side,
            "Line": base._num(base._first(row, ("line", "Line"))),
            "Book": base._first(row, ("book", "Book"), "—"),
            "Posted odds": base._american(base._first(
                row,
                ("posted_odds", "Posted odds", "over_odds", "overOdds", "odds", "price", "Price"),
            )),
            "Projection": base._num(base._first(
                row, ("projection", "Projection", "adj_projection", "Adj PRA", "proj")
            )),
            "Model probability": base._num(base._first(
                row, ("model_probability", "decision_probability", "model_prob", "model_over", "P(Over)")
            )),
            "Fair odds": base._american(base._first(
                row,
                ("fair_odds", "Fair odds", "fair_over", "fairOver", "model_fair_american", "Model fair American", "fair"),
            )),
            "No-vig probability": base._num(base._first(
                row, ("no_vig_probability", "no_vig_over", "no_vig", "No-vig over", "No-vig probability")
            )),
            "Edge": base._num(base._first(row, ("edge", "Edge", "no_vig_edge", "No-vig edge"))),
            "EV / $100": base._num(base._first(
                row, ("ev100", "EV / $100", "expected_value_100", "Expected value / $100")
            )),
            "Confidence": base._first(
                row, ("confidence", "Confidence", "confidence_grade", "Confidence grade", "data_quality"), "—"
            ),
            "Simulation count": base._int_num(base._first(row, ("sims", "Simulation count", "MC simulations"))),
            "Converged": base._converged(row),
            "Qualification state": _source_qualification(row),
            "Freshness": base._first(row, ("freshness", "Freshness", "market_age", "Quote freshness"), "—"),
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
        base._nested_rows(payload),
        day=day_str,
        market="PRA",
        timestamp=base._source_timestamp(payload),
        source="PRA Step-8 5M",
    )


def normalize_points(day: Any) -> pd.DataFrame:
    day_str = _day(day)
    if not day_str:
        return _empty()
    payload = st.session_state.get(f"wnba_points_v19_standard::{day_str}")
    return _normalize_prop_rows(
        base._nested_rows(payload),
        day=day_str,
        market="POINTS",
        timestamp=base._source_timestamp(payload),
        source="Points 5M",
    )


def normalize_rebounds(day: Any) -> pd.DataFrame:
    day_str = _day(day)
    if not day_str or _day(st.session_state.get("wnba_rebounds_step1_day")) != day_str:
        return _empty()

    prod = base._frame(st.session_state.get("wnba_rebounds_prod_guard_card"))
    final = base._frame(st.session_state.get("wnba_rebounds_step20_final_card"))
    qualified = base._frame(st.session_state.get("wnba_rebounds_step20_qualified"))
    step17 = base._frame(st.session_state.get("wnba_rebounds_step17_players"))
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
        sims = base._num(base._first(row, ("MC simulations", "Simulation count", "sims")))
        if not np.isfinite(sims) and base._bool(st.session_state.get("wnba_rebounds_step17_ready")):
            sims = STANDARD_SIMS

        ev = base._num(base._first(row, ("EV / $100", "ev100", "Expected value / $100")))
        if not np.isfinite(ev):
            roi = base._num(base._first(row, ("Expected ROI", "expected_roi")))
            ev = roi * 100.0 if np.isfinite(roi) else np.nan

        records.append({
            "Slate day": day_str,
            "Market": "REBOUNDS",
            "Player": base._first(row, ("Player", "player"), "—"),
            "Team": base._first(row, ("Team", "team"), "—"),
            "Opponent": base._first(row, ("Opponent", "opponent"), "—"),
            "Side": str(base._first(row, ("Side", "side"), "—")).strip().upper() or "—",
            "Line": base._num(base._first(row, ("Line", "line"))),
            "Book": base._first(row, ("Book", "book"), "—"),
            "Posted odds": base._american(base._first(row, ("Posted odds", "posted_odds", "Price", "price"))),
            "Projection": base._num(base._first(row, ("Expected REB", "projection", "Projection", "MC mean REB"))),
            "Model probability": base._num(base._first(row, ("Model decision probability", "model_probability", "decision_probability"))),
            "Fair odds": base._american(base._first(row, ("Model fair American", "fair_odds", "Fair odds"))),
            "No-vig probability": base._num(base._first(
                row,
                ("Market no-vig probability", "No-vig probability", "no_vig_probability", "No-vig over", "no_vig_over"),
            )),
            "Edge": base._num(base._first(row, ("No-vig edge", "edge", "Edge"))),
            "EV / $100": ev,
            "Confidence": base._first(row, ("Confidence grade", "confidence_grade", "Confidence"), "—"),
            "Simulation count": int(sims) if np.isfinite(sims) else 0,
            "Converged": base._converged(row),
            "Qualification state": _source_qualification(row),
            "Freshness": base._first(row, ("Quote freshness", "freshness", "Freshness"), "—"),
            "Source timestamp": "—",
            "Source": source,
        })

    out = pd.DataFrame(records, columns=COMMON_COLUMNS)
    return out.drop_duplicates(["Market", "Player", "Book", "Line", "Side"], keep="first").reset_index(drop=True)


def normalize_all(day: Any) -> pd.DataFrame:
    frames = [normalize_pra(day), normalize_points(day), normalize_rebounds(day)]
    frames = [f for f in frames if isinstance(f, pd.DataFrame) and not f.empty]
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
        "day": _day(day),
        "rows": int(len(frame)),
        "schema_columns": len(COMMON_COLUMNS),
        "feeds_with_rows": sum(1 for x in counts.values() if x > 0),
        "market_counts": counts,
        "missing_required_cells": int(missing),
        "ranking_enabled": False,
        "writes": 0,
        "simulations": 0,
    }


__all__ = [
    "MODEL_VERSION", "COMMON_COLUMNS", "normalize_pra", "normalize_points",
    "normalize_rebounds", "normalize_all", "diagnostics",
]
