"""Calibration + final intelligence for MLB Matchup Intelligence V2 Step 12.

Step 12 is the final V2 layer. It consumes the raw Step 11 distribution, persists
that raw forecast into the repository's existing prediction-history schema, uses
only graded V2 raw forecasts for empirical calibration, shrinks weak-input models
toward a neutral hit baseline, and publishes final probabilities, confidence,
fair odds and a pure-probability grade.

No historical correction is fabricated. Until enough graded V2 Step 11 forecasts
exist, the empirical calibrator stays identity and the final confidence/grade are
explicitly cold-start capped while predictions accumulate.
"""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import history as prediction_history
import mlb_matchup_probability_v1 as raw_engine

ET = ZoneInfo("America/New_York")
RAW_MODEL_VERSION = "MLB_MATCHUP_V2_STEP11_RAW"
MIN_BACKTEST_GAMES = 30
STRONG_BACKTEST_GAMES = 100
MATURE_BACKTEST_GAMES = 250
MIN_BIN_GAMES = 12
CALIBRATION_PRIOR_STRENGTH = 40.0
CALIBRATION_BINS = (0.0, 0.55, 0.65, 0.75, 0.85, 0.95, 1.000001)
MAX_GLOBAL_CALIBRATION_SHIFT = 0.06


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _rate(value: Any) -> float | None:
    val = _finite(value)
    if val is None:
        return None
    if abs(val) > 1.0:
        val /= 100.0
    return _clamp(val, 0.0, 1.0)


def american_fair_odds(probability: Any) -> int | None:
    p = _rate(probability)
    if p is None or p <= 0.0 or p >= 1.0:
        return None
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _tail_probability(distribution: dict[Any, Any] | None, threshold: int) -> float | None:
    if not distribution:
        return None
    total = 0.0
    seen = False
    for key, value in distribution.items():
        try:
            hits = int(key)
            p = float(value)
        except Exception:
            continue
        if hits >= int(threshold):
            total += p
        seen = True
    return _clamp(total, 0.0, 1.0) if seen else None


def raw_tail_probability(raw_profile: dict[str, Any] | None, threshold: int) -> float | None:
    raw = raw_profile or {}
    if threshold == 1:
        return _rate(raw.get("p1_plus"))
    if threshold == 2:
        return _rate(raw.get("p2_plus"))
    return _tail_probability(raw.get("monte_carlo_distribution") or {}, threshold)


def prediction_record(raw_profile: dict[str, Any] | None) -> dict[str, Any] | None:
    """Translate an eligible raw Step 11 forecast into the existing history schema."""
    raw = raw_profile or {}
    if str(raw.get("probability_status") or "GATED") == "GATED":
        return None
    game_pk = int(_finite(raw.get("game_pk")) or 0)
    player_id = int(_finite(raw.get("player_id")) or 0)
    p1 = raw_tail_probability(raw, 1)
    p2 = raw_tail_probability(raw, 2)
    p3 = raw_tail_probability(raw, 3)
    if not game_pk or not player_id or p1 is None:
        return None

    now = datetime.now(ET)
    game_date = str(raw.get("game_date") or "")[:10]
    if game_date and game_date < now.strftime("%Y-%m-%d"):
        return None
    status = str(raw.get("game_status") or "Scheduled")
    if any(token in status.lower() for token in ("final", "postpon", "cancel", "suspend")):
        return None

    return {
        "prediction_key": f"{game_pk}:{player_id}:{RAW_MODEL_VERSION}",
        "scan_id": now.strftime("%Y%m%dT%H%M%S"),
        "created_at_et": now.isoformat(),
        "game_date": game_date or now.strftime("%Y-%m-%d"),
        "model_version": RAW_MODEL_VERSION,
        "source": "matchup_v2_step12",
        "rank": np.nan,
        "game_pk": game_pk,
        "player_id": player_id,
        "player_name": raw.get("player_name") or "Hitter",
        "team": raw.get("team"),
        "opponent": raw.get("opponent"),
        "starter": raw.get("starter_name"),
        "lineup_position": raw.get("slot"),
        "expected_ab": raw.get("expected_ab"),
        "predicted_p1": p1,
        "predicted_p2": p2,
        "predicted_p3": p3,
        "expected_hits": raw.get("expected_hits"),
        "fair_odds": american_fair_odds(p1),
        "confidence": np.nan,
        "data_score": raw.get("composite_data_score"),
        "simulations": raw.get("simulations"),
        "seed": raw.get("random_seed"),
        "scenario_low": np.nan,
        "scenario_high": np.nan,
        "game_status": status,
        "grade_status": "PENDING",
        "actual_ab": np.nan,
        "actual_pa": np.nan,
        "actual_hits": np.nan,
        "actual_1plus": np.nan,
        "graded_at_et": np.nan,
    }


def persist_raw_prediction(raw_profile: dict[str, Any] | None) -> dict[str, Any]:
    record = prediction_record(raw_profile)
    if record is None:
        return {"status": "SKIPPED", "added": 0, "total": len(prediction_history.load_history())}
    try:
        added, total = prediction_history.append_prediction_records([record])
        return {"status": "SAVED" if added else "ALREADY_SAVED", "added": int(added), "total": int(total)}
    except Exception as exc:
        return {"status": "ERROR", "added": 0, "total": 0, "error": type(exc).__name__}


def load_v2_graded_history(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return only graded forecasts created by this exact raw V2 model version."""
    if frame is None:
        try:
            out = prediction_history.graded_history()
        except Exception:
            return pd.DataFrame()
    else:
        out = frame.copy()
        if "grade_status" in out.columns:
            out = out[out["grade_status"].astype(str).eq("GRADED")].copy()
    if out is None or out.empty or "model_version" not in out.columns:
        return pd.DataFrame()
    out = out[out["model_version"].astype(str).eq(RAW_MODEL_VERSION)].copy()
    for column in ("predicted_p1", "predicted_p2", "predicted_p3", "actual_hits", "actual_1plus"):
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def _pav(values: list[float], weights: list[float]) -> list[float]:
    """Small weighted pool-adjacent-violators implementation for monotone anchors."""
    if not values:
        return []
    blocks = [{"value": float(v), "weight": max(float(w), 1e-9), "count": 1} for v, w in zip(values, weights)]
    index = 0
    while index < len(blocks) - 1:
        if blocks[index]["value"] <= blocks[index + 1]["value"] + 1e-12:
            index += 1
            continue
        left = blocks[index]
        right = blocks[index + 1]
        weight = left["weight"] + right["weight"]
        value = (left["value"] * left["weight"] + right["value"] * right["weight"]) / weight
        merged = {"value": value, "weight": weight, "count": left["count"] + right["count"]}
        blocks[index:index + 2] = [merged]
        index = max(0, index - 1)
    expanded: list[float] = []
    for block in blocks:
        expanded.extend([float(block["value"])] * int(block["count"]))
    return expanded


def _target_arrays(records: pd.DataFrame, threshold: int) -> tuple[np.ndarray, np.ndarray]:
    probability_column = {1: "predicted_p1", 2: "predicted_p2", 3: "predicted_p3"}[int(threshold)]
    if records is None or records.empty or probability_column not in records.columns:
        return np.array([], dtype=float), np.array([], dtype=float)
    p = pd.to_numeric(records[probability_column], errors="coerce")
    if threshold == 1 and "actual_1plus" in records.columns:
        y = pd.to_numeric(records["actual_1plus"], errors="coerce")
    elif "actual_hits" in records.columns:
        hits = pd.to_numeric(records["actual_hits"], errors="coerce")
        y = (hits >= threshold).astype(float).where(hits.notna(), np.nan)
    else:
        y = pd.Series(np.nan, index=records.index)
    valid = p.notna() & y.notna()
    return p.loc[valid].clip(1e-6, 1 - 1e-6).to_numpy(float), y.loc[valid].to_numpy(float)


def fit_empirical_calibrator(records: pd.DataFrame | None, threshold: int = 1) -> dict[str, Any]:
    """Fit a conservative monotone empirical calibrator from graded V2 forecasts."""
    p, y = _target_arrays(records if records is not None else pd.DataFrame(), threshold)
    n = int(len(p))
    if n == 0:
        return {
            "status": "COLD_START",
            "threshold": int(threshold),
            "n": 0,
            "anchors": [],
            "global_gap": 0.0,
            "avg_prediction": None,
            "actual_rate": None,
            "raw_brier": None,
            "calibrated_brier": None,
        }

    avg_prediction = float(np.mean(p))
    actual_rate = float(np.mean(y))
    raw_brier = float(np.mean((p - y) ** 2))
    posterior_rate = (
        float(np.sum(y)) + CALIBRATION_PRIOR_STRENGTH * avg_prediction
    ) / (n + CALIBRATION_PRIOR_STRENGTH)
    global_gap = _clamp(posterior_rate - avg_prediction, -MAX_GLOBAL_CALIBRATION_SHIFT, MAX_GLOBAL_CALIBRATION_SHIFT)

    anchors: list[dict[str, Any]] = []
    for low, high in zip(CALIBRATION_BINS[:-1], CALIBRATION_BINS[1:]):
        mask = (p >= low) & (p < high)
        count = int(mask.sum())
        if count < MIN_BIN_GAMES:
            continue
        bp = p[mask]
        by = y[mask]
        mean_p = float(np.mean(bp))
        posterior = (
            float(np.sum(by)) + CALIBRATION_PRIOR_STRENGTH * mean_p
        ) / (count + CALIBRATION_PRIOR_STRENGTH)
        anchors.append({"x": mean_p, "y": _clamp(posterior, 0.01, 0.99), "n": count})

    if anchors:
        anchors.sort(key=lambda row: row["x"])
        monotone = _pav([row["y"] for row in anchors], [row["n"] for row in anchors])
        for row, value in zip(anchors, monotone):
            row["y"] = _clamp(value, 0.01, 0.99)

    if n < MIN_BACKTEST_GAMES:
        status = "COLD_START"
    elif n < STRONG_BACKTEST_GAMES:
        status = "WARMUP"
    elif n < MATURE_BACKTEST_GAMES:
        status = "STRONG"
    else:
        status = "MATURE"

    fit = {
        "status": status,
        "threshold": int(threshold),
        "n": n,
        "anchors": anchors,
        "global_gap": global_gap,
        "avg_prediction": avg_prediction,
        "actual_rate": actual_rate,
        "raw_brier": raw_brier,
        "calibrated_brier": None,
    }
    calibrated = np.array([apply_empirical_calibrator(value, fit) for value in p], dtype=float)
    fit["calibrated_brier"] = float(np.mean((calibrated - y) ** 2)) if len(calibrated) else None
    return fit


def apply_empirical_calibrator(probability: Any, fit: dict[str, Any] | None) -> float | None:
    p = _rate(probability)
    if p is None:
        return None
    fit = fit or {}
    if int(fit.get("n") or 0) < MIN_BACKTEST_GAMES:
        return p
    anchors = list(fit.get("anchors") or [])
    if len(anchors) >= 2:
        xs = np.array([float(row["x"]) for row in anchors], dtype=float)
        ys = np.array([float(row["y"]) for row in anchors], dtype=float)
        return _clamp(float(np.interp(p, xs, ys, left=ys[0], right=ys[-1])), 0.01, 0.99)
    return _clamp(p + float(fit.get("global_gap") or 0.0), 0.01, 0.99)


def neutral_distribution(raw_profile: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw_profile or {}
    base = _rate(raw.get("base_hit_per_pa"))
    starter_pa = _finite(raw.get("starter_pa"))
    bullpen_pa = _finite(raw.get("bullpen_pa"))
    if base is None or starter_pa is None or bullpen_pa is None:
        return {}
    dist = raw_engine.analytical_distribution(starter_pa, bullpen_pa, base, base)
    distribution = dist.get("distribution") or {}
    return {
        **dist,
        "p3_plus": _tail_probability(distribution, 3),
    }


def reliability_weight(raw_profile: dict[str, Any] | None) -> dict[str, float]:
    """Shrink weak-input probabilities toward the neutral event baseline, never zero."""
    raw = raw_profile or {}
    data_score = _clamp(_finite(raw.get("composite_data_score")) or 0.0, 0.0, 100.0)
    normalized = _clamp((data_score - raw_engine.MIN_COMPOSITE_DATA_SCORE) / (100.0 - raw_engine.MIN_COMPOSITE_DATA_SCORE), 0.0, 1.0)
    weight = 0.55 + 0.45 * normalized
    if bool(raw.get("projected")) and not bool(raw.get("confirmed")):
        weight *= 0.90
    if not bool(raw.get("monte_carlo_converged")):
        weight *= 0.94
    if str(raw.get("probability_status") or "") == "PROVISIONAL_RAW":
        weight *= 0.96
    weight = _clamp(weight, 0.45, 1.0)
    return {"weight": weight, "missing_data_penalty": 1.0 - weight, "data_score": data_score}


def _calibration_maturity(n: int) -> float:
    count = max(0, int(n or 0))
    if count < MIN_BACKTEST_GAMES:
        return 0.0
    if count < STRONG_BACKTEST_GAMES:
        return 0.35 + 0.35 * (count - MIN_BACKTEST_GAMES) / (STRONG_BACKTEST_GAMES - MIN_BACKTEST_GAMES)
    if count < MATURE_BACKTEST_GAMES:
        return 0.70 + 0.30 * (count - STRONG_BACKTEST_GAMES) / (MATURE_BACKTEST_GAMES - STRONG_BACKTEST_GAMES)
    return 1.0


def final_confidence(raw_profile: dict[str, Any] | None, p1_fit: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw_profile or {}
    fit = p1_fit or {}
    data_score = _clamp(_finite(raw.get("composite_data_score")) or 0.0, 0.0, 100.0)
    data_points = 40.0 * data_score / 100.0
    if bool(raw.get("confirmed")):
        lineup_points = 15.0
    elif bool(raw.get("projected")):
        lineup_points = 10.0
    else:
        lineup_points = 5.0
    mc_points = 10.0 if bool(raw.get("monte_carlo_converged")) else 5.0

    sigma_values = [
        _finite(raw.get("starter_probability_sigma")),
        _finite(raw.get("bullpen_probability_sigma")),
    ]
    sigma_values = [value for value in sigma_values if value is not None]
    mean_sigma = sum(sigma_values) / len(sigma_values) if sigma_values else 0.30
    uncertainty_points = 10.0 * (1.0 - _clamp((mean_sigma - 0.10) / 0.32, 0.0, 1.0))

    maturity = _calibration_maturity(int(fit.get("n") or 0))
    calibration_points = 20.0 * maturity
    brier = _finite(fit.get("calibrated_brier"))
    if brier is None:
        backtest_points = 0.0
    elif brier <= 0.18:
        backtest_points = 5.0
    elif brier <= 0.22:
        backtest_points = 4.0
    elif brier <= 0.25:
        backtest_points = 3.0
    else:
        backtest_points = 1.0

    score = int(round(_clamp(data_points + lineup_points + mc_points + uncertainty_points + calibration_points + backtest_points, 0.0, 100.0)))
    if score >= 90:
        label = "ELITE CONFIDENCE"
    elif score >= 80:
        label = "HIGH CONFIDENCE"
    elif score >= 70:
        label = "STRONG CONFIDENCE"
    elif score >= 60:
        label = "MODERATE CONFIDENCE"
    elif score >= 50:
        label = "CAUTIOUS CONFIDENCE"
    else:
        label = "LOW CONFIDENCE"
    return {
        "score": score,
        "label": label,
        "mean_probability_sigma": mean_sigma,
        "components": {
            "Step 2-10 data": (data_points, 40.0),
            "Lineup certainty": (lineup_points, 15.0),
            "Monte Carlo convergence": (mc_points, 10.0),
            "Structural uncertainty": (uncertainty_points, 10.0),
            "V2 calibration maturity": (calibration_points, 20.0),
            "Backtest quality": (backtest_points, 5.0),
        },
    }


def probability_grade(probability: Any, confidence: Any, calibration_status: str) -> str:
    p = _rate(probability) or 0.0
    c = _finite(confidence) or 0.0
    if p >= 0.80 and c >= 85:
        grade = "A+"
    elif p >= 0.75 and c >= 80:
        grade = "A"
    elif p >= 0.70 and c >= 75:
        grade = "A-"
    elif p >= 0.66 and c >= 70:
        grade = "B+"
    elif p >= 0.62 and c >= 65:
        grade = "B"
    elif p >= 0.58 and c >= 60:
        grade = "B-"
    elif p >= 0.54 and c >= 55:
        grade = "C+"
    elif p >= 0.50:
        grade = "C"
    else:
        grade = "D"

    order = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D"]
    cap = "B+" if calibration_status == "COLD_START" else "A-" if calibration_status == "WARMUP" else None
    if cap is not None and order.index(grade) < order.index(cap):
        grade = cap
    return grade


def _reliability_interval(p1: float, raw_profile: dict[str, Any], calibration_status: str) -> tuple[float, float, float]:
    data_score = _clamp(_finite(raw_profile.get("composite_data_score")) or 0.0, 0.0, 100.0)
    width = 0.020 + (1.0 - data_score / 100.0) * 0.080
    if bool(raw_profile.get("projected")) and not bool(raw_profile.get("confirmed")):
        width += 0.020
    if not bool(raw_profile.get("monte_carlo_converged")):
        width += 0.010
    if calibration_status == "COLD_START":
        width += 0.020
    elif calibration_status == "WARMUP":
        width += 0.010
    width = _clamp(width, 0.020, 0.120)
    return _clamp(p1 - width, 0.01, 0.99), _clamp(p1 + width, 0.01, 0.99), width


def build_final_intelligence(
    raw_profile: dict[str, Any] | None,
    backtest_records: pd.DataFrame | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Finalize raw Step 11 output without inventing unavailable empirical history."""
    raw = raw_profile or {}
    if not raw or str(raw.get("probability_status") or "GATED") == "GATED":
        return {
            **raw,
            "final_status": "GATED",
            "final_p0": None,
            "final_p1_plus": None,
            "final_p2_plus": None,
            "final_expected_hits": None,
            "final_confidence": 0,
            "final_confidence_label": "LOW CONFIDENCE",
            "final_grade": "D",
            "final_fair_odds_1_plus": None,
            "calibration_status_step12": "GATED",
            "calibration_sample": 0,
            "history_persistence_status": "SKIPPED",
        }

    persistence = persist_raw_prediction(raw) if persist else {"status": "DISABLED", "added": 0, "total": 0}
    records = load_v2_graded_history(backtest_records)
    p1_fit = fit_empirical_calibrator(records, 1)
    p2_fit = fit_empirical_calibrator(records, 2)
    p3_fit = fit_empirical_calibrator(records, 3)

    raw_p1 = raw_tail_probability(raw, 1)
    raw_p2 = raw_tail_probability(raw, 2)
    raw_p3 = raw_tail_probability(raw, 3)
    if raw_p1 is None or raw_p2 is None:
        return {**raw, "final_status": "GATED", "calibration_status_step12": "GATED", "history_persistence_status": persistence.get("status")}

    empirical_p1 = apply_empirical_calibrator(raw_p1, p1_fit) or raw_p1
    empirical_p2 = apply_empirical_calibrator(raw_p2, p2_fit) or raw_p2
    empirical_p3 = apply_empirical_calibrator(raw_p3, p3_fit) if raw_p3 is not None else None

    neutral = neutral_distribution(raw)
    neutral_p1 = _rate(neutral.get("p1_plus"))
    neutral_p2 = _rate(neutral.get("p2_plus"))
    neutral_p3 = _rate(neutral.get("p3_plus"))
    reliability = reliability_weight(raw)
    weight = reliability["weight"]

    final_p1 = empirical_p1 if neutral_p1 is None else neutral_p1 + weight * (empirical_p1 - neutral_p1)
    final_p2 = empirical_p2 if neutral_p2 is None else neutral_p2 + weight * (empirical_p2 - neutral_p2)
    if empirical_p3 is None:
        final_p3 = neutral_p3 if neutral_p3 is not None else 0.0
    else:
        final_p3 = empirical_p3 if neutral_p3 is None else neutral_p3 + weight * (empirical_p3 - neutral_p3)

    final_p1 = _clamp(final_p1, 0.01, 0.99)
    final_p2 = _clamp(final_p2, 0.0, final_p1)
    final_p3 = _clamp(final_p3, 0.0, final_p2)
    final_p0 = 1.0 - final_p1
    final_exactly_1 = final_p1 - final_p2

    correction_ratios = []
    for raw_value, final_value, component_weight in (
        (raw_p1, final_p1, 0.60),
        (raw_p2, final_p2, 0.30),
        (raw_p3, final_p3, 0.10),
    ):
        if raw_value is not None and raw_value >= 0.02:
            correction_ratios.append((final_value / raw_value, component_weight))
    denominator = sum(component_weight for _, component_weight in correction_ratios)
    factor = (
        sum(ratio * component_weight for ratio, component_weight in correction_ratios) / denominator
        if denominator > 0 else 1.0
    )
    factor = _clamp(factor, 0.85, 1.15)
    raw_expected_hits = _finite(raw.get("expected_hits"))
    final_expected_hits = raw_expected_hits * factor if raw_expected_hits is not None else None

    confidence = final_confidence(raw, p1_fit)
    calibration_status = str(p1_fit.get("status") or "COLD_START")
    grade = probability_grade(final_p1, confidence.get("score"), calibration_status)
    low, high, interval_width = _reliability_interval(final_p1, raw, calibration_status)

    exact_buckets = {
        0: final_p0,
        1: final_exactly_1,
        2: final_p2 - final_p3,
        3: final_p3,
    }
    cumulative = 0.0
    median_hits = 3
    for hits in range(4):
        cumulative += exact_buckets[hits]
        if cumulative >= 0.50:
            median_hits = hits
            break
    mode_hits = max(exact_buckets, key=exact_buckets.get)

    if calibration_status == "COLD_START":
        final_status = "FINAL_PROVISIONAL_COLD_START"
        note = f"Fewer than {MIN_BACKTEST_GAMES} graded V2 raw forecasts; empirical correction is identity while V2 history accumulates."
    elif str(raw.get("probability_status")) == "PROVISIONAL_RAW":
        final_status = "FINAL_PROVISIONAL_INPUTS"
        note = "Empirical calibration is active, but current-game inputs remain provisional."
    else:
        final_status = "FINAL_CALIBRATED"
        note = "Empirical V2 backtest calibration and reliability shrinkage are active."

    return {
        **raw,
        "final_status": final_status,
        "calibration_status_step12": calibration_status,
        "calibration_note": note,
        "calibration_sample": int(p1_fit.get("n") or 0),
        "calibration_min_games": MIN_BACKTEST_GAMES,
        "calibration_strong_games": STRONG_BACKTEST_GAMES,
        "calibration_mature_games": MATURE_BACKTEST_GAMES,
        "calibration_anchors_p1": p1_fit.get("anchors") or [],
        "backtest_avg_prediction": p1_fit.get("avg_prediction"),
        "backtest_actual_hit_rate": p1_fit.get("actual_rate"),
        "backtest_brier_raw": p1_fit.get("raw_brier"),
        "backtest_brier_calibrated": p1_fit.get("calibrated_brier"),
        "empirical_p1_plus": empirical_p1,
        "empirical_p2_plus": empirical_p2,
        "empirical_p3_plus": empirical_p3,
        "neutral_p1_plus": neutral_p1,
        "neutral_p2_plus": neutral_p2,
        "reliability_weight": weight,
        "missing_data_penalty": reliability.get("missing_data_penalty"),
        "final_p0": final_p0,
        "final_p1_plus": final_p1,
        "final_p2_plus": final_p2,
        "final_p3_plus": final_p3,
        "final_p_exactly_1": final_exactly_1,
        "final_expected_hits": final_expected_hits,
        "final_median_hits": median_hits,
        "final_mode_hits": mode_hits,
        "final_fair_odds_1_plus": american_fair_odds(final_p1),
        "final_fair_odds_2_plus": american_fair_odds(final_p2),
        "final_confidence": int(confidence.get("score") or 0),
        "final_confidence_label": confidence.get("label"),
        "final_confidence_components": confidence.get("components") or {},
        "final_grade": grade,
        "grade_basis": "Pure 1+ hit probability + model confidence; not sportsbook price/value.",
        "reliability_low": low,
        "reliability_high": high,
        "reliability_interval_width": interval_width,
        "empirical_calibration_delta": empirical_p1 - raw_p1,
        "reliability_delta": final_p1 - empirical_p1,
        "total_final_delta": final_p1 - raw_p1,
        "expected_hits_correction_factor": factor,
        "history_persistence_status": persistence.get("status"),
        "history_prediction_added": int(persistence.get("added") or 0),
        "history_prediction_total": int(persistence.get("total") or 0),
        "calibration_backtest_source": f"prediction_history.csv • exact model_version={RAW_MODEL_VERSION}",
    }


__all__ = [
    "CALIBRATION_BINS",
    "CALIBRATION_PRIOR_STRENGTH",
    "MATURE_BACKTEST_GAMES",
    "MIN_BACKTEST_GAMES",
    "MIN_BIN_GAMES",
    "RAW_MODEL_VERSION",
    "STRONG_BACKTEST_GAMES",
    "american_fair_odds",
    "apply_empirical_calibrator",
    "build_final_intelligence",
    "final_confidence",
    "fit_empirical_calibrator",
    "load_v2_graded_history",
    "neutral_distribution",
    "persist_raw_prediction",
    "prediction_record",
    "probability_grade",
    "raw_tail_probability",
    "reliability_weight",
]
