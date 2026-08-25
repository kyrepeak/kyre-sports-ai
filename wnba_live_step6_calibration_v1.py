"""WNBA Live Games Step-6.2 walk-forward calibration engine.

Purpose
-------
Calibrate the Step-6 mean/uncertainty only from completed quarter-boundary
replays, with a strict chronological train/validation split. The newest games
are never used to fit parameters. Historical sportsbook data is never requested.

The calibration candidate is NOT automatically promoted into production. This
module produces a recommended parameter set and an out-of-sample validation
report. Production Step 6 remains unchanged until the candidate passes the
validation contract and is explicitly promoted in code.

Calibration knobs are deliberately small/interpretable:
- remaining_total_scale: multiplicative correction to projected remaining total
- remaining_diff_scale: multiplicative correction to projected remaining scoring diff
- lead_persistence: correction tied to the exact current score margin
- sd_scale: multiplicative correction to remaining-score uncertainty

The first three alter the statistical mean; sd_scale alters probability spread.
All knobs are strongly shrunk toward the V1 identity prior to reduce overfit.
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

import wnba_live_projection_v1 as model
import wnba_live_step5_preview_v1 as preview
import wnba_live_step6_replay_v1 as replay

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE STEP-6.2 CALIBRATION V1 • WALK-FORWARD HOLDOUT"
DISCOVERY_GAMES = 16
TRAIN_GAMES = 10
VALIDATION_GAMES = 6
LOOKBACK_DAYS = 45
CHECKPOINTS = ("HALFTIME", "Q4_START")
MIN_TRAIN_STATES = 12
MIN_VALIDATION_STATES = 8
PARAM_SHRINK_PRIOR_STATES = 8.0

IDENTITY = {
    "remaining_total_scale": 1.0,
    "remaining_diff_scale": 1.0,
    "lead_persistence": 0.0,
    "sd_scale": 1.0,
}


def _num(value: Any, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _int(value: Any, default=0):
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _clip(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


def _date_key(value: Any) -> str:
    try:
        return pd.to_datetime(value, utc=True).isoformat()
    except Exception:
        return str(value or "")


def _checkpoint_map(bundle: dict) -> dict[str, dict]:
    out = {}
    for state in bundle.get("checkpoints") or []:
        cid = str(state.get("replay_checkpoint_id") or "")
        if cid:
            out[cid] = state
    return out


def _feature_row(game: dict, state: dict, projection: dict, truth: dict, split: str) -> dict:
    current_a = _int(state.get("away_score"))
    current_h = _int(state.get("home_score"))
    actual_a = _int(truth.get("away_final"))
    actual_h = _int(truth.get("home_final"))

    mu_a = float(projection.get("projected_remaining_away") or 0.0)
    mu_h = float(projection.get("projected_remaining_home") or 0.0)
    base_rem_total = mu_a + mu_h
    base_rem_diff_home = mu_h - mu_a
    current_home_margin = current_h - current_a
    actual_rem_a = actual_a - current_a
    actual_rem_h = actual_h - current_h
    actual_rem_total = actual_rem_a + actual_rem_h
    actual_rem_diff_home = actual_rem_h - actual_rem_a

    sd_a = float(projection.get("remaining_sd_away") or 1.0)
    sd_h = float(projection.get("remaining_sd_home") or 1.0)
    rho = float(projection.get("residual_correlation") or 0.10)
    var_margin = max(1e-6, sd_a * sd_a + sd_h * sd_h - 2.0 * rho * sd_a * sd_h)

    return {
        "split": split,
        "event_id": str(game.get("espn_event_id") or ""),
        "game_date": _date_key(game.get("captured_at")),
        "away_team": str(game.get("away_team") or "Away"),
        "home_team": str(game.get("home_team") or "Home"),
        "checkpoint": str(state.get("replay_checkpoint_id") or ""),
        "checkpoint_label": str(state.get("replay_checkpoint_label") or ""),
        "state": state,
        "projection": projection,
        "truth": truth,
        "current_away": current_a,
        "current_home": current_h,
        "current_home_margin": current_home_margin,
        "base_remaining_away": mu_a,
        "base_remaining_home": mu_h,
        "base_remaining_total": base_rem_total,
        "base_remaining_diff_home": base_rem_diff_home,
        "actual_remaining_away": actual_rem_a,
        "actual_remaining_home": actual_rem_h,
        "actual_remaining_total": actual_rem_total,
        "actual_remaining_diff_home": actual_rem_diff_home,
        "actual_final_away": actual_a,
        "actual_final_home": actual_h,
        "actual_home_win": bool(actual_h > actual_a),
        "base_margin_variance": var_margin,
        "away_history_games": _int(projection.get("away_history_games")),
        "home_history_games": _int(projection.get("home_history_games")),
    }


@st.cache_data(ttl=1800, show_spinner=False, max_entries=4)
def calibration_dataset(day_str: str) -> dict:
    games, discovery = preview.recent_completed_previews(
        day_str,
        limit=DISCOVERY_GAMES,
        lookback_days=LOOKBACK_DAYS,
    )
    games = sorted(games, key=lambda g: _date_key(g.get("captured_at")))

    # Chronological split by whole game prevents one checkpoint from a game being
    # used to fit while another checkpoint from the same game is validation.
    if len(games) < (TRAIN_GAMES + VALIDATION_GAMES):
        train_n = max(0, len(games) - VALIDATION_GAMES)
    else:
        train_n = TRAIN_GAMES
    train_ids = {str(g.get("espn_event_id") or "") for g in games[:train_n]}
    validation_ids = {
        str(g.get("espn_event_id") or "")
        for g in games[train_n: train_n + VALIDATION_GAMES]
    }

    rows = []
    errors = []
    games_ready = 0
    for game in games[: train_n + VALIDATION_GAMES]:
        event_id = str(game.get("espn_event_id") or "")
        split = "TRAIN" if event_id in train_ids else ("VALIDATION" if event_id in validation_ids else "SKIP")
        if split == "SKIP":
            continue
        bundle = replay.replay_bundle(game)
        if bundle.get("error"):
            errors.append(f"{event_id}: bundle {bundle.get('error')}")
            continue
        truth = bundle.get("truth") or {}
        cpmap = _checkpoint_map(bundle)
        game_rows = 0
        for cid in CHECKPOINTS:
            state = cpmap.get(cid)
            if not state:
                errors.append(f"{event_id}: missing {cid}")
                continue
            projection = replay.projection_for_replay(state)
            audit = replay.replay_audit(state, projection, truth)
            if not projection.get("ready") or not all(bool(x.get("pass")) for x in audit):
                errors.append(f"{event_id} {cid}: replay audit/model-ready failed")
                continue
            rows.append(_feature_row(game, state, projection, truth, split))
            game_rows += 1
        if game_rows:
            games_ready += 1

    train_rows = [r for r in rows if r["split"] == "TRAIN"]
    validation_rows = [r for r in rows if r["split"] == "VALIDATION"]
    return {
        "model_version": MODEL_VERSION,
        "day": day_str,
        "games_discovered": len(games),
        "games_ready": games_ready,
        "train_games": len(train_ids),
        "validation_games": len(validation_ids),
        "train_states": len(train_rows),
        "validation_states": len(validation_rows),
        "rows": rows,
        "discovery": discovery,
        "errors": errors[:40],
        "ready": len(train_rows) >= MIN_TRAIN_STATES and len(validation_rows) >= MIN_VALIDATION_STATES,
    }


def _shrink(raw: float, n: int, identity: float) -> float:
    w = float(n) / (float(n) + PARAM_SHRINK_PRIOR_STATES)
    return identity + w * (raw - identity)


def _fit_checkpoint(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 4:
        return dict(IDENTITY, sample=n, fit_status="IDENTITY • THIN SAMPLE")

    x_total = np.array([float(r["base_remaining_total"]) for r in rows], dtype=float)
    y_total = np.array([float(r["actual_remaining_total"]) for r in rows], dtype=float)
    denom_total = float(np.dot(x_total, x_total))
    raw_total = float(np.dot(x_total, y_total) / denom_total) if denom_total > 1e-9 else 1.0
    total_scale = _clip(_shrink(raw_total, n, 1.0), 0.92, 1.08)

    current_margin = np.array([float(r["current_home_margin"]) for r in rows], dtype=float)
    x_diff = np.array([float(r["base_remaining_diff_home"]) for r in rows], dtype=float)
    y_diff = np.array([float(r["actual_remaining_diff_home"]) for r in rows], dtype=float)

    # First estimate current-lead persistence from the residual left by V1.
    residual = y_diff - x_diff
    denom_lead = float(np.dot(current_margin, current_margin))
    raw_lead = float(np.dot(current_margin, residual) / denom_lead) if denom_lead > 1e-9 else 0.0
    lead_persistence = _clip(_shrink(raw_lead, n, 0.0), -0.20, 0.30)

    # Then calibrate remaining scoring differential after accounting for lead persistence.
    target_after_lead = y_diff - lead_persistence * current_margin
    denom_diff = float(np.dot(x_diff, x_diff))
    raw_diff = float(np.dot(x_diff, target_after_lead) / denom_diff) if denom_diff > 1e-9 else 1.0
    diff_scale = _clip(_shrink(raw_diff, n, 1.0), 0.80, 1.20)

    # Probability width is fit last, using the calibrated mean and a small grid.
    best_sd = 1.0
    best_brier = float("inf")
    for sd_scale in np.arange(0.80, 1.351, 0.025):
        losses = []
        for r in rows:
            pred = _predict_row(
                r,
                {
                    "remaining_total_scale": total_scale,
                    "remaining_diff_scale": diff_scale,
                    "lead_persistence": lead_persistence,
                    "sd_scale": float(sd_scale),
                },
            )
            target = 1.0 if r["actual_home_win"] else 0.0
            losses.append((pred["home_win_probability"] - target) ** 2)
        score = float(np.mean(losses)) if losses else float("inf")
        # Tiny identity tie-break prevents pointless variance changes.
        score += abs(float(sd_scale) - 1.0) * 1e-6
        if score < best_brier:
            best_brier = score
            best_sd = float(sd_scale)

    return {
        "remaining_total_scale": float(total_scale),
        "remaining_diff_scale": float(diff_scale),
        "lead_persistence": float(lead_persistence),
        "sd_scale": float(best_sd),
        "sample": n,
        "raw_total_scale": raw_total,
        "raw_diff_scale": raw_diff,
        "raw_lead_persistence": raw_lead,
        "training_brier_after_sd_fit": best_brier,
        "fit_status": "CALIBRATED",
    }


def fit_parameters(train_rows: list[dict]) -> dict:
    by_checkpoint = {}
    for cid in CHECKPOINTS:
        subset = [r for r in train_rows if r["checkpoint"] == cid]
        by_checkpoint[cid] = _fit_checkpoint(subset)
    return {
        "model_version": MODEL_VERSION,
        "fit_at": datetime.now(ET).isoformat(),
        "checkpoints": by_checkpoint,
        "train_states": len(train_rows),
        "sportsbook_used": False,
        "future_data_used": False,
    }


def _params_for_row(row: dict, fitted: dict | None) -> dict:
    if not fitted:
        return dict(IDENTITY)
    params = ((fitted.get("checkpoints") or {}).get(str(row.get("checkpoint") or "")) or {})
    out = dict(IDENTITY)
    for key in IDENTITY:
        if key in params:
            out[key] = float(params[key])
    return out


def _predict_row(row: dict, params: dict) -> dict:
    rem_total = max(0.0, float(row["base_remaining_total"]) * float(params["remaining_total_scale"]))
    rem_diff = (
        float(row["base_remaining_diff_home"]) * float(params["remaining_diff_scale"])
        + float(row["current_home_margin"]) * float(params["lead_persistence"])
    )
    rem_diff = _clip(rem_diff, -rem_total, rem_total)
    rem_h = max(0.0, (rem_total + rem_diff) / 2.0)
    rem_a = max(0.0, rem_total - rem_h)

    expected_a = float(row["current_away"]) + rem_a
    expected_h = float(row["current_home"]) + rem_h
    expected_total = expected_a + expected_h
    expected_home_margin = expected_h - expected_a

    sd_margin = math.sqrt(max(1e-9, float(row["base_margin_variance"]))) * float(params["sd_scale"])
    z = expected_home_margin / max(1e-9, sd_margin)
    home_p = _clip(NormalDist().cdf(z), 0.001, 0.999)

    return {
        "expected_away": expected_a,
        "expected_home": expected_h,
        "expected_total": expected_total,
        "expected_home_margin": expected_home_margin,
        "home_win_probability": home_p,
        "away_win_probability": 1.0 - home_p,
        "remaining_away": rem_a,
        "remaining_home": rem_h,
        "sd_margin": sd_margin,
    }


def _aggregate(rows: list[dict], fitted: dict | None) -> dict:
    if not rows:
        return {
            "states": 0,
            "winner_accuracy": None,
            "avg_actual_winner_probability": None,
            "brier": None,
            "team_mae": None,
            "total_mae": None,
            "margin_mae": None,
            "total_bias": None,
            "margin_bias": None,
            "composite": None,
        }

    winner = []
    winner_p = []
    brier = []
    team_ae = []
    total_abs = []
    margin_abs = []
    total_err = []
    margin_err = []
    for row in rows:
        params = _params_for_row(row, fitted)
        pred = _predict_row(row, params)
        actual_a = float(row["actual_final_away"])
        actual_h = float(row["actual_final_home"])
        actual_total = actual_a + actual_h
        actual_margin = actual_h - actual_a
        actual_home = bool(row["actual_home_win"])
        p_home = float(pred["home_win_probability"])
        actual_p = p_home if actual_home else (1.0 - p_home)
        winner.append((p_home >= 0.5) == actual_home)
        winner_p.append(actual_p)
        brier.append((p_home - (1.0 if actual_home else 0.0)) ** 2)
        team_ae.append((abs(pred["expected_away"] - actual_a) + abs(pred["expected_home"] - actual_h)) / 2.0)
        te = pred["expected_total"] - actual_total
        me = pred["expected_home_margin"] - actual_margin
        total_abs.append(abs(te))
        margin_abs.append(abs(me))
        total_err.append(te)
        margin_err.append(me)

    metrics = {
        "states": len(rows),
        "winner_accuracy": float(np.mean(winner)),
        "avg_actual_winner_probability": float(np.mean(winner_p)),
        "brier": float(np.mean(brier)),
        "team_mae": float(np.mean(team_ae)),
        "total_mae": float(np.mean(total_abs)),
        "margin_mae": float(np.mean(margin_abs)),
        "total_bias": float(np.mean(total_err)),
        "margin_bias": float(np.mean(margin_err)),
    }
    metrics["composite"] = (
        0.30 * metrics["brier"] / 0.25
        + 0.25 * metrics["team_mae"] / 8.0
        + 0.225 * metrics["total_mae"] / 12.0
        + 0.225 * metrics["margin_mae"] / 10.0
    )
    return metrics


def _group_metrics(rows: list[dict], fitted: dict | None) -> dict:
    return {
        cid: _aggregate([r for r in rows if r["checkpoint"] == cid], fitted)
        for cid in CHECKPOINTS
    }


def _promotion_contract(baseline: dict, candidate: dict, base_groups: dict, cand_groups: dict, n: int) -> dict:
    reasons = []
    if n < MIN_VALIDATION_STATES:
        reasons.append(f"validation sample {n} < {MIN_VALIDATION_STATES}")
    if baseline.get("composite") is None or candidate.get("composite") is None:
        reasons.append("missing validation metrics")
    else:
        if candidate["composite"] > baseline["composite"] * 0.97:
            reasons.append("composite improvement < 3%")
        if candidate["brier"] > baseline["brier"] + 0.005:
            reasons.append("Brier worsened > 0.005")
        if candidate["total_mae"] > baseline["total_mae"] + 0.50:
            reasons.append("total MAE worsened > 0.50")
        if candidate["margin_mae"] > baseline["margin_mae"] + 0.50:
            reasons.append("margin MAE worsened > 0.50")
        if candidate["winner_accuracy"] + 0.08 < baseline["winner_accuracy"]:
            reasons.append("winner accuracy materially worse")

    for cid in CHECKPOINTS:
        b = base_groups.get(cid) or {}
        c = cand_groups.get(cid) or {}
        if b.get("states", 0) >= 3 and b.get("composite") is not None and c.get("composite") is not None:
            if c["composite"] > b["composite"] * 1.10:
                reasons.append(f"{cid} composite degraded > 10%")

    safe = not reasons
    return {
        "safe_candidate": safe,
        "status": "SAFE CANDIDATE" if safe else "DO NOT PROMOTE",
        "reasons": reasons,
        "required_validation_states": MIN_VALIDATION_STATES,
    }


def calibration_audit(day_str: str) -> dict:
    dataset = calibration_dataset(day_str)
    train_rows = [r for r in dataset.get("rows") or [] if r.get("split") == "TRAIN"]
    val_rows = [r for r in dataset.get("rows") or [] if r.get("split") == "VALIDATION"]
    if not dataset.get("ready"):
        return {
            "model_version": MODEL_VERSION,
            "dataset": dataset,
            "ready": False,
            "error": "insufficient clean walk-forward replay states",
        }

    fitted = fit_parameters(train_rows)
    baseline_train = _aggregate(train_rows, None)
    candidate_train = _aggregate(train_rows, fitted)
    baseline_val = _aggregate(val_rows, None)
    candidate_val = _aggregate(val_rows, fitted)
    base_groups = _group_metrics(val_rows, None)
    cand_groups = _group_metrics(val_rows, fitted)
    contract = _promotion_contract(baseline_val, candidate_val, base_groups, cand_groups, len(val_rows))

    return {
        "model_version": MODEL_VERSION,
        "ready": True,
        "dataset": dataset,
        "fitted": fitted,
        "train": {"baseline": baseline_train, "candidate": candidate_train},
        "validation": {
            "baseline": baseline_val,
            "candidate": candidate_val,
            "baseline_by_checkpoint": base_groups,
            "candidate_by_checkpoint": cand_groups,
        },
        "contract": contract,
        "sportsbook_used": False,
        "actual_validation_finals_used_for_fit": False,
        "calibration_candidate_promoted": False,
    }


def calibrated_projection(row: dict, fitted: dict) -> dict:
    params = _params_for_row(row, fitted)
    pred = _predict_row(row, params)
    base = dict(row.get("projection") or {})
    base["projected_remaining_away"] = pred["remaining_away"]
    base["projected_remaining_home"] = pred["remaining_home"]
    base["projected_base_final_away"] = pred["expected_away"]
    base["projected_base_final_home"] = pred["expected_home"]
    base["projected_base_total"] = pred["expected_total"]
    base["projected_base_home_margin"] = pred["expected_home_margin"]
    base["remaining_sd_away"] = float(base.get("remaining_sd_away") or 1.0) * float(params["sd_scale"])
    base["remaining_sd_home"] = float(base.get("remaining_sd_home") or 1.0) * float(params["sd_scale"])
    base["calibration_applied"] = True
    base["calibration_version"] = MODEL_VERSION
    base["calibration_params"] = params
    base["sportsbook_used_in_projection"] = False
    return base


def _metrics_from_evals(evals: list[dict]) -> dict:
    if not evals:
        return _aggregate([], None)
    out = {
        "states": len(evals),
        "winner_accuracy": float(np.mean([bool(e.get("winner_call_correct")) for e in evals])),
        "avg_actual_winner_probability": float(np.mean([float(e.get("actual_winner_probability") or 0.0) for e in evals])),
        "brier": float(np.mean([float(e.get("brier_score") or 0.0) for e in evals])),
        "team_mae": float(np.mean([float(e.get("mean_team_abs_error") or 0.0) for e in evals])),
        "total_mae": float(np.mean([abs(float(e.get("total_error") or 0.0)) for e in evals])),
        "margin_mae": float(np.mean([abs(float(e.get("margin_error") or 0.0)) for e in evals])),
        "total_bias": float(np.mean([float(e.get("total_error") or 0.0) for e in evals])),
        "margin_bias": float(np.mean([float(e.get("margin_error") or 0.0) for e in evals])),
    }
    out["composite"] = (
        0.30 * out["brier"] / 0.25
        + 0.25 * out["team_mae"] / 8.0
        + 0.225 * out["total_mae"] / 12.0
        + 0.225 * out["margin_mae"] / 10.0
    )
    return out


def run_5m_confirmation(audit: dict) -> dict:
    if not audit.get("ready"):
        return {"ready": False, "error": "calibration audit not ready"}
    fitted = audit.get("fitted") or {}
    rows = [r for r in (audit.get("dataset") or {}).get("rows") or [] if r.get("split") == "VALIDATION"]
    if len(rows) < MIN_VALIDATION_STATES:
        return {"ready": False, "error": "insufficient validation states"}

    baseline_evals = []
    candidate_evals = []
    baseline_by_cp = {cid: [] for cid in CHECKPOINTS}
    candidate_by_cp = {cid: [] for cid in CHECKPOINTS}
    convergence_failures = []
    total_runtime = 0.0

    for row in rows:
        state = row["state"]
        truth = row["truth"]
        baseline_projection = row["projection"]
        candidate_projection = calibrated_projection(row, fitted)

        # Both use the exact same state-derived deterministic seed, so MC noise is paired.
        baseline_result = model.simulate_5m(state, baseline_projection, [])
        candidate_result = model.simulate_5m(state, candidate_projection, [])
        total_runtime += float(baseline_result.get("runtime_seconds") or 0.0)
        total_runtime += float(candidate_result.get("runtime_seconds") or 0.0)

        if str(baseline_result.get("convergence") or "") != "PASS":
            convergence_failures.append(f"BASE {row['event_id']} {row['checkpoint']}")
        if str(candidate_result.get("convergence") or "") != "PASS":
            convergence_failures.append(f"CAND {row['event_id']} {row['checkpoint']}")

        be = replay.evaluate_holdout(baseline_result, truth)
        ce = replay.evaluate_holdout(candidate_result, truth)
        baseline_evals.append(be)
        candidate_evals.append(ce)
        baseline_by_cp[row["checkpoint"]].append(be)
        candidate_by_cp[row["checkpoint"]].append(ce)

    baseline_metrics = _metrics_from_evals(baseline_evals)
    candidate_metrics = _metrics_from_evals(candidate_evals)
    base_groups = {cid: _metrics_from_evals(baseline_by_cp[cid]) for cid in CHECKPOINTS}
    cand_groups = {cid: _metrics_from_evals(candidate_by_cp[cid]) for cid in CHECKPOINTS}
    contract = _promotion_contract(
        baseline_metrics,
        candidate_metrics,
        base_groups,
        cand_groups,
        len(rows),
    )
    if convergence_failures:
        contract = dict(contract)
        contract["safe_candidate"] = False
        contract["status"] = "DO NOT PROMOTE"
        contract["reasons"] = list(contract.get("reasons") or []) + [
            f"{len(convergence_failures)} 5M convergence failure(s)"
        ]

    return {
        "model_version": MODEL_VERSION,
        "ready": True,
        "simulations_per_state_per_model": model.SIMULATIONS,
        "validation_states": len(rows),
        "total_simulations": len(rows) * model.SIMULATIONS * 2,
        "baseline": baseline_metrics,
        "candidate": candidate_metrics,
        "baseline_by_checkpoint": base_groups,
        "candidate_by_checkpoint": cand_groups,
        "contract": contract,
        "convergence_failures": convergence_failures,
        "paired_seed_contract": True,
        "runtime_seconds": total_runtime,
        "candidate_promoted": False,
    }


def clear_cache():
    try:
        calibration_dataset.clear()
    except Exception:
        pass
    try:
        preview.clear_cache()
    except Exception:
        pass
    try:
        replay.clear_cache()
    except Exception:
        pass


__all__ = [
    "MODEL_VERSION",
    "DISCOVERY_GAMES",
    "TRAIN_GAMES",
    "VALIDATION_GAMES",
    "CHECKPOINTS",
    "calibration_dataset",
    "calibration_audit",
    "run_5m_confirmation",
    "calibrated_projection",
    "clear_cache",
]
