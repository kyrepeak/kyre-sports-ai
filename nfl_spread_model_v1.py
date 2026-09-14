"""NFL Spread Model V1 — market-independent fair-margin regression.

This module predicts the football scoring margin (away points - home points)
without sportsbook input. It reuses the certified NFL historical/team-strength
feature family and UTC-safe runtime repairs from the frozen Moneyline stack, but
fits a separate ridge linear model to actual score margins.

Design:
- 2024 regular season trains the chronological holdout model;
- 2025 regular season is the holdout validation set;
- final coefficients are refit on 2024-25 only after validation;
- every historical feature uses information available before kickoff;
- features: strength gap, offense/defense scoring interaction gap, recent-L6
  margin gap, and away-perspective site sign;
- sportsbook spread/price is never an input and is not imported here.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

# Import the certified repair layer first so nfl_moneyline_hub_v43's historical
# date/filter seams are UTC-safe before this module reuses them.
import nfl_moneyline_hub_v431 as repaired
import nfl_moneyline_hub_v41 as historical
import nfl_moneyline_hub_v42 as matchup
import nfl_moneyline_hub_v43 as calibrated
import nfl_moneyline_hub_v4 as strength

MODEL_VERSION = "NFL SPREAD MODEL V1 • MARKET-INDEPENDENT FAIR MARGIN"
CALIBRATION_SEASONS = (2024, 2025)
HOLDOUT_SEASON = 2025
RIDGE_L2 = 4.0
MIN_TRAIN_GAMES = 180
MIN_VALID_GAMES = 180
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
FEATURE_NAMES = ("strength_gap", "scoring_gap", "recent_gap", "site_sign")


def _safe(value: Any, default: str = "") -> str:
    try:
        text = str(value if value is not None else "").strip()
    except Exception:
        text = ""
    return text or default


def _num(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _unique_margin_games(league: pd.DataFrame) -> pd.DataFrame:
    """Return one UTC-safe row per completed game with actual away margin."""
    if league is None or league.empty or "game_id" not in league.columns:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for game_id, group in league.groupby("game_id", sort=False):
        if len(group) < 2 or "home_away" not in group.columns:
            continue
        away = group[group["home_away"].astype(str).str.lower() == "away"]
        home = group[group["home_away"].astype(str).str.lower() == "home"]
        if away.empty or home.empty:
            continue

        a = away.iloc[0]
        h = home.iloc[0]
        kickoff = repaired._utc_timestamp(a.get("date"))
        if pd.isna(kickoff):
            continue
        away_abbr = _safe(a.get("team_abbr")).upper()
        home_abbr = _safe(h.get("team_abbr")).upper()
        if not away_abbr or not home_abbr:
            continue

        margin = _num(a.get("margin"))
        if not np.isfinite(margin):
            away_pf = _num(a.get("pf"))
            home_pf = _num(h.get("pf"))
            if not np.isfinite(away_pf) or not np.isfinite(home_pf):
                continue
            margin = float(away_pf - home_pf)

        rows.append(
            {
                "game_id": _safe(game_id),
                "date": kickoff,
                "away_abbr": away_abbr,
                "home_abbr": home_abbr,
                "away_margin": float(margin),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["date"] = repaired._utc_series(out["date"])
        out = out.dropna(subset=["date"]).sort_values(["date", "game_id"]).reset_index(drop=True)
    return out


@st.cache_data(ttl=21600, show_spinner=False)
def _margin_dataset() -> tuple[pd.DataFrame, dict[int, dict]]:
    """Build leakage-safe 2024-25 margin rows using 2023 as the first prior."""
    seasons_needed = sorted({min(CALIBRATION_SEASONS) - 1, *CALIBRATION_SEASONS})
    leagues: dict[int, pd.DataFrame] = {}
    diags: dict[int, dict] = {}
    for season in seasons_needed:
        frame, diag = historical._league_regular_season_games(int(season))
        leagues[int(season)] = frame
        diags[int(season)] = diag

    rows: list[dict[str, Any]] = []
    for season in CALIBRATION_SEASONS:
        prior_league = leagues.get(int(season) - 1, pd.DataFrame())
        current_league = leagues.get(int(season), pd.DataFrame())
        games = _unique_margin_games(current_league)
        if prior_league.empty or games.empty:
            continue

        for _, game in games.iterrows():
            kickoff = repaired._utc_timestamp(game.get("date"))
            if pd.isna(kickoff):
                continue
            away_profile = calibrated._historical_profile(
                _safe(game.get("away_abbr")).upper(), prior_league, current_league, kickoff
            )
            home_profile = calibrated._historical_profile(
                _safe(game.get("home_abbr")).upper(), prior_league, current_league, kickoff
            )
            feat = calibrated._pregame_feature_row(away_profile, home_profile)
            if feat is None:
                continue
            rows.append(
                {
                    "season": int(season),
                    "game_id": _safe(game.get("game_id")),
                    "date": kickoff,
                    "away_abbr": _safe(game.get("away_abbr")).upper(),
                    "home_abbr": _safe(game.get("home_abbr")).upper(),
                    "away_margin": float(game.get("away_margin")),
                    **feat,
                }
            )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["date", "game_id"]).reset_index(drop=True)
    return frame, diags


def _matrix(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    X = frame[list(FEATURE_NAMES)].astype(float).to_numpy()
    y = frame["away_margin"].astype(float).to_numpy()
    return X, y


def _scales_from(X: np.ndarray) -> np.ndarray:
    scales = np.ones(X.shape[1], dtype=float)
    for j in range(min(3, X.shape[1])):
        s = float(np.nanstd(X[:, j]))
        scales[j] = s if np.isfinite(s) and s > 1e-6 else 1.0
    # site_sign remains on its natural -1/0/+1 scale.
    return scales


def _fit_ridge_linear(
    X: np.ndarray,
    y: np.ndarray,
    scales: np.ndarray,
    l2: float = RIDGE_L2,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Fit ridge margin regression and an approximate coefficient covariance."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1)
    scales = np.asarray(scales, dtype=float).reshape(-1)
    if X.ndim != 2 or X.shape[0] != y.size or X.shape[1] != scales.size:
        raise ValueError("Spread margin regression matrix shape mismatch")

    safe_scales = np.where(np.isfinite(scales) & (np.abs(scales) > 1e-12), scales, 1.0)
    Xs = X / safe_scales
    info = Xs.T @ Xs + float(l2) * np.eye(Xs.shape[1])
    rhs = Xs.T @ y
    try:
        beta = np.linalg.solve(info, rhs)
    except np.linalg.LinAlgError:
        beta = np.linalg.pinv(info) @ rhs

    fitted = Xs @ beta
    residuals = y - fitted
    dof = max(int(y.size - beta.size), 1)
    sigma2 = float(np.sum(residuals * residuals, dtype=np.float64) / dof)
    try:
        inv_info = np.linalg.inv(info)
    except np.linalg.LinAlgError:
        inv_info = np.linalg.pinv(info)
    covariance = sigma2 * inv_info
    return beta, covariance, residuals, float(math.sqrt(max(sigma2, 0.0)))


def _predict(X: np.ndarray, beta: np.ndarray, scales: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X.reshape(1, -1)
    beta = np.asarray(beta, dtype=float).reshape(-1)
    scales = np.asarray(scales, dtype=float).reshape(-1)
    safe_scales = np.where(np.isfinite(scales) & (np.abs(scales) > 1e-12), scales, 1.0)
    if X.shape[1] != beta.size or scales.size != beta.size:
        raise ValueError("Spread margin prediction feature/coefficient shape mismatch")
    return (X / safe_scales) @ beta


def _validation_metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    y = np.asarray(y, dtype=float).reshape(-1)
    pred = np.asarray(pred, dtype=float).reshape(-1)
    if y.size == 0 or y.size != pred.size:
        return {}
    err = pred - y
    mae = float(np.mean(np.abs(err)))
    rmse = float(math.sqrt(np.mean(err * err)))
    bias = float(np.mean(err))
    sign_accuracy = float(np.mean(np.sign(pred) == np.sign(y)))
    baseline_mae = float(np.mean(np.abs(y)))
    corr = float(np.corrcoef(y, pred)[0, 1]) if y.size > 2 and np.std(pred) > 1e-9 else 0.0
    return {
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "sign_accuracy": sign_accuracy,
        "baseline_zero_margin_mae": baseline_mae,
        "mae_improvement_vs_zero": float(baseline_mae - mae),
        "correlation": corr,
    }


def _quality(metrics: dict[str, float], n_valid: int) -> str:
    mae = _num(metrics.get("mae"))
    rmse = _num(metrics.get("rmse"))
    bias = abs(_num(metrics.get("bias")))
    sign = _num(metrics.get("sign_accuracy"))
    improvement = _num(metrics.get("mae_improvement_vs_zero"))
    if not all(np.isfinite(x) for x in (mae, rmse, bias, sign, improvement)):
        return "LOW"
    if n_valid >= 220 and mae <= 11.5 and rmse <= 15.0 and bias <= 2.0 and sign >= 0.58 and improvement > 0:
        return "HIGH"
    if n_valid >= 180 and mae <= 13.5 and rmse <= 17.5 and bias <= 3.5 and sign >= 0.52 and improvement >= -0.25:
        return "MEDIUM"
    return "LOW"


@st.cache_data(ttl=21600, show_spinner=False)
def fit_margin_model() -> dict[str, Any]:
    """Chronologically validate, then refit the final market-independent model."""
    stage = "historical margin dataset"
    try:
        frame, diags = _margin_dataset()
        if frame is None or frame.empty:
            return {"ready": False, "error": "historical margin dataset is empty", "runtime_stage": stage, "diags": diags}

        required = {"season", "away_margin", *FEATURE_NAMES}
        missing = sorted(required.difference(frame.columns))
        if missing:
            return {"ready": False, "error": f"margin dataset missing columns: {', '.join(missing)}", "runtime_stage": stage, "diags": diags}

        clean = frame.copy()
        numeric_cols = ["season", "away_margin", *FEATURE_NAMES]
        for col in numeric_cols:
            clean[col] = pd.to_numeric(clean[col], errors="coerce")
        clean = clean.replace([np.inf, -np.inf], np.nan).dropna(subset=numeric_cols).reset_index(drop=True)

        train = clean[clean["season"] < HOLDOUT_SEASON].copy()
        valid = clean[clean["season"] == HOLDOUT_SEASON].copy()
        if len(train) < MIN_TRAIN_GAMES or len(valid) < MIN_VALID_GAMES:
            return {
                "ready": False,
                "error": f"insufficient chronological margin sample (train={len(train)}, validation={len(valid)})",
                "rows": int(len(clean)),
                "train_rows": int(len(train)),
                "valid_rows": int(len(valid)),
                "runtime_stage": "sample guard",
                "diags": diags,
            }

        stage = "2024 holdout fit"
        Xtr, ytr = _matrix(train)
        Xva, yva = _matrix(valid)
        train_scales = _scales_from(Xtr)
        beta_train, _, _, _ = _fit_ridge_linear(Xtr, ytr, train_scales)
        pva = _predict(Xva, beta_train, train_scales)
        validation = _validation_metrics(yva, pva)

        stage = "2024-25 final refit"
        Xall, yall = _matrix(clean)
        final_scales = _scales_from(Xall)
        beta, covariance, residuals, residual_sd = _fit_ridge_linear(Xall, yall, final_scales)
        quality = _quality(validation, len(valid))

        arrays_ok = (
            np.all(np.isfinite(np.asarray(beta, dtype=float)))
            and np.all(np.isfinite(np.asarray(final_scales, dtype=float)))
            and np.all(np.isfinite(np.asarray(covariance, dtype=float)))
            and np.all(np.isfinite(np.asarray(residuals, dtype=float)))
            and np.isfinite(residual_sd)
        )
        ready = bool(arrays_ok and quality != "LOW" and len(residuals) >= 300)

        return {
            "ready": ready,
            "model_version": MODEL_VERSION,
            "quality": quality,
            "rows": int(len(clean)),
            "train_rows": int(len(train)),
            "valid_rows": int(len(valid)),
            "train_seasons": "2024",
            "validation_season": str(HOLDOUT_SEASON),
            "feature_names": list(FEATURE_NAMES),
            "scales": np.asarray(final_scales, dtype=float),
            "beta": np.asarray(beta, dtype=float),
            "covariance": np.asarray(covariance, dtype=float),
            "residuals": np.asarray(residuals, dtype=float),
            "residual_sd": float(residual_sd),
            "validation": validation,
            "sportsbook_projection_influence": 0.0,
            "sportsbook_inputs": [],
            "diags": diags,
            "runtime_stage": "complete",
            "error": "" if ready else (
                "holdout validation quality did not pass the minimum margin-model guard"
                if quality == "LOW"
                else "final margin-model arrays did not pass runtime guards"
            ),
        }
    except Exception as exc:
        message = _safe(exc, "unknown margin-model runtime error").replace("\n", " ")[:260]
        return {
            "ready": False,
            "model_version": MODEL_VERSION,
            "error": f"runtime guard at {stage}: {type(exc).__name__}: {message}",
            "runtime_stage": stage,
            "runtime_exception": type(exc).__name__,
            "sportsbook_projection_influence": 0.0,
            "sportsbook_inputs": [],
        }


def current_game_feature(game: dict[str, Any], day_str: str) -> dict[str, Any]:
    """Build the certified pregame football feature vector for one current game."""
    away_abbr = _safe(game.get("away_abbr")).upper()
    home_abbr = _safe(game.get("home_abbr")).upper()
    away_team = _safe(game.get("away_team"), away_abbr)
    home_team = _safe(game.get("home_team"), home_abbr)
    game_id = _safe(game.get("game_id"))
    if not away_abbr or not home_abbr or not game_id:
        return {"ready": False, "error": "verified game identity is incomplete"}

    away_profile = strength._team_profile(away_abbr, away_team, day_str)
    home_profile = strength._team_profile(home_abbr, home_team, day_str)
    sites, site_diag = matchup._site_context(day_str)
    feat = matchup._matchup_features(
        game,
        away_profile,
        home_profile,
        sites.get(game_id, {}),
    )
    x = calibrated._current_feature_vector(feat)
    if x is None or not feat.get("ready"):
        return {
            "ready": False,
            "error": _safe(feat.get("reason"), "current matchup feature vector is incomplete"),
            "feature": feat,
            "away_profile_quality": _safe(away_profile.get("quality"), "LOW"),
            "home_profile_quality": _safe(home_profile.get("quality"), "LOW"),
            "site_provider_ok": bool(site_diag.get("ok")),
        }

    return {
        "ready": True,
        "game_id": game_id,
        "x": np.asarray(x, dtype=float).reshape(-1),
        "feature": feat,
        "away_profile_quality": _safe(away_profile.get("quality"), "LOW"),
        "home_profile_quality": _safe(home_profile.get("quality"), "LOW"),
        "site_provider_ok": bool(site_diag.get("ok")),
        "sportsbook_projection_influence": 0.0,
    }


def predict_game_margin(
    game: dict[str, Any],
    day_str: str,
    fitted: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Predict away-minus-home scoring margin from football features only."""
    model = fitted or fit_margin_model()
    if not model.get("ready"):
        return {
            "ready": False,
            "error": _safe(model.get("error"), "margin model is not ready"),
            "model_quality": _safe(model.get("quality"), "LOW"),
            "sportsbook_projection_influence": 0.0,
        }

    current = current_game_feature(game, day_str)
    if not current.get("ready"):
        return {
            "ready": False,
            "error": _safe(current.get("error"), "current football features are not ready"),
            "model_quality": _safe(model.get("quality"), "LOW"),
            "current": current,
            "sportsbook_projection_influence": 0.0,
        }

    x = np.asarray(current["x"], dtype=float).reshape(1, -1)
    beta = np.asarray(model["beta"], dtype=float).reshape(-1)
    scales = np.asarray(model["scales"], dtype=float).reshape(-1)
    covariance = np.asarray(model["covariance"], dtype=float)
    margin = float(_predict(x, beta, scales)[0])

    safe_scales = np.where(np.isfinite(scales) & (np.abs(scales) > 1e-12), scales, 1.0)
    xs = x / safe_scales
    quad = float((xs @ covariance @ xs.T).reshape(-1)[0])
    parameter_se = float(math.sqrt(max(quad if np.isfinite(quad) else 0.0, 0.0)))

    return {
        "ready": True,
        "game_id": _safe(game.get("game_id")),
        "model_version": MODEL_VERSION,
        "model_quality": _safe(model.get("quality"), "LOW"),
        "projected_away_margin": margin,
        "projected_home_margin": -margin,
        "fair_away_spread": -margin,
        "fair_home_spread": margin,
        "parameter_se": parameter_se,
        "residual_sd": float(model.get("residual_sd") or np.nan),
        "x": np.asarray(current["x"], dtype=float),
        "feature": current.get("feature") or {},
        "away_profile_quality": current.get("away_profile_quality"),
        "home_profile_quality": current.get("home_profile_quality"),
        "site_provider_ok": current.get("site_provider_ok"),
        "sportsbook_projection_influence": 0.0,
        "sportsbook_inputs": [],
    }


__all__ = [
    "CALIBRATION_SEASONS",
    "FEATURE_NAMES",
    "HOLDOUT_SEASON",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_fit_ridge_linear",
    "_margin_dataset",
    "_predict",
    "_quality",
    "_unique_margin_games",
    "_validation_metrics",
    "current_game_feature",
    "fit_margin_model",
    "predict_game_margin",
]
