"""WNBA Daily Picks — Game Total read-only connector V1.

Reads only completed same-session WNBA Game Total V1.5 Step-8 grading state.
It never imports/runs the Game Total source model, refreshes sportsbook data,
reruns simulations, changes probabilities, or writes source-model state.

A completed Step-8 PASS with zero QUALIFIED totals is still a healthy connected
source. Only QUALIFIED one-candidate-per-game rows are exposed to Daily Picks.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

MODEL_VERSION = "WNBA DAILY PICKS GAME TOTAL CONNECTOR V1 • READ ONLY"
STANDARD_SIMS = 5_000_000


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, list):
        return pd.DataFrame(value)
    return pd.DataFrame()


def _num(value: Any, default=np.nan) -> float:
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _source(day: Any):
    target = _day(day)
    saved_day = _day(st.session_state.get("wnba_game_total_v15_day"))
    grading_ready = bool(st.session_state.get("wnba_game_total_v15_grading_ready", False))
    final = _frame(st.session_state.get("wnba_game_total_v15_final_rows"))
    grade_meta_raw = st.session_state.get("wnba_game_total_v15_grading_meta")
    grade_meta = dict(grade_meta_raw) if isinstance(grade_meta_raw, dict) else {}
    mc_day = _day(st.session_state.get("wnba_game_total_v14_mc_day"))
    mc = _frame(st.session_state.get("wnba_game_total_v14_mc_records"))
    if mc.empty:
        mc = _frame(st.session_state.get("wnba_game_total_v14_mc_rows"))
    mc_meta_raw = st.session_state.get("wnba_game_total_v14_mc_meta")
    mc_meta = dict(mc_meta_raw) if isinstance(mc_meta_raw, dict) else {}
    return target, saved_day, grading_ready, final, grade_meta, mc_day, mc, mc_meta


def status(day: Any) -> dict[str, Any]:
    target, saved_day, grading_ready, final, grade_meta, mc_day, mc, mc_meta = _source(day)
    base = {
        "day": target,
        "state": "⏳ NOT RUN",
        "connected": False,
        "source": "WNBA Game Total V1.5 Step 8",
        "rows": 0,
        "production_picks": 0,
        "qualified": 0,
        "monitor": 0,
        "no_play": 0,
        "blocked": 0,
        "unique_distributions": 0,
        "completed_sims": 0,
        "converged": 0,
        "final_ready": 0,
        "ran_at": "—",
        "detail": "No completed same-day Game Total Step-8 grading payload is present in this session.",
    }
    if not target:
        return base

    sim_ready = bool(mc_meta.get("simulation_ready", False))
    games = int(_num(mc_meta.get("games"), 0) or 0)
    covered = int(_num(mc_meta.get("covered_games"), 0) or 0)
    sims_per_game = int(_num(mc_meta.get("simulations_per_game"), 0) or 0)
    conv_rows = int(_num(mc_meta.get("converged_rows"), 0) or 0)
    mc_rows = int(len(mc))
    all_conv = bool(mc_rows > 0 and "converged" in mc.columns and mc["converged"].fillna(False).astype(bool).all())
    grade_state = str(grade_meta.get("state") or "").upper()

    connected = bool(
        saved_day == target
        and mc_day == target
        and grading_ready
        and grade_state == "READY"
        and sim_ready
        and games > 0
        and covered == games
        and sims_per_game >= STANDARD_SIMS
        and mc_rows > 0
        and conv_rows == mc_rows
        and all_conv
    )

    grades = final.get("grade", pd.Series("", index=final.index)).astype(str).str.upper() if not final.empty else pd.Series(dtype=str)
    qualified = final.loc[grades.eq("QUALIFIED")].copy() if not final.empty else pd.DataFrame()
    monitor = int(grades.eq("MONITOR").sum()) if len(grades) else 0
    no_play = int(grades.eq("NO PLAY").sum()) if len(grades) else 0
    blocked = int(grades.eq("BLOCKED").sum()) if len(grades) else 0
    completed = int(games * sims_per_game) if games and sims_per_game else 0

    base.update({
        "state": "✅ CONNECTED" if connected else "⚠ CHECK",
        "connected": connected,
        "rows": int(len(final)),
        "production_picks": int(len(qualified)) if connected else 0,
        "qualified": int(len(qualified)),
        "monitor": monitor,
        "no_play": no_play,
        "blocked": blocked,
        "unique_distributions": games,
        "completed_sims": completed,
        "converged": conv_rows,
        "final_ready": int(len(qualified)) if connected else 0,
        "ran_at": str(mc_meta.get("run_at_et") or "—"),
        "detail": (
            f"Read-only Game Total Step-8 PASS • {len(qualified)} qualified game total(s) • {completed:,} game-level simulations"
            if connected else "Game Total Step-8 output is missing or failed read-only validation."
        ),
    })
    return base


def _mc_match(row: pd.Series, mc: pd.DataFrame):
    if mc is None or mc.empty:
        return None
    gid = str(row.get("game_id") or "")
    book = str(row.get("book") or "").strip().lower()
    line = _num(row.get("market_total"), np.nan)
    part = mc.loc[mc.get("game_id", pd.Series("", index=mc.index)).astype(str).eq(gid)].copy()
    if "book" in part.columns:
        part = part.loc[part["book"].astype(str).str.strip().str.lower().eq(book)]
    if "market_total" in part.columns and np.isfinite(line):
        vals = pd.to_numeric(part["market_total"], errors="coerce")
        part = part.loc[(vals - line).abs().le(1e-8)]
    return part.iloc[0] if not part.empty else None


def preview_rows(day: Any, limit: int = 20) -> pd.DataFrame:
    target, saved_day, grading_ready, final, grade_meta, mc_day, mc, mc_meta = _source(day)
    if not status(target).get("connected") or final.empty or saved_day != target:
        return pd.DataFrame()

    grades = final.get("grade", pd.Series("", index=final.index)).astype(str).str.upper()
    qualified = final.loc[grades.eq("QUALIFIED")].copy()
    records = []
    for _, r in qualified.iterrows():
        src = _mc_match(r, mc)
        away = str(r.get("away_team") or "").strip()
        home = str(r.get("home_team") or "").strip()
        side = str(r.get("side") or "").strip().upper()
        if not away or not home or side not in {"OVER", "UNDER"}:
            continue
        age_seconds = _num(src.get("age_seconds"), np.nan) if src is not None else np.nan
        freshness = "—" if not np.isfinite(age_seconds) else ("STALE" if age_seconds > 900 else f"FRESH {age_seconds/60.0:.1f}m")
        projection = _num(src.get("projected_total"), np.nan) if src is not None else np.nan
        records.append({
            "Slate day": target,
            "Market": "GAME TOTAL",
            "Player": f"{away} @ {home} Total",
            "Team": away,
            "Opponent": home,
            "Side": side,
            "Line": _num(r.get("market_total")),
            "Book": str(r.get("book") or "").strip(),
            "Posted odds": _num(r.get("posted_price")),
            "Projection": projection,
            "Model probability": _num(r.get("mc_win_prob")),
            "Fair odds": _num(r.get("mc_fair_odds")),
            "No-vig probability": _num(r.get("market_novig")),
            "Edge": _num(r.get("edge_pp")) / 100.0,
            "EV / $100": _num(r.get("ev")) * 100.0,
            "Confidence": "A",
            "Simulation count": int(_num(r.get("simulation_count"), 0) or 0),
            "Converged": bool(r.get("converged")),
            "Qualification state": "PRODUCTION READY",
            "Freshness": freshness,
            "Source timestamp": str(mc_meta.get("run_at_et") or "—"),
            "Source": "Game Total Step-8 5M final grading",
        })
    return pd.DataFrame(records).head(max(1, int(limit))).reset_index(drop=True)


def final_guard_proof(day: Any) -> pd.DataFrame:
    target, saved_day, grading_ready, final, grade_meta, mc_day, mc, mc_meta = _source(day)
    cols = [
        "Slate day", "Player", "Team", "Opponent", "Side", "Line", "Book", "Posted odds",
        "Tip ET proof", "Quote timestamp proof", "Quote age seconds proof", "Run timestamp proof",
        "Simulation count proof", "Converged proof", "Grade proof", "Source state proof",
    ]
    if saved_day != target or final.empty:
        return pd.DataFrame(columns=cols)
    records = []
    for _, r in final.iterrows():
        away = str(r.get("away_team") or "").strip()
        home = str(r.get("home_team") or "").strip()
        side = str(r.get("side") or "").strip().upper()
        src = _mc_match(r, mc)
        records.append({
            "Slate day": target,
            "Player": f"{away} @ {home} Total",
            "Team": away,
            "Opponent": home,
            "Side": side,
            "Line": _num(r.get("market_total")),
            "Book": str(r.get("book") or "").strip(),
            "Posted odds": _num(r.get("posted_price")),
            "Tip ET proof": str(r.get("first_tip_et") or "").strip(),
            "Quote timestamp proof": str(src.get("updated_at") or "—") if src is not None else "—",
            "Quote age seconds proof": _num(src.get("age_seconds"), np.nan) if src is not None else np.nan,
            "Run timestamp proof": str(mc_meta.get("run_at_et") or "—"),
            "Simulation count proof": int(_num(r.get("simulation_count"), 0) or 0),
            "Converged proof": bool(r.get("converged")),
            "Grade proof": str(r.get("grade") or "").upper(),
            "Source state proof": str(grade_meta.get("state") or "").upper(),
        })
    return pd.DataFrame(records, columns=cols)


__all__ = ["MODEL_VERSION", "status", "preview_rows", "final_guard_proof"]
