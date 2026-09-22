"""NFL Moneyline Step 6 Monte Carlo engine.

Model-only uncertainty propagation for the Step-4C calibrated logistic model.
Sportsbook prices never enter this engine.

V1 scope:
- draw calibration coefficients from the Step-4C covariance approximation;
- transform the fixed, verified Step-4B feature vector into per-draw P(win);
- simulate binary game outcomes conditional on each draw;
- 5,000,000 standard draws in deterministic batches;
- report MC standard error, batch stability and convergence.

Preseason game-plan uncertainty is NOT numerically fabricated when Step 3 is
unresolved. The resulting distribution remains a BASE model Monte Carlo output
and is final-output gated during preseason.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
import streamlit as st

MODEL_VERSION = "NFL MONEYLINE MC V1 • 5M PARAMETER-UNCERTAINTY SIMULATION"
SIMULATIONS = 5_000_000
BATCHES = 20
BATCH_SIZE = SIMULATIONS // BATCHES
HIST_BINS = 1800
MAX_BATCH_SPREAD = 0.0050
MAX_MC_SE = 0.00030


def deterministic_seed(game_id: str, day_str: str) -> int:
    raw = f"{MODEL_VERSION}|{day_str}|{game_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % (2**32 - 1)


def _psd_sqrt(covariance: np.ndarray) -> np.ndarray:
    cov = np.asarray(covariance, dtype=float)
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        raise ValueError("Monte Carlo covariance is not square")
    cov = 0.5 * (cov + cov.T)
    if not np.all(np.isfinite(cov)):
        raise ValueError("Monte Carlo covariance contains non-finite values")
    values, vectors = np.linalg.eigh(cov)
    values = np.clip(values, 0.0, None)
    return vectors @ np.diag(np.sqrt(values))


def _hist_quantile(counts: np.ndarray, edges: np.ndarray, q: float) -> float:
    total = int(np.sum(counts))
    if total <= 0:
        return np.nan
    target = float(np.clip(q, 0.0, 1.0)) * total
    cumulative = np.cumsum(counts)
    idx = int(np.searchsorted(cumulative, target, side="left"))
    idx = min(max(idx, 0), len(counts) - 1)
    before = int(cumulative[idx - 1]) if idx > 0 else 0
    inside = int(counts[idx])
    if inside <= 0:
        return float(0.5 * (edges[idx] + edges[idx + 1]))
    frac = float(np.clip((target - before) / inside, 0.0, 1.0))
    return float(edges[idx] + frac * (edges[idx + 1] - edges[idx]))


@st.cache_data(ttl=1800, show_spinner=False)
def run_parameter_monte_carlo(
    x_values: tuple,
    beta_values: tuple,
    scale_values: tuple,
    covariance_values: tuple,
    probability_floor: float,
    probability_ceiling: float,
    seed: int,
    simulations: int = SIMULATIONS,
    batches: int = BATCHES,
):
    x = np.asarray(x_values, dtype=float).reshape(-1)
    beta = np.asarray(beta_values, dtype=float).reshape(-1)
    scales = np.asarray(scale_values, dtype=float).reshape(-1)
    covariance = np.asarray(covariance_values, dtype=float).reshape(beta.size, beta.size)

    if x.size != beta.size or scales.size != beta.size:
        raise ValueError("Monte Carlo feature/coefficient shape mismatch")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(beta)):
        raise ValueError("Monte Carlo received non-finite feature/coefficient values")

    scales = np.where(np.isfinite(scales) & (np.abs(scales) > 1e-12), scales, 1.0)
    xs = x / scales
    root = _psd_sqrt(covariance)

    simulations = int(simulations)
    batches = int(batches)
    if simulations < 100_000 or batches < 2 or simulations % batches != 0:
        raise ValueError("Monte Carlo simulation/batch configuration is invalid")
    batch_size = simulations // batches

    rng = np.random.default_rng(int(seed))
    hist_edges = np.linspace(float(probability_floor), float(probability_ceiling), HIST_BINS + 1)
    hist_counts = np.zeros(HIST_BINS, dtype=np.int64)

    total_wins = 0
    total_prob = 0.0
    total_prob_sq = 0.0
    batch_win_rates = []
    batch_prob_means = []

    for _ in range(batches):
        z = rng.standard_normal((batch_size, beta.size))
        beta_draws = beta + z @ root.T
        logits = beta_draws @ xs
        logits = np.clip(logits, -30.0, 30.0)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        probabilities = np.clip(probabilities, float(probability_floor), float(probability_ceiling))

        outcomes = rng.random(batch_size) < probabilities
        wins = int(np.sum(outcomes))
        p_sum = float(np.sum(probabilities, dtype=np.float64))

        total_wins += wins
        total_prob += p_sum
        total_prob_sq += float(np.sum(probabilities * probabilities, dtype=np.float64))
        batch_win_rates.append(wins / batch_size)
        batch_prob_means.append(p_sum / batch_size)
        hist_counts += np.histogram(probabilities, bins=hist_edges)[0].astype(np.int64)

    win_rate = total_wins / simulations
    mean_probability = total_prob / simulations
    probability_variance = max(total_prob_sq / simulations - mean_probability**2, 0.0)
    probability_sd = math.sqrt(probability_variance)
    mc_se = math.sqrt(max(win_rate * (1.0 - win_rate), 0.0) / simulations)

    batch_rates = np.asarray(batch_win_rates, dtype=float)
    batch_means = np.asarray(batch_prob_means, dtype=float)
    batch_spread = float(np.max(batch_rates) - np.min(batch_rates))
    max_batch_deviation = float(np.max(np.abs(batch_rates - win_rate)))

    q05 = _hist_quantile(hist_counts, hist_edges, 0.05)
    q50 = _hist_quantile(hist_counts, hist_edges, 0.50)
    q95 = _hist_quantile(hist_counts, hist_edges, 0.95)

    converged = bool(
        np.isfinite(win_rate)
        and np.isfinite(mc_se)
        and batch_spread <= MAX_BATCH_SPREAD
        and mc_se <= MAX_MC_SE
    )

    return {
        "ready": True,
        "model_version": MODEL_VERSION,
        "simulations": simulations,
        "batches": batches,
        "batch_size": batch_size,
        "seed": int(seed),
        "away_win_rate": float(win_rate),
        "home_win_rate": float(1.0 - win_rate),
        "mean_probability": float(mean_probability),
        "median_probability": float(q50),
        "p05_probability": float(q05),
        "p95_probability": float(q95),
        "probability_sd": float(probability_sd),
        "mc_se": float(mc_se),
        "batch_spread": float(batch_spread),
        "max_batch_deviation": float(max_batch_deviation),
        "batch_win_min": float(np.min(batch_rates)),
        "batch_win_max": float(np.max(batch_rates)),
        "batch_probability_spread": float(np.max(batch_means) - np.min(batch_means)),
        "converged": converged,
        "uncertainty_scope": "Step-4C coefficient covariance only",
    }


__all__ = [
    "MODEL_VERSION", "SIMULATIONS", "BATCHES", "BATCH_SIZE",
    "MAX_BATCH_SPREAD", "MAX_MC_SE", "deterministic_seed",
    "run_parameter_monte_carlo",
]
