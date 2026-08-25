"""WNBA Live Games Step 6.5 — Q4-specific robustness + fresh holdout promotion audit.

Purpose
-------
Step 6.4 showed a useful asymmetry: the PBP-rich Q4 candidate improved its
out-of-sample Q4 metrics while the halftime candidate did not clear the combined
promotion contract. This module does NOT loosen any Step-6.4 parameter bounds,
does NOT alter production Step 6, and does NOT reuse halftime calibration.

Instead it asks a narrower evidence-based question:
    Is the existing bounded Q4 calibration robust across multiple chronological
    walk-forward folds, and does it still improve on a fresh tail holdout that
    was not used to fit or select fold parameters?

Strict contracts
----------------
- Q4_START only. Halftime remains production V1.
- Same PBP-rich replay transport proven by Step 6.3.
- Same Step-6.4 model form and parameter bounds; no bound expansion.
- Multiple disjoint chronological validation folds before final holdout review.
- Newest games are reserved as a final tail holdout and never enter fitting.
- Final boxscore is used only as validation truth after each checkpoint state is built.
- Sportsbook lines/prices are never requested or used.
- Paired 5M confirmation is blocked unless robustness AND fresh analytic holdout pass.
- Nothing is auto-promoted to production.
"""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_live_projection_v1 as model
import wnba_live_step5_preview_v1 as preview
import wnba_live_step6_calibration_v2 as cal
import wnba_live_step6_pbp_v1 as pbp
import wnba_live_step6_replay_v1 as replay

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE STEP-6.5 Q4 PROMOTION AUDIT V1 • ROBUSTNESS + FRESH HOLDOUT"

CHECKPOINT = "Q4_START"
DISCOVERY_GAMES = 40
LOOKBACK_DAYS = 120
FINAL_HOLDOUT_GAMES = 8
ROBUST_TRAIN_WINDOW = 16
ROBUST_VALIDATION_BLOCK = 4
ROBUST_FOLDS = 4
MIN_CLEAN_GAMES = ROBUST_TRAIN_WINDOW + ROBUST_VALIDATION_BLOCK * ROBUST_FOLDS + FINAL_HOLDOUT_GAMES
MIN_ROBUST_STATES = ROBUST_VALIDATION_BLOCK * ROBUST_FOLDS
MIN_FINAL_STATES = FINAL_HOLDOUT_GAMES


def _date_key(value: Any) -> str:
    try:
        return pd.to_datetime(value, utc=True).isoformat()
    except Exception:
        return str(value or "")


def _checkpoint_state(bundle: dict) -> dict | None:
    for state in bundle.get("checkpoints") or []:
        if str(state.get("replay_checkpoint_id") or "") == CHECKPOINT:
            return state
    return None


def _single_q4_row(game: dict) -> tuple[dict | None, str]:
    event_id = str(game.get("espn_event_id") or "")
    bundle = replay.replay_bundle(game)
    if bundle.get("error"):
        return None, f"{event_id}: replay bundle {bundle.get('error')}"
    state = _checkpoint_state(bundle)
    if not state:
        return None, f"{event_id}: missing {CHECKPOINT}"
    rec = pbp.reconstruct(state)
    checks = pbp.audit(state, rec)
    if not checks or not all(bool(x.get("pass")) for x in checks):
        return None, f"{event_id}: PBP fidelity audit failed"
    projection = cal.projection_for_pbp_replay(state, rec)
    truth = bundle.get("truth") or {}
    audit = replay.replay_audit(state, projection, truth)
    if not projection.get("ready") or not audit or not all(bool(x.get("pass")) for x in audit):
        return None, f"{event_id}: production-like Q4 replay audit/model-ready failed"
    row = cal._feature_row(game, state, projection, truth, "Q4_POOL", rec)
    row["game_date"] = _date_key(game.get("captured_at"))
    return row, ""


@st.cache_data(ttl=1800, show_spinner=False, max_entries=4)
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
        row, error = _single_q4_row(game)
        if row is not None:
            rows.append(row)
        elif error:
            errors.append(error)
    rows = sorted(rows, key=lambda r: str(r.get("game_date") or ""))
    return {
        "model_version": MODEL_VERSION,
        "day": day_str,
        "games_discovered": len(games),
        "clean_q4_games": len(rows),
        "rows": rows,
        "errors": errors[:80],
        "discovery": discovery,
        "ready": len(rows) >= MIN_CLEAN_GAMES,
        "required_clean_games": MIN_CLEAN_GAMES,
        "final_boxscore_used_in_projection": False,
        "sportsbook_used": False,
    }


def _fitted_for_q4(rows: list[dict]) -> dict:
    p = cal._fit_checkpoint(rows)
    return {
        "model_version": MODEL_VERSION,
        "fit_at": datetime.now(ET).isoformat(),
        "checkpoints": {CHECKPOINT: p},
        "train_states": len(rows),
        "sportsbook_used": False,
        "future_data_used": False,
        "historical_availability_used": False,
    }


def _pct_improvement(baseline: float | None, candidate: float | None) -> float | None:
    try:
        b = float(baseline)
        c = float(candidate)
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
        if float(cand["composite"]) > float(base["composite"]) * 1.10:
            reasons.append("fold composite degraded > 10%")
        if float(cand["brier"]) > float(base["brier"]) + 0.02:
            reasons.append("fold Brier degraded > 0.020")
        if float(cand["margin_mae"]) > float(base["margin_mae"]) + 1.25:
            reasons.append("fold margin MAE degraded > 1.25 pts")
    return {"pass": not reasons, "reasons": reasons}


def _robust_contract(base: dict, cand: dict, folds: list[dict]) -> dict:
    reasons = []
    warnings = []
    if int(base.get("states") or 0) < MIN_ROBUST_STATES:
        reasons.append(f"robustness validation states < {MIN_ROBUST_STATES}")
    comp_imp = _pct_improvement(base.get("composite"), cand.get("composite"))
    if comp_imp is None or comp_imp < 0.015:
        reasons.append("aggregate rolling-fold composite improvement < 1.5%")
    if float(cand.get("brier") or 999) > float(base.get("brier") or 999) + 0.003:
        reasons.append("aggregate rolling-fold Brier worsened > 0.003")
    if float(cand.get("margin_mae") or 999) > float(base.get("margin_mae") or 999) + 0.25:
        reasons.append("aggregate rolling-fold margin MAE worsened > 0.25 pts")
    if float(cand.get("total_mae") or 999) > float(base.get("total_mae") or 999) + 0.35:
        reasons.append("aggregate rolling-fold total MAE worsened > 0.35 pts")
    if float(cand.get("winner_accuracy") or 0) + 0.0625 < float(base.get("winner_accuracy") or 0):
        reasons.append("aggregate rolling-fold winner accuracy materially worse")
    bb = abs(float(base.get("margin_bias") or 0.0))
    cb = abs(float(cand.get("margin_bias") or 0.0))
    if bb >= 2.0 and cb > bb * 0.92:
        reasons.append("aggregate rolling-fold margin bias not reduced by at least 8%")

    fold_passes = sum(1 for f in folds if (f.get("contract") or {}).get("pass"))
    nonworse = sum(
        1 for f in folds
        if float((f.get("candidate") or {}).get("composite") or 999)
        <= float((f.get("baseline") or {}).get("composite") or 999)
    )
    if fold_passes < max(3, len(folds) - 1):
        reasons.append(f"only {fold_passes}/{len(folds)} folds cleared catastrophic-degradation guard")
    if nonworse < max(3, len(folds) - 1):
        reasons.append(f"candidate composite improved/non-worsened in only {nonworse}/{len(folds)} folds")

    bound_hits = []
    raw_diff = []
    for f in folds:
        params = f.get("params") or {}
        if CHECKPOINT in (params.get("bound_hits") or []):
            pass
        if "remaining_diff_scale" in (params.get("bound_hits") or []):
            bound_hits.append(f.get("fold"))
        try:
            raw_diff.append(float(params.get("raw_diff_scale")))
        except Exception:
            pass
    if bound_hits:
        warnings.append(f"remaining_diff_scale hit 0.800 bound in {len(bound_hits)}/{len(folds)} fold fits; bound was NOT expanded")
    if raw_diff:
        warnings.append(f"raw remaining-diff fit range {min(raw_diff):.3f} to {max(raw_diff):.3f}")

    return {
        "pass": not reasons,
        "status": "ROBUST Q4 CANDIDATE" if not reasons else "HOLD",
        "reasons": reasons,
        "warnings": warnings,
        "composite_improvement": comp_imp,
        "folds_passed": fold_passes,
        "folds_nonworse": nonworse,
    }


def _fresh_contract(base: dict, cand: dict, params: dict) -> dict:
    reasons = []
    warnings = []
    n = int(base.get("states") or 0)
    if n < MIN_FINAL_STATES:
        reasons.append(f"fresh Q4 holdout states {n} < {MIN_FINAL_STATES}")
    comp_imp = _pct_improvement(base.get("composite"), cand.get("composite"))
    if comp_imp is None or comp_imp < 0.02:
        reasons.append("fresh Q4 composite improvement < 2%")
    if float(cand.get("brier") or 999) > float(base.get("brier") or 999) + 0.003:
        reasons.append("fresh Q4 Brier worsened > 0.003")
    if float(cand.get("team_mae") or 999) > float(base.get("team_mae") or 999) + 0.25:
        reasons.append("fresh Q4 team MAE worsened > 0.25 pts")
    if float(cand.get("total_mae") or 999) > float(base.get("total_mae") or 999) + 0.35:
        reasons.append("fresh Q4 total MAE worsened > 0.35 pts")
    if float(cand.get("margin_mae") or 999) > float(base.get("margin_mae") or 999) + 0.25:
        reasons.append("fresh Q4 margin MAE worsened > 0.25 pts")
    if float(cand.get("winner_accuracy") or 0) + (1.0 / max(1, n)) < float(base.get("winner_accuracy") or 0):
        reasons.append("fresh Q4 winner accuracy worse by more than one game")
    if float(cand.get("avg_actual_winner_probability") or 0) + 0.01 < float(base.get("avg_actual_winner_probability") or 0):
        reasons.append("fresh Q4 actual-winner probability declined > 1 pp")
    bb = abs(float(base.get("margin_bias") or 0.0))
    cb = abs(float(cand.get("margin_bias") or 0.0))
    if bb >= 2.0 and cb > bb * 0.92:
        reasons.append("fresh Q4 margin bias not reduced by at least 8%")
    if "remaining_diff_scale" in (params.get("bound_hits") or []):
        warnings.append("final Q4 fit uses conservative 0.800 remaining_diff_scale floor; bound was not loosened")
    return {
        "pass": not reasons,
        "status": "SAFE FOR PAIRED 5M Q4 CONFIRMATION" if not reasons else "DO NOT PROMOTE",
        "reasons": reasons,
        "warnings": warnings,
        "composite_improvement": comp_imp,
    }


def robustness_audit(day_str: str) -> dict:
    dataset = q4_dataset(day_str)
    rows = list(dataset.get("rows") or [])
    if not dataset.get("ready"):
        return {
            "model_version": MODEL_VERSION,
            "ready": False,
            "dataset": dataset,
            "error": "insufficient clean Q4 PBP-rich games for robustness + fresh holdout design",
        }

    rows = rows[-MIN_CLEAN_GAMES:]
    final_rows = rows[-FINAL_HOLDOUT_GAMES:]
    dev_rows = rows[:-FINAL_HOLDOUT_GAMES]

    folds = []
    all_val_rows = []
    all_base_preds = []
    all_cand_preds = []
    for i in range(ROBUST_FOLDS):
        start = i * ROBUST_VALIDATION_BLOCK
        train = dev_rows[start:start + ROBUST_TRAIN_WINDOW]
        val_start = start + ROBUST_TRAIN_WINDOW
        val = dev_rows[val_start:val_start + ROBUST_VALIDATION_BLOCK]
        if len(train) < ROBUST_TRAIN_WINDOW or len(val) < ROBUST_VALIDATION_BLOCK:
            continue
        fitted = _fitted_for_q4(train)
        params = ((fitted.get("checkpoints") or {}).get(CHECKPOINT) or {})
        base = cal._aggregate(val, None)
        cand = cal._aggregate(val, fitted)
        contract = _fold_contract(base, cand)
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
            "contract": contract,
        })
        all_val_rows.extend(val)
        for r in val:
            all_base_preds.append((r, None))
            all_cand_preds.append((r, fitted))

    if len(all_val_rows) < MIN_ROBUST_STATES or len(folds) < ROBUST_FOLDS:
        return {
            "model_version": MODEL_VERSION,
            "ready": False,
            "dataset": dataset,
            "error": "could not construct all required chronological Q4 robustness folds",
            "folds": folds,
        }

    # Aggregate the exact fold-specific candidate predictions rather than fitting one
    # candidate across the whole development pool. This preserves walk-forward honesty.
    def aggregate_pairs(pairs: list[tuple[dict, dict | None]]) -> dict:
        if not pairs:
            return cal._aggregate([], None)
        winner = []
        winner_p = []
        brier = []
        team_ae = []
        total_abs = []
        margin_abs = []
        total_err = []
        margin_err = []
        for row, fitted in pairs:
            pred = cal._predict_row(row, cal._params_for_row(row, fitted))
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
            total_abs.append(abs(te)); margin_abs.append(abs(me)); total_err.append(te); margin_err.append(me)
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

    robust_base = aggregate_pairs(all_base_preds)
    robust_cand = aggregate_pairs(all_cand_preds)
    robust_contract = _robust_contract(robust_base, robust_cand, folds)

    # Final fit uses only the development pool. The newest eight games remain untouched
    # until this point and never influence these parameters.
    final_fitted = _fitted_for_q4(dev_rows)
    final_params = ((final_fitted.get("checkpoints") or {}).get(CHECKPOINT) or {})
    fresh_base = cal._aggregate(final_rows, None)
    fresh_cand = cal._aggregate(final_rows, final_fitted)
    fresh_contract = _fresh_contract(fresh_base, fresh_cand, final_params)

    safe = bool(robust_contract.get("pass") and fresh_contract.get("pass"))
    return {
        "model_version": MODEL_VERSION,
        "ready": True,
        "dataset": dataset,
        "design": {
            "clean_games_used": len(rows),
            "development_games": len(dev_rows),
            "fresh_final_holdout_games": len(final_rows),
            "robust_folds": len(folds),
            "robust_train_window": ROBUST_TRAIN_WINDOW,
            "robust_validation_block": ROBUST_VALIDATION_BLOCK,
            "robust_validation_states": len(all_val_rows),
            "checkpoint": CHECKPOINT,
        },
        "folds": folds,
        "robustness": {
            "baseline": robust_base,
            "candidate": robust_cand,
            "contract": robust_contract,
        },
        "final_fitted": final_fitted,
        "fresh_holdout_rows": final_rows,
        "fresh_holdout": {
            "baseline": fresh_base,
            "candidate": fresh_cand,
            "contract": fresh_contract,
        },
        "safe_for_5m": safe,
        "status": "SAFE FOR PAIRED 5M Q4 CONFIRMATION" if safe else "DO NOT PROMOTE",
        "halftime_policy": "FROZEN AT PRODUCTION V1",
        "parameter_bounds_expanded": False,
        "sportsbook_used": False,
        "candidate_promoted": False,
    }


def _metrics_from_evals(evals: list[dict]) -> dict:
    return cal._metrics_from_evals(evals)


def _five_m_contract(base: dict, cand: dict, n: int, params: dict, convergence_failures: list[str]) -> dict:
    contract = _fresh_contract(base, cand, params)
    reasons = list(contract.get("reasons") or [])
    warnings = list(contract.get("warnings") or [])
    if convergence_failures:
        reasons.append(f"{len(convergence_failures)} 5M convergence failure(s)")
    safe = not reasons
    return {
        "pass": safe,
        "status": "SAFE FOR Q4 PRODUCTION V2 REVIEW" if safe else "DO NOT PROMOTE",
        "reasons": reasons,
        "warnings": warnings,
        "validation_states": n,
    }


def run_5m_confirmation(audit: dict) -> dict:
    if not audit.get("ready"):
        return {"ready": False, "error": "Step 6.5 audit is not ready"}
    if not audit.get("safe_for_5m"):
        return {"ready": False, "error": "robustness/fresh analytic contracts did not both pass"}
    rows = list(audit.get("fresh_holdout_rows") or [])
    fitted = audit.get("final_fitted") or {}
    params = ((fitted.get("checkpoints") or {}).get(CHECKPOINT) or {})
    if len(rows) < MIN_FINAL_STATES:
        return {"ready": False, "error": "insufficient fresh Q4 holdout states"}

    base_evals = []
    cand_evals = []
    convergence_failures = []
    runtime = 0.0
    details = []
    for row in rows:
        state = row["state"]
        truth = row["truth"]
        base_projection = row["projection"]
        cand_projection = cal.calibrated_projection(row, fitted)
        br = model.simulate_5m(state, base_projection, [])
        cr = model.simulate_5m(state, cand_projection, [])
        runtime += float(br.get("runtime_seconds") or 0.0) + float(cr.get("runtime_seconds") or 0.0)
        if str(br.get("convergence") or "") != "PASS":
            convergence_failures.append(f"BASE {row['event_id']} {CHECKPOINT}")
        if str(cr.get("convergence") or "") != "PASS":
            convergence_failures.append(f"CAND {row['event_id']} {CHECKPOINT}")
        be = replay.evaluate_holdout(br, truth)
        ce = replay.evaluate_holdout(cr, truth)
        base_evals.append(be)
        cand_evals.append(ce)
        details.append({
            "event_id": row.get("event_id"),
            "game_date": row.get("game_date"),
            "away_team": row.get("away_team"),
            "home_team": row.get("home_team"),
            "baseline": be,
            "candidate": ce,
            "base_convergence": br.get("convergence"),
            "candidate_convergence": cr.get("convergence"),
        })

    base = _metrics_from_evals(base_evals)
    cand = _metrics_from_evals(cand_evals)
    contract = _five_m_contract(base, cand, len(rows), params, convergence_failures)
    return {
        "model_version": MODEL_VERSION,
        "ready": True,
        "validation_states": len(rows),
        "simulations_per_state_per_model": model.SIMULATIONS,
        "total_simulations": len(rows) * model.SIMULATIONS * 2,
        "baseline": base,
        "candidate": cand,
        "contract": contract,
        "convergence_failures": convergence_failures,
        "runtime_seconds": runtime,
        "details": details,
        "paired_deterministic_seeds": True,
        "halftime_policy": "FROZEN AT PRODUCTION V1",
        "candidate_promoted": False,
    }


def clear_cache():
    try:
        q4_dataset.clear()
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
