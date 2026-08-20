"""WNBA Daily Picks guard adapter V2 — Assists Connector Step 7.

Extends the frozen Daily Picks Step-10 guard to the four-market selected board:
PRA, Points, Rebounds and Assists. The existing guard logic remains unchanged for
PRA/Points/Rebounds.

The frozen V1 exact-quote gate predates Assists, so Assists rows are evaluated
through the identical player-prop guard contract using a temporary POINTS market
label, then restored immediately to ASSISTS.

Important continuity rule: the 22-column common contract intentionally omits
source-specific availability and tip-time fields. The completed Assists V20 Top-5
payload retains those exact fields because Step 20 used them before publishing.
For Assists only, this adapter reads that already-loaded same-session proof through
the passive connector, matches it to the exact selected quote, and translates it
into the existing V1 Availability/Game-state gate fields on a temporary copy.
Unknown evidence remains MONITOR; bad evidence remains BLOCKED. No guard is
weakened and no source value is mutated.

This adapter is read-only. It launches no simulations, makes no network requests,
refreshes no source model, performs no re-ranking/backfill and writes no source or
Daily Picks production state.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
import re
import unicodedata

import numpy as np
import pandas as pd

import wnba_daily_picks_guard_v1 as v1
import wnba_daily_picks_assists_connector_v1 as assists_connector

MODEL_VERSION = "WNBA DAILY PICKS GUARD V2 • ASSISTS CONNECTOR STEP 7"
STANDARD_SIMS = v1.STANDARD_SIMS
MAX_OUTPUT_AGE_MIN = v1.MAX_OUTPUT_AGE_MIN
GUARD_COLUMNS = list(v1.GUARD_COLUMNS)

_BASE_MARKETS = {"PRA", "POINTS", "REBOUNDS"}
_ET = ZoneInfo("America/New_York")
_GOOD_AVAIL = ("ACTIVE", "AVAILABLE", "STARTER", "CONFIRMED")
_HOLD_AVAIL = ("QUESTIONABLE", "DOUBTFUL", "DAY-TO-DAY", "GTD", "PROBABLE", "GAME TIME DECISION", "REPORTED")
_BAD_AVAIL = ("OUT", "INACTIVE", "SUSPENDED", "DNP", "DID NOT PLAY")


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    s = str(value).strip()
    return "" if s.upper() in {"", "—", "-", "NONE", "NAN", "NULL", "N/A", "NA"} else s


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _num(value: Any) -> float:
    try:
        x = float(value)
        return float(x) if np.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _market_series(frame: pd.DataFrame) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=str)
    return frame.get("Market", pd.Series("", index=frame.index)).astype(str).str.strip().str.upper()


def _proof_key(row: pd.Series) -> tuple[str, str, str, str, float | None, str]:
    line = _num(row.get("Line"))
    return (
        _norm(row.get("Player")),
        _norm(row.get("Team")),
        _norm(row.get("Opponent")),
        _text(row.get("Side")).upper(),
        round(float(line), 6) if np.isfinite(line) else None,
        _norm(row.get("Book")),
    )


def _availability_gate(value: Any) -> str:
    s = _text(value).upper()
    if not s:
        return "SOURCE"
    if any(tok in s for tok in _BAD_AVAIL):
        return "REJECT"
    if any(tok in s for tok in _HOLD_AVAIL):
        return "HOLD"
    if any(tok in s for tok in _GOOD_AVAIL):
        return "PASS"
    return "SOURCE"


def _tip_datetime(value: Any, slate_day: Any) -> datetime | None:
    """Parse full timestamps or display-only ET tip times against the ET slate."""
    s = _text(value)
    day_str = _day(slate_day)
    if not s or not day_str:
        return None

    # Strip a trailing display timezone token; a real ISO offset is preserved.
    clean = re.sub(r"\s+ET$", "", s, flags=re.IGNORECASE).strip()
    has_date = bool(re.search(r"\b\d{4}-\d{1,2}-\d{1,2}\b", clean))

    if has_date:
        try:
            ts = pd.to_datetime(clean, errors="raise")
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.tz_localize(_ET)
            else:
                ts = ts.tz_convert(_ET)
            return ts.to_pydatetime()
        except Exception:
            return None

    # Display-only values such as "8:00 PM ET" are attached to the exact
    # Eastern slate date. This prevents UTC rollover or bare-time ambiguity.
    for fmt in ("%I:%M %p", "%I:%M:%S %p", "%I %p", "%H:%M", "%H:%M:%S"):
        try:
            t = datetime.strptime(clean, fmt).time()
            d = datetime.strptime(day_str, "%Y-%m-%d").date()
            return datetime.combine(d, t, tzinfo=_ET)
        except Exception:
            continue
    return None


def _tip_gate(value: Any, slate_day: Any, now_et: datetime | None) -> str:
    tip = _tip_datetime(value, slate_day)
    if tip is None:
        return "SOURCE"
    now = now_et or datetime.now(_ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    else:
        now = now.astimezone(_ET)
    return "PASS" if tip > now else "REJECT"


def _enrich_assists_final_proof(
    rows: pd.DataFrame,
    slate_day: Any,
    *,
    now_et: datetime | None,
) -> pd.DataFrame:
    """Attach exact Step-20 availability/tip proof to a guard-only copy."""
    if rows is None or rows.empty:
        return rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame()

    out = rows.copy()
    proof = assists_connector.final_guard_proof(slate_day)
    if proof is None or proof.empty:
        out["Assists availability proof"] = "—"
        out["Assists tip proof"] = "—"
        return out

    pmap: dict[tuple[str, str, str, str, float | None, str], pd.Series] = {}
    for _, p in proof.iterrows():
        key = _proof_key(pd.Series({
            "Player": p.get("Player"),
            "Team": p.get("Team"),
            "Opponent": p.get("Opponent"),
            "Side": p.get("Side"),
            "Line": p.get("Line"),
            "Book": p.get("Book"),
        }))
        # Exact duplicates are harmless; first source row wins deterministically.
        pmap.setdefault(key, p)

    enriched: list[dict[str, Any]] = []
    for _, row in out.iterrows():
        rec = row.to_dict()
        src = pmap.get(_proof_key(row))
        if src is None:
            rec["Assists availability proof"] = "—"
            rec["Assists tip proof"] = "—"
            enriched.append(rec)
            continue

        availability = _text(src.get("Availability proof")).upper()
        tip_text = _text(src.get("Tip ET proof"))
        rec["Assists availability proof"] = availability or "—"
        rec["Assists tip proof"] = tip_text or "—"

        current_avail = _text(rec.get("Availability gate")).upper()
        source_avail = _availability_gate(availability)
        if current_avail not in {"REJECT", "HOLD"} and source_avail in {"PASS", "HOLD", "REJECT"}:
            rec["Availability gate"] = source_avail

        current_game = _text(rec.get("Game-state gate")).upper()
        source_game = _tip_gate(tip_text, slate_day, now_et)
        if current_game != "REJECT" and source_game in {"PASS", "REJECT"}:
            rec["Game-state gate"] = source_game

        enriched.append(rec)

    return pd.DataFrame(enriched)


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
        # Restore evidence that was intentionally omitted from the common schema,
        # using only the exact same-session Step-20 source rows.
        assists_rows = _enrich_assists_final_proof(assists_rows, slate_day, now_et=now_et)
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
