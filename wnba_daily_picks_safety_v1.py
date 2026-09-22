"""WNBA Daily Picks Step 6 — read-only production safety gates.

Consumes only the Step-5 standardized PRA / Points / Rebounds rows plus passive
connector metadata. It never imports a production model, runs/restores a
simulation, requests sportsbook/network data, refreshes injuries, regrades a
source model, ranks picks, or writes Streamlit production state.

The gate is deliberately fail-safe:
- explicit bad/stale/started/OUT evidence => REJECT
- incomplete/uncertain evidence => HOLD
- only rows that clear every available hard gate => SAFE

Missing source values are never invented.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
import re

import numpy as np
import pandas as pd
import streamlit as st

MODEL_VERSION = "WNBA DAILY PICKS SAFETY V1 • STEP 6 READ ONLY"
STANDARD_SIMS = 5_000_000
MAX_QUOTE_AGE_MIN = 15.0
_ET = ZoneInfo("America/New_York")

SAFETY_COLUMNS = [
    "Safety state", "Hard failures", "Holds", "Slate gate", "Identity gate",
    "Market gate", "Simulation gate", "Convergence gate", "Availability gate",
    "Game-state gate", "Freshness gate",
]

_BAD_QUAL = ("OUT", "INACTIVE", "VOID", "EXPIRED", "CANCEL", "CANCELED", "CANCELLED")
_HOLD_QUAL = ("MONITOR", "HOLD", "CHECK", "QUESTIONABLE", "DOUBTFUL", "DAY-TO-DAY", "GTD", "PENDING")
_BAD_GAME = ("FINAL", "IN PROGRESS", "LIVE", "STARTED", "HALFTIME", "END OF", "POSTPONED", "CANCELED", "CANCELLED")
_GOOD_GAME = ("UPCOMING", "SCHEDULED", "PRE", "PREGAME", "NOT STARTED")
_BAD_AVAIL = ("OUT", "INACTIVE", "SUSPENDED", "DNP", "DID NOT PLAY")
_HOLD_AVAIL = ("QUESTIONABLE", "DOUBTFUL", "DAY-TO-DAY", "GTD", "PROBABLE", "GAME TIME DECISION")
_GOOD_AVAIL = ("ACTIVE", "AVAILABLE", "STARTER", "CONFIRMED")
_MISSING_TEXT = {"", "—", "-", "NONE", "NAN", "NULL", "N/A", "NA"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    s = str(value).strip()
    return "" if s.upper() in _MISSING_TEXT else s


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


def _frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, (list, tuple)):
        try:
            return pd.DataFrame(list(value))
        except Exception:
            return pd.DataFrame()
    if isinstance(value, dict):
        # Common session payloads wrap table rows under `rows`.
        if isinstance(value.get("rows"), (list, tuple, pd.DataFrame)):
            return _frame(value.get("rows"))
        try:
            return pd.DataFrame([value])
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _market_feed(market: str, feeds: dict[str, dict] | None) -> dict:
    feeds = feeds or {}
    return feeds.get(str(market).strip().upper(), {}) or {}


def _feed_simulation_proof(feed: dict) -> bool:
    unique = int(_num(feed.get("unique_distributions")) if np.isfinite(_num(feed.get("unique_distributions"))) else 0)
    converged = int(_num(feed.get("converged")) if np.isfinite(_num(feed.get("converged"))) else 0)
    completed = _num(feed.get("completed_sims"))
    return bool(
        feed.get("connected")
        and unique > 0
        and converged >= unique
        and np.isfinite(completed)
        and completed >= unique * STANDARD_SIMS
    )


def _parse_timestamp(value: Any) -> datetime | None:
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


def _freshness_minutes(value: Any) -> float | None:
    s = _text(value).upper()
    if not s:
        return None
    if "STALE" in s or "EXPIRED" in s:
        return float("inf")
    # Handles: 2m, 2 min, FRESH (2m), <=5m, ≤5m, 90s.
    m = re.search(r"(\d+(?:\.\d+)?)\s*(M|MIN|MINS|MINUTE|MINUTES)\b", s)
    if m:
        return float(m.group(1))
    sec = re.search(r"(\d+(?:\.\d+)?)\s*(S|SEC|SECS|SECOND|SECONDS)\b", s)
    if sec:
        return float(sec.group(1)) / 60.0
    if "FRESH" in s:
        return 0.0
    return None


def _candidate_session_frames(tokens: tuple[str, ...], max_keys: int = 160) -> list[tuple[str, pd.DataFrame]]:
    found: list[tuple[str, pd.DataFrame]] = []
    # Read-only inspection only. We intentionally never assign/delete session keys.
    try:
        keys = list(st.session_state.keys())[:max_keys]
    except Exception:
        return found
    for key in keys:
        name = str(key).lower()
        if not any(t in name for t in tokens):
            continue
        try:
            frame = _frame(st.session_state.get(key))
        except Exception:
            continue
        if not frame.empty and len(frame.columns) <= 80:
            found.append((str(key), frame.head(500)))
    return found


def _find_player_availability(player: str) -> tuple[str, str]:
    player_key = _text(player).lower()
    if not player_key:
        return "UNKNOWN", ""
    evidence: list[str] = []
    for _, frame in _candidate_session_frames(("injur", "avail", "roster", "status")):
        lower = {str(c).strip().lower(): c for c in frame.columns}
        pcol = next((lower[x] for x in ("player", "player name", "player_name", "name") if x in lower), None)
        scol = next((lower[x] for x in ("status", "availability", "designation", "injury status", "injury_status", "state") if x in lower), None)
        if pcol is None or scol is None:
            continue
        try:
            matched = frame[frame[pcol].astype(str).str.strip().str.lower() == player_key]
        except Exception:
            continue
        for value in matched[scol].tolist():
            s = _text(value).upper()
            if s:
                evidence.append(s)
    joined = " | ".join(dict.fromkeys(evidence))
    if any(tok in joined for tok in _BAD_AVAIL):
        return "REJECT", joined
    if any(tok in joined for tok in _HOLD_AVAIL):
        return "HOLD", joined
    if any(tok in joined for tok in _GOOD_AVAIL):
        return "PASS", joined
    return "UNKNOWN", joined


def _find_game_state(team: str, opponent: str) -> tuple[str, str]:
    team_key, opp_key = _text(team).lower(), _text(opponent).lower()
    if not team_key or not opp_key:
        return "UNKNOWN", ""
    evidence: list[str] = []
    for _, frame in _candidate_session_frames(("slate", "schedule", "game", "matchup", "step1")):
        lower = {str(c).strip().lower(): c for c in frame.columns}
        scol = next((lower[x] for x in ("status", "game status", "game_status", "state") if x in lower), None)
        if scol is None:
            continue
        away = next((lower[x] for x in ("away", "away team", "away_team") if x in lower), None)
        home = next((lower[x] for x in ("home", "home team", "home_team") if x in lower), None)
        tcol = next((lower[x] for x in ("team", "team name", "team_name") if x in lower), None)
        ocol = next((lower[x] for x in ("opponent", "opp", "opponent team") if x in lower), None)
        matched = pd.DataFrame()
        try:
            if away is not None and home is not None:
                a = frame[away].astype(str).str.strip().str.lower()
                h = frame[home].astype(str).str.strip().str.lower()
                mask = ((a == team_key) & (h == opp_key)) | ((a == opp_key) & (h == team_key))
                matched = frame[mask]
            elif tcol is not None and ocol is not None:
                t = frame[tcol].astype(str).str.strip().str.lower()
                o = frame[ocol].astype(str).str.strip().str.lower()
                mask = ((t == team_key) & (o == opp_key)) | ((t == opp_key) & (o == team_key))
                matched = frame[mask]
        except Exception:
            continue
        if matched.empty:
            continue
        for value in matched[scol].tolist():
            s = _text(value).upper()
            if s:
                evidence.append(s)
    joined = " | ".join(dict.fromkeys(evidence))
    if any(tok in joined for tok in _BAD_GAME):
        return "REJECT", joined
    if any(tok in joined for tok in _GOOD_GAME):
        return "PASS", joined
    return "UNKNOWN", joined


def evaluate(
    frame: pd.DataFrame,
    slate_day: Any,
    *,
    feeds: dict[str, dict] | None = None,
    now_et: datetime | None = None,
) -> pd.DataFrame:
    """Return a copied audit table with Step-6 safety results; never mutates source rows."""
    target_day = _day(slate_day)
    if frame is None or frame.empty:
        cols = list(frame.columns) if isinstance(frame, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in SAFETY_COLUMNS if c not in cols])

    now = now_et or datetime.now(_ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    else:
        now = now.astimezone(_ET)

    records: list[dict[str, Any]] = []
    for _, row in frame.copy().iterrows():
        failures: list[str] = []
        holds: list[str] = []
        gates: dict[str, str] = {}

        market = _text(row.get("Market")).upper()
        player = _text(row.get("Player"))
        team = _text(row.get("Team"))
        opponent = _text(row.get("Opponent"))
        feed = _market_feed(market, feeds)

        # 1) exact Eastern slate date.
        row_day = _day(row.get("Slate day"))
        if not target_day or row_day != target_day:
            failures.append("wrong/missing slate date")
            gates["Slate gate"] = "REJECT"
        else:
            gates["Slate gate"] = "PASS"

        # 2) player/team/opponent identity integrity.
        if not player or not team or not opponent or team.lower() == opponent.lower():
            failures.append("player/team/opponent identity incomplete")
            gates["Identity gate"] = "REJECT"
        else:
            gates["Identity gate"] = "PASS"

        # 3) exact market fields required before a row can ever reach ranking.
        side = _text(row.get("Side")).upper()
        line = _num(row.get("Line"))
        odds = _num(row.get("Posted odds"))
        projection = _num(row.get("Projection"))
        probability = _num(row.get("Model probability"))
        book = _text(row.get("Book"))
        market_ok = (
            market in {"PRA", "POINTS", "REBOUNDS"}
            and side in {"OVER", "UNDER"}
            and np.isfinite(line)
            and bool(book)
            and np.isfinite(odds)
            and np.isfinite(projection)
            and np.isfinite(probability)
            and 0.0 <= probability <= 1.0
        )
        if not market_ok:
            failures.append("exact line/book/odds/projection/probability incomplete")
            gates["Market gate"] = "REJECT"
        else:
            gates["Market gate"] = "PASS"

        # 4) source connector consistency + completed standard production simulation.
        row_sims = _num(row.get("Simulation count"))
        feed_sim_ok = _feed_simulation_proof(feed)
        if not feed.get("connected"):
            failures.append("source connector is not connected")
            gates["Simulation gate"] = "REJECT"
        elif (np.isfinite(row_sims) and row_sims >= STANDARD_SIMS) or feed_sim_ok:
            gates["Simulation gate"] = "PASS"
        else:
            failures.append("5M simulation proof missing/incomplete")
            gates["Simulation gate"] = "REJECT"

        row_conv = _bool(row.get("Converged"))
        feed_conv_ok = bool(feed.get("connected")) and int(feed.get("converged", 0) or 0) >= int(feed.get("unique_distributions", 0) or 0) > 0
        if row_conv or feed_conv_ok:
            gates["Convergence gate"] = "PASS"
        else:
            failures.append("Monte Carlo convergence not verified")
            gates["Convergence gate"] = "REJECT"

        # 5) preserve source qualification states; explicit bad/uncertain states can only downgrade.
        qual = _text(row.get("Qualification state")).upper()
        if any(tok in qual for tok in _BAD_QUAL):
            failures.append(f"source state {qual}")
        elif any(tok in qual for tok in _HOLD_QUAL):
            holds.append(f"source state {qual}")

        # 6) read-only availability override when explicit same-session evidence exists.
        availability_state, availability_evidence = _find_player_availability(player)
        if availability_state == "REJECT":
            failures.append(f"availability {availability_evidence}")
            gates["Availability gate"] = "REJECT"
        elif availability_state == "HOLD":
            holds.append(f"availability {availability_evidence}")
            gates["Availability gate"] = "HOLD"
        elif availability_state == "PASS":
            gates["Availability gate"] = "PASS"
        else:
            gates["Availability gate"] = "SOURCE"

        # 7) started/final protection whenever the loaded session exposes explicit game state.
        game_state, game_evidence = _find_game_state(team, opponent)
        if game_state == "REJECT":
            failures.append(f"game state {game_evidence}")
            gates["Game-state gate"] = "REJECT"
        elif game_state == "PASS":
            gates["Game-state gate"] = "PASS"
        else:
            gates["Game-state gate"] = "SOURCE"

        # 8) quote/output freshness. Explicit stale evidence rejects. Missing proof holds.
        fresh_min = _freshness_minutes(row.get("Freshness"))
        timestamp = _parse_timestamp(row.get("Source timestamp"))
        if timestamp is None:
            timestamp = _parse_timestamp(feed.get("ran_at"))
        if timestamp is not None and timestamp.strftime("%Y-%m-%d") != target_day:
            failures.append("source timestamp is not from the current slate day")
            gates["Freshness gate"] = "REJECT"
        elif fresh_min is not None:
            if fresh_min > MAX_QUOTE_AGE_MIN:
                failures.append(f"quote stale ({fresh_min:.0f}m)")
                gates["Freshness gate"] = "REJECT"
            else:
                gates["Freshness gate"] = "PASS"
        elif timestamp is not None:
            age_min = max(0.0, (now - timestamp).total_seconds() / 60.0)
            if age_min > MAX_QUOTE_AGE_MIN:
                holds.append(f"quote freshness missing; source output age {age_min:.0f}m")
                gates["Freshness gate"] = "HOLD"
            else:
                gates["Freshness gate"] = "PASS"
        else:
            holds.append("quote/source freshness proof unavailable")
            gates["Freshness gate"] = "HOLD"

        state = "REJECT" if failures else ("HOLD" if holds else "SAFE")
        rec = row.to_dict()
        rec.update({
            "Safety state": state,
            "Hard failures": " • ".join(dict.fromkeys(failures)) if failures else "—",
            "Holds": " • ".join(dict.fromkeys(holds)) if holds else "—",
            **{c: gates.get(c, "—") for c in SAFETY_COLUMNS if c not in {"Safety state", "Hard failures", "Holds"}},
        })
        records.append(rec)

    return pd.DataFrame(records)


def diagnostics(audit: pd.DataFrame) -> dict[str, Any]:
    if audit is None or audit.empty:
        return {
            "rows": 0, "safe": 0, "hold": 0, "reject": 0,
            "ranking_enabled": False, "writes": 0, "simulations": 0, "network_requests": 0,
        }
    states = audit.get("Safety state", pd.Series(dtype=str)).astype(str).str.upper()
    return {
        "rows": int(len(audit)),
        "safe": int((states == "SAFE").sum()),
        "hold": int((states == "HOLD").sum()),
        "reject": int((states == "REJECT").sum()),
        "ranking_enabled": False,
        "writes": 0,
        "simulations": 0,
        "network_requests": 0,
    }


__all__ = [
    "MODEL_VERSION", "STANDARD_SIMS", "MAX_QUOTE_AGE_MIN", "SAFETY_COLUMNS",
    "evaluate", "diagnostics",
]
