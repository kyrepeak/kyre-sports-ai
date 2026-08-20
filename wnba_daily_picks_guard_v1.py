"""WNBA Daily Picks Step 10 — final production-readiness guard.

Consumes only the already-built Step-9 selections plus passive connector metadata.
It never imports/runs PRA, Points or Rebounds production models, never launches or
restores simulations, never refreshes injuries/markets, never makes network calls,
and never writes source-model state.

The guard is intentionally stricter than ranking:
- explicit failure/stale/started/invalid evidence => BLOCKED
- missing finalization, lineup/availability or game-state proof => MONITOR
- only a row with current same-day evidence and source-final readiness => READY

Step 10 does not backfill a held selection with a lower-ranked candidate. It is a
guard, not another ranking engine.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo
import json
import re
import unicodedata

import numpy as np
import pandas as pd

MODEL_VERSION = "WNBA DAILY PICKS GUARD V1 • STEP 10 READ ONLY"
STANDARD_SIMS = 5_000_000
MAX_OUTPUT_AGE_MIN = 15.0
_ET = ZoneInfo("America/New_York")

GUARD_COLUMNS = [
    "Guard state", "Guard reasons", "Finalization gate", "Connector gate",
    "Slate recheck", "Exact quote gate", "Simulation recheck", "Convergence recheck",
    "Availability recheck", "Game-state recheck", "Freshness recheck",
    "Guard checked at ET", "Guard fingerprint",
]

_BAD_QUAL = ("OUT", "INACTIVE", "VOID", "EXPIRED", "CANCEL", "CANCELED", "CANCELLED", "REJECT", "BLOCK")
_HOLD_QUAL = ("MONITOR", "HOLD", "CHECK", "QUESTIONABLE", "DOUBTFUL", "DAY-TO-DAY", "GTD", "PENDING")
_READY_QUAL = ("FINAL READY", "PRODUCTION READY", "READY")
_MISSING = {"", "—", "-", "NONE", "NAN", "NULL", "N/A", "NA"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    s = str(value).strip()
    return "" if s.upper() in _MISSING else s


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


def _bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return _text(value).upper() in {"TRUE", "1", "YES", "Y", "PASS", "VERIFIED", "READY", "CONNECTED", "✅"}


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _timestamp(value: Any) -> datetime | None:
    s = _text(value)
    if not s:
        return None
    try:
        ts = pd.to_datetime(s)
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.tz_localize(_ET)
        else:
            ts = ts.tz_convert(_ET)
        return ts.to_pydatetime()
    except Exception:
        return None


def _fresh_minutes(value: Any) -> float | None:
    s = _text(value).upper()
    if not s:
        return None
    if "STALE" in s or "EXPIRED" in s:
        return float("inf")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(M|MIN|MINS|MINUTE|MINUTES)\b", s)
    if m:
        return float(m.group(1))
    sec = re.search(r"(\d+(?:\.\d+)?)\s*(S|SEC|SECS|SECOND|SECONDS)\b", s)
    if sec:
        return float(sec.group(1)) / 60.0
    if "FRESH" in s:
        return 0.0
    return None


def _feed(market: Any, feeds: dict[str, dict] | None) -> dict:
    feeds = feeds or {}
    return feeds.get(_text(market).upper(), {}) or {}


def _feed_simulation_ok(feed: dict) -> bool:
    try:
        unique = int(float(feed.get("unique_distributions", 0) or 0))
        converged = int(float(feed.get("converged", 0) or 0))
        completed = float(feed.get("completed_sims", 0) or 0)
    except Exception:
        return False
    return bool(feed.get("connected") and unique > 0 and converged >= unique and completed >= unique * STANDARD_SIMS)


def _row_fingerprint(row: pd.Series) -> str:
    payload = {
        "day": _day(row.get("Slate day")),
        "market": _text(row.get("Market")).upper(),
        "player": _norm(row.get("Player")),
        "team": _norm(row.get("Team")),
        "opponent": _norm(row.get("Opponent")),
        "side": _text(row.get("Side")).upper(),
        "line": _num(row.get("Line")),
        "book": _norm(row.get("Book")),
        "odds": _num(row.get("Posted odds")),
        "projection": _num(row.get("Projection")),
        "prob": _num(row.get("Model probability")),
        "sims": _num(row.get("Simulation count")),
        "source_ts": _text(row.get("Source timestamp")),
    }
    text = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(text.encode("utf-8")).hexdigest()[:12]


def _exact_quote_ok(row: pd.Series) -> bool:
    return bool(
        _text(row.get("Market")).upper() in {"PRA", "POINTS", "REBOUNDS"}
        and _text(row.get("Player"))
        and _text(row.get("Team"))
        and _text(row.get("Opponent"))
        and _text(row.get("Side")).upper() in {"OVER", "UNDER"}
        and np.isfinite(_num(row.get("Line")))
        and _text(row.get("Book"))
        and np.isfinite(_num(row.get("Posted odds")))
        and np.isfinite(_num(row.get("Projection")))
        and np.isfinite(_num(row.get("Model probability")))
    )


def evaluate(
    selected: pd.DataFrame,
    slate_day: Any,
    *,
    feeds: dict[str, dict] | None = None,
    now_et: datetime | None = None,
) -> pd.DataFrame:
    """Return Step-10 guard states for Step-9 selections without mutating inputs."""
    target_day = _day(slate_day)
    if selected is None or selected.empty:
        cols = list(selected.columns) if isinstance(selected, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in GUARD_COLUMNS if c not in cols])

    now = now_et or datetime.now(_ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    else:
        now = now.astimezone(_ET)

    records: list[dict[str, Any]] = []
    for _, row in selected.copy().iterrows():
        blocked: list[str] = []
        monitor: list[str] = []
        gates: dict[str, str] = {}
        market = _text(row.get("Market")).upper()
        feed = _feed(market, feeds)

        # The row must still be a Step-9 selection from a Step-8 ranked candidate.
        if _text(row.get("Selection state")).upper() != "SELECTED" or _text(row.get("Rank state")).upper() != "RANKED":
            blocked.append("row is no longer an eligible Step-9 selection")

        # Re-run the most important Step-6 outcomes at guard time.
        safety_state = _text(row.get("Safety state")).upper()
        if safety_state != "SAFE":
            blocked.append(f"Step-6 safety is {safety_state or 'UNKNOWN'}")

        row_day = _day(row.get("Slate day"))
        feed_day = _day(feed.get("day"))
        if not target_day or row_day != target_day or (feed_day and feed_day != target_day):
            blocked.append("slate date no longer matches the current ET slate")
            gates["Slate recheck"] = "BLOCKED"
        else:
            gates["Slate recheck"] = "PASS"

        if not _exact_quote_ok(row):
            blocked.append("exact quote/projection fields are incomplete")
            gates["Exact quote gate"] = "BLOCKED"
        else:
            gates["Exact quote gate"] = "PASS"

        if not feed.get("connected"):
            blocked.append("source connector is no longer connected")
            gates["Connector gate"] = "BLOCKED"
        else:
            gates["Connector gate"] = "PASS"

        row_sims = _num(row.get("Simulation count"))
        sim_ok = (np.isfinite(row_sims) and row_sims >= STANDARD_SIMS) or _feed_simulation_ok(feed)
        if not sim_ok:
            blocked.append("5M production simulation proof is missing")
            gates["Simulation recheck"] = "BLOCKED"
        else:
            gates["Simulation recheck"] = "PASS"

        conv_ok = _bool(row.get("Converged")) or _feed_simulation_ok(feed)
        if not conv_ok:
            blocked.append("Monte Carlo convergence is no longer verified")
            gates["Convergence recheck"] = "BLOCKED"
        else:
            gates["Convergence recheck"] = "PASS"

        availability = _text(row.get("Availability gate")).upper()
        if availability in {"REJECT", "BLOCKED"}:
            blocked.append("player availability failed the current-session recheck")
            gates["Availability recheck"] = "BLOCKED"
        elif availability == "HOLD":
            monitor.append("player availability is uncertain")
            gates["Availability recheck"] = "MONITOR"
        elif availability == "PASS":
            gates["Availability recheck"] = "PASS"
        else:
            # Fail closed at the final card: Step 6 can rank source-verified rows,
            # but Step 10 requires explicit current-session availability evidence.
            monitor.append("explicit current-session player availability proof is missing")
            gates["Availability recheck"] = "MONITOR"

        game_state = _text(row.get("Game-state gate")).upper()
        if game_state in {"REJECT", "BLOCKED"}:
            blocked.append("game is started/final/ineligible")
            gates["Game-state recheck"] = "BLOCKED"
        elif game_state == "PASS":
            gates["Game-state recheck"] = "PASS"
        else:
            monitor.append("explicit current-session UPCOMING game-state proof is missing")
            gates["Game-state recheck"] = "MONITOR"

        # Guard-time freshness cannot trust a static 'FRESH 2m' label forever.
        # Prefer the actual source timestamp when present and use the label only
        # when no timestamp exists (common for the Rebounds production guard).
        source_ts = _timestamp(row.get("Source timestamp")) or _timestamp(feed.get("ran_at"))
        label_age = _fresh_minutes(row.get("Freshness"))
        if source_ts is not None:
            if source_ts.strftime("%Y-%m-%d") != target_day:
                blocked.append("source output is from another slate day")
                gates["Freshness recheck"] = "BLOCKED"
            else:
                age_min = max(0.0, (now - source_ts).total_seconds() / 60.0)
                if age_min > MAX_OUTPUT_AGE_MIN:
                    blocked.append(f"source output stale at guard time ({age_min:.0f}m)")
                    gates["Freshness recheck"] = "BLOCKED"
                else:
                    gates["Freshness recheck"] = "PASS"
        elif label_age is not None:
            if label_age > MAX_OUTPUT_AGE_MIN:
                blocked.append(f"quote stale at guard time ({label_age:.0f}m)")
                gates["Freshness recheck"] = "BLOCKED"
            else:
                gates["Freshness recheck"] = "PASS"
        else:
            monitor.append("freshness proof unavailable at final guard")
            gates["Freshness recheck"] = "MONITOR"

        # Final-card status is deliberately stricter than Step-8 ranking.
        qual = _text(row.get("Qualification state")).upper()
        source = _text(row.get("Source")).upper()
        if any(tok in qual for tok in _BAD_QUAL):
            blocked.append(f"source qualification is {qual}")
            gates["Finalization gate"] = "BLOCKED"
        elif any(tok in qual for tok in _HOLD_QUAL):
            monitor.append(f"source qualification is {qual}")
            gates["Finalization gate"] = "MONITOR"
        elif any(tok in qual for tok in _READY_QUAL) or "PRODUCTION GUARD" in source or "FINAL CARD" in source:
            gates["Finalization gate"] = "PASS"
        elif "QUALIFIED" in qual:
            monitor.append("source row is qualified but not explicitly final-ready")
            gates["Finalization gate"] = "MONITOR"
        else:
            monitor.append("explicit source final-ready state is missing")
            gates["Finalization gate"] = "MONITOR"

        state = "BLOCKED" if blocked else ("MONITOR" if monitor else "READY")
        reasons = blocked if blocked else monitor
        rec = row.to_dict()
        rec.update({
            "Guard state": state,
            "Guard reasons": " • ".join(dict.fromkeys(reasons)) if reasons else "ALL FINAL GUARDS PASSED",
            "Guard checked at ET": now.strftime("%Y-%m-%d %I:%M:%S %p ET"),
            "Guard fingerprint": _row_fingerprint(row),
            **{c: gates.get(c, "—") for c in GUARD_COLUMNS if c not in {"Guard state", "Guard reasons", "Guard checked at ET", "Guard fingerprint"}},
        })
        records.append(rec)

    return pd.DataFrame(records)


def ready_rows(guarded: pd.DataFrame) -> pd.DataFrame:
    if guarded is None or guarded.empty or "Guard state" not in guarded.columns:
        return pd.DataFrame(columns=list(guarded.columns) if isinstance(guarded, pd.DataFrame) else [])
    out = guarded[guarded["Guard state"].astype(str).str.upper().eq("READY")].copy()
    if "Daily rank" in out.columns:
        out = out.sort_values("Daily rank", kind="mergesort", na_position="last")
    return out.reset_index(drop=True)


def diagnostics(guarded: pd.DataFrame) -> dict[str, Any]:
    if guarded is None or guarded.empty:
        return {
            "selected": 0, "ready": 0, "monitor": 0, "blocked": 0,
            "markets": 0, "simulations": 0, "network_requests": 0,
            "source_model_writes": 0,
        }
    states = guarded.get("Guard state", pd.Series(dtype=str)).astype(str).str.upper()
    ready = guarded[states.eq("READY")]
    markets = ready.get("Market", pd.Series(dtype=str)).astype(str).str.upper()
    return {
        "selected": int(len(guarded)),
        "ready": int(states.eq("READY").sum()),
        "monitor": int(states.eq("MONITOR").sum()),
        "blocked": int(states.eq("BLOCKED").sum()),
        "markets": int(markets[markets.str.len().gt(0)].nunique()) if not markets.empty else 0,
        "simulations": 0,
        "network_requests": 0,
        "source_model_writes": 0,
    }


def card_fingerprint(guarded: pd.DataFrame) -> str:
    if guarded is None or guarded.empty:
        return "EMPTY"
    fields = [c for c in (
        "Daily rank", "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
        "Posted odds", "Projection", "Model probability", "Guard state", "Guard fingerprint",
    ) if c in guarded.columns]
    work = guarded[fields].copy()
    if "Daily rank" in work.columns:
        work = work.sort_values("Daily rank", kind="mergesort", na_position="last")
    text = work.to_json(orient="records", date_format="iso", double_precision=10)
    return sha256(text.encode("utf-8")).hexdigest()[:12]


__all__ = [
    "MODEL_VERSION", "STANDARD_SIMS", "MAX_OUTPUT_AGE_MIN", "GUARD_COLUMNS",
    "evaluate", "ready_rows", "diagnostics", "card_fingerprint",
]
