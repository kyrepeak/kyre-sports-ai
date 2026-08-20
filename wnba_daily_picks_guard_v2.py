"""WNBA Daily Picks guard adapter V2 — Assists Connector Step 7.

Extends the frozen Daily Picks Step-10 guard to the four-market selected board:
PRA, Points, Rebounds and Assists. The existing guard logic remains unchanged for
PRA/Points/Rebounds.

The frozen V1 exact-quote gate predates Assists, so Assists rows are evaluated
through the identical player-prop guard contract using a temporary POINTS market
label, then restored immediately to ASSISTS. The corresponding Assists connector
metadata is supplied only to that isolated guard call. No projection, price,
probability, safety evidence, simulation proof, availability evidence, game-state
evidence or freshness value is changed.

This adapter is read-only. It launches no simulations, makes no network requests,
refreshes no source model, performs no re-ranking/backfill and writes no source or
Daily Picks production state.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

import wnba_daily_picks_guard_v1 as v1

MODEL_VERSION = "WNBA DAILY PICKS GUARD V2 • ASSISTS CONNECTOR STEP 7"
STANDARD_SIMS = v1.STANDARD_SIMS
MAX_OUTPUT_AGE_MIN = v1.MAX_OUTPUT_AGE_MIN
GUARD_COLUMNS = list(v1.GUARD_COLUMNS)

_BASE_MARKETS = {"PRA", "POINTS", "REBOUNDS"}


def _market_series(frame: pd.DataFrame) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=str)
    return frame.get("Market", pd.Series("", index=frame.index)).astype(str).str.strip().str.upper()


def evaluate_four_market(
    selected: pd.DataFrame,
    slate_day: Any,
    *,
    feeds: dict[str, dict] | None = None,
    now_et=None,
) -> pd.DataFrame:
    """Apply the frozen Step-10 guard to selected PRA/Points/Rebounds/Assists rows."""
    if selected is None or selected.empty:
        cols = list(selected.columns) if isinstance(selected, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in GUARD_COLUMNS if c not in cols])

    feeds = feeds or {}
    work = selected.copy().reset_index(drop=True)
    work["__guard_input_order"] = range(len(work))
    market = _market_series(work)

    outputs: list[pd.DataFrame] = []

    base_rows = work.loc[market.isin(_BASE_MARKETS)].copy()
    if not base_rows.empty:
        base_feeds = {m: feeds.get(m, {}) for m in _BASE_MARKETS}
        base_guarded = v1.evaluate(base_rows, slate_day, feeds=base_feeds, now_et=now_et)
        if isinstance(base_guarded, pd.DataFrame) and not base_guarded.empty:
            outputs.append(base_guarded)

    assists_rows = work.loc[market.eq("ASSISTS")].copy()
    if not assists_rows.empty:
        shim = assists_rows.copy()
        shim["Market"] = "POINTS"
        assists_feed = feeds.get("ASSISTS", {}) or {}
        assisted = v1.evaluate(
            shim,
            slate_day,
            feeds={"POINTS": assists_feed},
            now_et=now_et,
        )
        if isinstance(assisted, pd.DataFrame) and not assisted.empty:
            assisted["Market"] = "ASSISTS"
            # Recompute the fingerprint with the true market identity rather than
            # the temporary compatibility label used only inside V1's quote gate.
            assisted["Guard fingerprint"] = [v1._row_fingerprint(row) for _, row in assisted.iterrows()]
            outputs.append(assisted)

    # Unknown markets are fail-closed rather than silently disappearing.
    unknown = work.loc[~market.isin(_BASE_MARKETS | {"ASSISTS"})].copy()
    if not unknown.empty:
        recs = []
        for _, row in unknown.iterrows():
            rec = row.to_dict()
            rec.update({
                "Guard state": "BLOCKED",
                "Guard reasons": "market is not supported by the four-market production guard",
                "Finalization gate": "BLOCKED",
                "Connector gate": "BLOCKED",
                "Slate recheck": "BLOCKED",
                "Exact quote gate": "BLOCKED",
                "Simulation recheck": "BLOCKED",
                "Convergence recheck": "BLOCKED",
                "Availability recheck": "BLOCKED",
                "Game-state recheck": "BLOCKED",
                "Freshness recheck": "BLOCKED",
                "Guard checked at ET": "—",
                "Guard fingerprint": v1._row_fingerprint(row),
            })
            recs.append(rec)
        outputs.append(pd.DataFrame(recs))

    if not outputs:
        return pd.DataFrame(columns=list(work.columns) + [c for c in GUARD_COLUMNS if c not in work.columns])

    guarded = pd.concat(outputs, ignore_index=True, sort=False)
    if "__guard_input_order" in guarded.columns:
        guarded = guarded.sort_values("__guard_input_order", kind="mergesort").drop(columns=["__guard_input_order"], errors="ignore")
    return guarded.reset_index(drop=True)


def ready_rows(guarded: pd.DataFrame) -> pd.DataFrame:
    return v1.ready_rows(guarded)


def diagnostics(guarded: pd.DataFrame, selected: pd.DataFrame | None = None) -> dict[str, Any]:
    diag = dict(v1.diagnostics(guarded))

    def count(frame: pd.DataFrame | None, market_name: str, state: str | None = None) -> int:
        if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
            return 0
        m = _market_series(frame).eq(market_name)
        if state is not None:
            s = frame.get("Guard state", pd.Series("", index=frame.index)).astype(str).str.upper().eq(state)
            m = m & s
        return int(m.sum())

    selected_rows = 0 if selected is None or not isinstance(selected, pd.DataFrame) else int(len(selected))
    guarded_rows = 0 if guarded is None or not isinstance(guarded, pd.DataFrame) else int(len(guarded))
    diag.update({
        "selected_input": selected_rows,
        "guarded_rows": guarded_rows,
        "coverage_pass": bool(guarded_rows == selected_rows),
        "assists_selected": count(selected, "ASSISTS"),
        "assists_ready": count(guarded, "ASSISTS", "READY"),
        "assists_monitor": count(guarded, "ASSISTS", "MONITOR"),
        "assists_blocked": count(guarded, "ASSISTS", "BLOCKED"),
        "four_market_guard": True,
        "simulations": 0,
        "network_requests": 0,
        "source_model_writes": 0,
        "ranking_changes": 0,
        "backfills": 0,
    })
    return diag


def card_fingerprint(guarded: pd.DataFrame) -> str:
    return v1.card_fingerprint(guarded)


__all__ = [
    "MODEL_VERSION", "STANDARD_SIMS", "MAX_OUTPUT_AGE_MIN", "GUARD_COLUMNS",
    "evaluate_four_market", "ready_rows", "diagnostics", "card_fingerprint",
]
