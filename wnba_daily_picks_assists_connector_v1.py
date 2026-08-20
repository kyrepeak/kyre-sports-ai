"""WNBA Daily Picks — Assists read-only connector V1.

Passive inspector for the completed WNBA Assists V20 Step-20 production output.
This module reads only same-day Streamlit session-state payloads already produced
from the Assists page. It does NOT import any Assists production module, run or
restore Monte Carlo, refresh sportsbook/injury/roster data, regrade a market,
change a projection, write to Assists state, or perform Daily Picks ranking.

A Step-20 PASS with zero published picks is still considered a healthy connected
source: "no qualified picks" is a valid production result and must not be confused
with "model not run".

For the final Daily Picks guard, ``final_guard_proof`` exposes only the already-
loaded Step-20 Top-5 fields that Step 20 itself used to qualify the pick: exact
player/market identity, availability and tip time. This is a read-only continuity
bridge so the final guard can recheck current evidence without weakening any gate
or making a network request.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

MODEL_VERSION = "WNBA DAILY PICKS ASSISTS CONNECTOR V1 • READ ONLY"
STANDARD_SIMS = 5_000_000


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _standard_key(day: Any) -> str:
    return f"wnba_assists_v20_standard::{_day(day)}"


def _top5_key(day: Any) -> str:
    return f"wnba_assists_v20_top5::{_day(day)}"


def _qualified_key(day: Any) -> str:
    return f"wnba_assists_v20_qualified::{_day(day)}"


def _candidates_key(day: Any) -> str:
    return f"wnba_assists_v20_candidates::{_day(day)}"


def _diag_key(day: Any) -> str:
    return f"wnba_assists_v20_diag::{_day(day)}"


def _frame(value: Any) -> pd.DataFrame:
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _num(value: Any, default: float = np.nan) -> float:
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(dtype=bool)
    return frame[column].fillna(False).astype(bool)


def _source_time(frame: pd.DataFrame) -> str:
    if frame is None or frame.empty or "Source timestamp" not in frame.columns:
        return "—"
    stamps = pd.to_datetime(frame["Source timestamp"], utc=True, errors="coerce").dropna()
    if stamps.empty:
        return "—"
    # The newest visible production quote is useful display metadata only; the
    # downstream Daily Picks guard will independently recheck actual age later.
    return stamps.max().strftime("%Y-%m-%d %I:%M:%S %p UTC")


def status(day: Any) -> dict[str, Any]:
    """Return a strictly read-only health snapshot for the requested ET day."""
    day_str = _day(day)
    empty = {
        "day": day_str,
        "state": "⏳ NOT RUN" if day_str else "NEXT",
        "connected": False,
        "detail": (
            "No completed same-day Assists Step-20 production payload is present in this Streamlit session."
            if day_str else "No valid Daily Picks slate day."
        ),
        "source": "NONE",
        "rows": 0,
        "production_picks": 0,
        "qualified": 0,
        "candidate_sides": 0,
        "completed_sims": 0,
        "converged": 0,
        "final_ready": 0,
        "monitor": 0,
        "step20_ready": False,
        "ran_at": "—",
    }
    if not day_str:
        return empty

    # READ ONLY: no assignment/pop/setdefault/update to session_state here.
    standard = _frame(st.session_state.get(_standard_key(day_str)))
    top5 = _frame(st.session_state.get(_top5_key(day_str)))
    qualified = _frame(st.session_state.get(_qualified_key(day_str)))
    candidates = _frame(st.session_state.get(_candidates_key(day_str)))
    diag_raw = st.session_state.get(_diag_key(day_str))
    diag = dict(diag_raw) if isinstance(diag_raw, dict) else {}

    layer_ready = bool(diag.get("layer_ready"))
    state_token = str(diag.get("state") or "").upper().strip()
    published = int(diag.get("published") or len(top5))
    qualified_players = int(diag.get("qualified_players") or len(qualified))
    candidate_sides = int(diag.get("candidate_sides") or len(candidates))

    # If picks exist, every standardized production row must independently carry
    # 5M proof, convergence, and explicit production-ready state. A valid 0/5
    # Step-20 PASS has no rows to validate and is still a connected source.
    row_proof = True
    completed_sims = 0
    converged_rows = 0
    production_rows = 0
    if not standard.empty:
        sims = pd.to_numeric(standard.get("Simulation count"), errors="coerce").fillna(0)
        conv = _bool_series(standard, "Converged")
        qstate = standard.get("Qualification state", pd.Series("", index=standard.index)).astype(str).str.upper()
        market = standard.get("Market", pd.Series("", index=standard.index)).astype(str).str.upper()
        slate = standard.get("Slate day", pd.Series("", index=standard.index)).map(_day)
        completed_sims = int(sims.sum())
        converged_rows = int(conv.sum())
        production_rows = int(qstate.eq("PRODUCTION READY").sum())
        row_proof = bool(
            sims.ge(STANDARD_SIMS).all()
            and conv.all()
            and qstate.eq("PRODUCTION READY").all()
            and market.eq("ASSISTS").all()
            and slate.eq(day_str).all()
        )

    # A current Step-20 PASS can legitimately publish zero rows. Require explicit
    # layer readiness + VERIFIED state so an absent/old payload cannot masquerade
    # as a healthy empty result.
    connected = bool(layer_ready and state_token == "VERIFIED" and row_proof)
    if connected:
        if standard.empty:
            detail = "Read-only Assists Step-20 PASS • 0 production picks published • no picks forced"
        else:
            detail = (
                f"Read-only Assists Step-20 PASS • {len(standard)} production-ready pick(s) • "
                f"{completed_sims:,} visible pick-level simulation proofs"
            )
    else:
        detail = "Assists Step-20 production output is missing or failed read-only validation."

    return {
        "day": day_str,
        "state": "✅ CONNECTED" if connected else "⚠ CHECK",
        "connected": connected,
        "detail": detail,
        "source": "WNBA Assists V20 Step 20" if diag else "NONE",
        "rows": int(len(standard)),
        "production_picks": int(len(standard)),
        "qualified": qualified_players,
        "candidate_sides": candidate_sides,
        "completed_sims": completed_sims,
        "converged": converged_rows,
        "final_ready": production_rows,
        "monitor": max(0, qualified_players - published),
        "step20_ready": bool(layer_ready and state_token == "VERIFIED"),
        "published": published,
        "diversity_holds": int(diag.get("diversity_holds") or 0),
        "status_risk_holds": int(diag.get("status_risk_rows") or 0),
        "ran_at": _source_time(standard),
    }


def preview_rows(day: Any, limit: int = 12) -> pd.DataFrame:
    """Return display-only standardized Step-20 Assists rows."""
    day_str = _day(day)
    if not day_str:
        return pd.DataFrame()
    rows = _frame(st.session_state.get(_standard_key(day_str)))
    if rows.empty:
        return pd.DataFrame()
    keep = [
        c for c in (
            "Slate day", "Market", "Player", "Team", "Opponent", "Side", "Line",
            "Book", "Posted odds", "Projection", "Model probability", "Fair odds",
            "No-vig probability", "Edge", "EV / $100", "Confidence",
            "Simulation count", "Converged", "Qualification state", "Freshness",
            "Source timestamp", "Source",
        ) if c in rows.columns
    ]
    out = rows[keep].copy()
    keys = [c for c in ("Player", "Side", "Line", "Book") if c in out.columns]
    if keys:
        out = out.drop_duplicates(subset=keys, keep="first")
    return out.head(max(1, int(limit))).reset_index(drop=True)


def final_guard_proof(day: Any) -> pd.DataFrame:
    """Expose exact same-session Step-20 availability/tip evidence, read-only.

    The standardized 22-column Daily Picks contract intentionally omits source-
    specific status/tip fields. Step 20's Top-5 payload still retains them. This
    function returns only those already-computed fields so the final Daily Picks
    guard can require explicit proof rather than treating a generic SOURCE gate as
    permanently unresolved.
    """
    day_str = _day(day)
    cols = [
        "Slate day", "Player", "Team", "Opponent", "Side", "Line", "Book",
        "Availability proof", "Tip ET proof", "Source timestamp proof",
    ]
    if not day_str:
        return pd.DataFrame(columns=cols)

    top5 = _frame(st.session_state.get(_top5_key(day_str)))
    if top5.empty:
        return pd.DataFrame(columns=cols)

    records: list[dict[str, Any]] = []
    for _, row in top5.iterrows():
        records.append({
            "Slate day": day_str,
            "Player": str(row.get("PLAYER_NAME") or "").strip(),
            "Team": str(row.get("TEAM") or "").strip(),
            "Opponent": str(row.get("OPPONENT") or "").strip(),
            "Side": str(row.get("SIDE") or "").strip().upper(),
            "Line": _num(row.get("LINE")),
            "Book": str(row.get("BOOK") or "").strip(),
            "Availability proof": str(row.get("AVAILABILITY") or "").strip().upper(),
            "Tip ET proof": str(row.get("TIP_ET") or "").strip(),
            "Source timestamp proof": str(row.get("SOURCE_TIMESTAMP") or "").strip(),
        })

    out = pd.DataFrame(records, columns=cols)
    if out.empty:
        return out
    return out.drop_duplicates(
        subset=["Player", "Team", "Opponent", "Side", "Line", "Book"],
        keep="first",
    ).reset_index(drop=True)


__all__ = ["MODEL_VERSION", "status", "preview_rows", "final_guard_proof"]
