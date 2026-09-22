"""WNBA Spread V1.6 — Step 7 actual 5,000,000-draw Monte Carlo engine.

Consumes only the frozen Step-6 probability board. Each game's independent
Step-5 mean + Step-6 empirical sigma define a discrete final-margin distribution.
The same simulated game outcomes are reused across every sportsbook row for that
game, so book comparisons are coherent and no book gets a separate random game.

Key contracts:
- exactly 5,000,000 game-margin draws per game;
- 20 streaming batches of 250,000 draws (bounded memory);
- integer final margins via np.rint so integer spread pushes are real events;
- deterministic snapshot-derived seed for reproducibility;
- explicit Monte Carlo SE, max batch deviation, analytic-vs-MC delta and convergence;
- sportsbook lines/prices never alter the Step-5 projected mean or Step-6 sigma.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import wnba_spread_probability_v15 as analytic

MODEL_VERSION = "WNBA SPREAD MONTE CARLO V1.6"
ET = ZoneInfo("America/New_York")

N_SIMS = 5_000_000
BATCH_SIZE = 250_000
N_BATCHES = N_SIMS // BATCH_SIZE
MAX_ANALYTIC_DELTA_PP = 0.25
MAX_BATCH_DEVIATION_PP = 0.60
MAX_MC_SE_PP = 0.05
MIN_QUALIFIED_COVER = 0.55
MIN_QUALIFIED_EDGE_PP = 3.0


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _american_profit(odds) -> float:
    x = _num(odds, np.nan)
    if not np.isfinite(x) or x == 0:
        return np.nan
    return x / 100.0 if x > 0 else 100.0 / abs(x)


def board_fingerprint(day_str: str, board: pd.DataFrame) -> str:
    """Fingerprint every simulation-defining and grading-defining input."""
    if board is None or board.empty:
        return ""
    cols = [
        "game_id", "away_team", "home_team", "book",
        "away_spread", "home_spread", "away_price", "home_price",
        "projected_home_margin", "sigma", "away_no_push", "home_no_push",
        "away_market_novig", "home_market_novig", "state",
    ]
    payload = []
    temp = board.copy()
    sort_cols = [c for c in ("game_id", "book", "home_spread", "away_spread") if c in temp.columns]
    if sort_cols:
        temp = temp.sort_values(sort_cols, kind="stable")
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
        return 16062026
    return int(fingerprint[:16], 16) % (2**32 - 1)


def _side_grade(state: str, cover: float, edge_pp: float, ev: float) -> str:
    if str(state).upper() == "BLOCKED":
        return "BLOCKED"
    if str(state).upper() != "READY":
        return "MONITOR"
    if not np.isfinite(cover) or not np.isfinite(edge_pp):
        return "MONITOR"
    if cover >= MIN_QUALIFIED_COVER and edge_pp >= MIN_QUALIFIED_EDGE_PP and (not np.isfinite(ev) or ev > 0):
        return "QUALIFIED"
    return "NO PLAY"


def _simulate_game(
    mean_home: float,
    sigma: float,
    lines: list[float],
    rng: np.random.Generator,
    progress_callback=None,
    progress_offset: int = 0,
    progress_total: int = 1,
):
    unique_lines = sorted(set(float(x) for x in lines if np.isfinite(_num(x, np.nan))))
    counters = {line: {"home": 0, "away": 0, "push": 0, "batch_np": []} for line in unique_lines}
    total_sum = 0.0
    total_sq = 0.0
    completed = 0

    for batch_idx in range(N_BATCHES):
        draws = np.rint(rng.normal(float(mean_home), float(sigma), size=BATCH_SIZE)).astype(np.int16, copy=False)
        total_sum += float(draws.sum(dtype=np.int64))
        total_sq += float(np.square(draws.astype(np.int32), dtype=np.int64).sum(dtype=np.int64))
        completed += int(draws.size)

        for line in unique_lines:
            settled = draws.astype(np.float32, copy=False) + np.float32(line)
            home_n = int(np.count_nonzero(settled > 0))
            away_n = int(np.count_nonzero(settled < 0))
            push_n = int(draws.size - home_n - away_n)
            c = counters[line]
            c["home"] += home_n
            c["away"] += away_n
            c["push"] += push_n
            denom = home_n + away_n
            c["batch_np"].append(home_n / denom if denom else np.nan)

        if progress_callback is not None:
            done = progress_offset + batch_idx + 1
            try:
                progress_callback(done, progress_total)
            except Exception:
                pass

    sim_mean = total_sum / completed if completed else np.nan
    if completed > 1:
        var = (total_sq - completed * sim_mean * sim_mean) / (completed - 1)
        sim_sd = float(np.sqrt(max(0.0, var)))
    else:
        sim_sd = np.nan
    return counters, {"simulated_mean": sim_mean, "simulated_sd": sim_sd, "draws": completed}


def run_monte_carlo(day_str: str, board: pd.DataFrame, progress_callback=None):
    """Run exactly 5M discrete-margin simulations per unique game."""
    empty_meta = {
        "state": "N/A", "games": 0, "rows": 0, "converged_rows": 0,
        "qualified_games": 0, "simulations_per_game": N_SIMS,
        "batches": N_BATCHES, "batch_size": BATCH_SIZE,
    }
    if board is None or board.empty:
        return pd.DataFrame(), pd.DataFrame(), empty_meta

    fingerprint = board_fingerprint(day_str, board)
    seed = _seed_from_fingerprint(fingerprint)
    rng = np.random.default_rng(seed)
    game_ids = [str(x) for x in board["game_id"].astype(str).drop_duplicates().tolist()]
    total_progress = max(1, len(game_ids) * N_BATCHES)
    rows = []

    for game_index, gid in enumerate(game_ids):
        part = board.loc[board["game_id"].astype(str).eq(gid)].copy()
        if part.empty:
            continue
        first = part.iloc[0]
        mean_home = _num(first.get("projected_home_margin"), np.nan)
        sigma = _num(first.get("sigma"), np.nan)
        if not np.isfinite(mean_home) or not np.isfinite(sigma) or sigma <= 0:
            continue
        # Step 6 should give one game-level mean/sigma across books. Refuse to mix
        # inconsistent rows rather than silently simulating different game states.
        means = pd.to_numeric(part.get("projected_home_margin"), errors="coerce").dropna().astype(float)
        sigmas = pd.to_numeric(part.get("sigma"), errors="coerce").dropna().astype(float)
        if means.empty or sigmas.empty or (means.max() - means.min()) > 1e-8 or (sigmas.max() - sigmas.min()) > 1e-8:
            continue

        line_values = pd.to_numeric(part.get("home_spread"), errors="coerce").dropna().astype(float).tolist()
        counters, game_diag = _simulate_game(
            mean_home,
            sigma,
            line_values,
            rng,
            progress_callback=progress_callback,
            progress_offset=game_index * N_BATCHES,
            progress_total=total_progress,
        )

        for _, src in part.iterrows():
            home_spread = _num(src.get("home_spread"), np.nan)
            away_spread = _num(src.get("away_spread"), np.nan)
            c = counters.get(float(home_spread))
            if c is None:
                continue
            home_n, away_n, push_n = int(c["home"]), int(c["away"]), int(c["push"])
            total = home_n + away_n + push_n
            no_push_n = home_n + away_n
            home = home_n / total if total else np.nan
            away = away_n / total if total else np.nan
            push = push_n / total if total else np.nan
            home_np = home_n / no_push_n if no_push_n else np.nan
            away_np = away_n / no_push_n if no_push_n else np.nan
            mc_se_pp = 100.0 * np.sqrt(home_np * (1.0 - home_np) / no_push_n) if no_push_n and np.isfinite(home_np) else np.nan
            batch_probs = np.asarray(c.get("batch_np") or [], dtype=float)
            batch_probs = batch_probs[np.isfinite(batch_probs)]
            max_batch_dev_pp = 100.0 * float(np.max(np.abs(batch_probs - home_np))) if len(batch_probs) and np.isfinite(home_np) else np.nan

            analytic_home_np = _num(src.get("home_no_push"), np.nan)
            analytic_away_np = _num(src.get("away_no_push"), np.nan)
            analytic_delta_pp = 100.0 * abs(home_np - analytic_home_np) if np.isfinite(home_np) and np.isfinite(analytic_home_np) else np.nan
            converged = bool(
                np.isfinite(mc_se_pp) and mc_se_pp <= MAX_MC_SE_PP
                and np.isfinite(max_batch_dev_pp) and max_batch_dev_pp <= MAX_BATCH_DEVIATION_PP
                and np.isfinite(analytic_delta_pp) and analytic_delta_pp <= MAX_ANALYTIC_DELTA_PP
                and total == N_SIMS
            )

            upstream = str(src.get("state") or "MONITOR").upper()
            state = "READY" if upstream == "READY" and converged else "MONITOR"
            if upstream == "BLOCKED":
                state = "BLOCKED"

            home_market = _num(src.get("home_market_novig"), np.nan)
            away_market = _num(src.get("away_market_novig"), np.nan)
            home_edge_pp = 100.0 * (home_np - home_market) if np.isfinite(home_np) and np.isfinite(home_market) else np.nan
            away_edge_pp = 100.0 * (away_np - away_market) if np.isfinite(away_np) and np.isfinite(away_market) else np.nan
            home_price = _num(src.get("home_price"), np.nan)
            away_price = _num(src.get("away_price"), np.nan)
            home_profit = _american_profit(home_price)
            away_profit = _american_profit(away_price)
            home_ev = home * home_profit - away if np.isfinite(home_profit) and np.isfinite(home) and np.isfinite(away) else np.nan
            away_ev = away * away_profit - home if np.isfinite(away_profit) and np.isfinite(home) and np.isfinite(away) else np.nan

            if np.isfinite(home_edge_pp) and (not np.isfinite(away_edge_pp) or home_edge_pp >= away_edge_pp):
                best_side = str(src.get("home_team") or "Home")
                best_spread = home_spread
                best_price = home_price
                best_cover = home_np
                best_edge = home_edge_pp
                best_ev = home_ev
            else:
                best_side = str(src.get("away_team") or "Away")
                best_spread = away_spread
                best_price = away_price
                best_cover = away_np
                best_edge = away_edge_pp
                best_ev = away_ev
            grade = _side_grade(state, best_cover, best_edge, best_ev)

            rows.append({
                **{k: src.get(k) for k in src.index},
                "mc_home_cover": float(home),
                "mc_away_cover": float(away),
                "mc_push": float(push),
                "mc_home_no_push": float(home_np),
                "mc_away_no_push": float(away_np),
                "mc_home_fair_odds": analytic._fair_american(home_np),
                "mc_away_fair_odds": analytic._fair_american(away_np),
                "mc_home_edge_pp": float(home_edge_pp) if np.isfinite(home_edge_pp) else np.nan,
                "mc_away_edge_pp": float(away_edge_pp) if np.isfinite(away_edge_pp) else np.nan,
                "mc_home_ev": float(home_ev) if np.isfinite(home_ev) else np.nan,
                "mc_away_ev": float(away_ev) if np.isfinite(away_ev) else np.nan,
                "mc_se_pp": float(mc_se_pp),
                "max_batch_deviation_pp": float(max_batch_dev_pp),
                "analytic_delta_pp": float(analytic_delta_pp),
                "simulated_mean_home_margin": float(game_diag.get("simulated_mean", np.nan)),
                "simulated_margin_sd": float(game_diag.get("simulated_sd", np.nan)),
                "simulation_count": int(total),
                "batches": int(N_BATCHES),
                "batch_size": int(BATCH_SIZE),
                "seed": int(seed),
                "converged": bool(converged),
                "mc_state": state,
                "best_side": best_side,
                "best_spread": float(best_spread),
                "best_price": float(best_price),
                "best_cover_no_push": float(best_cover),
                "best_edge_pp": float(best_edge) if np.isfinite(best_edge) else np.nan,
                "best_ev": float(best_ev) if np.isfinite(best_ev) else np.nan,
                "grade": grade,
                "snapshot_fingerprint": fingerprint,
            })

    detail = pd.DataFrame(rows)
    if detail.empty:
        meta = dict(empty_meta)
        meta.update({"state": "CHECK", "games": len(game_ids), "seed": seed, "fingerprint": fingerprint})
        return detail, pd.DataFrame(), meta

    # One production candidate per game: choose the strongest positive model-vs-
    # no-vig edge among exact book rows. This avoids duplicate same-game outputs.
    final_rows = []
    for gid, part in detail.groupby(detail["game_id"].astype(str), sort=False):
        ranked = part.copy()
        ranked["_edge"] = pd.to_numeric(ranked["best_edge_pp"], errors="coerce").fillna(-999.0)
        ranked["_cover"] = pd.to_numeric(ranked["best_cover_no_push"], errors="coerce").fillna(-1.0)
        ranked["_ev"] = pd.to_numeric(ranked["best_ev"], errors="coerce").fillna(-999.0)
        ranked = ranked.sort_values(["_edge", "_cover", "_ev"], ascending=False, kind="stable")
        final_rows.append(ranked.iloc[0].drop(labels=["_edge", "_cover", "_ev"]))
    final = pd.DataFrame(final_rows).reset_index(drop=True) if final_rows else pd.DataFrame()

    converged_rows = int(detail["converged"].fillna(False).astype(bool).sum())
    ready_rows = int(detail["mc_state"].astype(str).eq("READY").sum())
    monitor_rows = int(detail["mc_state"].astype(str).eq("MONITOR").sum())
    qualified_games = int(final["grade"].astype(str).eq("QUALIFIED").sum()) if not final.empty else 0
    covered_games = int(detail.loc[detail["mc_state"].astype(str).isin(["READY", "MONITOR"]), "game_id"].astype(str).nunique())
    state = "READY" if covered_games == len(game_ids) and converged_rows == len(detail) else "CHECK"
    meta = {
        "state": state,
        "games": int(len(game_ids)),
        "covered_games": covered_games,
        "rows": int(len(detail)),
        "ready_rows": ready_rows,
        "monitor_rows": monitor_rows,
        "converged_rows": converged_rows,
        "qualified_games": qualified_games,
        "simulations_per_game": int(N_SIMS),
        "total_game_draws": int(N_SIMS * len(game_ids)),
        "batches": int(N_BATCHES),
        "batch_size": int(BATCH_SIZE),
        "seed": int(seed),
        "fingerprint": fingerprint,
        "run_at_et": datetime.now(tz=ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
        "convergence_contract": {
            "max_mc_se_pp": MAX_MC_SE_PP,
            "max_batch_deviation_pp": MAX_BATCH_DEVIATION_PP,
            "max_analytic_delta_pp": MAX_ANALYTIC_DELTA_PP,
        },
        "qualification_contract": {
            "min_cover_no_push": MIN_QUALIFIED_COVER,
            "min_edge_pp": MIN_QUALIFIED_EDGE_PP,
            "positive_ev_required_when_price_known": True,
        },
        "model_ready": bool(state == "READY"),
    }
    return detail, final, meta


__all__ = [
    "MODEL_VERSION", "N_SIMS", "BATCH_SIZE", "N_BATCHES",
    "board_fingerprint", "run_monte_carlo",
]
