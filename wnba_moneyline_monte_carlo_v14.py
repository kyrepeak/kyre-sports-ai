"""WNBA Moneyline V1.4 — Step 7 actual 5,000,000-draw Monte Carlo engine.

Consumes only the frozen Step-6 comparison board. Each unique game's Step-5
projected home margin and empirical sigma define the simulation distribution.
Exactly 5,000,000 continuous final-margin draws are streamed per game in
20 batches of 250,000. The same simulated game outcomes are reused across every
sportsbook row for that game.

Contracts:
- exactly 5,000,000 game draws per game;
- deterministic snapshot-derived seed;
- 20 bounded batches of 250,000 draws;
- no sportsbook line/price enters the simulation distribution;
- Monte Carlo SE, maximum batch deviation and analytic-vs-MC delta are audited;
- ±5% projected-margin sensitivity reuses the same random shocks;
- simulation results are valid only for the exact Step-6 snapshot fingerprint.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

MODEL_VERSION = "WNBA MONEYLINE MONTE CARLO V1.4"
ET = ZoneInfo("America/New_York")

N_SIMS = 5_000_000
BATCH_SIZE = 250_000
N_BATCHES = N_SIMS // BATCH_SIZE
MAX_ANALYTIC_DELTA_PP = 0.25
MAX_BATCH_DEVIATION_PP = 0.60
MAX_MC_SE_PP = 0.05


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _fair_american(probability) -> float:
    p = _num(probability, np.nan)
    if not np.isfinite(p) or p <= 0.0 or p >= 1.0:
        return np.nan
    if p >= 0.5:
        return -100.0 * p / (1.0 - p)
    return 100.0 * (1.0 - p) / p


def _american_profit(odds) -> float:
    x = _num(odds, np.nan)
    if not np.isfinite(x) or x == 0:
        return np.nan
    return x / 100.0 if x > 0 else 100.0 / abs(x)


def board_fingerprint(day_str: str, board: pd.DataFrame) -> str:
    """Fingerprint every simulation/comparison-defining Step-6 input."""
    if board is None or board.empty:
        return ""
    cols = [
        "game_id", "away_team", "home_team", "book",
        "away_price", "home_price",
        "projected_home_margin", "sigma",
        "away_model_prob", "home_model_prob",
        "away_market_novig", "home_market_novig",
        "state", "freshness", "age_seconds",
    ]
    temp = board.copy()
    sort_cols = [c for c in ("game_id", "book") if c in temp.columns]
    if sort_cols:
        temp = temp.sort_values(sort_cols, kind="stable")
    payload = []
    for _, row in temp.iterrows():
        item = {}
        for c in cols:
            v = row.get(c)
            if isinstance(v, (np.floating, float)):
                item[c] = None if not np.isfinite(float(v)) else round(float(v), 10)
            elif isinstance(v, (np.integer, int)):
                item[c] = int(v)
            else:
                item[c] = None if pd.isna(v) else str(v)
        payload.append(item)
    raw = json.dumps({"day": str(day_str), "rows": payload}, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def _seed_from_fingerprint(fingerprint: str) -> int:
    if not fingerprint:
        return 14082026
    return int(fingerprint[:16], 16) % (2**32 - 1)


def _simulate_game(
    mean_home: float,
    sigma: float,
    rng: np.random.Generator,
    progress_callback=None,
    progress_offset: int = 0,
    progress_total: int = 1,
):
    """Stream 5M normal-margin draws and count base plus ±5% mean scenarios."""
    home_wins = 0
    low_home_wins = 0
    high_home_wins = 0
    batch_home_probs = []
    total_sum = 0.0
    total_sq = 0.0
    completed = 0

    shift = 0.05 * abs(float(mean_home))
    low_mean = float(mean_home) - shift
    high_mean = float(mean_home) + shift

    for batch_idx in range(N_BATCHES):
        z = rng.standard_normal(BATCH_SIZE)
        margins = float(mean_home) + float(sigma) * z

        home_n = int(np.count_nonzero(margins > 0.0))
        low_n = int(np.count_nonzero(low_mean + float(sigma) * z > 0.0))
        high_n = int(np.count_nonzero(high_mean + float(sigma) * z > 0.0))

        home_wins += home_n
        low_home_wins += low_n
        high_home_wins += high_n
        batch_home_probs.append(home_n / BATCH_SIZE)

        total_sum += float(margins.sum(dtype=np.float64))
        total_sq += float(np.square(margins, dtype=np.float64).sum(dtype=np.float64))
        completed += int(margins.size)

        if progress_callback is not None:
            done = progress_offset + batch_idx + 1
            try:
                progress_callback(done, progress_total)
            except Exception:
                pass

    home_prob = home_wins / completed if completed else np.nan
    away_prob = 1.0 - home_prob if np.isfinite(home_prob) else np.nan
    low_home_prob = low_home_wins / completed if completed else np.nan
    high_home_prob = high_home_wins / completed if completed else np.nan

    sim_mean = total_sum / completed if completed else np.nan
    if completed > 1:
        var = (total_sq - completed * sim_mean * sim_mean) / (completed - 1)
        sim_sd = float(np.sqrt(max(0.0, var)))
    else:
        sim_sd = np.nan

    batch_probs = np.asarray(batch_home_probs, dtype=float)
    max_batch_deviation_pp = (
        100.0 * float(np.max(np.abs(batch_probs - home_prob)))
        if len(batch_probs) and np.isfinite(home_prob)
        else np.nan
    )
    mc_se_pp = (
        100.0 * float(np.sqrt(home_prob * (1.0 - home_prob) / completed))
        if completed and np.isfinite(home_prob)
        else np.nan
    )

    return {
        "home_prob": float(home_prob),
        "away_prob": float(away_prob),
        "low_home_prob": float(low_home_prob),
        "high_home_prob": float(high_home_prob),
        "low_mean": float(low_mean),
        "high_mean": float(high_mean),
        "max_batch_deviation_pp": float(max_batch_deviation_pp),
        "mc_se_pp": float(mc_se_pp),
        "simulated_mean": float(sim_mean),
        "simulated_sd": float(sim_sd),
        "draws": int(completed),
    }


def run_monte_carlo(day_str: str, board: pd.DataFrame, progress_callback=None):
    """Run exactly 5M frozen-distribution margin draws per unique game."""
    empty_meta = {
        "state": "N/A",
        "games": 0,
        "covered_games": 0,
        "rows": 0,
        "converged_rows": 0,
        "simulations_per_game": N_SIMS,
        "batches": N_BATCHES,
        "batch_size": BATCH_SIZE,
        "simulation_ready": False,
    }
    if board is None or board.empty:
        return pd.DataFrame(), empty_meta

    fingerprint = board_fingerprint(day_str, board)
    seed = _seed_from_fingerprint(fingerprint)
    rng = np.random.default_rng(seed)
    game_ids = [str(x) for x in board["game_id"].astype(str).drop_duplicates().tolist()]
    total_progress = max(1, len(game_ids) * N_BATCHES)
    rows = []
    covered_ids = set()

    for game_index, gid in enumerate(game_ids):
        part = board.loc[board["game_id"].astype(str).eq(gid)].copy()
        if part.empty:
            continue

        means = pd.to_numeric(part.get("projected_home_margin"), errors="coerce").dropna().astype(float)
        sigmas = pd.to_numeric(part.get("sigma"), errors="coerce").dropna().astype(float)
        analytic_home = pd.to_numeric(part.get("home_model_prob"), errors="coerce").dropna().astype(float)

        if means.empty or sigmas.empty or analytic_home.empty:
            continue
        if (means.max() - means.min()) > 1e-8 or (sigmas.max() - sigmas.min()) > 1e-8:
            continue
        if (analytic_home.max() - analytic_home.min()) > 1e-8:
            continue

        mean_home = float(means.iloc[0])
        sigma = float(sigmas.iloc[0])
        target_home = float(analytic_home.iloc[0])
        if not np.isfinite(mean_home) or not np.isfinite(sigma) or sigma <= 0:
            continue
        if not np.isfinite(target_home) or not (0.0 <= target_home <= 1.0):
            continue

        diag = _simulate_game(
            mean_home,
            sigma,
            rng,
            progress_callback=progress_callback,
            progress_offset=game_index * N_BATCHES,
            progress_total=total_progress,
        )

        mc_home = _num(diag.get("home_prob"), np.nan)
        mc_away = _num(diag.get("away_prob"), np.nan)
        analytic_delta_pp = 100.0 * abs(mc_home - target_home)
        converged = bool(
            int(diag.get("draws", 0)) == N_SIMS
            and np.isfinite(diag.get("mc_se_pp")) and diag["mc_se_pp"] <= MAX_MC_SE_PP
            and np.isfinite(diag.get("max_batch_deviation_pp")) and diag["max_batch_deviation_pp"] <= MAX_BATCH_DEVIATION_PP
            and np.isfinite(analytic_delta_pp) and analytic_delta_pp <= MAX_ANALYTIC_DELTA_PP
        )

        covered_ids.add(gid)

        for _, src in part.iterrows():
            upstream = str(src.get("state") or "MONITOR").upper()
            if upstream == "BLOCKED":
                mc_state = "BLOCKED"
            elif converged and upstream == "READY":
                mc_state = "READY"
            elif converged:
                mc_state = "MONITOR"
            else:
                mc_state = "CHECK"

            away_market = _num(src.get("away_market_novig"), np.nan)
            home_market = _num(src.get("home_market_novig"), np.nan)
            away_edge_pp = 100.0 * (mc_away - away_market) if np.isfinite(away_market) else np.nan
            home_edge_pp = 100.0 * (mc_home - home_market) if np.isfinite(home_market) else np.nan

            away_price = _num(src.get("away_price"), np.nan)
            home_price = _num(src.get("home_price"), np.nan)
            away_profit = _american_profit(away_price)
            home_profit = _american_profit(home_price)
            away_ev = mc_away * away_profit - mc_home if np.isfinite(away_profit) else np.nan
            home_ev = mc_home * home_profit - mc_away if np.isfinite(home_profit) else np.nan

            rows.append({
                **{k: src.get(k) for k in src.index},
                "mc_away_win_prob": float(mc_away),
                "mc_home_win_prob": float(mc_home),
                "mc_away_fair_odds": _fair_american(mc_away),
                "mc_home_fair_odds": _fair_american(mc_home),
                "mc_away_edge_pp": float(away_edge_pp) if np.isfinite(away_edge_pp) else np.nan,
                "mc_home_edge_pp": float(home_edge_pp) if np.isfinite(home_edge_pp) else np.nan,
                "mc_away_ev": float(away_ev) if np.isfinite(away_ev) else np.nan,
                "mc_home_ev": float(home_ev) if np.isfinite(home_ev) else np.nan,
                "mc_se_pp": float(diag["mc_se_pp"]),
                "max_batch_deviation_pp": float(diag["max_batch_deviation_pp"]),
                "analytic_delta_pp": float(analytic_delta_pp),
                "simulated_mean_home_margin": float(diag["simulated_mean"]),
                "simulated_margin_sd": float(diag["simulated_sd"]),
                "sensitivity_low_home_prob": float(diag["low_home_prob"]),
                "sensitivity_high_home_prob": float(diag["high_home_prob"]),
                "sensitivity_low_mean": float(diag["low_mean"]),
                "sensitivity_high_mean": float(diag["high_mean"]),
                "sensitivity_span_pp": 100.0 * abs(float(diag["high_home_prob"]) - float(diag["low_home_prob"])),
                "simulation_count": int(diag["draws"]),
                "batches": int(N_BATCHES),
                "batch_size": int(BATCH_SIZE),
                "seed": int(seed),
                "converged": bool(converged),
                "mc_state": mc_state,
                "snapshot_fingerprint": fingerprint,
                "sportsbook_simulation_inputs": 0,
            })

    detail = pd.DataFrame(rows)
    if detail.empty:
        meta = dict(empty_meta)
        meta.update({
            "state": "CHECK",
            "games": int(len(game_ids)),
            "seed": int(seed),
            "fingerprint": fingerprint,
        })
        return detail, meta

    converged_rows = int(detail["converged"].fillna(False).astype(bool).sum())
    covered_games = int(detail["game_id"].astype(str).nunique())
    ready_rows = int(detail["mc_state"].astype(str).eq("READY").sum())
    monitor_rows = int(detail["mc_state"].astype(str).eq("MONITOR").sum())
    check_rows = int(detail["mc_state"].astype(str).eq("CHECK").sum())
    simulation_ready = bool(
        set(game_ids) == covered_ids
        and covered_games == len(game_ids)
        and converged_rows == len(detail)
        and check_rows == 0
    )

    meta = {
        "state": "READY" if simulation_ready else "CHECK",
        "games": int(len(game_ids)),
        "covered_games": covered_games,
        "rows": int(len(detail)),
        "converged_rows": converged_rows,
        "ready_rows": ready_rows,
        "monitor_rows": monitor_rows,
        "check_rows": check_rows,
        "simulations_per_game": N_SIMS,
        "batches": N_BATCHES,
        "batch_size": BATCH_SIZE,
        "total_game_draws": int(covered_games * N_SIMS),
        "seed": int(seed),
        "fingerprint": fingerprint,
        "run_at_et": datetime.now(ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
        "simulation_ready": simulation_ready,
        "sportsbook_simulation_inputs": 0,
        "convergence_contract": {
            "max_mc_se_pp": MAX_MC_SE_PP,
            "max_batch_deviation_pp": MAX_BATCH_DEVIATION_PP,
            "max_analytic_delta_pp": MAX_ANALYTIC_DELTA_PP,
        },
    }
    return detail, meta


__all__ = [
    "MODEL_VERSION",
    "N_SIMS",
    "BATCH_SIZE",
    "N_BATCHES",
    "MAX_ANALYTIC_DELTA_PP",
    "MAX_BATCH_DEVIATION_PP",
    "MAX_MC_SE_PP",
    "board_fingerprint",
    "run_monte_carlo",
]
