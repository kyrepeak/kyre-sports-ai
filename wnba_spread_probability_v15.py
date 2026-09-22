"""WNBA Spread V1.5 — Step 6 analytical cover probability + fair spread.

Consumes only:
- Step-5 market-independent projected home margin;
- date-cut empirical team/league margin dispersion for uncertainty; and
- Step-4 exact sportsbook spread/price pairs as comparison thresholds.

The sportsbook line/price NEVER changes the Step-5 projected mean. Step 6 only asks
how often the independent margin distribution would cover an already-verified line.
No Monte Carlo is run here; the 5M simulation remains Step 7.
"""
from __future__ import annotations

from math import erf, sqrt

import numpy as np
import pandas as pd

import wnba_spread_projection_v14 as projection

MODEL_VERSION = "WNBA SPREAD PROBABILITY V1.5"

MIN_TEAM_MARGIN_GAMES = 8
PRIOR_GAMES = 8.0
MIN_SIGMA = 7.0
MAX_SIGMA = 24.0
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


def _team_margin_sample(history: pd.DataFrame, team_id: int) -> np.ndarray:
    if history is None or history.empty:
        return np.asarray([], dtype=float)
    part = history.loc[pd.to_numeric(history.get("TEAM_ID"), errors="coerce").eq(int(team_id))].copy()
    if part.empty:
        return np.asarray([], dtype=float)
    pf = pd.to_numeric(part.get("PF"), errors="coerce")
    pa = pd.to_numeric(part.get("PA"), errors="coerce")
    vals = (pf - pa).dropna().astype(float).to_numpy()
    return vals[np.isfinite(vals)]


def _league_margin_sample(history: pd.DataFrame) -> np.ndarray:
    if history is None or history.empty:
        return np.asarray([], dtype=float)
    # One row per game only. The context history contains two team-perspective rows.
    if "HOME" in history.columns:
        part = history.loc[history["HOME"].astype(bool)].copy()
    else:
        part = history.drop_duplicates(subset=["GAME_ID"], keep="first").copy()
    pf = pd.to_numeric(part.get("PF"), errors="coerce")
    pa = pd.to_numeric(part.get("PA"), errors="coerce")
    vals = (pf - pa).dropna().astype(float).to_numpy()
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
    # Empirical-Bayes-style variance shrinkage prevents a short/noisy team sample
    # from creating unrealistically narrow or wide cover probabilities.
    weight = max(1.0, float(n - 1))
    shrunk = (weight * tv + PRIOR_GAMES * league_var) / (weight + PRIOR_GAMES)
    source = "TEAM+LEAGUE" if n >= MIN_TEAM_MARGIN_GAMES else "SHORT_SAMPLE+LEAGUE"
    return float(shrunk), n, source


def _component_margin_sd(row: pd.Series) -> float:
    margins = []
    for prefix in ("season", "recent", "venue", "advanced"):
        a = _num(row.get(f"{prefix}_away"), np.nan)
        h = _num(row.get(f"{prefix}_home"), np.nan)
        if np.isfinite(a) and np.isfinite(h):
            margins.append(h - a)
    if len(margins) < 2:
        return 0.0
    return float(np.std(np.asarray(margins, dtype=float), ddof=1))


def _game_sigma(day_str: str, game: pd.Series, proj: pd.Series, history: pd.DataFrame, league_var: float) -> dict:
    away_id = int(_num(game.get("away_team_id"), 0) or 0)
    home_id = int(_num(game.get("home_team_id"), 0) or 0)
    away_vals = _team_margin_sample(history, away_id)
    home_vals = _team_margin_sample(history, home_id)
    away_var, away_n, away_source = _shrink_var(away_vals, league_var)
    home_var, home_n, home_source = _shrink_var(home_vals, league_var)

    valid = [v for v in (away_var, home_var, league_var) if np.isfinite(v) and v > 0]
    if not valid:
        return {
            "sigma": np.nan, "away_n": away_n, "home_n": home_n,
            "source": "UNAVAILABLE", "component_sd": np.nan,
        }

    if np.isfinite(away_var) and np.isfinite(home_var) and np.isfinite(league_var):
        base_var = 0.40 * away_var + 0.40 * home_var + 0.20 * league_var
    elif np.isfinite(away_var) and np.isfinite(home_var):
        base_var = 0.50 * away_var + 0.50 * home_var
    else:
        base_var = float(np.mean(valid))

    component_sd = _component_margin_sd(proj)
    # Component disagreement is epistemic uncertainty. It widens the empirical
    # game-margin sigma modestly; it never shifts the projected mean.
    sigma = sqrt(max(0.0, base_var) + (COMPONENT_DISAGREEMENT_WEIGHT * component_sd) ** 2)
    sigma = float(np.clip(sigma, MIN_SIGMA, MAX_SIGMA))
    return {
        "sigma": sigma,
        "away_n": away_n,
        "home_n": home_n,
        "source": f"{away_source} / {home_source}",
        "component_sd": component_sd,
    }


def _cover_probs(mean_home_margin: float, sigma: float, home_spread: float) -> dict:
    """Return home/away cover + push from an integer-score normal approximation."""
    mean = _num(mean_home_margin, np.nan)
    sd = _num(sigma, np.nan)
    spread = _num(home_spread, np.nan)
    if not np.isfinite(mean) or not np.isfinite(sd) or sd <= 0 or not np.isfinite(spread):
        return {"home_cover": np.nan, "away_cover": np.nan, "push": np.nan}

    threshold = -spread  # home covers when actual home margin > threshold
    if _is_integer_line(spread):
        k = float(round(threshold))
        lo = _norm_cdf(k - 0.5, mean, sd)
        hi = _norm_cdf(k + 0.5, mean, sd)
        away_cover = lo
        push = max(0.0, hi - lo)
        home_cover = max(0.0, 1.0 - hi)
    else:
        away_cover = _norm_cdf(threshold, mean, sd)
        push = 0.0
        home_cover = 1.0 - away_cover

    total = home_cover + away_cover + push
    if np.isfinite(total) and total > 0:
        home_cover /= total
        away_cover /= total
        push /= total
    return {"home_cover": float(home_cover), "away_cover": float(away_cover), "push": float(push)}


def probability_board(day_str: str, pregame: pd.DataFrame, projected: pd.DataFrame, ready_lines: pd.DataFrame):
    """Build book-by-book analytical cover probabilities without Monte Carlo."""
    empty_meta = {
        "state": "N/A", "games": 0, "covered_games": 0, "rows": 0,
        "ready": 0, "monitor": 0, "blocked": 0, "model_ready": False,
    }
    if pregame is None or pregame.empty or projected is None or projected.empty or ready_lines is None or ready_lines.empty:
        return pd.DataFrame(), empty_meta

    history = projection._history_before(day_str)
    league_vals = _league_margin_sample(history)
    league_var = _sample_var(league_vals)
    if not np.isfinite(league_var) or league_var <= 0:
        meta = dict(empty_meta)
        meta.update({"state": "CHECK", "games": int(len(pregame)), "blocked": int(len(pregame))})
        return pd.DataFrame(), meta

    games = {str(r.get("game_id") or ""): r for _, r in pregame.iterrows()}
    projs = {str(r.get("game_id") or ""): r for _, r in projected.iterrows()}
    rows = []
    covered_ids = set()

    for _, line in ready_lines.iterrows():
        gid = str(line.get("game_id") or "")
        game = games.get(gid)
        proj = projs.get(gid)
        if game is None or proj is None:
            continue
        if str(proj.get("state") or "BLOCKED").upper() == "BLOCKED":
            continue

        mean_home = _num(proj.get("home_margin"), np.nan)
        home_spread = _num(line.get("home_spread"), np.nan)
        away_spread = _num(line.get("away_spread"), np.nan)
        sigma_info = _game_sigma(day_str, game, proj, history, league_var)
        sigma = _num(sigma_info.get("sigma"), np.nan)
        probs = _cover_probs(mean_home, sigma, home_spread)
        if not all(np.isfinite(_num(probs.get(k), np.nan)) for k in ("home_cover", "away_cover", "push")):
            continue

        push = probs["push"]
        no_push_mass = max(1e-12, 1.0 - push)
        home_model_np = probs["home_cover"] / no_push_mass
        away_model_np = probs["away_cover"] / no_push_mass

        home_price = _num(line.get("home_spread_price"), np.nan)
        away_price = _num(line.get("away_spread_price"), np.nan)
        home_imp = _american_implied(home_price)
        away_imp = _american_implied(away_price)
        denom = home_imp + away_imp if np.isfinite(home_imp) and np.isfinite(away_imp) else np.nan
        home_market = home_imp / denom if np.isfinite(denom) and denom > 0 else np.nan
        away_market = away_imp / denom if np.isfinite(denom) and denom > 0 else np.nan

        proj_state = str(proj.get("state") or "READY").upper()
        short_sample = int(sigma_info.get("away_n", 0)) < MIN_TEAM_MARGIN_GAMES or int(sigma_info.get("home_n", 0)) < MIN_TEAM_MARGIN_GAMES
        state = "MONITOR" if proj_state == "MONITOR" or short_sample else "READY"

        rows.append({
            "game_id": gid,
            "away_team": str(game.get("away_team") or line.get("away_team") or "Away"),
            "home_team": str(game.get("home_team") or line.get("home_team") or "Home"),
            "first_tip_et": str(game.get("first_tip_et") or line.get("first_tip_et") or "—"),
            "book": str(line.get("book") or ""),
            "away_spread": away_spread,
            "home_spread": home_spread,
            "away_price": away_price,
            "home_price": home_price,
            "projected_home_margin": mean_home,
            "fair_home_spread": -mean_home,
            "fair_away_spread": mean_home,
            "sigma": sigma,
            "margin_low80": mean_home - 1.2815515655 * sigma,
            "margin_high80": mean_home + 1.2815515655 * sigma,
            "away_cover": probs["away_cover"],
            "home_cover": probs["home_cover"],
            "push": push,
            "away_no_push": away_model_np,
            "home_no_push": home_model_np,
            "away_fair_odds": _fair_american(away_model_np),
            "home_fair_odds": _fair_american(home_model_np),
            "away_market_novig": away_market,
            "home_market_novig": home_market,
            "away_edge_pp": 100.0 * (away_model_np - away_market) if np.isfinite(away_market) else np.nan,
            "home_edge_pp": 100.0 * (home_model_np - home_market) if np.isfinite(home_market) else np.nan,
            "away_margin_games": int(sigma_info.get("away_n", 0)),
            "home_margin_games": int(sigma_info.get("home_n", 0)),
            "league_margin_games": int(len(league_vals)),
            "component_margin_sd": _num(sigma_info.get("component_sd"), np.nan),
            "sigma_source": str(sigma_info.get("source") or ""),
            "projection_state": proj_state,
            "state": state,
            "sportsbook_projection_inputs": 0,
            "probability_method": "analytic empirical-sigma normal + integer push correction",
        })
        covered_ids.add(gid)

    frame = pd.DataFrame(rows)
    game_ids = set(str(x) for x in pregame.get("game_id", pd.Series(dtype=object)).astype(str).tolist())
    ready = int((frame.get("state", pd.Series(dtype=object)).astype(str) == "READY").sum()) if not frame.empty else 0
    monitor = int((frame.get("state", pd.Series(dtype=object)).astype(str) == "MONITOR").sum()) if not frame.empty else 0
    blocked_games = int(len(game_ids - covered_ids))
    state = "READY" if game_ids and game_ids.issubset(covered_ids) else "CHECK"
    meta = {
        "state": state,
        "games": int(len(game_ids)),
        "covered_games": int(len(game_ids & covered_ids)),
        "rows": int(len(frame)),
        "ready": ready,
        "monitor": monitor,
        "blocked": blocked_games,
        "league_margin_games": int(len(league_vals)),
        "league_sigma": float(sqrt(league_var)),
        "model_ready": bool(state == "READY"),
    }
    return frame, meta


__all__ = [
    "MODEL_VERSION", "probability_board", "_cover_probs", "_fair_american",
    "_american_implied", "_game_sigma",
]
