"""WNBA Live Games Step 6.4 — PBP-rich walk-forward calibration.

This lab is intentionally downstream of the Step-6.3 fidelity gate. It rebuilds
historical halftime/start-Q4 states from checkpoint-only ESPN play-by-play, then
runs the *production Step-6 projection structure* with those partial box metrics.

The goal is to answer a different question than Step 6.2:
    Does a small, interpretable calibration improve the production-like model
    when historical replay has the same pace/PPP/possession information that a
    real live Step-6 state receives?

Strict contracts
----------------
- Chronological whole-game split: older games fit, newest games validate.
- Future plays and the completed final boxscore never enter the projection.
- Historical injury state is not backfilled or guessed.
- Sportsbook prices/lines are never requested or used in the projection.
- Candidate parameters are never auto-promoted into production.
- Exact 5M paired holdout confirmation is available only after the analytic
  out-of-sample contract passes.
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

import wnba_live_flow_v1 as flow
import wnba_live_projection_v1 as model
import wnba_live_second_half_v14 as history
import wnba_live_step5_preview_v1 as preview
import wnba_live_step6_pbp_v1 as pbp
import wnba_live_step6_replay_v1 as replay

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE STEP-6.4 CALIBRATION V2 • PBP-RICH WALK-FORWARD"
DISCOVERY_GAMES = 24
TRAIN_GAMES = 16
VALIDATION_GAMES = 8
LOOKBACK_DAYS = 60
CHECKPOINTS = ("HALFTIME", "Q4_START")
MIN_TRAIN_STATES = 24
MIN_VALIDATION_STATES = 12
RIDGE_STRENGTH = 10.0

IDENTITY = {
    "remaining_total_scale": 1.0,
    "remaining_diff_scale": 1.0,
    "lead_persistence": 0.0,
    "home_bias_per10": 0.0,
    "sd_scale": 1.0,
}

BOUNDS = {
    "remaining_total_scale": (0.94, 1.06),
    "remaining_diff_scale": (0.80, 1.20),
    "lead_persistence": (-0.20, 0.20),
    "home_bias_per10": (-2.50, 2.50),
    "sd_scale": (0.82, 1.22),
}


def _num(value: Any, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _int(value: Any, default=0):
    try:
        if isinstance(value, dict):
            value = value.get("number", value.get("value", value.get("displayValue")))
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


def _flow_from_pbp(state: dict, rec: dict) -> dict:
    elapsed = flow.elapsed_seconds(state)
    remaining = flow.regulation_seconds_remaining(state)
    away = _int(state.get("away_score"))
    home = _int(state.get("home_score"))
    total = away + home
    elapsed_min = elapsed / 60.0 if elapsed > 0 else 0.0
    pace40 = _num(rec.get("pace40"))
    blended = _num(rec.get("blended_possessions"))
    current_period = max(1, _int(state.get("period"), 1))

    first_half_away = sum(_int((state.get("away_lines") or {}).get(p)) for p in (1, 2))
    first_half_home = sum(_int((state.get("home_lines") or {}).get(p)) for p in (1, 2))
    second_half_away = sum(
        _int((state.get("away_lines") or {}).get(p))
        for p in range(3, min(current_period, 4) + 1)
    )
    second_half_home = sum(
        _int((state.get("home_lines") or {}).get(p))
        for p in range(3, min(current_period, 4) + 1)
    )
    score_pace_total = (total / elapsed_min * 40.0) if elapsed_min > 0 else None
    remaining_poss = (pace40 * (remaining / 2400.0)) if pace40 is not None else None

    return {
        "event_id": str(state.get("espn_event_id") or ""),
        "summary_meta": {
            "available": True,
            "source": "checkpoint-only ESPN PBP reconstruction",
            "future_boxscore_blocked": True,
        },
        "data_quality": "HIGH" if str(rec.get("quality") or "") == "HIGH" else "CHECK",
        "elapsed_seconds": elapsed,
        "regulation_remaining_seconds": remaining,
        "total_points": total,
        "score_pace_total": score_pace_total,
        "current_period": current_period,
        "current_quarter_total": 0,
        "current_quarter_scoring_pace": None,
        "first_half_away": first_half_away,
        "first_half_home": first_half_home,
        "second_half_away": second_half_away,
        "second_half_home": second_half_home,
        "away": rec.get("away_metrics") or {},
        "home": rec.get("home_metrics") or {},
        "blended_possessions": blended,
        "pace40": pace40,
        "remaining_possessions": remaining_poss,
        "replay_safe": True,
        "historical_pbp_only": True,
    }


def projection_for_pbp_replay(state: dict, rec: dict) -> dict:
    """Production-structure replay using only checkpoint PBP + pregame history."""
    flow_data = _flow_from_pbp(state, rec)
    hist = history.profiles_for_game(state)
    away_profile = hist.get("away") or {}
    home_profile = hist.get("home") or {}

    segments, mu_a, mu_h, live_rate_a, live_rate_h = model._segment_projection(
        state, flow_data, away_profile, home_profile
    )
    current_a = _int(state.get("away_score"))
    current_h = _int(state.get("home_score"))

    history_mult = model._history_uncertainty(away_profile, home_profile)
    # Historical availability cannot be reconstructed safely. Neutralize it for
    # intrinsic model calibration rather than inventing a designation state.
    availability_mult = 1.0
    flow_mult = 1.0 if str(flow_data.get("data_quality") or "").upper() == "HIGH" else 1.08
    uncertainty_mult = model._clip(history_mult * availability_mult * flow_mult, 1.0, 1.35)

    sd_a = max(0.85, math.sqrt(max(0.25, mu_a) * 1.35) * uncertainty_mult)
    sd_h = max(0.85, math.sqrt(max(0.25, mu_h) * 1.35) * uncertainty_mult)
    pace40 = _num(flow_data.get("pace40"), model.LEAGUE_PACE_PRIOR)
    rho = model._clip(0.10 + (float(pace40) - model.LEAGUE_PACE_PRIOR) / 120.0, 0.04, 0.18)

    away_games = _int(away_profile.get("games"))
    home_games = _int(home_profile.get("games"))
    enough_history = away_games >= model.MIN_HISTORY_GAMES and home_games >= model.MIN_HISTORY_GAMES
    ready = bool(
        rec.get("score_reconciled")
        and str(rec.get("quality") or "") == "HIGH"
        and enough_history
        and bool(segments)
    )

    live_w = model._live_weight(_int(flow_data.get("elapsed_seconds")), "HIGH")
    ot_hist_a = model._historical_rate(away_profile, home_profile, 4)
    ot_hist_h = model._historical_rate(home_profile, away_profile, 4)
    ot_rate_a = model._clip((1.0 - live_w) * ot_hist_a + live_w * live_rate_a, 1.0, 3.2)
    ot_rate_h = model._clip((1.0 - live_w) * ot_hist_h + live_w * live_rate_h, 1.0, 3.2)

    return {
        "model_version": model.MODEL_VERSION,
        "calibration_replay_version": MODEL_VERSION,
        "state_key": model.state_key(state),
        "ready": ready,
        "data_quality": "HIGH" if ready else "LOW",
        "flow": flow_data,
        "history": hist,
        "context": {
            "replay_only": True,
            "availability": {
                "historical_availability_used": False,
                "neutralized_for_intrinsic_calibration": True,
            },
        },
        "segments": segments,
        "away_history_games": away_games,
        "home_history_games": home_games,
        "away_history_reliability": away_profile.get("reliability") or "THIN",
        "home_history_reliability": home_profile.get("reliability") or "THIN",
        "projected_remaining_away": mu_a,
        "projected_remaining_home": mu_h,
        "projected_base_final_away": current_a + mu_a,
        "projected_base_final_home": current_h + mu_h,
        "projected_base_total": current_a + current_h + mu_a + mu_h,
        "projected_base_home_margin": (current_h + mu_h) - (current_a + mu_a),
        "remaining_sd_away": sd_a,
        "remaining_sd_home": sd_h,
        "residual_correlation": rho,
        "uncertainty_multiplier": uncertainty_mult,
        "history_uncertainty_multiplier": history_mult,
        "availability_uncertainty_multiplier": availability_mult,
        "availability_meta": {
            "historical_availability_used": False,
            "neutralized_for_intrinsic_calibration": True,
        },
        "ot_rate_away": ot_rate_a,
        "ot_rate_home": ot_rate_h,
        "sportsbook_used_in_projection": False,
        "h2h_used_in_mean": False,
        "player_value_adjustment_used": False,
        "future_boxscore_used": False,
        "historical_availability_used": False,
        "actual_final_used_in_projection": False,
        "replay_only": True,
        "pbp_checkpoint_only": True,
    }


def _feature_row(game: dict, state: dict, projection: dict, truth: dict, split: str, rec: dict) -> dict:
    current_a = _int(state.get("away_score"))
    current_h = _int(state.get("home_score"))
    actual_a = _int(truth.get("away_final"))
    actual_h = _int(truth.get("home_final"))
    mu_a = float(projection.get("projected_remaining_away") or 0.0)
    mu_h = float(projection.get("projected_remaining_home") or 0.0)
    sd_a = float(projection.get("remaining_sd_away") or 1.0)
    sd_h = float(projection.get("remaining_sd_home") or 1.0)
    rho = float(projection.get("residual_correlation") or 0.10)
    rem_minutes = sum(float(x.get("minutes") or 0.0) for x in projection.get("segments") or [])
    var_margin = max(1e-6, sd_a * sd_a + sd_h * sd_h - 2.0 * rho * sd_a * sd_h)
    return {
        "split": split,
        "event_id": str(game.get("espn_event_id") or ""),
        "game_date": _date_key(game.get("captured_at")),
        "away_team": str(game.get("away_team") or "Away"),
        "home_team": str(game.get("home_team") or "Home"),
        "checkpoint": str(state.get("replay_checkpoint_id") or ""),
        "state": state,
        "projection": projection,
        "truth": truth,
        "reconstruction": rec,
        "current_away": current_a,
        "current_home": current_h,
        "current_home_margin": current_h - current_a,
        "remaining_minutes": rem_minutes,
        "base_remaining_away": mu_a,
        "base_remaining_home": mu_h,
        "base_remaining_total": mu_a + mu_h,
        "base_remaining_diff_home": mu_h - mu_a,
        "actual_remaining_away": actual_a - current_a,
        "actual_remaining_home": actual_h - current_h,
        "actual_remaining_total": (actual_a - current_a) + (actual_h - current_h),
        "actual_remaining_diff_home": (actual_h - current_h) - (actual_a - current_a),
        "actual_final_away": actual_a,
        "actual_final_home": actual_h,
        "actual_home_win": bool(actual_h > actual_a),
        "base_margin_variance": var_margin,
        "pace40": _num(rec.get("pace40")),
        "away_history_games": _int(projection.get("away_history_games")),
        "home_history_games": _int(projection.get("home_history_games")),
    }


@st.cache_data(ttl=1800, show_spinner=False, max_entries=4)
def calibration_dataset(day_str: str) -> dict:
    games, discovery = preview.recent_completed_previews(day_str, limit=DISCOVERY_GAMES, lookback_days=LOOKBACK_DAYS)
    games = sorted(games, key=lambda g: _date_key(g.get("captured_at")))
    if len(games) < (TRAIN_GAMES + VALIDATION_GAMES):
        train_n = max(0, len(games) - VALIDATION_GAMES)
    else:
        train_n = TRAIN_GAMES
    selected = games[: train_n + VALIDATION_GAMES]
    train_ids = {str(g.get("espn_event_id") or "") for g in selected[:train_n]}
    validation_ids = {str(g.get("espn_event_id") or "") for g in selected[train_n:]}

    rows = []
    errors = []
    games_ready = 0
    for game in selected:
        event_id = str(game.get("espn_event_id") or "")
        split = "TRAIN" if event_id in train_ids else "VALIDATION"
        bundle = replay.replay_bundle(game)
        if bundle.get("error"):
            errors.append(f"{event_id}: bundle {bundle.get('error')}")
            continue
        truth = bundle.get("truth") or {}
        cpmap = _checkpoint_map(bundle)
        accepted = 0
        for cid in CHECKPOINTS:
            state = cpmap.get(cid)
            if not state:
                errors.append(f"{event_id}: missing {cid}")
                continue
            rec = pbp.reconstruct(state)
            checks = pbp.audit(state, rec)
            if not all(bool(x.get("pass")) for x in checks):
                errors.append(f"{event_id} {cid}: PBP fidelity audit failed")
                continue
            projection = projection_for_pbp_replay(state, rec)
            audit = replay.replay_audit(state, projection, truth)
            if not projection.get("ready") or not all(bool(x.get("pass")) for x in audit):
                errors.append(f"{event_id} {cid}: production-like replay audit/model-ready failed")
                continue
            rows.append(_feature_row(game, state, projection, truth, split, rec))
            accepted += 1
        if accepted:
            games_ready += 1

    train_rows = [r for r in rows if r["split"] == "TRAIN"]
    validation_rows = [r for r in rows if r["split"] == "VALIDATION"]
    return {
        "model_version": MODEL_VERSION,
        "day": day_str,
        "games_discovered": len(games),
        "games_selected": len(selected),
        "games_ready": games_ready,
        "train_games": len(train_ids),
        "validation_games": len(validation_ids),
        "train_states": len(train_rows),
        "validation_states": len(validation_rows),
        "rows": rows,
        "discovery": discovery,
        "errors": errors[:60],
        "ready": len(train_rows) >= MIN_TRAIN_STATES and len(validation_rows) >= MIN_VALIDATION_STATES,
        "pbp_required": True,
        "final_boxscore_used_in_projection": False,
        "sportsbook_used": False,
    }


def _ridge_scalar(x: np.ndarray, y: np.ndarray, prior: float, lam: float) -> float:
    denom = float(np.dot(x, x) + lam)
    return float((np.dot(x, y) + lam * prior) / denom) if denom > 1e-9 else float(prior)


def _ridge_diff(rows: list[dict]) -> tuple[float, float, float]:
    X = np.array([
        [
            float(r["base_remaining_diff_home"]),
            float(r["current_home_margin"]),
            float(r["remaining_minutes"]) / 10.0,
        ]
        for r in rows
    ], dtype=float)
    y = np.array([float(r["actual_remaining_diff_home"]) for r in rows], dtype=float)
    prior = np.array([1.0, 0.0, 0.0], dtype=float)
    if len(rows) < 4:
        return 1.0, 0.0, 0.0

    scales = np.sqrt(np.mean(X * X, axis=0))
    scales = np.where(scales < 1e-6, 1.0, scales)
    Z = X / scales
    prior_z = prior * scales
    reg = RIDGE_STRENGTH * np.eye(3)
    try:
        beta_z = np.linalg.solve(Z.T @ Z + reg, Z.T @ y + reg @ prior_z)
        beta = beta_z / scales
    except Exception:
        beta = prior
    return float(beta[0]), float(beta[1]), float(beta[2])


def _predict_row(row: dict, params: dict) -> dict:
    rem_total = max(0.0, float(row["base_remaining_total"]) * float(params["remaining_total_scale"]))
    rem10 = float(row["remaining_minutes"]) / 10.0
    rem_diff = (
        float(row["base_remaining_diff_home"]) * float(params["remaining_diff_scale"])
        + float(row["current_home_margin"]) * float(params["lead_persistence"])
        + rem10 * float(params["home_bias_per10"])
    )
    rem_diff = _clip(rem_diff, -rem_total, rem_total)
    rem_h = max(0.0, (rem_total + rem_diff) / 2.0)
    rem_a = max(0.0, rem_total - rem_h)
    expected_a = float(row["current_away"]) + rem_a
    expected_h = float(row["current_home"]) + rem_h
    expected_total = expected_a + expected_h
    expected_margin = expected_h - expected_a
    sd_margin = math.sqrt(max(1e-9, float(row["base_margin_variance"]))) * float(params["sd_scale"])
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


def _fit_checkpoint(rows: list[dict]) -> dict:
    n = len(rows)
    if n < 6:
        return dict(IDENTITY, sample=n, fit_status="IDENTITY • THIN SAMPLE", bound_hits=[])

    x_total = np.array([float(r["base_remaining_total"]) for r in rows], dtype=float)
    y_total = np.array([float(r["actual_remaining_total"]) for r in rows], dtype=float)
    raw_total = _ridge_scalar(x_total, y_total, 1.0, RIDGE_STRENGTH)

    raw_diff, raw_lead, raw_home_bias = _ridge_diff(rows)
    p = {
        "remaining_total_scale": _clip(raw_total, *BOUNDS["remaining_total_scale"]),
        "remaining_diff_scale": _clip(raw_diff, *BOUNDS["remaining_diff_scale"]),
        "lead_persistence": _clip(raw_lead, *BOUNDS["lead_persistence"]),
        "home_bias_per10": _clip(raw_home_bias, *BOUNDS["home_bias_per10"]),
        "sd_scale": 1.0,
    }

    best_sd = 1.0
    best_brier = float("inf")
    lo, hi = BOUNDS["sd_scale"]
    for sd in np.arange(lo, hi + 0.0001, 0.02):
        losses = []
        trial = dict(p)
        trial["sd_scale"] = float(sd)
        for r in rows:
            pred = _predict_row(r, trial)
            target = 1.0 if r["actual_home_win"] else 0.0
            losses.append((pred["home_win_probability"] - target) ** 2)
        score = float(np.mean(losses)) if losses else float("inf")
        score += abs(float(sd) - 1.0) * 2e-5
        if score < best_brier:
            best_brier = score
            best_sd = float(sd)
    p["sd_scale"] = best_sd

    bound_hits = []
    for key, (lo_b, hi_b) in BOUNDS.items():
        val = float(p[key])
        if abs(val - lo_b) < 1e-6 or abs(val - hi_b) < 1e-6:
            bound_hits.append(key)

    return {
        **p,
        "sample": n,
        "raw_total_scale": raw_total,
        "raw_diff_scale": raw_diff,
        "raw_lead_persistence": raw_lead,
        "raw_home_bias_per10": raw_home_bias,
        "training_brier_after_sd_fit": best_brier,
        "fit_status": "CALIBRATED",
        "bound_hits": bound_hits,
    }


def fit_parameters(train_rows: list[dict]) -> dict:
    by_cp = {}
    for cid in CHECKPOINTS:
        by_cp[cid] = _fit_checkpoint([r for r in train_rows if r["checkpoint"] == cid])
    return {
        "model_version": MODEL_VERSION,
        "fit_at": datetime.now(ET).isoformat(),
        "checkpoints": by_cp,
        "train_states": len(train_rows),
        "sportsbook_used": False,
        "future_data_used": False,
        "historical_availability_used": False,
    }


def _params_for_row(row: dict, fitted: dict | None) -> dict:
    out = dict(IDENTITY)
    if not fitted:
        return out
    p = ((fitted.get("checkpoints") or {}).get(str(row.get("checkpoint") or "")) or {})
    for key in IDENTITY:
        if p.get(key) is not None:
            out[key] = float(p[key])
    return out


def _aggregate(rows: list[dict], fitted: dict | None) -> dict:
    if not rows:
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
    for r in rows:
        pred = _predict_row(r, _params_for_row(r, fitted))
        aa = float(r["actual_final_away"])
        ah = float(r["actual_final_home"])
        at = aa + ah
        am = ah - aa
        home_won = bool(r["actual_home_win"])
        ph = float(pred["home_win_probability"])
        winner.append((ph >= 0.5) == home_won)
        winner_p.append(ph if home_won else 1.0 - ph)
        brier.append((ph - (1.0 if home_won else 0.0)) ** 2)
        team_ae.append((abs(pred["expected_away"] - aa) + abs(pred["expected_home"] - ah)) / 2.0)
        te = pred["expected_total"] - at
        me = pred["expected_home_margin"] - am
        total_abs.append(abs(te)); margin_abs.append(abs(me)); total_err.append(te); margin_err.append(me)

    out = {
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
    out["composite"] = (
        0.30 * out["brier"] / 0.25
        + 0.25 * out["team_mae"] / 8.0
        + 0.225 * out["total_mae"] / 12.0
        + 0.225 * out["margin_mae"] / 10.0
    )
    return out


def _group_metrics(rows: list[dict], fitted: dict | None) -> dict:
    return {cid: _aggregate([r for r in rows if r["checkpoint"] == cid], fitted) for cid in CHECKPOINTS}


def _fit_warnings(fitted: dict) -> list[str]:
    warnings = []
    for cid in CHECKPOINTS:
        p = ((fitted.get("checkpoints") or {}).get(cid) or {})
        hits = p.get("bound_hits") or []
        if hits:
            warnings.append(f"{cid}: parameter bound hit(s): {', '.join(hits)}")
    return warnings


def _promotion_contract(baseline: dict, candidate: dict, base_groups: dict, cand_groups: dict, n: int, fitted: dict) -> dict:
    reasons = []
    warnings = _fit_warnings(fitted)
    if n < MIN_VALIDATION_STATES:
        reasons.append(f"validation sample {n} < {MIN_VALIDATION_STATES}")
    if baseline.get("composite") is None or candidate.get("composite") is None:
        reasons.append("missing validation metrics")
    else:
        if candidate["composite"] > baseline["composite"] * 0.98:
            reasons.append("composite improvement < 2%")
        if candidate["brier"] > baseline["brier"] + 0.003:
            reasons.append("Brier worsened > 0.003")
        if candidate["team_mae"] > baseline["team_mae"] + 0.25:
            reasons.append("team MAE worsened > 0.25")
        if candidate["total_mae"] > baseline["total_mae"] + 0.35:
            reasons.append("total MAE worsened > 0.35")
        if candidate["margin_mae"] > baseline["margin_mae"] + 0.35:
            reasons.append("margin MAE worsened > 0.35")
        if candidate["winner_accuracy"] + 0.07 < baseline["winner_accuracy"]:
            reasons.append("winner accuracy materially worse")
        if abs(float(baseline["margin_bias"])) >= 2.0 and abs(float(candidate["margin_bias"])) > abs(float(baseline["margin_bias"])) * 0.92:
            reasons.append("material baseline margin bias not reduced by at least 8%")

    for cid in CHECKPOINTS:
        b = base_groups.get(cid) or {}
        c = cand_groups.get(cid) or {}
        if b.get("states", 0) >= 4 and b.get("composite") is not None and c.get("composite") is not None:
            if c["composite"] > b["composite"] * 1.05:
                reasons.append(f"{cid} composite degraded > 5%")

    safe = not reasons
    return {
        "safe_candidate": safe,
        "status": "SAFE FOR 5M CONFIRMATION" if safe else "DO NOT PROMOTE",
        "reasons": reasons,
        "warnings": warnings,
        "required_validation_states": MIN_VALIDATION_STATES,
    }


def calibration_audit(day_str: str) -> dict:
    dataset = calibration_dataset(day_str)
    train_rows = [r for r in dataset.get("rows") or [] if r.get("split") == "TRAIN"]
    val_rows = [r for r in dataset.get("rows") or [] if r.get("split") == "VALIDATION"]
    if not dataset.get("ready"):
        return {
            "model_version": MODEL_VERSION,
            "ready": False,
            "dataset": dataset,
            "error": "insufficient clean PBP-rich walk-forward replay states",
        }
    fitted = fit_parameters(train_rows)
    base_train = _aggregate(train_rows, None)
    cand_train = _aggregate(train_rows, fitted)
    base_val = _aggregate(val_rows, None)
    cand_val = _aggregate(val_rows, fitted)
    base_groups = _group_metrics(val_rows, None)
    cand_groups = _group_metrics(val_rows, fitted)
    contract = _promotion_contract(base_val, cand_val, base_groups, cand_groups, len(val_rows), fitted)
    return {
        "model_version": MODEL_VERSION,
        "ready": True,
        "dataset": dataset,
        "fitted": fitted,
        "train": {"baseline": base_train, "candidate": cand_train},
        "validation": {
            "baseline": base_val,
            "candidate": cand_val,
            "baseline_by_checkpoint": base_groups,
            "candidate_by_checkpoint": cand_groups,
        },
        "contract": contract,
        "sportsbook_used": False,
        "actual_validation_finals_used_for_fit": False,
        "calibration_candidate_promoted": False,
        "replay_data_mode": "PBP-RICH CHECKPOINT ONLY",
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
        return {"ready": False, "error": "PBP-rich calibration audit not ready"}
    if not (audit.get("contract") or {}).get("safe_candidate"):
        return {"ready": False, "error": "analytic holdout contract did not pass; 5M confirmation blocked"}
    fitted = audit.get("fitted") or {}
    rows = [r for r in (audit.get("dataset") or {}).get("rows") or [] if r.get("split") == "VALIDATION"]
    if len(rows) < MIN_VALIDATION_STATES:
        return {"ready": False, "error": "insufficient validation states"}

    baseline_evals = []
    candidate_evals = []
    base_by_cp = {cid: [] for cid in CHECKPOINTS}
    cand_by_cp = {cid: [] for cid in CHECKPOINTS}
    convergence_failures = []
    runtime = 0.0

    for row in rows:
        state = row["state"]
        truth = row["truth"]
        bp = row["projection"]
        cp = calibrated_projection(row, fitted)
        br = model.simulate_5m(state, bp, [])
        cr = model.simulate_5m(state, cp, [])
        runtime += float(br.get("runtime_seconds") or 0.0) + float(cr.get("runtime_seconds") or 0.0)
        if str(br.get("convergence") or "") != "PASS":
            convergence_failures.append(f"BASE {row['event_id']} {row['checkpoint']}")
        if str(cr.get("convergence") or "") != "PASS":
            convergence_failures.append(f"CAND {row['event_id']} {row['checkpoint']}")
        be = replay.evaluate_holdout(br, truth)
        ce = replay.evaluate_holdout(cr, truth)
        baseline_evals.append(be); candidate_evals.append(ce)
        base_by_cp[row["checkpoint"]].append(be); cand_by_cp[row["checkpoint"]].append(ce)

    base = _metrics_from_evals(baseline_evals)
    cand = _metrics_from_evals(candidate_evals)
    bg = {cid: _metrics_from_evals(base_by_cp[cid]) for cid in CHECKPOINTS}
    cg = {cid: _metrics_from_evals(cand_by_cp[cid]) for cid in CHECKPOINTS}
    contract = _promotion_contract(base, cand, bg, cg, len(rows), fitted)
    if convergence_failures:
        contract = dict(contract)
        contract["safe_candidate"] = False
        contract["status"] = "DO NOT PROMOTE"
        contract["reasons"] = list(contract.get("reasons") or []) + [f"{len(convergence_failures)} 5M convergence failure(s)"]
    elif contract.get("safe_candidate"):
        contract = dict(contract)
        contract["status"] = "SAFE FOR PRODUCTION V2 REVIEW"

    return {
        "model_version": MODEL_VERSION,
        "ready": True,
        "simulations_per_state_per_model": model.SIMULATIONS,
        "validation_states": len(rows),
        "total_simulations": len(rows) * model.SIMULATIONS * 2,
        "baseline": base,
        "candidate": cand,
        "baseline_by_checkpoint": bg,
        "candidate_by_checkpoint": cg,
        "contract": contract,
        "convergence_failures": convergence_failures,
        "runtime_seconds": runtime,
        "paired_deterministic_seeds": True,
        "candidate_promoted": False,
    }


def clear_cache():
    for fn in (calibration_dataset,):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        pbp.clear_cache()
    except Exception:
        pass
    try:
        replay.clear_cache()
    except Exception:
        pass
    try:
        preview.clear_cache()
    except Exception:
        pass
