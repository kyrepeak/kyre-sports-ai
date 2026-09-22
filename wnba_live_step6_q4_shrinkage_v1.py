"""WNBA Live Games Step 6.6 — structurally simplified Q4 residual-shrink audit.

Why this exists
---------------
Step 6.5.1 diagnosed a structural failure rather than a transport/runtime bug:
the fitted Q4 remaining-differential coefficient wanted values near zero or
negative, but the Step-6.4 family forced it to stay at or above 0.800. At the
same time, fitting total scale, home bias and SD together added variance without
stable out-of-sample benefit.

This module therefore makes one principled repair instead of widening the old
search space:
- Q4 only; halftime remains production V1.
- Keep the production V1 remaining TOTAL unchanged exactly.
- Keep the production V1 uncertainty/SD unchanged exactly.
- Remove the free home-bias term.
- Fit only two interpretable Q4 mean terms on training data:
    1) how much of the production remaining-differential signal survives (alpha)
    2) modest regression/persistence of the current score margin (beta)
- alpha is allowed to shrink all the way to zero because Step 6.5 showed the
  0.800 floor was the wrong structural assumption. It is never allowed negative.
- chronological rolling validation is required; newest games are a retrospective
  consistency check only and are not promotion evidence.
- no sportsbook, no final-box leakage, no future plays, no historical injury
  backfill, and no production auto-promotion.

Memory contract
---------------
The Step-6.4 feature builder returns nested replay/projection/history objects that
are useful for paired 5M replay confirmation, but Step 6.6 never uses them. This
module now strips those unused nested objects immediately and retains only the
scalar fields required by the two-parameter audit. Calibration math is unchanged;
only the in-memory representation is smaller.
"""
from __future__ import annotations

from datetime import datetime
import math
from statistics import NormalDist
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_live_step5_preview_v1 as preview
import wnba_live_step6_calibration_v2 as cal
import wnba_live_step6_q4_promotion_v1 as q4

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE STEP-6.6 Q4 SHRINKAGE V1 • TWO-PARAMETER STRUCTURAL REPAIR"

DISCOVERY_GAMES = 64
LOOKBACK_DAYS = 180
TRAIN_WINDOW = 24
VALIDATION_BLOCK = 6
ROBUST_FOLDS = 4
TAIL_RECHECK_GAMES = 8
REQUIRED_CLEAN_GAMES = TRAIN_WINDOW + VALIDATION_BLOCK * ROBUST_FOLDS + TAIL_RECHECK_GAMES
RIDGE = 18.0

ALPHA_BOUNDS = (0.0, 1.0)
BETA_BOUNDS = (-0.20, 0.10)

# Step 6.6 only needs these scalar fields. Keeping nested state/projection/truth/
# reconstruction objects here would duplicate large replay payloads in both
# Streamlit caches and session state without changing a single fitted value.
ROW_FIELDS = (
    "event_id",
    "game_date",
    "away_team",
    "home_team",
    "current_away",
    "current_home",
    "current_home_margin",
    "base_remaining_total",
    "base_remaining_diff_home",
    "actual_remaining_diff_home",
    "actual_final_away",
    "actual_final_home",
    "actual_home_win",
    "base_margin_variance",
)


def _num(value: Any, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _clip(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


def _date_key(value: Any) -> str:
    try:
        return pd.to_datetime(value, utc=True).isoformat()
    except Exception:
        return str(value or "")


def _compact_row(row: dict) -> dict:
    return {key: row.get(key) for key in ROW_FIELDS}


@st.cache_data(ttl=1800, show_spinner=False, max_entries=1)
def q4_dataset(day_str: str) -> dict:
    games, discovery = preview.recent_completed_previews(
        day_str,
        limit=DISCOVERY_GAMES,
        lookback_days=LOOKBACK_DAYS,
    )
    games = sorted(games, key=lambda g: _date_key(g.get("captured_at")))
    rows = []
    errors = []
    for game in games:
        row, error = q4._single_q4_row(game)
        if row is not None:
            rows.append(_compact_row(row))
        elif error:
            errors.append(error)
    rows = sorted(rows, key=lambda r: str(r.get("game_date") or ""))
    return {
        "model_version": MODEL_VERSION,
        "day": day_str,
        "games_discovered": len(games),
        "clean_q4_games": len(rows),
        "rows": rows,
        "errors": errors[:120],
        "discovery": discovery,
        "required_clean_games": REQUIRED_CLEAN_GAMES,
        "ready": len(rows) >= REQUIRED_CLEAN_GAMES,
        "sportsbook_used": False,
        "future_data_used": False,
        "final_boxscore_used_in_projection": False,
    }


def fit_params(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 8:
        return {
            "alpha": 1.0,
            "beta": 0.0,
            "raw_alpha": 1.0,
            "raw_beta": 0.0,
            "sample": n,
            "fit_status": "IDENTITY • THIN SAMPLE",
            "bound_hits": [],
        }

    X = np.array([
        [float(r["base_remaining_diff_home"]), float(r["current_home_margin"])]
        for r in rows
    ], dtype=float)
    y = np.array([float(r["actual_remaining_diff_home"]) for r in rows], dtype=float)

    scales = np.sqrt(np.mean(X * X, axis=0))
    scales = np.where(scales < 1e-6, 1.0, scales)
    Z = X / scales

    # Strongly regularize toward production identity [alpha=1, beta=0].
    prior = np.array([1.0, 0.0], dtype=float)
    prior_z = prior * scales
    reg = RIDGE * np.eye(2)
    try:
        beta_z = np.linalg.solve(Z.T @ Z + reg, Z.T @ y + reg @ prior_z)
        raw = beta_z / scales
    except Exception:
        raw = prior

    raw_alpha = float(raw[0])
    raw_beta = float(raw[1])
    alpha = _clip(raw_alpha, *ALPHA_BOUNDS)
    beta = _clip(raw_beta, *BETA_BOUNDS)
    hits = []
    if abs(alpha - ALPHA_BOUNDS[0]) < 1e-9 or abs(alpha - ALPHA_BOUNDS[1]) < 1e-9:
        hits.append("alpha")
    if abs(beta - BETA_BOUNDS[0]) < 1e-9 or abs(beta - BETA_BOUNDS[1]) < 1e-9:
        hits.append("beta")

    return {
        "alpha": alpha,
        "beta": beta,
        "raw_alpha": raw_alpha,
        "raw_beta": raw_beta,
        "sample": n,
        "fit_status": "CALIBRATED • TWO-PARAMETER SHRINKAGE",
        "bound_hits": hits,
        "remaining_total_scale": 1.0,
        "sd_scale": 1.0,
        "home_bias_per10": 0.0,
    }


def predict_row(row: dict, params: dict | None) -> dict:
    p = params or {"alpha": 1.0, "beta": 0.0}
    alpha = float(p.get("alpha", 1.0))
    beta = float(p.get("beta", 0.0))

    # The total is intentionally identical to production V1.
    rem_total = max(0.0, float(row["base_remaining_total"]))
    rem_diff = (
        alpha * float(row["base_remaining_diff_home"])
        + beta * float(row["current_home_margin"])
    )
    rem_diff = _clip(rem_diff, -rem_total, rem_total)
    rem_h = max(0.0, (rem_total + rem_diff) / 2.0)
    rem_a = max(0.0, rem_total - rem_h)

    expected_a = float(row["current_away"]) + rem_a
    expected_h = float(row["current_home"]) + rem_h
    expected_total = expected_a + expected_h
    expected_margin = expected_h - expected_a

    # Distribution width is intentionally unchanged from production V1.
    sd_margin = math.sqrt(max(1e-9, float(row["base_margin_variance"])))
    home_p = _clip(NormalDist().cdf(expected_margin / max(1e-9, sd_margin)), 0.001, 0.999)
    return {
        "expected_away": expected_a,
        "expected_home": expected_h,
        "expected_total": expected_total,
        "expected_home_margin": expected_margin,
        "home_win_probability": home_p,
        "away_win_probability": 1.0 - home_p,
        "remaining_away": rem_a,
        "remaining_home": rem_h,
        "sd_margin": sd_margin,
    }


def _aggregate_pairs(pairs: list[tuple[dict, dict | None]]) -> dict:
    if not pairs:
        return {k: None for k in (
            "winner_accuracy", "avg_actual_winner_probability", "brier", "team_mae",
            "total_mae", "margin_mae", "total_bias", "margin_bias", "composite"
        )} | {"states": 0}

    winner = []
    winner_p = []
    brier = []
    team_ae = []
    total_abs = []
    margin_abs = []
    total_err = []
    margin_err = []
    for row, params in pairs:
        pred = predict_row(row, params)
        aa = float(row["actual_final_away"])
        ah = float(row["actual_final_home"])
        at = aa + ah
        am = ah - aa
        home_won = bool(row["actual_home_win"])
        ph = float(pred["home_win_probability"])
        winner.append((ph >= 0.5) == home_won)
        winner_p.append(ph if home_won else 1.0 - ph)
        brier.append((ph - (1.0 if home_won else 0.0)) ** 2)
        team_ae.append((abs(pred["expected_away"] - aa) + abs(pred["expected_home"] - ah)) / 2.0)
        te = pred["expected_total"] - at
        me = pred["expected_home_margin"] - am
        total_abs.append(abs(te))
        margin_abs.append(abs(me))
        total_err.append(te)
        margin_err.append(me)

    out = {
        "states": len(pairs),
        "winner_accuracy": float(np.mean(winner)),
        "avg_actual_winner_probability": float(np.mean(winner_p)),
        "brier": float(np.mean(brier)),
        "team_mae": float(np.mean(team_ae)),
        "total_mae": float(np.mean(total_abs)),
        "margin_mae": float(np.mean(margin_abs)),
        "total_bias": float(np.mean(total_err)),
        "margin_bias": float(np.mean(margin_err)),
    }
    out["composite"] = (
        0.30 * out["brier"] / 0.25
        + 0.25 * out["team_mae"] / 8.0
        + 0.225 * out["total_mae"] / 12.0
        + 0.225 * out["margin_mae"] / 10.0
    )
    return out


def _aggregate(rows: list[dict], params: dict | None) -> dict:
    return _aggregate_pairs([(r, params) for r in rows])


def _pct_improvement(base: Any, cand: Any) -> float | None:
    try:
        b = float(base)
        c = float(cand)
        if abs(b) < 1e-12:
            return None
        return (b - c) / abs(b)
    except Exception:
        return None


def _fold_contract(base: dict, cand: dict) -> dict:
    reasons = []
    if base.get("composite") is None or cand.get("composite") is None:
        reasons.append("missing fold metrics")
    else:
        if float(cand["composite"]) > float(base["composite"]) * 1.03:
            reasons.append("fold composite degraded > 3%")
        if float(cand["brier"]) > float(base["brier"]) + 0.010:
            reasons.append("fold Brier degraded > 0.010")
        if float(cand["margin_mae"]) > float(base["margin_mae"]) + 0.75:
            reasons.append("fold margin MAE degraded > 0.75 pts")
    return {"pass": not reasons, "reasons": reasons}


def _robust_contract(base: dict, cand: dict, folds: list[dict]) -> dict:
    reasons = []
    warnings = []
    n = int(base.get("states") or 0)
    if n < VALIDATION_BLOCK * ROBUST_FOLDS:
        reasons.append(f"rolling validation states {n} < {VALIDATION_BLOCK * ROBUST_FOLDS}")

    comp_imp = _pct_improvement(base.get("composite"), cand.get("composite"))
    if comp_imp is None or comp_imp < 0.010:
        reasons.append("aggregate rolling composite improvement < 1.0%")
    if float(cand.get("brier") or 999) > float(base.get("brier") or 999) + 0.002:
        reasons.append("aggregate rolling Brier worsened > 0.002")
    if float(cand.get("margin_mae") or 999) > float(base.get("margin_mae") or 999) - 0.10:
        reasons.append("aggregate rolling margin MAE improvement < 0.10 pts")
    if float(cand.get("team_mae") or 999) > float(base.get("team_mae") or 999) + 0.10:
        reasons.append("aggregate rolling team MAE worsened > 0.10 pts")
    if float(cand.get("winner_accuracy") or 0) + (1.0 / max(1, n)) < float(base.get("winner_accuracy") or 0):
        reasons.append("aggregate rolling winner accuracy worse by more than one state")

    fold_passes = sum(1 for f in folds if (f.get("contract") or {}).get("pass"))
    nonworse = sum(
        1 for f in folds
        if float((f.get("candidate") or {}).get("composite") or 999)
        <= float((f.get("baseline") or {}).get("composite") or 999) * 1.01
    )
    if fold_passes < 3:
        reasons.append(f"only {fold_passes}/{len(folds)} folds cleared stability guard")
    if nonworse < 3:
        reasons.append(f"candidate composite was within 1% of baseline in only {nonworse}/{len(folds)} folds")

    alphas = [float((f.get("params") or {}).get("alpha") or 0.0) for f in folds]
    raw_alphas = [float((f.get("params") or {}).get("raw_alpha") or 0.0) for f in folds]
    if alphas:
        warnings.append(f"fold alpha range {min(alphas):.3f} to {max(alphas):.3f}; raw {min(raw_alphas):.3f} to {max(raw_alphas):.3f}")

    return {
        "pass": not reasons,
        "status": "STABLE FOR SHADOW FREEZE" if not reasons else "HOLD",
        "reasons": reasons,
        "warnings": warnings,
        "composite_improvement": comp_imp,
        "folds_passed": fold_passes,
        "folds_nonworse": nonworse,
    }


def _tail_diagnostic(base: dict, cand: dict) -> dict:
    warnings = ["retrospective only; this tail was already visible during earlier model development"]
    checks = []
    if base.get("composite") is not None and cand.get("composite") is not None:
        checks.append(float(cand["composite"]) <= float(base["composite"]) * 1.03)
        checks.append(float(cand["brier"]) <= float(base["brier"]) + 0.010)
        checks.append(float(cand["margin_mae"]) <= float(base["margin_mae"]) + 0.75)
    return {
        "pass": bool(checks) and all(checks),
        "status": "CONSISTENT" if bool(checks) and all(checks) else "CAUTION",
        "reasons": [] if bool(checks) and all(checks) else ["retrospective tail shows material degradation guard failure"],
        "warnings": warnings,
    }


def robustness_audit(day_str: str) -> dict:
    dataset = q4_dataset(day_str)
    rows = list(dataset.get("rows") or [])
    if not dataset.get("ready"):
        return {
            "model_version": MODEL_VERSION,
            "ready": False,
            "dataset": dataset,
            "error": "insufficient clean Q4 PBP-rich games for the 56-game structural audit",
        }

    rows = rows[-REQUIRED_CLEAN_GAMES:]
    tail_rows = rows[-TAIL_RECHECK_GAMES:]
    dev_rows = rows[:-TAIL_RECHECK_GAMES]

    folds = []
    base_pairs = []
    cand_pairs = []
    for i in range(ROBUST_FOLDS):
        start = i * VALIDATION_BLOCK
        train = dev_rows[start:start + TRAIN_WINDOW]
        val_start = start + TRAIN_WINDOW
        val = dev_rows[val_start:val_start + VALIDATION_BLOCK]
        if len(train) < TRAIN_WINDOW or len(val) < VALIDATION_BLOCK:
            continue
        params = fit_params(train)
        base = _aggregate(val, {"alpha": 1.0, "beta": 0.0})
        cand = _aggregate(val, params)
        folds.append({
            "fold": i + 1,
            "train_states": len(train),
            "validation_states": len(val),
            "train_start": train[0].get("game_date"),
            "train_end": train[-1].get("game_date"),
            "validation_start": val[0].get("game_date"),
            "validation_end": val[-1].get("game_date"),
            "baseline": base,
            "candidate": cand,
            "params": params,
            "contract": _fold_contract(base, cand),
        })
        base_pairs.extend((r, {"alpha": 1.0, "beta": 0.0}) for r in val)
        cand_pairs.extend((r, params) for r in val)

    if len(folds) != ROBUST_FOLDS:
        return {
            "model_version": MODEL_VERSION,
            "ready": False,
            "dataset": dataset,
            "folds": folds,
            "error": "could not construct all required chronological Q4 folds",
        }

    robust_base = _aggregate_pairs(base_pairs)
    robust_cand = _aggregate_pairs(cand_pairs)
    robust_contract = _robust_contract(robust_base, robust_cand, folds)

    final_params = fit_params(dev_rows)
    tail_base = _aggregate(tail_rows, {"alpha": 1.0, "beta": 0.0})
    tail_cand = _aggregate(tail_rows, final_params)
    tail_contract = _tail_diagnostic(tail_base, tail_cand)

    return {
        "model_version": MODEL_VERSION,
        "ready": True,
        "dataset": dataset,
        "design": {
            "clean_games_used": len(rows),
            "development_games": len(dev_rows),
            "tail_recheck_games": len(tail_rows),
            "robust_folds": len(folds),
            "robust_validation_states": int(robust_base.get("states") or 0),
            "train_window": TRAIN_WINDOW,
            "validation_block": VALIDATION_BLOCK,
        },
        "folds": folds,
        "robustness": {
            "baseline": robust_base,
            "candidate": robust_cand,
            "contract": robust_contract,
        },
        "tail": {
            "baseline": tail_base,
            "candidate": tail_cand,
            "contract": tail_contract,
        },
        "final_params": final_params,
        "shadow_freeze_eligible": bool(robust_contract.get("pass")),
        "tail_consistent": bool(tail_contract.get("pass")),
        "sportsbook_used": False,
        "production_changed": False,
        "prospective_games_used": 0,
        "created_at": datetime.now(ET).isoformat(),
    }


def clear_cache():
    try:
        q4_dataset.clear()
    except Exception:
        pass
    try:
        preview.recent_completed_previews.clear()
    except Exception:
        pass
    # Step 6.6 calls the shared Q4 replay transport; release its historical PBP,
    # replay and preview caches too after an audit. This changes no model values.
    try:
        q4.clear_cache()
    except Exception:
        pass
