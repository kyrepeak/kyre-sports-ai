"""WNBA Rebounds + Assists V1 — Step 5 projection + correlated 5M Monte Carlo.

This module is isolated to the new WNBA R+A route.

Projection policy
-----------------
* Sportsbook line/price NEVER changes the statistical projection.
* REB and AST are projected separately from verified pre-slate player history.
* Expected minutes and per-36 component rates blend season/L10/L5 information.
* Step-4 pace/rebound/assist environment enters only through deliberately
  shrunken, capped matchup multipliers.
* H2H hit rates and sportsbook probabilities are not projection inputs.
* If official tracking metrics (potential assists/rebound chances) are absent,
  no synthetic tracking values are invented.

Simulation policy
-----------------
* Standard run: 5,000,000 correlated REB+AST draws.
* Deterministic seed; 250,000-draw batches.
* Empirical REB/AST game correlation is sample-shrunk toward zero.
* Exact integer lines support pushes; half-point lines cannot push.
* Reports actual simulations, batches, seed, MC SE, batch spread, convergence,
  mean/median/mode, P10/P90, component SDs and fair odds.
"""
from __future__ import annotations

import hashlib
import math
import time

import numpy as np
import pandas as pd
import streamlit as st

MODEL_VERSION = "WNBA R+A V1 • STEP 5 PROJECTION + CORRELATED MC"
STANDARD_SIMS = 5_000_000
BATCH_SIZE = 250_000
CONVERGENCE_BATCH_SPREAD = 0.006
CONVERGENCE_MC_SE = 0.0005

_BLOCKED = {"OUT", "INACTIVE", "DOUBTFUL"}
_UNCERTAIN = {"QUESTIONABLE", "DAY-TO-DAY", "PROBABLE", "GAME-TIME DECISION"}


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _weighted(values):
    """Weighted mean of (value, weight) pairs with missing-value renormalization."""
    good = [(float(v), float(w)) for v, w in values if np.isfinite(_num(v, np.nan)) and float(w) > 0]
    if not good:
        return np.nan
    den = sum(w for _, w in good)
    return sum(v * w for v, w in good) / den if den > 0 else np.nan


def _rate36(frame: pd.DataFrame, col: str):
    if frame is None or frame.empty or col not in frame.columns or "MIN" not in frame.columns:
        return np.nan
    mins = pd.to_numeric(frame["MIN"], errors="coerce")
    vals = pd.to_numeric(frame[col], errors="coerce")
    mask = mins.gt(0) & vals.notna()
    if not mask.any():
        return np.nan
    total_min = float(mins[mask].sum())
    return 36.0 * float(vals[mask].sum()) / total_min if total_min > 0 else np.nan


def _shrunken_ratio(numerator, denominator, strength, low=0.92, high=1.08):
    num = _num(numerator, np.nan)
    den = _num(denominator, np.nan)
    if not np.isfinite(num) or not np.isfinite(den) or den <= 0:
        return 1.0
    raw = num / den
    factor = 1.0 + float(strength) * (raw - 1.0)
    return float(np.clip(factor, low, high))


def _status(ctx):
    av = (ctx or {}).get("availability") or {}
    return str(av.get("player_status") or "STATUS CHECK").upper().strip()


def project_ra(player_row, logs: pd.DataFrame, ctx: dict) -> dict:
    """Project REB and AST separately. No sportsbook information is accepted."""
    logs = logs.copy() if isinstance(logs, pd.DataFrame) else pd.DataFrame()
    if logs.empty:
        return {"state": "NO_HISTORY", "model_version": MODEL_VERSION}

    status = _status(ctx)
    if status in _BLOCKED:
        return {
            "state": "BLOCKED_STATUS",
            "player_status": status,
            "model_version": MODEL_VERSION,
        }

    season = logs.copy()
    l10 = season.head(10)
    l5 = season.head(5)

    row_min = _num(player_row.get("MIN"), np.nan)
    season_min = _num(pd.to_numeric(season.get("MIN"), errors="coerce").mean(), np.nan)
    l10_min = _num(pd.to_numeric(l10.get("MIN"), errors="coerce").mean(), np.nan)
    l5_min = _num(pd.to_numeric(l5.get("MIN"), errors="coerce").mean(), np.nan)

    # Stable season anchor + recent role. Recent form matters, but cannot dominate.
    proj_min = _weighted([
        (row_min if np.isfinite(row_min) else season_min, 0.35),
        (l10_min, 0.30),
        (l5_min, 0.35),
    ])
    if not np.isfinite(proj_min):
        return {"state": "NO_MINUTES", "model_version": MODEL_VERSION}
    proj_min = float(np.clip(proj_min, 8.0, 40.5))

    # Season row averages provide a stable anchor even if current-team logs are short.
    row_reb = _num(player_row.get("REB"), np.nan)
    row_ast = _num(player_row.get("AST"), np.nan)
    season_reb36 = 36.0 * row_reb / row_min if np.isfinite(row_reb) and np.isfinite(row_min) and row_min > 0 else _rate36(season, "REB")
    season_ast36 = 36.0 * row_ast / row_min if np.isfinite(row_ast) and np.isfinite(row_min) and row_min > 0 else _rate36(season, "AST")

    reb36 = _weighted([
        (season_reb36, 0.35),
        (_rate36(l10, "REB"), 0.30),
        (_rate36(l5, "REB"), 0.35),
    ])
    ast36 = _weighted([
        (season_ast36, 0.35),
        (_rate36(l10, "AST"), 0.30),
        (_rate36(l5, "AST"), 0.35),
    ])
    if not np.isfinite(reb36) or not np.isfinite(ast36):
        return {"state": "NO_COMPONENT_RATES", "model_version": MODEL_VERSION}

    role = (ctx or {}).get("role") or {}
    team_env = (ctx or {}).get("team_env") or {}
    opp_env = (ctx or {}).get("opp_env") or {}
    team_adv = (ctx or {}).get("team_adv") or {}

    # Pace compares today's blended environment with the player's recent team pace.
    pace_factor = _shrunken_ratio(
        (ctx or {}).get("blended_pace"),
        team_adv.get("PACE"),
        strength=0.35,
        low=0.94,
        high=1.06,
    )

    # Rebound environment: opponent misses today vs misses the player's team has
    # recently faced, plus opponent rebound allowance vs the player's team norm.
    miss_factor = _shrunken_ratio(
        opp_env.get("team_misses"),
        team_env.get("opp_misses"),
        strength=0.25,
        low=0.92,
        high=1.08,
    )
    reb_allow_factor = _shrunken_ratio(
        opp_env.get("opp_reb"),
        team_env.get("team_reb"),
        strength=0.20,
        low=0.92,
        high=1.08,
    )
    reb_env_factor = float(np.clip(math.sqrt(miss_factor * reb_allow_factor), 0.92, 1.08))

    # Assist environment: what today's opponent has recently allowed compared
    # with the player's team's own recent assist production.
    ast_env_factor = _shrunken_ratio(
        opp_env.get("opp_ast"),
        team_env.get("team_ast"),
        strength=0.30,
        low=0.92,
        high=1.08,
    )

    base_reb = reb36 * proj_min / 36.0
    base_ast = ast36 * proj_min / 36.0
    proj_reb = float(max(0.0, base_reb * pace_factor * reb_env_factor))
    proj_ast = float(max(0.0, base_ast * pace_factor * ast_env_factor))
    proj_ra = proj_reb + proj_ast

    # Variance/correlation comes from game-level REB+AST, preserving shared-minute
    # behavior. Shrink correlation toward zero to protect small samples.
    hist = season.head(20).copy()
    hist_reb = pd.to_numeric(hist.get("REB"), errors="coerce")
    hist_ast = pd.to_numeric(hist.get("AST"), errors="coerce")
    hist_min = pd.to_numeric(hist.get("MIN"), errors="coerce")
    valid = hist_reb.notna() & hist_ast.notna()
    corr_games = int(valid.sum())
    raw_corr = float(hist_reb[valid].corr(hist_ast[valid])) if corr_games >= 3 else 0.0
    if not np.isfinite(raw_corr):
        raw_corr = 0.0
    shrink = corr_games / (corr_games + 12.0) if corr_games >= 8 else 0.0
    corr = float(np.clip(raw_corr * shrink, -0.55, 0.55))

    reb_sd_emp = float(hist_reb[valid].std(ddof=0)) if corr_games >= 3 else np.nan
    ast_sd_emp = float(hist_ast[valid].std(ddof=0)) if corr_games >= 3 else np.nan
    hist_avg_min = _num(hist_min[valid].mean(), proj_min)
    minute_scale = math.sqrt(proj_min / hist_avg_min) if np.isfinite(hist_avg_min) and hist_avg_min > 0 else 1.0
    minute_scale = float(np.clip(minute_scale, 0.85, 1.15))

    reb_sd = max(1.20, (reb_sd_emp * minute_scale) if np.isfinite(reb_sd_emp) else math.sqrt(max(proj_reb, 1.0)) * 0.95)
    ast_sd = max(1.00, (ast_sd_emp * minute_scale) if np.isfinite(ast_sd_emp) else math.sqrt(max(proj_ast, 1.0)) * 0.95)

    # Uncertainty widens the distribution; it does not change the mean.
    min_sd = _num(role.get("l10_min_sd"), np.nan)
    vol_ratio = min_sd / proj_min if np.isfinite(min_sd) and proj_min > 0 else 0.0
    vol_penalty = float(np.clip(max(0.0, vol_ratio - 0.08) * 0.50, 0.0, 0.12))
    reliability = str((ctx or {}).get("reliability") or "LOW").upper()
    reliability_penalty = 0.0 if reliability == "HIGH" else (0.06 if reliability == "MEDIUM" else 0.12)
    sample_penalty = 0.0 if corr_games >= 15 else (0.05 if corr_games >= 8 else 0.10)
    status_penalty = 0.10 if status in _UNCERTAIN else 0.0
    uncertainty_mult = 1.0 + vol_penalty + reliability_penalty + sample_penalty + status_penalty
    reb_sd *= uncertainty_mult
    ast_sd *= uncertainty_mult

    cov = corr * reb_sd * ast_sd
    covariance = np.asarray([[reb_sd * reb_sd, cov], [cov, ast_sd * ast_sd]], dtype=float)

    quality = "HIGH" if (corr_games >= 15 and reliability == "HIGH" and status not in _UNCERTAIN) else (
        "MEDIUM" if corr_games >= 8 and reliability in {"HIGH", "MEDIUM"} else "LOW"
    )

    return {
        "state": "READY",
        "model_version": MODEL_VERSION,
        "player_status": status,
        "data_quality": quality,
        "history_games": int(len(season)),
        "corr_games": corr_games,
        "proj_min": proj_min,
        "reb36": float(reb36),
        "ast36": float(ast36),
        "base_reb": float(base_reb),
        "base_ast": float(base_ast),
        "pace_factor": pace_factor,
        "reb_env_factor": reb_env_factor,
        "ast_env_factor": ast_env_factor,
        "proj_reb": proj_reb,
        "proj_ast": proj_ast,
        "proj_ra": proj_ra,
        "raw_corr": raw_corr,
        "corr": corr,
        "reb_sd": float(reb_sd),
        "ast_sd": float(ast_sd),
        "uncertainty_mult": float(uncertainty_mult),
        "covariance": covariance,
        "projection_inputs": "season/L10/L5 minutes + REB/AST rates + shrunken pace/rebound/assist environment",
        "sportsbook_in_projection": False,
    }


def _stable_seed(day_str, game_id, player_key, line, sims):
    token = f"{MODEL_VERSION}|{day_str}|{game_id}|{player_key}|{float(line):.3f}|{int(sims)}"
    return int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16)


def _nearest_psd(cov):
    a = np.asarray(cov, dtype=float)
    a = (a + a.T) / 2.0
    vals, vecs = np.linalg.eigh(a)
    vals = np.clip(vals, 1e-6, None)
    out = (vecs * vals) @ vecs.T
    return (out + out.T) / 2.0


def _fair_american(prob):
    p = float(np.clip(_num(prob, 0.5), 1e-6, 1 - 1e-6))
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _hist_quantile(hist, q):
    total = int(np.sum(hist))
    if total <= 0:
        return np.nan
    target = max(1, int(math.ceil(float(q) * total)))
    return float(np.searchsorted(np.cumsum(hist), target, side="left"))


@st.cache_data(ttl=900, show_spinner=False, max_entries=256)
def simulate_ra_cached(day_str, game_id, player_key, line, proj_reb, proj_ast,
                       reb_sd, ast_sd, corr, sims=STANDARD_SIMS,
                       batch_size=BATCH_SIZE):
    line = float(line)
    means = np.asarray([float(proj_reb), float(proj_ast)], dtype=float)
    corr = float(np.clip(corr, -0.55, 0.55))
    cov = np.asarray([
        [float(reb_sd) ** 2, corr * float(reb_sd) * float(ast_sd)],
        [corr * float(reb_sd) * float(ast_sd), float(ast_sd) ** 2],
    ], dtype=float)
    cov = _nearest_psd(cov)

    n_sims = int(sims)
    bsize = int(max(10_000, batch_size))
    seed = _stable_seed(day_str, game_id, player_key, line, n_sims)
    rng = np.random.default_rng(seed)

    completed = over = under = push = 0
    batches = 0
    batch_ps = []
    hist = np.zeros(96, dtype=np.int64)
    total_sum = total_sq = 0.0
    started = time.perf_counter()
    integer_line = abs(line - round(line)) < 1e-9

    while completed < n_sims:
        n = min(bsize, n_sims - completed)
        draws = rng.multivariate_normal(means, cov, size=n, check_valid="ignore")
        draws = np.rint(np.clip(draws, 0.0, None)).astype(np.int16, copy=False)
        ra = draws.sum(axis=1, dtype=np.int32)

        if integer_line:
            target = int(round(line))
            o = int(np.count_nonzero(ra > target))
            u = int(np.count_nonzero(ra < target))
            p = n - o - u
        else:
            o = int(np.count_nonzero(ra > line))
            u = n - o
            p = 0

        over += o
        under += u
        push += p
        completed += n
        batches += 1
        resolved = o + u
        batch_ps.append(o / resolved if resolved else 0.5)
        total_sum += float(ra.sum(dtype=np.int64))
        total_sq += float(np.square(ra.astype(np.float64)).sum())
        bc = np.bincount(np.minimum(ra, len(hist) - 1), minlength=len(hist))
        hist += bc[:len(hist)]

    resolved = over + under
    p_over = over / resolved if resolved else 0.5
    p_under = under / resolved if resolved else 0.5
    p_push = push / completed if completed else 0.0
    mc_se = math.sqrt(max(p_over * (1.0 - p_over), 0.0) / max(resolved, 1))
    batch_spread = max(batch_ps) - min(batch_ps) if len(batch_ps) > 1 else 0.0
    mean_ra = total_sum / completed if completed else np.nan
    var_ra = max(total_sq / completed - mean_ra * mean_ra, 0.0) if completed else np.nan

    return {
        "state": "COMPLETE",
        "model_version": MODEL_VERSION,
        "sims": int(completed),
        "batches": int(batches),
        "batch_size": bsize,
        "seed": int(seed),
        "line": line,
        "p_over": float(p_over),
        "p_under": float(p_under),
        "p_push": float(p_push),
        "p_over_raw": float(over / completed) if completed else 0.0,
        "p_under_raw": float(under / completed) if completed else 0.0,
        "fair_over": _fair_american(p_over),
        "fair_under": _fair_american(p_under),
        "mc_se": float(mc_se),
        "max_batch_diff": float(batch_spread),
        "converged": bool(batch_spread <= CONVERGENCE_BATCH_SPREAD and mc_se <= CONVERGENCE_MC_SE),
        "mean_ra": float(mean_ra),
        "sd_ra": float(math.sqrt(var_ra)) if np.isfinite(var_ra) else np.nan,
        "median_ra": _hist_quantile(hist, 0.50),
        "mode_ra": float(np.argmax(hist)) if hist.sum() else np.nan,
        "p10": _hist_quantile(hist, 0.10),
        "p90": _hist_quantile(hist, 0.90),
        "elapsed_s": float(time.perf_counter() - started),
    }


def run_standard(day_str, player_row, line, projection):
    if str((projection or {}).get("state")) != "READY":
        return {"state": "PROJECTION_NOT_READY"}
    if not np.isfinite(_num(line, np.nan)):
        return {"state": "NO_VERIFIED_LINE"}
    game_id = str(player_row.get("game_id") or "")
    player_key = str(
        player_row.get("ESPN_PLAYER_ID")
        or player_row.get("PLAYER_ID")
        or player_row.get("PLAYER_NAME")
        or "player"
    )
    return simulate_ra_cached(
        str(day_str), game_id, player_key, float(line),
        float(projection["proj_reb"]), float(projection["proj_ast"]),
        float(projection["reb_sd"]), float(projection["ast_sd"]),
        float(projection["corr"]), int(STANDARD_SIMS), int(BATCH_SIZE),
    )


__all__ = [
    "MODEL_VERSION", "STANDARD_SIMS", "BATCH_SIZE",
    "project_ra", "run_standard", "simulate_ra_cached",
]
