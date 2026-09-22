"""WNBA Game Total V1.3 — Step 6 analytical O/U probability + fair total.

Consumes only:
- Step-5 market-independent projected game total;
- date-cut empirical team/league full-game-total dispersion; and
- Step-4 exact same-book sportsbook total/price pairs as comparison thresholds.

The sportsbook total and prices NEVER move the Step-5 projected mean. Step 6 asks
how often the independent total distribution would finish Over/Under an already
verified line. Integer totals receive explicit push probability through continuity
correction. No Monte Carlo is run here; the actual 5M simulation remains Step 7.
"""
from __future__ import annotations

from math import erf, sqrt

import numpy as np
import pandas as pd

import wnba_spread_projection_v14 as score_projection

MODEL_VERSION = "WNBA GAME TOTAL PROBABILITY V1.3"

MIN_TEAM_TOTAL_GAMES = 8
PRIOR_GAMES = 8.0
MIN_SIGMA = 8.0
MAX_SIGMA = 30.0
COMPONENT_DISAGREEMENT_WEIGHT = 0.25


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm_cdf(x: float, mean: float, sigma: float) -> float:
    if not np.isfinite(x) or not np.isfinite(mean) or not np.isfinite(sigma) or sigma <= 0:
        return np.nan
    z = (x - mean) / (sigma * sqrt(2.0))
    return 0.5 * (1.0 + erf(z))


def _american_implied(odds) -> float:
    x = _num(odds, np.nan)
    if not np.isfinite(x) or x == 0:
        return np.nan
    if x > 0:
        return 100.0 / (x + 100.0)
    return (-x) / ((-x) + 100.0)


def _fair_american(probability) -> float:
    p = _num(probability, np.nan)
    if not np.isfinite(p) or p <= 0 or p >= 1:
        return np.nan
    if p >= 0.5:
        return -100.0 * p / (1.0 - p)
    return 100.0 * (1.0 - p) / p


def _is_integer_line(value) -> bool:
    x = _num(value, np.nan)
    return bool(np.isfinite(x) and abs(x - round(x)) <= 1e-8)


def _team_total_sample(history: pd.DataFrame, team_id: int) -> np.ndarray:
    if history is None or history.empty:
        return np.asarray([], dtype=float)
    part = history.loc[pd.to_numeric(history.get("TEAM_ID"), errors="coerce").eq(int(team_id))].copy()
    if part.empty:
        return np.asarray([], dtype=float)
    pf = pd.to_numeric(part.get("PF"), errors="coerce")
    pa = pd.to_numeric(part.get("PA"), errors="coerce")
    vals = (pf + pa).dropna().astype(float).to_numpy()
    return vals[np.isfinite(vals)]


def _league_total_sample(history: pd.DataFrame) -> np.ndarray:
    if history is None or history.empty:
        return np.asarray([], dtype=float)
    # Context history has two team-perspective rows per game; keep one actual game.
    if "HOME" in history.columns:
        part = history.loc[history["HOME"].astype(bool)].copy()
    elif "GAME_ID" in history.columns:
        part = history.drop_duplicates(subset=["GAME_ID"], keep="first").copy()
    else:
        part = history.iloc[::2].copy()
    pf = pd.to_numeric(part.get("PF"), errors="coerce")
    pa = pd.to_numeric(part.get("PA"), errors="coerce")
    vals = (pf + pa).dropna().astype(float).to_numpy()
    return vals[np.isfinite(vals)]


def _sample_var(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 2:
        return np.nan
    return float(np.var(arr, ddof=1))


def _shrink_var(team_values: np.ndarray, league_var: float) -> tuple[float, int, str]:
    arr = np.asarray(team_values, dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(len(arr))
    tv = _sample_var(arr)
    if not np.isfinite(league_var) or league_var <= 0:
        return tv, n, "TEAM_ONLY" if np.isfinite(tv) else "UNAVAILABLE"
    if n < 2 or not np.isfinite(tv):
        return float(league_var), n, "LEAGUE_FALLBACK"
    weight = max(1.0, float(n - 1))
    shrunk = (weight * tv + PRIOR_GAMES * league_var) / (weight + PRIOR_GAMES)
    source = "TEAM+LEAGUE" if n >= MIN_TEAM_TOTAL_GAMES else "SHORT_SAMPLE+LEAGUE"
    return float(shrunk), n, source


def _component_total_sd(proj: pd.Series) -> float:
    values = []
    for key in (
        "season_total_component", "recent_total_component",
        "venue_total_component", "advanced_total_component",
    ):
        x = _num(proj.get(key), np.nan)
        if np.isfinite(x):
            values.append(x)
    if len(values) < 2:
        return 0.0
    return float(np.std(np.asarray(values, dtype=float), ddof=1))


def _game_sigma(game: pd.Series, proj: pd.Series, history: pd.DataFrame, league_var: float) -> dict:
    away_id = int(_num(game.get("away_team_id"), 0) or 0)
    home_id = int(_num(game.get("home_team_id"), 0) or 0)
    away_vals = _team_total_sample(history, away_id)
    home_vals = _team_total_sample(history, home_id)
    away_var, away_n, away_source = _shrink_var(away_vals, league_var)
    home_var, home_n, home_source = _shrink_var(home_vals, league_var)

    valid = [v for v in (away_var, home_var, league_var) if np.isfinite(v) and v > 0]
    if not valid:
        return {"sigma": np.nan, "away_n": away_n, "home_n": home_n, "source": "UNAVAILABLE", "component_sd": np.nan}

    if np.isfinite(away_var) and np.isfinite(home_var) and np.isfinite(league_var):
        base_var = 0.40 * away_var + 0.40 * home_var + 0.20 * league_var
    elif np.isfinite(away_var) and np.isfinite(home_var):
        base_var = 0.50 * away_var + 0.50 * home_var
    else:
        base_var = float(np.mean(valid))

    component_sd = _component_total_sd(proj)
    sigma = sqrt(max(0.0, base_var) + (COMPONENT_DISAGREEMENT_WEIGHT * component_sd) ** 2)
    sigma = float(np.clip(sigma, MIN_SIGMA, MAX_SIGMA))
    return {
        "sigma": sigma,
        "away_n": away_n,
        "home_n": home_n,
        "source": f"{away_source} / {home_source}",
        "component_sd": component_sd,
    }


def _total_probs(mean_total: float, sigma: float, line: float) -> dict:
    mean = _num(mean_total, np.nan)
    sd = _num(sigma, np.nan)
    threshold = _num(line, np.nan)
    if not np.isfinite(mean) or not np.isfinite(sd) or sd <= 0 or not np.isfinite(threshold):
        return {"over": np.nan, "under": np.nan, "push": np.nan}

    # Basketball scoring is integer-valued. Integer totals therefore have an
    # explicit push bucket centered on that score; half-points have no push.
    if _is_integer_line(threshold):
        k = float(round(threshold))
        lo = _norm_cdf(k - 0.5, mean, sd)
        hi = _norm_cdf(k + 0.5, mean, sd)
        under = lo
        push = max(0.0, hi - lo)
        over = max(0.0, 1.0 - hi)
    else:
        under = _norm_cdf(threshold, mean, sd)
        push = 0.0
        over = 1.0 - under

    total = over + under + push
    if np.isfinite(total) and total > 0:
        over /= total
        under /= total
        push /= total
    return {"over": float(over), "under": float(under), "push": float(push)}


def probability_board(day_str: str, pregame: pd.DataFrame, projected: pd.DataFrame, ready_lines: pd.DataFrame):
    empty_meta = {
        "state": "N/A", "games": 0, "covered_games": 0, "rows": 0,
        "ready": 0, "monitor": 0, "blocked": 0, "model_ready": False,
        "league_total_games": 0, "sportsbook_projection_inputs": 0,
    }
    if pregame is None or pregame.empty or projected is None or projected.empty or ready_lines is None or ready_lines.empty:
        return pd.DataFrame(), empty_meta

    history = score_projection._history_before(day_str)
    league_vals = _league_total_sample(history)
    league_var = _sample_var(league_vals)
    if not np.isfinite(league_var) or league_var <= 0:
        meta = dict(empty_meta)
        meta.update({"state": "CHECK", "games": int(len(pregame)), "blocked": int(len(pregame)), "league_total_games": int(len(league_vals))})
        return pd.DataFrame(), meta

    games = {str(r.get("game_id") or ""): r for _, r in pregame.iterrows()}
    projs = {str(r.get("game_id") or ""): r for _, r in projected.iterrows()}
    rows = []
    covered_ids = set()

    for _, line_row in ready_lines.iterrows():
        gid = str(line_row.get("game_id") or "")
        game = games.get(gid)
        proj = projs.get(gid)
        if game is None or proj is None:
            continue
        proj_state = str(proj.get("state") or "BLOCKED").upper()
        if proj_state == "BLOCKED":
            continue

        mean_total = _num(proj.get("projected_total"), np.nan)
        market_total = _num(line_row.get("total"), np.nan)
        sigma_info = _game_sigma(game, proj, history, league_var)
        sigma = _num(sigma_info.get("sigma"), np.nan)
        probs = _total_probs(mean_total, sigma, market_total)
        if not all(np.isfinite(_num(probs.get(k), np.nan)) for k in ("over", "under", "push")):
            continue

        push = probs["push"]
        no_push_mass = max(1e-12, 1.0 - push)
        over_np = probs["over"] / no_push_mass
        under_np = probs["under"] / no_push_mass

        over_price = _num(line_row.get("over_price"), np.nan)
        under_price = _num(line_row.get("under_price"), np.nan)
        over_imp = _american_implied(over_price)
        under_imp = _american_implied(under_price)
        denom = over_imp + under_imp if np.isfinite(over_imp) and np.isfinite(under_imp) else np.nan
        over_market = over_imp / denom if np.isfinite(denom) and denom > 0 else np.nan
        under_market = under_imp / denom if np.isfinite(denom) and denom > 0 else np.nan

        short_sample = int(sigma_info.get("away_n", 0)) < MIN_TEAM_TOTAL_GAMES or int(sigma_info.get("home_n", 0)) < MIN_TEAM_TOTAL_GAMES
        state = "MONITOR" if proj_state == "MONITOR" or short_sample else "READY"

        rows.append({
            "game_id": gid,
            "away_team": str(game.get("away_team") or line_row.get("away_team") or "Away"),
            "home_team": str(game.get("home_team") or line_row.get("home_team") or "Home"),
            "first_tip_et": str(game.get("first_tip_et") or line_row.get("first_tip_et") or "—"),
            "book": str(line_row.get("book") or ""),
            "market_total": market_total,
            "over_price": over_price,
            "under_price": under_price,
            "projected_total": mean_total,
            "fair_total": mean_total,
            "sigma": sigma,
            "total_low80": mean_total - 1.2815515655 * sigma,
            "total_high80": mean_total + 1.2815515655 * sigma,
            "over": probs["over"],
            "under": probs["under"],
            "push": push,
            "over_no_push": over_np,
            "under_no_push": under_np,
            "over_fair_odds": _fair_american(over_np),
            "under_fair_odds": _fair_american(under_np),
            "over_market_novig": over_market,
            "under_market_novig": under_market,
            "over_edge_pp": 100.0 * (over_np - over_market) if np.isfinite(over_market) else np.nan,
            "under_edge_pp": 100.0 * (under_np - under_market) if np.isfinite(under_market) else np.nan,
            "away_total_games": int(sigma_info.get("away_n", 0)),
            "home_total_games": int(sigma_info.get("home_n", 0)),
            "league_total_games": int(len(league_vals)),
            "component_total_sd": _num(sigma_info.get("component_sd"), np.nan),
            "sigma_source": str(sigma_info.get("source") or ""),
            "projection_state": proj_state,
            "state": state,
            "sportsbook_projection_inputs": 0,
            "probability_method": "analytic empirical-total-sigma normal + integer push correction",
        })
        covered_ids.add(gid)

    frame = pd.DataFrame(rows)
    game_ids = set(str(x) for x in pregame.get("game_id", pd.Series(dtype=object)).astype(str).tolist())
    ready = int(frame.get("state", pd.Series(dtype=object)).astype(str).eq("READY").sum()) if not frame.empty else 0
    monitor = int(frame.get("state", pd.Series(dtype=object)).astype(str).eq("MONITOR").sum()) if not frame.empty else 0
    blocked = int(len(game_ids - covered_ids))
    state = "READY" if game_ids and game_ids.issubset(covered_ids) else "CHECK"
    meta = {
        "state": state,
        "games": int(len(game_ids)),
        "covered_games": int(len(game_ids & covered_ids)),
        "rows": int(len(frame)),
        "ready": ready,
        "monitor": monitor,
        "blocked": blocked,
        "league_total_games": int(len(league_vals)),
        "league_sigma": float(sqrt(league_var)),
        "model_ready": bool(state == "READY"),
        "sportsbook_projection_inputs": 0,
    }
    return frame, meta


__all__ = [
    "MODEL_VERSION", "probability_board", "_total_probs", "_fair_american",
    "_american_implied", "_game_sigma",
]
