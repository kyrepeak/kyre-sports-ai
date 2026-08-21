"""WNBA Daily Picks — Spread read-only connector V1.

Reads only the completed same-session WNBA Spread V1.6/V1.6.1 Step-7 Monte Carlo
payload. It never imports/runs the Spread model, refreshes sportsbook/injury data,
reruns simulations, changes a projection, or writes source-model state.

A completed Step-7 PASS with zero QUALIFIED spreads is still a healthy connected
source. Only QUALIFIED one-candidate-per-game rows are exposed to Daily Picks.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

MODEL_VERSION = "WNBA DAILY PICKS SPREAD CONNECTOR V1 • READ ONLY"
STANDARD_SIMS = 5_000_000
_ET = ZoneInfo("America/New_York")


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _frame(value: Any) -> pd.DataFrame:
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _num(value: Any, default=np.nan) -> float:
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _older_quote_timestamp(row: pd.Series) -> str:
    vals = []
    for col in ("away_updated_at", "home_updated_at"):
        try:
            ts = pd.to_datetime(row.get(col), utc=True, errors="coerce")
            if pd.notna(ts):
                vals.append(ts)
        except Exception:
            pass
    if not vals:
        return "—"
    return min(vals).isoformat()


def _quote_age_minutes(row: pd.Series, now=None) -> float:
    stamp = _older_quote_timestamp(row)
    if stamp == "—":
        return np.nan
    try:
        now_utc = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now).tz_convert("UTC")
        ts = pd.to_datetime(stamp, utc=True)
        return max(0.0, float((now_utc - ts).total_seconds() / 60.0))
    except Exception:
        return np.nan


def _tip_datetime(day_str: str, tip_value: Any):
    text = str(tip_value or "").replace(" ET", "").strip()
    if not day_str or not text:
        return None
    try:
        ts = pd.Timestamp(f"{day_str} {text}")
        return ts.tz_localize(_ET)
    except Exception:
        return None


def _source_frames(day: Any):
    day_str = _day(day)
    saved_day = _day(st.session_state.get("wnba_spread_v16_mc_date"))
    detail = _frame(st.session_state.get("wnba_spread_v16_mc_detail"))
    final = _frame(st.session_state.get("wnba_spread_v16_mc_final"))
    meta_raw = st.session_state.get("wnba_spread_v16_mc_meta")
    meta = dict(meta_raw) if isinstance(meta_raw, dict) else {}
    return day_str, saved_day, detail, final, meta


def status(day: Any) -> dict[str, Any]:
    day_str, saved_day, detail, final, meta = _source_frames(day)
    base = {
        "day": day_str, "state": "⏳ NOT RUN", "connected": False,
        "source": "WNBA Spread V1.6 Step 7", "rows": 0, "production_picks": 0,
        "qualified": 0, "unique_distributions": 0, "completed_sims": 0,
        "converged": 0, "final_ready": 0, "monitor": 0, "ran_at": "—",
        "detail": "No completed same-day Spread Step-7 payload is present in this session.",
    }
    if not day_str:
        return base

    state = str(meta.get("state") or "").upper()
    games = int(_num(meta.get("games"), 0) or 0)
    covered = int(_num(meta.get("covered_games"), 0) or 0)
    sims_per_game = int(_num(meta.get("simulations_per_game"), 0) or 0)
    conv = int(_num(meta.get("converged_rows"), 0) or 0)
    detail_rows = int(len(detail))
    all_conv = bool(detail_rows > 0 and "converged" in detail.columns and detail["converged"].fillna(False).astype(bool).all())
    connected = bool(
        saved_day == day_str and state == "READY" and games > 0 and covered == games
        and sims_per_game >= STANDARD_SIMS and detail_rows > 0 and conv == detail_rows and all_conv
    )

    qualified = pd.DataFrame()
    if not final.empty and "grade" in final.columns:
        qualified = final.loc[final["grade"].astype(str).str.upper().eq("QUALIFIED")].copy()

    completed = int(games * sims_per_game) if games and sims_per_game else 0
    base.update({
        "state": "✅ CONNECTED" if connected else "⚠ CHECK",
        "connected": connected,
        "rows": int(len(final)),
        "production_picks": int(len(qualified)) if connected else 0,
        "qualified": int(len(qualified)),
        "unique_distributions": games,
        "completed_sims": completed,
        "converged": conv,
        "final_ready": int(len(qualified)) if connected else 0,
        "monitor": int((final.get("grade", pd.Series(dtype=str)).astype(str).str.upper() == "MONITOR").sum()) if not final.empty else 0,
        "ran_at": str(meta.get("run_at_et") or "—"),
        "detail": (
            f"Read-only Spread Step-7 PASS • {len(qualified)} qualified game spread(s) • {completed:,} game-level simulations"
            if connected else "Spread Step-7 output is missing or failed read-only validation."
        ),
    })
    return base


def preview_rows(day: Any, limit: int = 20) -> pd.DataFrame:
    """Map only QUALIFIED final Spread candidates into the 22-column common contract."""
    day_str, saved_day, detail, final, meta = _source_frames(day)
    if not status(day_str).get("connected") or final.empty or saved_day != day_str:
        return pd.DataFrame()

    rows = final.loc[final.get("grade", pd.Series("", index=final.index)).astype(str).str.upper().eq("QUALIFIED")].copy()
    records = []
    for _, r in rows.iterrows():
        best_team = str(r.get("best_side") or "").strip()
        away = str(r.get("away_team") or "").strip()
        home = str(r.get("home_team") or "").strip()
        if not best_team or best_team not in {away, home}:
            continue
        is_home = best_team == home
        opp = away if is_home else home
        team_margin = _num(r.get("projected_home_margin")) if is_home else -_num(r.get("projected_home_margin"))
        no_vig = _num(r.get("home_market_novig")) if is_home else _num(r.get("away_market_novig"))
        fair_odds = _num(r.get("mc_home_fair_odds")) if is_home else _num(r.get("mc_away_fair_odds"))
        edge_pp = _num(r.get("best_edge_pp"))
        ev = _num(r.get("best_ev"))
        age = _quote_age_minutes(r)
        freshness = "—" if not np.isfinite(age) else ("STALE" if age > 15 else f"FRESH {age:.1f}m")
        records.append({
            "Slate day": day_str,
            "Market": "SPREAD",
            "Player": best_team,
            "Team": best_team,
            "Opponent": opp,
            "Side": "SPREAD",
            "Line": _num(r.get("best_spread")),
            "Book": str(r.get("book") or "").strip(),
            "Posted odds": _num(r.get("best_price")),
            "Projection": team_margin,
            "Model probability": _num(r.get("best_cover_no_push")),
            "Fair odds": fair_odds,
            "No-vig probability": no_vig,
            "Edge": edge_pp / 100.0 if np.isfinite(edge_pp) else np.nan,
            "EV / $100": ev * 100.0 if np.isfinite(ev) else np.nan,
            "Confidence": "A" if bool(r.get("converged")) else "MONITOR",
            "Simulation count": int(_num(r.get("simulation_count"), 0) or 0),
            "Converged": bool(r.get("converged")),
            "Qualification state": "PRODUCTION READY",
            "Freshness": freshness,
            "Source timestamp": str(meta.get("run_at_et") or "—"),
            "Source": "Spread Step-7 5M final grading",
        })
    return pd.DataFrame(records).head(max(1, int(limit))).reset_index(drop=True)


def final_guard_proof(day: Any) -> pd.DataFrame:
    day_str, saved_day, detail, final, meta = _source_frames(day)
    cols = [
        "Slate day", "Team", "Opponent", "Line", "Book", "Tip ET proof",
        "Quote timestamp proof", "Run timestamp proof", "Simulation count proof",
        "Converged proof", "Grade proof", "Source state proof",
    ]
    if saved_day != day_str or final.empty:
        return pd.DataFrame(columns=cols)
    records = []
    for _, r in final.iterrows():
        team = str(r.get("best_side") or "").strip()
        away = str(r.get("away_team") or "").strip()
        home = str(r.get("home_team") or "").strip()
        opp = home if team == away else away
        records.append({
            "Slate day": day_str,
            "Team": team,
            "Opponent": opp,
            "Line": _num(r.get("best_spread")),
            "Book": str(r.get("book") or "").strip(),
            "Tip ET proof": str(r.get("first_tip_et") or "").strip(),
            "Quote timestamp proof": _older_quote_timestamp(r),
            "Run timestamp proof": str(meta.get("run_at_et") or "—"),
            "Simulation count proof": int(_num(r.get("simulation_count"), 0) or 0),
            "Converged proof": bool(r.get("converged")),
            "Grade proof": str(r.get("grade") or "").upper(),
            "Source state proof": str(meta.get("state") or "").upper(),
        })
    return pd.DataFrame(records, columns=cols)


__all__ = ["MODEL_VERSION", "status", "preview_rows", "final_guard_proof"]
