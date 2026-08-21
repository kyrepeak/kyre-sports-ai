"""WNBA Daily Picks Spread safety adapter V3.

Evaluates only read-only Spread common-schema rows. Existing four-market safety
engines remain untouched. No network requests, simulations, or source writes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
import re

import numpy as np
import pandas as pd

import wnba_daily_picks_safety_v1 as base
import wnba_daily_picks_spread_connector_v1 as spread_feed

MODEL_VERSION = "WNBA DAILY PICKS SAFETY V3 • SPREAD READ ONLY"
SAFETY_COLUMNS = list(base.SAFETY_COLUMNS)
STANDARD_SIMS = 5_000_000
MAX_QUOTE_AGE_MIN = 15.0
_ET = ZoneInfo("America/New_York")


def _text(v: Any) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v): return ""
    except Exception:
        pass
    s = str(v).strip()
    return "" if s.upper() in {"","—","NONE","NAN","NULL","N/A","NA"} else s


def _num(v: Any) -> float:
    try:
        x = float(v); return x if np.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _day(v: Any) -> str:
    try: return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception: return ""


def _fresh_minutes(v: Any):
    s = _text(v).upper()
    if not s: return None
    if "STALE" in s: return float("inf")
    m = re.search(r"(\d+(?:\.\d+)?)\s*M", s)
    return float(m.group(1)) if m else (0.0 if "FRESH" in s else None)


def _norm(v: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _text(v).lower())


def _proof_map(day_str: str):
    proof = spread_feed.final_guard_proof(day_str)
    out = {}
    if proof is None or proof.empty: return out
    for _, r in proof.iterrows():
        line = _num(r.get("Line"))
        key = (_norm(r.get("Team")), _norm(r.get("Opponent")), round(line,6) if np.isfinite(line) else None, _norm(r.get("Book")))
        out[key] = r
    return out


def _tip(day_str: str, value: Any):
    text = _text(value).replace(" ET", "").strip()
    if not text: return None
    try:
        return pd.Timestamp(f"{day_str} {text}").tz_localize(_ET).to_pydatetime()
    except Exception:
        return None


def evaluate_spread(frame: pd.DataFrame, slate_day: Any, now_et=None) -> pd.DataFrame:
    target = _day(slate_day)
    if frame is None or frame.empty:
        cols = list(frame.columns) if isinstance(frame, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in SAFETY_COLUMNS if c not in cols])
    feed = spread_feed.status(target)
    proofs = _proof_map(target)
    now = now_et or datetime.now(_ET)
    if now.tzinfo is None: now = now.replace(tzinfo=_ET)
    else: now = now.astimezone(_ET)
    records = []
    for _, row in frame.copy().iterrows():
        failures, holds, gates = [], [], {}
        if _day(row.get("Slate day")) != target:
            failures.append("wrong/missing slate date"); gates["Slate gate"] = "REJECT"
        else: gates["Slate gate"] = "PASS"
        team, opp = _text(row.get("Team")), _text(row.get("Opponent"))
        if not team or not opp or _norm(team) == _norm(opp):
            failures.append("team/opponent identity incomplete"); gates["Identity gate"] = "REJECT"
        else: gates["Identity gate"] = "PASS"
        market_ok = bool(
            _text(row.get("Market")).upper() == "SPREAD" and _text(row.get("Side")).upper() == "SPREAD"
            and np.isfinite(_num(row.get("Line"))) and _text(row.get("Book"))
            and np.isfinite(_num(row.get("Posted odds"))) and np.isfinite(_num(row.get("Projection")))
            and 0 <= _num(row.get("Model probability")) <= 1
        )
        if not market_ok:
            failures.append("exact spread/book/odds/projection/probability incomplete"); gates["Market gate"] = "REJECT"
        else: gates["Market gate"] = "PASS"
        sims = _num(row.get("Simulation count"))
        if not feed.get("connected") or not np.isfinite(sims) or sims < STANDARD_SIMS:
            failures.append("5M Spread source proof missing"); gates["Simulation gate"] = "REJECT"
        else: gates["Simulation gate"] = "PASS"
        if bool(row.get("Converged")):
            gates["Convergence gate"] = "PASS"
        else:
            failures.append("Spread Monte Carlo convergence missing"); gates["Convergence gate"] = "REJECT"
        key = (_norm(team), _norm(opp), round(_num(row.get("Line")),6) if np.isfinite(_num(row.get("Line"))) else None, _norm(row.get("Book")))
        proof = proofs.get(key)
        if proof is None:
            failures.append("exact Step-7 final candidate proof missing")
        else:
            if _text(proof.get("Grade proof")).upper() != "QUALIFIED": failures.append("source spread is not QUALIFIED")
        # Step 7 can only run after Spread Step 3 passed; connected Step-7 state is source availability proof.
        if feed.get("connected"): gates["Availability gate"] = "PASS"
        else: gates["Availability gate"] = "REJECT"
        tip = _tip(target, proof.get("Tip ET proof") if proof is not None else None)
        if tip is None:
            holds.append("tip-time proof unavailable"); gates["Game-state gate"] = "HOLD"
        elif tip <= now:
            failures.append("game has reached/passed scheduled tip"); gates["Game-state gate"] = "REJECT"
        else: gates["Game-state gate"] = "PASS"
        age = _fresh_minutes(row.get("Freshness"))
        if age is None:
            holds.append("quote freshness proof unavailable"); gates["Freshness gate"] = "HOLD"
        elif age > MAX_QUOTE_AGE_MIN:
            failures.append(f"spread quote stale ({age:.0f}m)"); gates["Freshness gate"] = "REJECT"
        else: gates["Freshness gate"] = "PASS"
        state = "REJECT" if failures else ("HOLD" if holds else "SAFE")
        rec = row.to_dict()
        rec.update({
            "Safety state": state,
            "Hard failures": " • ".join(dict.fromkeys(failures)) if failures else "none",
            "Holds": " • ".join(dict.fromkeys(holds)) if holds else "none",
            **{c: gates.get(c, "—") for c in SAFETY_COLUMNS if c not in {"Safety state","Hard failures","Holds"}},
        })
        records.append(rec)
    return pd.DataFrame(records)


__all__ = ["MODEL_VERSION","SAFETY_COLUMNS","evaluate_spread"]
