"""WNBA Points V1.9.8.4.2 — safe preflight coverage repair.

Preflight-only wrapper over V1.9.8.4.1. Projection, SportsGameOdds transport,
Monte Carlo, grading, calibration, persistence, PRA and MLB math are unchanged.

The inherited readiness gate required every raw sportsbook Points player to have
a current projection. A stale/unmodellable raw quote could therefore disable the
entire 5M button even though the production engine itself safely simulates only
the inner intersection of current projections and exact O/U pairs.

This wrapper keeps the strict roster/history/sanity/position gates, but changes
coverage to the production-safe contract: every UPCOMING game must have at least
one exact projection+market pair. Raw quote players with no projection remain
excluded from simulation/output and can never become picks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v19841 as prior
import wnba_points_hub_v19 as v19

MODEL_VERSION = "WNBA POINTS V1.9.8.4.2 • SAFE PREFLIGHT COVERAGE REPAIR"
PRA_FROZEN_BRANCH = prior.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = prior.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = prior.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = prior.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = prior.POINTS_FROZEN_COMMIT

# Patch the exact manually-loaded V1.7 UI object used by the live V1.9 chain.
# Import V1.9 directly instead of reaching through V1.9.2's module globals;
# this avoids AttributeError during Streamlit cold-start/import ordering.
v171 = v19.v18.v171
v17 = v171.base
ui = v17.ui


def _started(value) -> bool:
    text = str(value or "").strip().upper()
    return any(token in text for token in (
        "FINAL", "IN PROGRESS", "IN_PROGRESS", "LIVE", "HALFTIME",
    ))


def _readiness_snapshot_safe(day):
    points = ui.points
    try:
        projections, pairs, _snap, pmeta, lineups = points._prepare(day)
    except Exception as exc:
        return {
            "error": str(exc), "preview": pd.DataFrame(), "active_games": 0,
            "lineups_confirmed": 0, "market_players": 0, "matched_players": 0,
            "eligible_pairs": 0, "empirical_players": 0, "ready": False,
            "matched_games": 0, "unmatched_market_players": 0,
        }

    projections = projections if isinstance(projections, pd.DataFrame) else pd.DataFrame()
    pairs = pairs if isinstance(pairs, pd.DataFrame) else pd.DataFrame()
    pmeta = pmeta if isinstance(pmeta, dict) else {}
    schedule_df = pmeta.get("schedule")
    schedule_df = schedule_df if isinstance(schedule_df, pd.DataFrame) else pd.DataFrame()

    if schedule_df.empty:
        active = pd.DataFrame()
    else:
        started = schedule_df.apply(
            lambda r: _started(r.get("status") or r.get("status_text") or ""), axis=1
        )
        active = schedule_df.loc[~started].copy()

    active_ids = set(active.get("game_id", pd.Series(dtype=str)).astype(str).tolist())
    active_games = len(active_ids)
    lineups_confirmed = sum(1 for gid in active_ids if bool((lineups or {}).get(gid, False)))

    if projections.empty or pairs.empty:
        market_players = 0 if pairs.empty or "player_key" not in pairs else int(pairs["player_key"].astype(str).nunique())
        return {
            "error": "", "preview": pd.DataFrame(), "active_games": active_games,
            "lineups_confirmed": lineups_confirmed, "market_players": market_players,
            "matched_players": 0, "eligible_pairs": 0, "empirical_players": 0,
            "ready": False, "matched_games": 0,
            "unmatched_market_players": market_players,
        }

    if not {"game_id", "player_key"}.issubset(projections.columns) or not {"game_id", "player_key"}.issubset(pairs.columns):
        return {
            "error": "projection/market identity columns are incomplete",
            "preview": pd.DataFrame(), "active_games": active_games,
            "lineups_confirmed": lineups_confirmed, "market_players": 0,
            "matched_players": 0, "eligible_pairs": 0, "empirical_players": 0,
            "ready": False, "matched_games": 0, "unmatched_market_players": 0,
        }

    proj_cols = [
        "game_id", "player_key", "PLAYER_NAME", "PROJ_PTS", "RAW_PROJ_PTS",
        "PROJ_MIN", "ROLE_LABEL", "context_quality",
    ]
    proj_small = projections[[c for c in proj_cols if c in projections.columns]].copy()
    proj_small["game_id"] = proj_small["game_id"].astype(str)
    proj_small["player_key"] = proj_small["player_key"].astype(str)

    pair_small = pairs.copy()
    pair_small["game_id"] = pair_small["game_id"].astype(str)
    pair_small["player_key"] = pair_small["player_key"].astype(str)
    if active_ids:
        pair_small = pair_small.loc[pair_small["game_id"].isin(active_ids)].copy()

    matched = pair_small.merge(proj_small, on=["game_id", "player_key"], how="inner")
    market_players = int(pair_small["player_key"].nunique()) if not pair_small.empty else 0
    matched_players = int(matched["player_key"].nunique()) if not matched.empty else 0
    eligible_pairs = int(len(matched))
    matched_game_ids = set(matched.get("game_id", pd.Series(dtype=str)).astype(str).tolist())
    matched_games = len(active_ids & matched_game_ids)
    raw_keys = set(pair_small["player_key"].astype(str).tolist()) if not pair_small.empty else set()
    matched_keys = set(matched["player_key"].astype(str).tolist()) if not matched.empty else set()
    unmatched_market_players = len(raw_keys - matched_keys)

    empirical_players = 0
    history_meta = {}
    if not matched.empty:
        unique_proj = matched.drop_duplicates(["game_id", "player_key"])
        for _, row in unique_proj.iterrows():
            gid = str(row.get("game_id") or "")
            pkey = str(row.get("player_key") or "")
            _, _, dmeta = points._points_distribution(row, bool((lineups or {}).get(gid, False)))
            dmeta = dmeta or {}
            history_meta[(gid, pkey)] = dmeta
            if int(dmeta.get("hist_games") or 0) >= 5:
                empirical_players += 1

    preview_rows = []
    for _, row in matched.head(20).iterrows():
        gid = str(row.get("game_id") or "")
        pkey = str(row.get("player_key") or "")
        dmeta = history_meta.get((gid, pkey), {})
        proj = pd.to_numeric(pd.Series([row.get("PROJ_PTS")]), errors="coerce").iloc[0]
        line = pd.to_numeric(pd.Series([row.get("line")]), errors="coerce").iloc[0]
        try:
            freshness, _ = points.market._freshness(row.get("market_age"))
        except Exception:
            freshness = "UNKNOWN"
        preview_rows.append({
            "Player": str(row.get("PLAYER_NAME") or row.get("player_name") or "Player"),
            "Book": str(row.get("book") or ""),
            "Line": float(line) if pd.notna(line) else np.nan,
            "Proj PTS": round(float(proj), 2) if pd.notna(proj) else np.nan,
            "Delta": round(float(proj - line), 2) if pd.notna(proj) and pd.notna(line) else np.nan,
            "Hist GP": int(dmeta.get("hist_games") or 0),
            "Lineup": "CONFIRMED" if bool((lineups or {}).get(gid, False)) else "PENDING",
            "Freshness": freshness,
        })

    # Production already ignores any pair whose projection is absent. Require
    # complete GAME coverage, not an impossible 100% raw sportsbook-player match.
    coverage_ok = bool(active_games > 0 and eligible_pairs > 0 and active_ids.issubset(matched_game_ids))
    return {
        "error": "", "preview": pd.DataFrame(preview_rows),
        "active_games": active_games, "lineups_confirmed": lineups_confirmed,
        "market_players": market_players, "matched_players": matched_players,
        "eligible_pairs": eligible_pairs, "empirical_players": empirical_players,
        "ready": coverage_ok, "matched_games": matched_games,
        "unmatched_market_players": int(unmatched_market_players),
    }


def _install():
    # V1.7 resolves this helper dynamically through the loaded UI module.
    ui._readiness_snapshot = _readiness_snapshot_safe


def _diagnostics(day):
    try:
        points = ui.points
        info = _readiness_snapshot_safe(day)
        _pool, pdiag = points.corrected_player_pool(day)
        pdiag = pdiag if isinstance(pdiag, dict) else {}
        teams = int(pdiag.get("teams") or 0)
        official = int(pdiag.get("official_roster_teams") or 0)
        proxy = int(pdiag.get("proxy_roster_teams") or 0)
        missing = int(pdiag.get("missing_roster_teams") or 0)
        roster_ready = bool(teams > 0 and official == teams and proxy == 0 and missing == 0)
        history = v171._history_gate(day)
        history = history if isinstance(history, dict) else {}
        position = history.get("position_gate") or {}
        return {
            "active_games": int(info.get("active_games") or 0),
            "matched_games": int(info.get("matched_games") or 0),
            "market_players": int(info.get("market_players") or 0),
            "matched_players": int(info.get("matched_players") or 0),
            "excluded_market_players": int(info.get("unmatched_market_players") or 0),
            "eligible_pairs": int(info.get("eligible_pairs") or 0),
            "coverage_ready": bool(info.get("ready")),
            "roster_ready": roster_ready,
            "history_ready": bool(history.get("ready")),
            "history_verified": int(history.get("verified") or 0),
            "history_expected": int(history.get("expected") or 0),
            "history_missing": int(history.get("missing") or 0),
            "sanity_holds": int(history.get("sanity_count") or 0),
            "position_ready": bool(position.get("ready")) if position else True,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    result = prior.render_wnba_points_hub(section_header, status_info, team_logo, h)

    day = st.session_state.get("wnba_points_date") or st.session_state.get("wnba_points_date_control")
    if day is not None:
        try:
            day = pd.to_datetime(day).strftime("%Y-%m-%d")
            diag = _diagnostics(day)
        except Exception:
            diag = {}
        with st.expander("🔎 Points 5M unlock diagnostics", expanded=False):
            if diag.get("error"):
                st.error(diag["error"])
            else:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Upcoming game coverage", f"{diag.get('matched_games',0)}/{diag.get('active_games',0)}")
                c2.metric("Simulatable players", f"{diag.get('matched_players',0)}/{diag.get('market_players',0)} raw")
                c3.metric("Exact eligible pairs", diag.get("eligible_pairs", 0))
                c4.metric("Excluded raw quotes", diag.get("excluded_market_players", 0))
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Game-level coverage", "PASS" if diag.get("coverage_ready") else "CHECK")
                d2.metric("Current rosters", "PASS" if diag.get("roster_ready") else "CHECK")
                d3.metric("Empirical history", "PASS" if diag.get("history_ready") else f"CHECK {diag.get('history_verified',0)}/{diag.get('history_expected',0)}")
                d4.metric("Position matchup", "PASS" if diag.get("position_ready") else "CHECK")
                if diag.get("excluded_market_players", 0):
                    st.info(
                        f"ℹ️ {diag['excluded_market_players']} raw sportsbook player quote(s) have no current Points projection. "
                        "They are excluded from simulation/output instead of disabling every valid player."
                    )
                if diag.get("coverage_ready") and diag.get("roster_ready") and diag.get("history_ready"):
                    st.success("✅ POINTS 5M UNLOCK CHAIN READY • every upcoming game has exact simulatable Points coverage and the strict roster/history/position gates pass.")
                else:
                    blockers = []
                    if not diag.get("coverage_ready"):
                        blockers.append("upcoming game-level projection + exact-market coverage")
                    if not diag.get("roster_ready"):
                        blockers.append("current roster verification")
                    if not diag.get("history_ready"):
                        blockers.append(f"empirical history/sanity ({diag.get('history_missing',0)} missing; {diag.get('sanity_holds',0)} sanity hold)")
                    if not diag.get("position_ready"):
                        blockers.append("position matchup")
                    st.warning("⚠️ Remaining 5M blocker(s): " + " • ".join(blockers or ["unknown preflight gate"]))
                st.caption(
                    "No unmatched sportsbook row is simulated. Full upcoming GAME coverage is still required; only raw player quotes with no current projection stop deadlocking valid distributions."
                )
    return result


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "render_wnba_points_hub",
]
