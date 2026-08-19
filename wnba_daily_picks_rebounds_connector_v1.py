"""WNBA Daily Picks — Step 4 Rebounds read-only connector.

Passive state inspector for the existing WNBA Rebounds production chain. It reads
only already-computed same-day Streamlit session outputs. It does NOT import any
Rebounds production module, run or restore Monte Carlo, call SportsGameOdds,
refresh schedule/roster/injury data, regrade markets, change projections, mutate
Rebounds state, or select Daily Picks.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

MODEL_VERSION = "WNBA DAILY PICKS REBOUNDS CONNECTOR V1 • READ ONLY"
STANDARD_SIMS = 5_000_000


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


def _unique_players(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    keys = [c for c in ("Player", "Team") if c in frame.columns]
    if len(keys) == 2:
        return int(frame[keys].drop_duplicates().shape[0])
    return int(len(frame))


def _completed_sims(frame: pd.DataFrame) -> int:
    if frame.empty or "MC simulations" not in frame.columns:
        return 0
    work = frame.copy()
    keys = [c for c in ("Player", "Team") if c in work.columns]
    work["_sims"] = pd.to_numeric(work["MC simulations"], errors="coerce").fillna(0)
    if len(keys) == 2:
        work = work.drop_duplicates(subset=keys, keep="first")
    return int(work["_sims"].sum())


def _converged(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    work = frame.copy()
    keys = [c for c in ("Player", "Team") if c in work.columns]
    if len(keys) == 2:
        work = work.drop_duplicates(subset=keys, keep="first")
    state_ok = (
        work.get("Step17 state", pd.Series(index=work.index, dtype=str))
        .fillna("").astype(str).str.upper().eq("VERIFIED")
    )
    mc_ok = (
        work.get("MC convergence", pd.Series(index=work.index, dtype=str))
        .fillna("").astype(str).str.upper().eq("PASS")
    )
    return int((state_ok & mc_ok).sum())


def _unique_rows(frame: pd.DataFrame, keys: tuple[str, ...]) -> int:
    if frame.empty:
        return 0
    use = [c for c in keys if c in frame.columns]
    if use:
        return int(frame.drop_duplicates(subset=use, keep="first").shape[0])
    return int(len(frame))


def status(day: Any) -> dict[str, Any]:
    """Return a read-only Rebounds production health snapshot for one ET slate."""
    day_str = _day(day)
    empty = {
        "day": day_str,
        "state": "⏳ NOT RUN" if day_str else "NEXT",
        "connected": False,
        "detail": "No completed same-day Rebounds production payload is present in this Streamlit session." if day_str else "No valid Daily Picks slate day.",
        "source": "NONE",
        "players": 0,
        "unique_distributions": 0,
        "completed_sims": 0,
        "converged": 0,
        "qualified": 0,
        "final_card": 0,
        "final_ready": 0,
        "monitor": 0,
        "step17_ready": False,
        "step20_ready": False,
        "production_ready": False,
        "fingerprint": "—",
    }
    if not day_str:
        return empty

    # READS ONLY. Never assign, update, setdefault, pop, or otherwise mutate
    # Streamlit session state in this connector.
    rebound_day = _day(st.session_state.get("wnba_rebounds_step1_day"))
    if not rebound_day:
        return empty
    if rebound_day != day_str:
        stale = dict(empty)
        stale.update({
            "state": "⚠ STALE DAY",
            "detail": f"Loaded Rebounds state belongs to {rebound_day}, not Daily Picks slate {day_str}.",
            "source": "STALE SESSION",
        })
        return stale

    step17 = _frame(st.session_state.get("wnba_rebounds_step17_players"))
    qualified = _frame(st.session_state.get("wnba_rebounds_step20_qualified"))
    final_card = _frame(st.session_state.get("wnba_rebounds_step20_final_card"))
    prod_card = _frame(st.session_state.get("wnba_rebounds_prod_guard_card"))

    step17_ready = bool(st.session_state.get("wnba_rebounds_step17_ready"))
    step20_ready = bool(st.session_state.get("wnba_rebounds_step20_ready"))
    production_ready = bool(st.session_state.get("wnba_rebounds_prod_guard_ready"))
    fingerprint = str(st.session_state.get("wnba_rebounds_prod_guard_fingerprint") or "—")

    if step17.empty:
        return empty

    unique = _unique_players(step17)
    sims = _completed_sims(step17)
    converged = _converged(step17)
    qualified_count = _unique_rows(qualified, ("Player", "Book", "Line", "Side"))
    final_count = _unique_rows(final_card, ("Player",))

    final_ready = 0
    monitor = 0
    if not prod_card.empty and "Production pick state" in prod_card.columns:
        states = prod_card["Production pick state"].fillna("").astype(str).str.upper()
        final_ready = int(states.eq("READY").sum())
        monitor = int(states.eq("HOLD").sum())

    expected_min = unique * STANDARD_SIMS
    fully_completed = unique > 0 and sims >= expected_min
    fully_converged = unique > 0 and converged == unique
    connected = bool(step17_ready and step20_ready and fully_completed and fully_converged)
    state = "✅ CONNECTED" if connected else "⚠ CHECK"
    source = "STEP 17 5M + STEP 20 FINAL CARD"
    detail = (
        f"Read-only Rebounds payload • {unique} player distributions • {sims:,} completed sims • "
        f"{qualified_count} qualified side(s) • {final_count} Step-20 final-card row(s)"
    )
    if not connected:
        detail += " • full Step-17/20 completion or convergence validation did not pass"

    return {
        "day": day_str,
        "state": state,
        "connected": connected,
        "detail": detail,
        "source": source,
        "players": unique,
        "unique_distributions": unique,
        "completed_sims": sims,
        "converged": converged,
        "qualified": qualified_count,
        "final_card": final_count,
        "final_ready": final_ready,
        "monitor": monitor,
        "step17_ready": step17_ready,
        "step20_ready": step20_ready,
        "production_ready": production_ready,
        "fingerprint": fingerprint,
    }


def preview_rows(day: Any, limit: int = 12) -> pd.DataFrame:
    """Return display-only Rebounds rows; never rank or qualify inside Daily Picks."""
    day_str = _day(day)
    if not day_str or _day(st.session_state.get("wnba_rebounds_step1_day")) != day_str:
        return pd.DataFrame()

    final_card = _frame(st.session_state.get("wnba_rebounds_step20_final_card"))
    prod_card = _frame(st.session_state.get("wnba_rebounds_prod_guard_card"))
    step17 = _frame(st.session_state.get("wnba_rebounds_step17_players"))

    if not prod_card.empty:
        source = prod_card.copy()
        cols = [c for c in (
            "Rank", "Player", "Team", "Opponent", "Book", "Line", "Side", "Posted odds",
            "Model decision probability", "No-vig edge", "Expected ROI", "Model fair American",
            "Confidence grade", "Quote freshness", "Game status", "Production pick state",
        ) if c in source.columns]
        return source[cols].head(max(1, int(limit))).reset_index(drop=True)

    if not final_card.empty:
        cols = [c for c in (
            "Rank", "Player", "Team", "Opponent", "Book", "Line", "Side", "Posted odds",
            "Model decision probability", "No-vig edge", "Expected ROI", "Model fair American",
            "Confidence grade", "Final card state",
        ) if c in final_card.columns]
        return final_card[cols].head(max(1, int(limit))).reset_index(drop=True)

    if step17.empty:
        return pd.DataFrame()
    cols = [c for c in (
        "Player", "Team", "Opponent", "Expected REB", "MC mean REB", "MC median REB",
        "MC P10 REB", "MC P90 REB", "MC simulations", "MC convergence", "Step17 state",
    ) if c in step17.columns]
    return step17[cols].head(max(1, int(limit))).reset_index(drop=True)


__all__ = ["MODEL_VERSION", "status", "preview_rows"]
