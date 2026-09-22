"""Kyre Sports AI — NFL Moneyline V4.3.1 Step-4C runtime repair.

Repairs V4.3's calibration runtime without changing Steps 1-4B or the intended
Step-4C statistical design.

Repairs:
- normalize historical calibration timestamps to UTC before comparisons;
- avoid implicit NumPy ndarray -> Python scalar conversion;
- make calibration diagnostics formatting type-safe;
- isolate Step-4C runtime failures so the Moneyline page fails closed instead of
  crashing the entire NFL route.

The historical design remains 2024 train -> 2025 chronological holdout -> final
2024-25 refit. Sportsbook prices, Monte Carlo, no-vig edge/EV and final grading
remain OFF. Preseason Step 3 remains the final-output safety gate.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v43 as v43

MODEL_VERSION = "NFL MONEYLINE V4.3.1 • STEP 4C RUNTIME + UTC REPAIR"


def _safe(value, default="") -> str:
    try:
        text = str(value if value is not None else "").strip()
    except Exception:
        text = ""
    return text or default


def _num(value):
    try:
        return float(value)
    except Exception:
        return np.nan


def _utc_series(values) -> pd.Series:
    """Return a UTC-normalized datetime Series; invalid values become NaT."""
    return pd.to_datetime(values, utc=True, errors="coerce")


def _utc_timestamp(value):
    """Return a UTC Timestamp or NaT without tz-naive/tz-aware ambiguity."""
    try:
        return pd.to_datetime(value, utc=True, errors="coerce")
    except Exception:
        return pd.NaT


def _team_rows_utc(frame: pd.DataFrame, abbr: str, before=None) -> pd.DataFrame:
    """V4.3 team filter with explicit UTC normalization before comparisons."""
    if frame is None or frame.empty or "team_abbr" not in frame.columns:
        return pd.DataFrame()

    mask = frame["team_abbr"].astype(str).str.upper() == _safe(abbr).upper()
    out = frame.loc[mask].copy()
    if out.empty:
        return out.reset_index(drop=True)

    if "date" not in out.columns:
        return pd.DataFrame()

    dates = _utc_series(out["date"])
    valid = dates.notna()
    out = out.loc[valid].copy()
    dates = dates.loc[valid]

    if before is not None:
        cutoff = _utc_timestamp(before)
        if pd.isna(cutoff):
            return pd.DataFrame()
        keep = dates < cutoff
        out = out.loc[keep].copy()
        dates = dates.loc[keep]

    if out.empty:
        return out.reset_index(drop=True)

    out["date"] = dates
    return out.sort_values("date").reset_index(drop=True)


def _unique_games_utc(league: pd.DataFrame) -> pd.DataFrame:
    """Build one row per completed away/home game with UTC-safe kickoff values."""
    if league is None or league.empty or "game_id" not in league.columns:
        return pd.DataFrame()

    rows = []
    for game_id, group in league.groupby("game_id", sort=False):
        if len(group) < 2 or "home_away" not in group.columns:
            continue
        away = group[group["home_away"].astype(str).str.lower() == "away"]
        home = group[group["home_away"].astype(str).str.lower() == "home"]
        if away.empty or home.empty:
            continue

        a = away.iloc[0]
        h = home.iloc[0]
        result = _safe(a.get("result")).upper()
        if result not in {"W", "L"}:
            continue

        kickoff = _utc_timestamp(a.get("date"))
        if pd.isna(kickoff):
            continue

        away_abbr = _safe(a.get("team_abbr")).upper()
        home_abbr = _safe(h.get("team_abbr")).upper()
        if not away_abbr or not home_abbr:
            continue

        rows.append({
            "game_id": _safe(game_id),
            "date": kickoff,
            "away_abbr": away_abbr,
            "home_abbr": home_abbr,
            "away_win": 1.0 if result == "W" else 0.0,
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out["date"] = _utc_series(out["date"])
        out = out.dropna(subset=["date"]).sort_values(["date", "game_id"]).reset_index(drop=True)
    return out


def _scalar(value, default=np.nan) -> float:
    """Extract exactly one numeric scalar from NumPy/Pandas output safely."""
    try:
        arr = np.asarray(value, dtype=float).reshape(-1)
        if arr.size != 1:
            return float(default)
        val = float(arr[0])
        return val if np.isfinite(val) else float(default)
    except Exception:
        return float(default)


def _probability_with_interval_safe(x: np.ndarray, model: dict):
    beta = np.asarray(model.get("beta"), dtype=float).reshape(-1)
    scales = np.asarray(model.get("scales"), dtype=float).reshape(-1)
    covariance = np.asarray(model.get("covariance"), dtype=float)
    x = np.asarray(x, dtype=float)

    if x.ndim == 1:
        x = x.reshape(1, -1)
    if x.shape[0] != 1 or x.shape[1] != beta.size or scales.size != beta.size:
        raise ValueError("Step 4C feature/coefficient shape mismatch")
    if covariance.shape != (beta.size, beta.size):
        raise ValueError("Step 4C covariance shape mismatch")

    safe_scales = np.where(np.isfinite(scales) & (np.abs(scales) > 1e-12), scales, 1.0)
    xs = x / safe_scales

    logit = _scalar(xs @ beta)
    if not np.isfinite(logit):
        raise ValueError("Step 4C produced a non-finite logit")

    raw = _scalar(v43._sigmoid(logit))
    p = float(np.clip(raw, v43.PROB_FLOOR, v43.PROB_CEILING))

    quad = _scalar(xs @ covariance @ xs.T, default=0.0)
    var_logit = max(quad if np.isfinite(quad) else 0.0, 0.0)
    se = float(math.sqrt(var_logit))

    lo_raw = _scalar(v43._sigmoid(logit - 1.96 * se))
    hi_raw = _scalar(v43._sigmoid(logit + 1.96 * se))
    lo = float(np.clip(lo_raw, v43.PROB_FLOOR, v43.PROB_CEILING))
    hi = float(np.clip(hi_raw, v43.PROB_FLOOR, v43.PROB_CEILING))
    return p, lo, hi, raw


def _safe_metric_text(value, digits=3) -> str:
    n = _num(value)
    return f"{n:.{digits}f}" if np.isfinite(n) else "—"


def _render_model_diagnostics_safe(model: dict):
    validation = model.get("validation") or {}
    with st.expander("📊 Step 4C calibration diagnostics", expanded=False):
        rows = [
            {"Diagnostic": "Calibration seasons", "Value": "2024-2025 regular season"},
            {"Diagnostic": "Chronological train", "Value": f"2024 • {int(_num(model.get('train_rows')) if np.isfinite(_num(model.get('train_rows'))) else 0)} games"},
            {"Diagnostic": "Holdout validation", "Value": f"2025 • {int(_num(model.get('valid_rows')) if np.isfinite(_num(model.get('valid_rows'))) else 0)} games"},
            {"Diagnostic": "Final fit sample", "Value": f"{int(_num(model.get('rows')) if np.isfinite(_num(model.get('rows'))) else 0)} games"},
            {"Diagnostic": "Holdout Brier score", "Value": _safe_metric_text(validation.get("brier"))},
            {"Diagnostic": "Holdout log loss", "Value": _safe_metric_text(validation.get("logloss"))},
            {"Diagnostic": "Holdout calibration error", "Value": _safe_metric_text(validation.get("ece"))},
            {"Diagnostic": "Holdout accuracy", "Value": v43._fmt_pct(validation.get("accuracy"))},
            {"Diagnostic": "Calibration quality", "Value": _safe(model.get("quality"), "—")},
            {"Diagnostic": "Runtime repair", "Value": "UTC-normalized dates + explicit NumPy scalar extraction"},
            {"Diagnostic": "Probability caps", "Value": f"{v43.PROB_FLOOR:.0%} to {v43.PROB_CEILING:.0%}"},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            "Validation remains chronological: 2024 fits the holdout model and 2025 tests it. "
            "The final coefficients are refit on both seasons only after validation. No sportsbook odds are used."
        )


def _fit_calibration_model_safe():
    """Run V4.3 calibration with fail-closed diagnostics instead of page failure."""
    stage = "historical dataset"
    try:
        frame, diags = v43._calibration_dataset()
        if frame is None or frame.empty:
            return {"ready": False, "error": "historical calibration dataset is empty", "diags": diags, "runtime_stage": stage}

        required = {"season", "strength_gap", "scoring_gap", "recent_gap", "site_sign", "away_win"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            return {"ready": False, "error": f"calibration dataset missing columns: {', '.join(missing)}", "diags": diags, "runtime_stage": stage}

        clean = frame.copy()
        numeric_cols = ["season", "strength_gap", "scoring_gap", "recent_gap", "site_sign", "away_win"]
        for col in numeric_cols:
            clean[col] = pd.to_numeric(clean[col], errors="coerce")
        clean = clean.replace([np.inf, -np.inf], np.nan).dropna(subset=numeric_cols).reset_index(drop=True)

        train = clean[clean["season"] < v43.HOLDOUT_SEASON].copy()
        valid = clean[clean["season"] == v43.HOLDOUT_SEASON].copy()
        if len(train) < v43.MIN_TRAIN_GAMES or len(valid) < v43.MIN_VALID_GAMES:
            return {
                "ready": False,
                "error": f"insufficient chronological calibration sample (train={len(train)}, validation={len(valid)})",
                "rows": int(len(clean)),
                "train_rows": int(len(train)),
                "valid_rows": int(len(valid)),
                "diags": diags,
                "runtime_stage": "sample guard",
            }

        stage = "2024 holdout fit"
        Xtr, ytr, cols = v43._matrix(train)
        Xva, yva, _ = v43._matrix(valid)
        scales = v43._scales_from(Xtr)
        beta_train, _, converged_train = v43._fit_ridge_logistic(Xtr, ytr, scales)
        pva = v43._predict(Xva, beta_train, scales, cap=True)
        validation = v43._metrics(yva, pva)

        stage = "2024-25 final refit"
        Xall, yall, _ = v43._matrix(clean)
        final_scales = v43._scales_from(Xall)
        beta, covariance, converged_final = v43._fit_ridge_logistic(Xall, yall, final_scales)
        quality = v43._quality(validation, len(valid))

        arrays_ok = (
            np.all(np.isfinite(np.asarray(beta, dtype=float)))
            and np.all(np.isfinite(np.asarray(final_scales, dtype=float)))
            and np.all(np.isfinite(np.asarray(covariance, dtype=float)))
        )
        ready = bool(converged_train and converged_final and arrays_ok and quality != "LOW")

        return {
            "ready": ready,
            "fit_converged": bool(converged_train and converged_final),
            "quality": quality,
            "rows": int(len(clean)),
            "train_rows": int(len(train)),
            "valid_rows": int(len(valid)),
            "train_seasons": "2024",
            "validation_season": str(v43.HOLDOUT_SEASON),
            "feature_names": cols,
            "scales": np.asarray(final_scales, dtype=float),
            "beta": np.asarray(beta, dtype=float),
            "covariance": np.asarray(covariance, dtype=float),
            "validation": validation,
            "diags": diags,
            "runtime_stage": "complete",
            "error": "" if ready else (
                "validation quality did not pass minimum thresholds" if quality == "LOW" else "calibration fit did not converge cleanly"
            ),
        }
    except Exception as exc:
        # Do not let calibration take the page down. Keep the model fail-closed and
        # expose only the exception class + short message for repair diagnostics.
        message = _safe(exc, "unknown runtime error").replace("\n", " ")[:240]
        return {
            "ready": False,
            "error": f"runtime guard at {stage}: {type(exc).__name__}: {message}",
            "runtime_stage": stage,
            "runtime_exception": type(exc).__name__,
        }


# Patch only V4.3's runtime seams. Statistical design and earlier steps remain intact.
v43._team_rows = _team_rows_utc
v43._unique_games = _unique_games_utc
v43._probability_with_interval = _probability_with_interval_safe
v43._render_model_diagnostics = _render_model_diagnostics_safe
v43._fit_calibration_model = st.cache_data(ttl=21600, show_spinner=False)(_fit_calibration_model_safe)


_ORIGINAL_STEP4C_RENDER = v43._render_step4c


def _render_step4c_fail_closed():
    try:
        return _ORIGINAL_STEP4C_RENDER()
    except Exception as exc:
        # Last-resort UI firewall: a Step-4C runtime problem must never blank the
        # working Steps 1-4B page.
        message = _safe(exc, "unknown Step 4C error").replace("\n", " ")[:260]
        st.warning(
            f"⚠️ STEP 4C CHECK • runtime firewall caught {type(exc).__name__}: {message}. "
            "No base probability is exposed; Steps 1-4B remain valid."
        )
        st.session_state["nfl_moneyline_v43_probability_ready"] = False
        st.session_state["nfl_moneyline_v431_runtime_error"] = {
            "type": type(exc).__name__,
            "message": message,
        }
        return False


v43._render_step4c = _render_step4c_fail_closed


def render_nfl_moneyline_hub():
    return v43.render_nfl_moneyline_hub()


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
