"""WNBA Game Total V1.4 — actual 5M Monte Carlo engine.

Runs exactly 5,000,000 market-independent full-game total draws per unique game in
20 x 250,000 streaming batches. One game draw stream is reused across every exact
sportsbook total row for that game. The frozen Step-5 projected total and Step-6
empirical sigma are the only simulation parameters; sportsbook lines/prices are
settlement/comparison thresholds only.

Basketball totals are integer-valued. Continuous normal shocks are rounded to the
nearest integer score total before Over/Under/push settlement, matching Step 6's
continuity-corrected analytical probabilities. Integer lines can push; half-lines
cannot. No grading/ranking or Daily Picks output is performed here.
"""
from __future__ import annotations

import hashlib
import json
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import wnba_game_total_probability_v13 as analytic

MODEL_VERSION = "WNBA GAME TOTAL MONTE CARLO V1.4"
SIMULATIONS_PER_GAME = 5_000_000
BATCHES = 20
BATCH_SIZE = 250_000
MAX_MC_SE_PP = 0.05
MAX_BATCH_DEVIATION_PP = 0.60
MAX_ANALYTIC_DELTA_PP = 0.25
SENSITIVITY_FRACTION = 0.05
ET = ZoneInfo("America/New_York")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _is_integer_line(value) -> bool:
    x = _num(value, np.nan)
    return bool(np.isfinite(x) and abs(x - round(x)) <= 1e-8)


def _fair_american(probability):
    return analytic._fair_american(probability)


def board_fingerprint(day_str: str, board: pd.DataFrame) -> str:
    """Stable simulation fingerprint; volatile quote-age fields are excluded."""
    if board is None or board.empty:
        return ""
    cols = [
        "game_id", "away_team", "home_team", "book", "market_total",
        "over_price", "under_price", "projected_total", "sigma",
        "over", "under", "push", "over_no_push", "under_no_push",
        "over_market_novig", "under_market_novig", "projection_state", "state",
    ]
    rows = []
    for _, r in board.iterrows():
        item = {}
        for c in cols:
            v = r.get(c)
            if isinstance(v, (np.integer, np.floating)):
                v = float(v)
            if pd.isna(v) if not isinstance(v, (list, dict)) else False:
                v = None
            item[c] = v
        rows.append(item)
    rows.sort(key=lambda x: (str(x.get("game_id")), str(x.get("book")), str(x.get("market_total"))))
    payload = json.dumps({"day": str(day_str), "rows": rows}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _seed_from_fingerprint(fingerprint: str) -> int:
    if not fingerprint:
        return 14082026
    return int(fingerprint[:8], 16) % (2**32 - 1)


def _settle(discrete_totals: np.ndarray, line: float):
    line = float(line)
    over = int(np.count_nonzero(discrete_totals > line))
    under = int(np.count_nonzero(discrete_totals < line))
    push = int(len(discrete_totals) - over - under)
    return over, under, push


def _safe_no_push(over_count: int, under_count: int) -> tuple[float, float]:
    denom = int(over_count) + int(under_count)
    if denom <= 0:
        return np.nan, np.nan
    return float(over_count / denom), float(under_count / denom)


def run_monte_carlo(day_str: str, board: pd.DataFrame, progress_callback=None):
    empty_meta = {
        "state": "N/A", "simulation_ready": False, "games": 0,
        "covered_games": 0, "rows": 0, "converged_rows": 0,
        "simulations_per_game": SIMULATIONS_PER_GAME, "batches": BATCHES,
        "batch_size": BATCH_SIZE, "sportsbook_simulation_inputs": 0,
    }
    if board is None or board.empty:
        return pd.DataFrame(), empty_meta

    fingerprint = board_fingerprint(day_str, board)
    seed = _seed_from_fingerprint(fingerprint)
    game_ids = [str(x) for x in board["game_id"].astype(str).drop_duplicates().tolist()]
    total_batch_slots = max(1, len(game_ids) * BATCHES)
    done = 0
    out_rows = []

    for game_index, gid in enumerate(game_ids):
        part = board.loc[board["game_id"].astype(str).eq(gid)].copy().reset_index(drop=True)
        if part.empty:
            continue

        ref = part.iloc[0]
        mean_total = _num(ref.get("projected_total"), np.nan)
        sigma = _num(ref.get("sigma"), np.nan)
        if not np.isfinite(mean_total) or not np.isfinite(sigma) or sigma <= 0:
            continue

        # Independent deterministic stream per game while keeping one snapshot seed.
        game_seed = (seed + 1_000_003 * (game_index + 1)) % (2**32 - 1)
        rng = np.random.default_rng(game_seed)
        low_mean = float(mean_total * (1.0 - SENSITIVITY_FRACTION))
        high_mean = float(mean_total * (1.0 + SENSITIVITY_FRACTION))

        trackers = []
        for _, row in part.iterrows():
            trackers.append({
                "row": row.to_dict(),
                "over": 0, "under": 0, "push": 0,
                "low_over": 0, "low_under": 0, "low_push": 0,
                "high_over": 0, "high_under": 0, "high_push": 0,
                "batch_probs": [],
            })

        sum_total = 0.0
        sumsq_total = 0.0
        n_total = 0

        for _batch in range(BATCHES):
            shocks = rng.standard_normal(BATCH_SIZE)
            base_discrete = np.floor(mean_total + sigma * shocks + 0.5).astype(np.int16)
            low_discrete = np.floor(low_mean + sigma * shocks + 0.5).astype(np.int16)
            high_discrete = np.floor(high_mean + sigma * shocks + 0.5).astype(np.int16)

            sum_total += float(base_discrete.astype(np.float64).sum())
            sumsq_total += float(np.square(base_discrete.astype(np.float64)).sum())
            n_total += int(BATCH_SIZE)

            for tracker in trackers:
                line = _num(tracker["row"].get("market_total"), np.nan)
                if not np.isfinite(line):
                    continue
                o, u, p = _settle(base_discrete, line)
                lo, lu, lp = _settle(low_discrete, line)
                ho, hu, hp = _settle(high_discrete, line)
                tracker["over"] += o
                tracker["under"] += u
                tracker["push"] += p
                tracker["low_over"] += lo
                tracker["low_under"] += lu
                tracker["low_push"] += lp
                tracker["high_over"] += ho
                tracker["high_under"] += hu
                tracker["high_push"] += hp
                tracker["batch_probs"].append((o / BATCH_SIZE, u / BATCH_SIZE, p / BATCH_SIZE))

            done += 1
            if callable(progress_callback):
                progress_callback(done, total_batch_slots)

        sim_mean = sum_total / max(1, n_total)
        if n_total > 1:
            sim_var = max(0.0, (sumsq_total - n_total * sim_mean * sim_mean) / (n_total - 1))
            sim_sd = float(np.sqrt(sim_var))
        else:
            sim_sd = np.nan

        for tracker in trackers:
            row = dict(tracker["row"])
            n = int(n_total)
            over = tracker["over"] / n
            under = tracker["under"] / n
            push = tracker["push"] / n
            over_np, under_np = _safe_no_push(tracker["over"], tracker["under"])
            low_over_np, low_under_np = _safe_no_push(tracker["low_over"], tracker["low_under"])
            high_over_np, high_under_np = _safe_no_push(tracker["high_over"], tracker["high_under"])

            analytic_over = _num(row.get("over"), np.nan)
            analytic_under = _num(row.get("under"), np.nan)
            analytic_push = _num(row.get("push"), np.nan)
            analytic_deltas = [
                abs(over - analytic_over) if np.isfinite(analytic_over) else np.nan,
                abs(under - analytic_under) if np.isfinite(analytic_under) else np.nan,
                abs(push - analytic_push) if np.isfinite(analytic_push) else np.nan,
            ]
            analytic_delta_pp = 100.0 * max([x for x in analytic_deltas if np.isfinite(x)] or [np.inf])

            se_over = np.sqrt(max(0.0, over * (1.0 - over)) / n)
            se_under = np.sqrt(max(0.0, under * (1.0 - under)) / n)
            mc_se_pp = 100.0 * max(se_over, se_under)

            batch_probs = tracker["batch_probs"]
            max_batch_dev = 0.0
            for bo, bu, bp in batch_probs:
                max_batch_dev = max(
                    max_batch_dev,
                    abs(bo - over), abs(bu - under), abs(bp - push),
                )
            max_batch_deviation_pp = 100.0 * max_batch_dev

            converged = bool(
                n == SIMULATIONS_PER_GAME
                and mc_se_pp <= MAX_MC_SE_PP
                and max_batch_deviation_pp <= MAX_BATCH_DEVIATION_PP
                and analytic_delta_pp <= MAX_ANALYTIC_DELTA_PP
            )

            over_market = _num(row.get("over_market_novig"), np.nan)
            under_market = _num(row.get("under_market_novig"), np.nan)
            upstream_state = str(row.get("state") or "READY").upper()
            mc_state = "CHECK" if not converged else ("MONITOR" if upstream_state == "MONITOR" else "READY")

            row.update({
                "simulation_count": n,
                "seed": int(game_seed),
                "mc_over_prob": float(over),
                "mc_under_prob": float(under),
                "mc_push_prob": float(push),
                "mc_over_no_push": float(over_np),
                "mc_under_no_push": float(under_np),
                "mc_over_fair_odds": _fair_american(over_np),
                "mc_under_fair_odds": _fair_american(under_np),
                "mc_over_edge_pp": 100.0 * (over_np - over_market) if np.isfinite(over_market) and np.isfinite(over_np) else np.nan,
                "mc_under_edge_pp": 100.0 * (under_np - under_market) if np.isfinite(under_market) and np.isfinite(under_np) else np.nan,
                "simulated_mean_total": float(sim_mean),
                "simulated_total_sd": float(sim_sd),
                "mc_se_pp": float(mc_se_pp),
                "max_batch_deviation_pp": float(max_batch_deviation_pp),
                "analytic_delta_pp": float(analytic_delta_pp),
                "sensitivity_low_mean": low_mean,
                "sensitivity_high_mean": high_mean,
                "sensitivity_low_over_prob": float(low_over_np),
                "sensitivity_high_over_prob": float(high_over_np),
                "sensitivity_low_under_prob": float(low_under_np),
                "sensitivity_high_under_prob": float(high_under_np),
                "sensitivity_span_pp": 100.0 * max(
                    abs(high_over_np - low_over_np) if np.isfinite(high_over_np) and np.isfinite(low_over_np) else 0.0,
                    abs(high_under_np - low_under_np) if np.isfinite(high_under_np) and np.isfinite(low_under_np) else 0.0,
                ),
                "converged": converged,
                "mc_state": mc_state,
                "sportsbook_simulation_inputs": 0,
                "simulation_method": "5M integer-total normal-shock Monte Carlo; market threshold only",
            })
            out_rows.append(row)

    detail = pd.DataFrame(out_rows)
    covered_ids = set(detail.get("game_id", pd.Series(dtype=object)).astype(str).tolist()) if not detail.empty else set()
    converged_rows = int(detail.get("converged", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()) if not detail.empty else 0
    all_rows_converged = bool(len(detail) and converged_rows == len(detail))
    simulation_ready = bool(set(game_ids).issubset(covered_ids) and all_rows_converged)
    run_at_et = pd.Timestamp.now(tz=ET).strftime("%Y-%m-%d %I:%M:%S %p ET")

    meta = {
        "state": "READY" if simulation_ready else "CHECK",
        "simulation_ready": simulation_ready,
        "games": int(len(game_ids)),
        "covered_games": int(len(set(game_ids) & covered_ids)),
        "rows": int(len(detail)),
        "converged_rows": converged_rows,
        "simulations_per_game": SIMULATIONS_PER_GAME,
        "batches": BATCHES,
        "batch_size": BATCH_SIZE,
        "total_game_draws": int(len(game_ids) * SIMULATIONS_PER_GAME),
        "sportsbook_simulation_inputs": 0,
        "seed": int(seed),
        "fingerprint": fingerprint,
        "run_at_et": run_at_et,
        "convergence_contract": {
            "max_mc_se_pp": MAX_MC_SE_PP,
            "max_batch_deviation_pp": MAX_BATCH_DEVIATION_PP,
            "max_analytic_delta_pp": MAX_ANALYTIC_DELTA_PP,
        },
    }
    return detail, meta


__all__ = [
    "MODEL_VERSION", "SIMULATIONS_PER_GAME", "BATCHES", "BATCH_SIZE",
    "MAX_MC_SE_PP", "MAX_BATCH_DEVIATION_PP", "MAX_ANALYTIC_DELTA_PP",
    "SENSITIVITY_FRACTION", "board_fingerprint", "run_monte_carlo",
]
