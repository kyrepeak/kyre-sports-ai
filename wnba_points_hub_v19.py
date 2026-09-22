"""WNBA Points V1.9 hub — positional matchup gate + final Points hierarchy."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_v19 as points


def _load_v18():
    path = Path(__file__).with_name("wnba_points_hub_v18.py")
    spec = importlib.util.spec_from_file_location("_kyre_wnba_points_v18_base_for_v19", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load WNBA Points V1.8 base.")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v18 = _load_v18()
MODEL_VERSION = "WNBA POINTS V1.9 • POSITION MATCHUP + FINAL HIERARCHY"
PRA_FROZEN_BRANCH = v18.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = v18.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = v18.MLB_FROZEN_BRANCH

# Redirect the inherited page chain to V1.9 execution without touching PRA/MLB.
v18.points = points
v18.v171.points = points
v18.v171.base.points = points
v18.v171.base.ui.points = points
v18.v171.ui.points = points

_orig_history_gate = v18.v171._history_gate
_orig_integrity = v18.v171._render_integrity


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _position_gate(day):
    try:
        projections, pairs, _, _, _ = points._prepare(day)
    except Exception as exc:
        return {
            "expected": 0, "verified": 0, "neutral": 0, "ready": False,
            "error": f"{type(exc).__name__}: {exc}", "min_factor": np.nan,
            "max_factor": np.nan, "teams": 0,
        }
    projections = projections if isinstance(projections, pd.DataFrame) else pd.DataFrame()
    pairs = pairs if isinstance(pairs, pd.DataFrame) else pd.DataFrame()
    if projections.empty or pairs.empty:
        return {"expected": 0, "verified": 0, "neutral": 0, "ready": False, "teams": 0}

    market_keys = set()
    for _, r in pairs.iterrows():
        market_keys.add((str(r.get("game_id") or ""), str(r.get("player_key") or "")))
    matched = projections.loc[
        projections.apply(
            lambda r: (str(r.get("game_id") or ""), str(r.get("player_key") or "")) in market_keys,
            axis=1,
        )
    ].copy()
    matched = matched.drop_duplicates(["game_id", "player_key"], keep="first")
    expected = len(matched)
    if not expected:
        return {"expected": 0, "verified": 0, "neutral": 0, "ready": False, "teams": 0}

    source = matched.get("position_source", pd.Series("", index=matched.index)).astype(str)
    bucket = matched.get("position_bucket", pd.Series("UNKNOWN", index=matched.index)).astype(str)
    games = pd.to_numeric(matched.get("position_games", 0), errors="coerce").fillna(0)
    verified_mask = source.str.contains("opp L10 position scoring share", regex=False) & bucket.ne("UNKNOWN") & games.ge(5)
    verified = int(verified_mask.sum())
    neutral = int(expected - verified)
    factors = pd.to_numeric(matched.get("position_factor", 1.0), errors="coerce").dropna()
    teams = int(pd.to_numeric(matched.get("opponent_team_id"), errors="coerce").dropna().nunique())
    return {
        "expected": int(expected),
        "verified": verified,
        "neutral": neutral,
        "ready": bool(expected > 0 and neutral == 0),
        "teams": teams,
        "min_factor": float(factors.min()) if len(factors) else np.nan,
        "max_factor": float(factors.max()) if len(factors) else np.nan,
    }


def _history_gate_with_position(day):
    h = _orig_history_gate(day)
    pg = _position_gate(day)
    h = dict(h or {})
    h["position_gate"] = pg
    h["ready"] = bool(h.get("ready") and pg.get("ready"))
    return h


def _render_integrity_with_position(info):
    _orig_integrity(info)
    pg = ((info or {}).get("history_gate") or {}).get("position_gate") or {}
    st.markdown("### 🎯 Position Matchup Integrity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matched players", pg.get("expected", 0))
    c2.metric("Position verified", f"{pg.get('verified',0)}/{pg.get('expected',0)}")
    c3.metric("Opponent teams", pg.get("teams", 0))
    c4.metric("Neutral fallbacks", pg.get("neutral", 0))
    if pg.get("error"):
        st.error(f"⛔ Position matchup gate could not complete: {pg['error']}")
    elif pg.get("ready"):
        lo = _num(pg.get("min_factor"), 1.0)
        hi = _num(pg.get("max_factor"), 1.0)
        st.success(
            f"✅ POSITION MATCHUP GATE PASSED • every matched Points player has a verified opponent L10 positional scoring sample. "
            f"Residual factors are tightly capped; current range {lo:.3f}×–{hi:.3f}×."
        )
        st.caption(
            "Guard/Wing/Big scoring shares are normalized against total points allowed, so overall opponent defense remains handled by L10 DRTG. "
            "Sportsbook lines never influence this matchup factor."
        )
    else:
        st.error(
            f"⛔ POSITION MATCHUP NOT READY • {pg.get('neutral',0)} matched player(s) would require a neutral positional fallback. "
            "The 5M button remains locked until the verified position layer is complete."
        )


def _decision_tier(row):
    fresh = str(row.get("freshness") or "").upper()
    role = str(row.get("role_label") or "").upper()
    converged = bool(row.get("converged"))
    qualified = bool(row.get("model_qualified"))
    lineup = bool(row.get("lineup_ready"))
    p = _num(row.get("model_over"), 0.0)
    edge = _num(row.get("edge"), -1.0)
    dq = _num(row.get("data_quality"), 0.0)
    if fresh == "STALE" or role == "OUT" or not converged:
        return "⛔ AVOID"
    if qualified and not lineup:
        return "⚠️ MONITOR"
    if qualified and lineup and p >= 0.60 and edge >= 0.08 and dq >= 0.75:
        return "🔥 BEST BET"
    if qualified and lineup:
        return "✅ STRONG"
    return "⛔ AVOID"


def _render_final_points_board(day):
    rows = points.combined_rows(day)
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return
    work = rows.copy()
    for col in ("model_over", "edge", "data_quality", "market_age"):
        work[col] = pd.to_numeric(work.get(col), errors="coerce")
    work["Decision"] = work.apply(_decision_tier, axis=1)
    work["_tier"] = work["Decision"].map({
        "🔥 BEST BET": 0, "✅ STRONG": 1, "⚠️ MONITOR": 2, "⛔ AVOID": 3,
    }).fillna(9)
    work = work.sort_values(
        ["_tier", "model_over", "edge", "data_quality"],
        ascending=[True, False, False, False],
    )
    # One best sportsbook offer per player/line for the candidate board.
    best = work.drop_duplicates(["player_key", "line"], keep="first").copy()
    qualified = best[best["Decision"].isin(["🔥 BEST BET", "✅ STRONG", "⚠️ MONITOR"])].head(5)

    st.markdown("### 🏆 Top Points Candidates")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BEST BET", int((best["Decision"] == "🔥 BEST BET").sum()))
    c2.metric("STRONG", int((best["Decision"] == "✅ STRONG").sum()))
    c3.metric("MONITOR", int((best["Decision"] == "⚠️ MONITOR").sum()))
    c4.metric("AVOID", int((best["Decision"] == "⛔ AVOID").sum()))

    if qualified.empty:
        st.info("No qualified Points candidate currently clears the final hierarchy. Nothing is forced.")
        return
    view = qualified.copy()
    view["P(Over)"] = (view["model_over"] * 100).round(1).astype(str) + "%"
    view["No-vig O"] = (pd.to_numeric(view["no_vig_over"], errors="coerce") * 100).round(1).astype(str) + "%"
    view["Edge"] = (view["edge"] * 100).round(1).map(lambda x: f"{x:+.1f} pp")
    view["Proj PTS"] = pd.to_numeric(view["projection"], errors="coerce").round(2)
    view["MC Mean"] = pd.to_numeric(view["sim_mean"], errors="coerce").round(2)
    view["Pass"] = view["pass_source"].astype(str)
    view["Book"] = view["book"].astype(str)
    view["Line"] = pd.to_numeric(view["line"], errors="coerce")
    view["Player"] = view["player"].astype(str)
    st.dataframe(
        view[["Decision", "Player", "Book", "Line", "Proj PTS", "MC Mean", "P(Over)", "No-vig O", "Edge", "Pass"]],
        use_container_width=True,
        hide_index=True,
    )
    if (qualified["Decision"] == "⚠️ MONITOR").any():
        st.warning("⚠️ Starting fives are still pending for one or more qualified players. MONITOR candidates are not Final Ready until explicit lineup confirmation publishes.")
    st.caption("Points remains isolated from the shared WNBA Daily Master Card until this V1.9 layer is validated and frozen.")


# Patch V1.7.1's hooks before V1.8 delegates into it.
v18.v171._history_gate = _history_gate_with_position
v18.v171._render_integrity = _render_integrity_with_position


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🏀 WNBA Points V1.9 • position matchup + rotation minutes + empirical variance • PRA V3.2.1 frozen • MLB V2.1.7 frozen")
    result = v18.render_wnba_points_hub(section_header, status_info, team_logo, h)
    day = st.session_state.get("wnba_points_date") or st.session_state.get("wnba_points_date_control")
    if day:
        _render_final_points_board(pd.to_datetime(day).strftime("%Y-%m-%d"))
    return result


__all__ = ["MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH", "render_wnba_points_hub"]
