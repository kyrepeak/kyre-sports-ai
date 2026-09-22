"""WNBA Spread V1.4 — independent projected-score / projected-margin engine.

This is Step 5 only. The model consumes verified pregame team history, recent form,
venue splits, recent pace/efficiency when sufficiently sampled, and current
availability. Sportsbook lines/prices are intentionally not accepted as inputs.

Design goals:
- no market anchoring;
- no H2H multiplier (H2H remains descriptive only);
- date-cut historical team data to avoid future leakage;
- conservative replacement-adjusted OUT-player scoring impact;
- fail closed when required scoring history or an OUT player's impact cannot be
  resolved from the verified roster/player-production pool.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

import wnba_spread_hub_v10 as foundation

MODEL_VERSION = "WNBA SPREAD PROJECTION V1.4"

WEIGHTS = {"season": 0.30, "recent": 0.30, "venue": 0.20, "advanced": 0.20}
MIN_TEAM_GAMES = 5
MIN_VENUE_GAMES = 4
MIN_ADV_GAMES = 5
OUT_REPLACEMENT_FACTOR = 0.40
MAX_PLAYER_OUT_IMPACT = 6.5
MAX_TEAM_OUT_IMPACT = 12.0


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm_name(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _mean2(a, b):
    a, b = _num(a), _num(b)
    return (a + b) / 2.0 if np.isfinite(a) and np.isfinite(b) else np.nan


def _history_before(day_str: str) -> pd.DataFrame:
    selected = pd.to_datetime(day_str)
    season = int(selected.year)
    try:
        frame = foundation.context._season_team_games(season)
    except Exception:
        frame = pd.DataFrame()
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    out["GAME_DATE"] = pd.to_datetime(out["GAME_DATE"], errors="coerce")
    return out.loc[out["GAME_DATE"].notna() & (out["GAME_DATE"] < selected)].copy().reset_index(drop=True)


def _venue_split(history: pd.DataFrame, team_id: int, home: bool) -> dict:
    if history is None or history.empty:
        return {"GP": 0, "PF": np.nan, "PA": np.nan, "DIFF": np.nan}
    part = history.loc[
        pd.to_numeric(history["TEAM_ID"], errors="coerce").eq(int(team_id))
        & history["HOME"].astype(bool).eq(bool(home))
    ].copy()
    if part.empty:
        return {"GP": 0, "PF": np.nan, "PA": np.nan, "DIFF": np.nan}
    pf = float(pd.to_numeric(part["PF"], errors="coerce").mean())
    pa = float(pd.to_numeric(part["PA"], errors="coerce").mean())
    return {"GP": int(len(part)), "PF": pf, "PA": pa, "DIFF": pf - pa}


def _league_home_edge(history: pd.DataFrame) -> float:
    if history is None or history.empty:
        return 0.0
    home = history.loc[history["HOME"].astype(bool)].copy()
    if len(home) < 20:
        return 0.0
    margin = pd.to_numeric(home["PF"], errors="coerce") - pd.to_numeric(home["PA"], errors="coerce")
    x = float(margin.mean()) if margin.notna().any() else 0.0
    return float(np.clip(x, -5.0, 5.0)) if np.isfinite(x) else 0.0


def _verified_pool(day_str: str):
    try:
        pool, diag = foundation.availability.base._verified_pool_for_day(day_str)
    except Exception as exc:
        return pd.DataFrame(), {"state": "CHECK", "reason": type(exc).__name__}
    return (pool if isinstance(pool, pd.DataFrame) else pd.DataFrame()), (diag or {})


def _find_stat_row(pool: pd.DataFrame, team_id: int, player_id, player_name: str):
    if pool is None or pool.empty:
        return None
    part = pool.loc[pd.to_numeric(pool.get("TEAM_ID"), errors="coerce").eq(int(team_id))].copy()
    if part.empty:
        return None
    if player_id is not None and str(player_id).strip() and "PLAYER_ID" in part.columns:
        target = pd.to_numeric(pd.Series([player_id]), errors="coerce").iloc[0]
        if pd.notna(target):
            exact = part.loc[pd.to_numeric(part["PLAYER_ID"], errors="coerce").eq(float(target))]
            if not exact.empty:
                return exact.iloc[0]
    target_name = _norm_name(player_name)
    if target_name and "PLAYER_NAME" in part.columns:
        names = part["PLAYER_NAME"].map(_norm_name)
        exact = part.loc[names.eq(target_name)]
        if not exact.empty:
            return exact.iloc[0]
    return None


def _reference_role(stat_row) -> tuple[float, float]:
    if stat_row is None:
        return np.nan, np.nan
    pts = _num(stat_row.get("PTS"), np.nan)
    mins = _num(stat_row.get("MIN"), np.nan)
    l10_gp = _num(stat_row.get("L10_GP"), 0.0)
    l10_pts = _num(stat_row.get("L10_PTS"), np.nan)
    l10_min = _num(stat_row.get("L10_MIN"), np.nan)
    if l10_gp >= 3 and np.isfinite(l10_pts):
        pts = 0.65 * l10_pts + 0.35 * pts if np.isfinite(pts) else l10_pts
    if l10_gp >= 3 and np.isfinite(l10_min):
        mins = 0.65 * l10_min + 0.35 * mins if np.isfinite(mins) else l10_min
    return pts, mins


def _availability_impact(game: pd.Series, pool: pd.DataFrame) -> dict:
    away_id = int(_num(game.get("away_team_id"), 0) or 0)
    home_id = int(_num(game.get("home_team_id"), 0) or 0)
    try:
        snap = foundation.availability.availability_for_game(game, pool)
    except Exception as exc:
        return {
            "away_impact": 0.0, "home_impact": 0.0, "hard_out": 0,
            "uncertain": 0, "impact_unknown": 1, "reason": type(exc).__name__,
        }
    statuses = snap.get("players")
    if not isinstance(statuses, pd.DataFrame) or statuses.empty:
        return {"away_impact": 0.0, "home_impact": 0.0, "hard_out": 0, "uncertain": 0, "impact_unknown": 0, "reason": ""}

    impacts = {away_id: 0.0, home_id: 0.0}
    hard_out = uncertain = unknown = 0
    out_set = set(foundation.availability.OUT_STATUSES)
    uncertain_set = set(foundation.availability.UNCERTAIN_STATUSES)

    for _, status in statuses.iterrows():
        designation = str(status.get("DESIGNATION") or "").upper().strip()
        tid = int(_num(status.get("TEAM_ID"), 0) or 0)
        if designation in uncertain_set:
            uncertain += 1
        if designation not in out_set:
            continue
        hard_out += 1
        stat = _find_stat_row(pool, tid, status.get("PLAYER_ID"), status.get("PLAYER_NAME"))
        if stat is None:
            unknown += 1
            continue
        pts, mins = _reference_role(stat)
        if not np.isfinite(pts) or pts < 0:
            unknown += 1
            continue
        role = float(np.clip((mins / 30.0) if np.isfinite(mins) and mins > 0 else 0.35, 0.35, 1.0))
        # Replacement players recover a meaningful portion of raw scoring. Only
        # the conservative net portion is removed from the team projection.
        net = float(np.clip(OUT_REPLACEMENT_FACTOR * pts * role, 0.0, MAX_PLAYER_OUT_IMPACT))
        impacts[tid] = impacts.get(tid, 0.0) + net

    for tid in list(impacts):
        impacts[tid] = float(np.clip(impacts[tid], 0.0, MAX_TEAM_OUT_IMPACT))
    return {
        "away_impact": impacts.get(away_id, 0.0),
        "home_impact": impacts.get(home_id, 0.0),
        "hard_out": hard_out,
        "uncertain": uncertain,
        "impact_unknown": unknown,
        "reason": "",
    }


def _game_projection(game: pd.Series, ctx: dict, history: pd.DataFrame, pool: pd.DataFrame, pool_diag: dict) -> dict:
    gid = str(game.get("game_id") or "")
    away_name = str(game.get("away_team") or "Away")
    home_name = str(game.get("home_team") or "Home")
    away_id = int(_num(game.get("away_team_id"), 0) or 0)
    home_id = int(_num(game.get("home_team_id"), 0) or 0)
    away = (ctx or {}).get("away") or {}
    home = (ctx or {}).get("home") or {}

    components = {}
    if int(_num(away.get("GP"), 0) or 0) >= MIN_TEAM_GAMES and int(_num(home.get("GP"), 0) or 0) >= MIN_TEAM_GAMES:
        a = _mean2(away.get("PF"), home.get("PA")); h = _mean2(home.get("PF"), away.get("PA"))
        if np.isfinite(a) and np.isfinite(h): components["season"] = (a, h)
        a = _mean2(away.get("L10_PF"), home.get("L10_PA")); h = _mean2(home.get("L10_PF"), away.get("L10_PA"))
        if np.isfinite(a) and np.isfinite(h): components["recent"] = (a, h)

    away_road = _venue_split(history, away_id, home=False)
    home_home = _venue_split(history, home_id, home=True)
    if away_road["GP"] >= MIN_VENUE_GAMES and home_home["GP"] >= MIN_VENUE_GAMES:
        a = _mean2(away_road["PF"], home_home["PA"]); h = _mean2(home_home["PF"], away_road["PA"])
        if np.isfinite(a) and np.isfinite(h): components["venue"] = (a, h)

    adv_ok = (
        int(_num(away.get("ADV_GAMES"), 0) or 0) >= MIN_ADV_GAMES
        and int(_num(home.get("ADV_GAMES"), 0) or 0) >= MIN_ADV_GAMES
    )
    if adv_ok:
        pace = _mean2(away.get("PACE_L10"), home.get("PACE_L10"))
        away_rating = _mean2(away.get("ORTG_L10"), home.get("DRTG_L10"))
        home_rating = _mean2(home.get("ORTG_L10"), away.get("DRTG_L10"))
        if np.isfinite(pace) and pace > 0 and np.isfinite(away_rating) and np.isfinite(home_rating):
            components["advanced"] = (pace * away_rating / 100.0, pace * home_rating / 100.0)

    required_ok = "season" in components and "recent" in components
    if not required_ok:
        return {
            "game_id": gid, "away_team": away_name, "home_team": home_name,
            "state": "BLOCKED", "reason": "season/recent scoring history incomplete",
            "component_count": len(components), "components": ", ".join(components),
        }

    weight_sum = sum(WEIGHTS[k] for k in components)
    away_score = sum(WEIGHTS[k] * components[k][0] for k in components) / weight_sum
    home_score = sum(WEIGHTS[k] * components[k][1] for k in components) / weight_sum

    # Venue splits already encode location. If they are unavailable, use the
    # date-cut league home margin as a fallback rather than inventing a constant.
    home_edge_fallback = 0.0
    if "venue" not in components:
        home_edge_fallback = _league_home_edge(history)
        away_score -= home_edge_fallback / 2.0
        home_score += home_edge_fallback / 2.0

    av = _availability_impact(game, pool)
    away_score -= float(av["away_impact"])
    home_score -= float(av["home_impact"])

    blocked = int(av.get("impact_unknown", 0) or 0) > 0
    uncertain = int(av.get("uncertain", 0) or 0)
    pool_state = str((pool_diag or {}).get("state") or "CHECK").upper()
    state = "BLOCKED" if blocked else ("MONITOR" if uncertain or "advanced" not in components or pool_state != "VERIFIED" else "READY")
    reason = "OUT-player impact unresolved" if blocked else ("uncertain availability / reduced data layer" if state == "MONITOR" else "")

    margin_home = home_score - away_score
    if abs(margin_home) < 0.05:
        winner, winner_margin = "Even", 0.0
    elif margin_home > 0:
        winner, winner_margin = home_name, margin_home
    else:
        winner, winner_margin = away_name, -margin_home

    return {
        "game_id": gid,
        "away_team": away_name,
        "home_team": home_name,
        "first_tip_et": str(game.get("first_tip_et") or "—"),
        "away_score": float(away_score),
        "home_score": float(home_score),
        "home_margin": float(margin_home),
        "winner": winner,
        "winner_margin": float(winner_margin),
        "state": state,
        "reason": reason,
        "component_count": int(len(components)),
        "components": ", ".join(components.keys()),
        "season_away": components.get("season", (np.nan, np.nan))[0],
        "season_home": components.get("season", (np.nan, np.nan))[1],
        "recent_away": components.get("recent", (np.nan, np.nan))[0],
        "recent_home": components.get("recent", (np.nan, np.nan))[1],
        "venue_away": components.get("venue", (np.nan, np.nan))[0],
        "venue_home": components.get("venue", (np.nan, np.nan))[1],
        "advanced_away": components.get("advanced", (np.nan, np.nan))[0],
        "advanced_home": components.get("advanced", (np.nan, np.nan))[1],
        "away_road_gp": int(away_road["GP"]),
        "home_home_gp": int(home_home["GP"]),
        "home_edge_fallback": float(home_edge_fallback),
        "away_out_impact": float(av["away_impact"]),
        "home_out_impact": float(av["home_impact"]),
        "hard_out": int(av["hard_out"]),
        "uncertain": uncertain,
        "impact_unknown": int(av["impact_unknown"]),
        "sportsbook_inputs": 0,
    }


def project_slate(day_str: str, pregame: pd.DataFrame, contexts: dict):
    """Project every clock-safe pregame game without accepting market inputs."""
    if pregame is None or pregame.empty:
        return pd.DataFrame(), {"state": "N/A", "games": 0, "projected": 0, "ready": 0, "monitor": 0, "blocked": 0, "sportsbook_inputs": 0}
    history = _history_before(day_str)
    pool, pool_diag = _verified_pool(day_str)
    rows = []
    for _, game in pregame.iterrows():
        gid = str(game.get("game_id") or "")
        rows.append(_game_projection(game, (contexts or {}).get(gid) or {}, history, pool, pool_diag))
    frame = pd.DataFrame(rows)
    states = frame.get("state", pd.Series(dtype=object)).astype(str).str.upper()
    blocked = int(states.eq("BLOCKED").sum())
    monitor = int(states.eq("MONITOR").sum())
    ready = int(states.eq("READY").sum())
    projected = int(states.isin(["READY", "MONITOR"]).sum())
    state = "READY" if projected == len(pregame) and blocked == 0 else "CHECK"
    return frame, {
        "state": state,
        "games": int(len(pregame)),
        "projected": projected,
        "ready": ready,
        "monitor": monitor,
        "blocked": blocked,
        "sportsbook_inputs": 0,
        "pool_state": str((pool_diag or {}).get("state") or "CHECK"),
        "history_games": int(len(history) // 2) if isinstance(history, pd.DataFrame) and not history.empty else 0,
    }


__all__ = ["MODEL_VERSION", "project_slate"]
