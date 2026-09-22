"""Kyre Sports AI — NFL Moneyline V4.3 Step-4C historical probability calibration.

Builds on V4.2 without changing Steps 1-4B. Step 4C calibrates the existing
pregame feature set against completed historical NFL regular-season outcomes.

Calibration design:
- calibration seasons: 2024 and 2025 regular seasons;
- 2025 is a chronological holdout for validation before the final fit;
- each historical game's features use only information available BEFORE kickoff;
- prior-season carryover + in-season shrinkage reuse the exact Step-4A helpers;
- features are the Step-4B concepts: strength gap, offense-vs-defense scoring
  interaction, recent-L6 gap, and home/away site sign;
- ridge logistic regression is implemented with NumPy (no sportsbook input);
- final operational probabilities are conservatively capped at 5%-95%;
- reported interval is model-parameter uncertainty, not an outcome guarantee.

The 2.0-point Step-4B structural home-field display input is NOT used as a fixed
probability coefficient. Historical outcomes learn the home-field log-odds term.

During preseason, a successful Step 4C probability remains a BASE MODEL output.
Step 3 game-plan/rotation integrity remains a separate final-output gate. No
sportsbook price, no-vig edge, EV, Monte Carlo, ranking or recommendation is
enabled by this module.
"""
from __future__ import annotations

from datetime import date
from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v1 as step1
import nfl_moneyline_hub_v4 as v4
import nfl_moneyline_hub_v41 as v41
import nfl_moneyline_hub_v42 as v42

MODEL_VERSION = "NFL MONEYLINE V4.3 • STEP 4C HISTORICAL P(WIN) CALIBRATION"
CALIBRATION_SEASONS = (2024, 2025)
HOLDOUT_SEASON = 2025
RIDGE_L2 = 2.0
PROB_FLOOR = 0.05
PROB_CEILING = 0.95
MIN_TRAIN_GAMES = 180
MIN_VALID_GAMES = 180


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _num(value):
    try:
        return float(value)
    except Exception:
        return np.nan


def _sigmoid(z):
    z = np.clip(np.asarray(z, dtype=float), -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))


def _clip_probability(p):
    return np.clip(np.asarray(p, dtype=float), PROB_FLOOR, PROB_CEILING)


def _team_rows(frame: pd.DataFrame, abbr: str, before=None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    mask = frame["team_abbr"].astype(str).str.upper() == _safe(abbr).upper()
    out = frame.loc[mask].copy()
    if before is not None and not out.empty:
        cutoff = pd.Timestamp(before)
        dates = pd.to_datetime(out["date"])
        if getattr(dates.dt, "tz", None) is not None and cutoff.tzinfo is None:
            cutoff = cutoff.tz_localize(foundation.ET)
        elif getattr(dates.dt, "tz", None) is None and cutoff.tzinfo is not None:
            cutoff = cutoff.tz_localize(None)
        out = out.loc[dates < cutoff].copy()
    return out.sort_values("date").reset_index(drop=True)


def _historical_profile(team_abbr: str, prior_league: pd.DataFrame, current_league: pd.DataFrame, before) -> dict:
    prior_games = _team_rows(prior_league, team_abbr)
    current_games = _team_rows(current_league, team_abbr, before=before)
    prior = v4._summarize_games(prior_games)
    current = v4._summarize_games(current_games)
    if int(prior.get("games") or 0) < 12:
        return {"ready": False}
    blended = v4._blend(prior, current)
    strength, parts = v4._strength_index(blended)
    needed = [strength, blended.get("ppg"), blended.get("papg"), blended.get("recent6_diff_pg")]
    if not all(np.isfinite(_num(x)) for x in needed):
        return {"ready": False}
    return {
        "ready": True,
        "strength_index": float(strength),
        "blended": blended,
        "components": parts,
    }


def _unique_games(league: pd.DataFrame) -> pd.DataFrame:
    """Convert V4.1's two-team-per-game league frame into one away/home row."""
    if league is None or league.empty:
        return pd.DataFrame()
    rows = []
    for game_id, group in league.groupby("game_id", sort=False):
        if len(group) < 2:
            continue
        away = group[group["home_away"].astype(str).str.lower() == "away"]
        home = group[group["home_away"].astype(str).str.lower() == "home"]
        if away.empty or home.empty:
            continue
        a = away.iloc[0]
        h = home.iloc[0]
        result = _safe(a.get("result")).upper()
        if result not in {"W", "L"}:  # ties excluded from binary calibration
            continue
        rows.append({
            "game_id": _safe(game_id),
            "date": pd.Timestamp(a.get("date")),
            "away_abbr": _safe(a.get("team_abbr")).upper(),
            "home_abbr": _safe(h.get("team_abbr")).upper(),
            "away_win": 1.0 if result == "W" else 0.0,
        })
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["date", "game_id"]).reset_index(drop=True)
    return frame


def _pregame_feature_row(away_profile: dict, home_profile: dict) -> dict | None:
    if not away_profile.get("ready") or not home_profile.get("ready"):
        return None
    ab = away_profile.get("blended") or {}
    hb = home_profile.get("blended") or {}
    vals = [
        away_profile.get("strength_index"), home_profile.get("strength_index"),
        ab.get("ppg"), ab.get("papg"), ab.get("recent6_diff_pg"),
        hb.get("ppg"), hb.get("papg"), hb.get("recent6_diff_pg"),
    ]
    if not all(np.isfinite(_num(x)) for x in vals):
        return None
    away_interaction = 0.5 * (float(ab["ppg"]) + float(hb["papg"]))
    home_interaction = 0.5 * (float(hb["ppg"]) + float(ab["papg"]))
    return {
        "strength_gap": float(away_profile["strength_index"] - home_profile["strength_index"]),
        "scoring_gap": float(away_interaction - home_interaction),
        "recent_gap": float(ab["recent6_diff_pg"] - hb["recent6_diff_pg"]),
        # Away-team perspective. A home-team perspective would negate every feature,
        # including this site sign, preserving exact complementary probabilities.
        "site_sign": -1.0,
    }


@st.cache_data(ttl=21600, show_spinner=False)
def _calibration_dataset():
    """Build leakage-safe historical rows for 2024-25 using 2023 as first prior."""
    seasons_needed = sorted(set([min(CALIBRATION_SEASONS) - 1, *CALIBRATION_SEASONS]))
    leagues = {}
    diags = {}
    for season in seasons_needed:
        frame, diag = v41._league_regular_season_games(int(season))
        leagues[int(season)] = frame
        diags[int(season)] = diag

    rows = []
    for season in CALIBRATION_SEASONS:
        prior_league = leagues.get(int(season) - 1, pd.DataFrame())
        current_league = leagues.get(int(season), pd.DataFrame())
        games = _unique_games(current_league)
        if prior_league.empty or games.empty:
            continue
        for _, game in games.iterrows():
            kickoff = pd.Timestamp(game["date"])
            away_profile = _historical_profile(game["away_abbr"], prior_league, current_league, kickoff)
            home_profile = _historical_profile(game["home_abbr"], prior_league, current_league, kickoff)
            feat = _pregame_feature_row(away_profile, home_profile)
            if feat is None:
                continue
            rows.append({
                "season": int(season),
                "game_id": _safe(game["game_id"]),
                "date": kickoff,
                "away_abbr": _safe(game["away_abbr"]),
                "home_abbr": _safe(game["home_abbr"]),
                "away_win": float(game["away_win"]),
                **feat,
            })

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["date", "game_id"]).reset_index(drop=True)
    return frame, diags


def _matrix(frame: pd.DataFrame):
    cols = ["strength_gap", "scoring_gap", "recent_gap", "site_sign"]
    X = frame[cols].astype(float).to_numpy()
    y = frame["away_win"].astype(float).to_numpy()
    return X, y, cols


def _scales_from(X: np.ndarray) -> np.ndarray:
    scales = np.ones(X.shape[1], dtype=float)
    for j in range(min(3, X.shape[1])):
        s = float(np.nanstd(X[:, j]))
        scales[j] = s if np.isfinite(s) and s > 1e-6 else 1.0
    # Site sign deliberately stays on its natural +/-1 scale.
    return scales


def _fit_ridge_logistic(X: np.ndarray, y: np.ndarray, scales: np.ndarray, l2: float = RIDGE_L2):
    Xs = X / scales
    beta = np.zeros(Xs.shape[1], dtype=float)
    converged = False
    for _ in range(100):
        p = _sigmoid(Xs @ beta)
        w = np.clip(p * (1.0 - p), 1e-6, None)
        grad = Xs.T @ (y - p) - float(l2) * beta
        info = Xs.T @ (Xs * w[:, None]) + float(l2) * np.eye(Xs.shape[1])
        try:
            step = np.linalg.solve(info, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.pinv(info) @ grad
        beta = beta + step
        if float(np.linalg.norm(step)) < 1e-7:
            converged = True
            break
    p = _sigmoid(Xs @ beta)
    w = np.clip(p * (1.0 - p), 1e-6, None)
    info = Xs.T @ (Xs * w[:, None]) + float(l2) * np.eye(Xs.shape[1])
    try:
        covariance = np.linalg.inv(info)
    except np.linalg.LinAlgError:
        covariance = np.linalg.pinv(info)
    return beta, covariance, converged


def _predict(X: np.ndarray, beta: np.ndarray, scales: np.ndarray, cap=True):
    raw = _sigmoid((X / scales) @ beta)
    return _clip_probability(raw) if cap else raw


def _metrics(y: np.ndarray, p: np.ndarray) -> dict:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, dtype=float)
    brier = float(np.mean((p - y) ** 2))
    logloss = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    accuracy = float(np.mean((p >= 0.5) == (y >= 0.5)))

    # Expected calibration error over five fixed probability bins.
    edges = np.linspace(0.0, 1.0, 6)
    ece = 0.0
    bins_used = 0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        n = int(mask.sum())
        if not n:
            continue
        bins_used += 1
        ece += (n / len(p)) * abs(float(p[mask].mean()) - float(y[mask].mean()))
    return {"brier": brier, "logloss": logloss, "accuracy": accuracy, "ece": float(ece), "bins": bins_used}


def _quality(metrics: dict, n_valid: int) -> str:
    if n_valid >= 220 and metrics.get("brier", 1) <= 0.235 and metrics.get("logloss", 9) <= 0.675 and metrics.get("ece", 1) <= 0.08:
        return "HIGH"
    if n_valid >= 180 and metrics.get("brier", 1) <= 0.255 and metrics.get("logloss", 9) <= 0.715 and metrics.get("ece", 1) <= 0.12:
        return "MEDIUM"
    return "LOW"


@st.cache_data(ttl=21600, show_spinner=False)
def _fit_calibration_model():
    frame, diags = _calibration_dataset()
    if frame.empty:
        return {"ready": False, "error": "historical calibration dataset is empty", "diags": diags}

    train = frame[frame["season"] < HOLDOUT_SEASON].copy()
    valid = frame[frame["season"] == HOLDOUT_SEASON].copy()
    if len(train) < MIN_TRAIN_GAMES or len(valid) < MIN_VALID_GAMES:
        return {
            "ready": False,
            "error": f"insufficient chronological calibration sample (train={len(train)}, validation={len(valid)})",
            "rows": int(len(frame)),
            "diags": diags,
        }

    Xtr, ytr, cols = _matrix(train)
    Xva, yva, _ = _matrix(valid)
    scales = _scales_from(Xtr)
    beta_train, _, converged_train = _fit_ridge_logistic(Xtr, ytr, scales)
    pva = _predict(Xva, beta_train, scales, cap=True)
    valid_metrics = _metrics(yva, pva)

    Xall, yall, _ = _matrix(frame)
    final_scales = _scales_from(Xall)
    beta, covariance, converged_final = _fit_ridge_logistic(Xall, yall, final_scales)
    quality = _quality(valid_metrics, len(valid))

    return {
        "ready": bool(converged_train and converged_final and quality != "LOW"),
        "fit_converged": bool(converged_train and converged_final),
        "quality": quality,
        "rows": int(len(frame)),
        "train_rows": int(len(train)),
        "valid_rows": int(len(valid)),
        "train_seasons": "2024",
        "validation_season": str(HOLDOUT_SEASON),
        "feature_names": cols,
        "scales": final_scales,
        "beta": beta,
        "covariance": covariance,
        "validation": valid_metrics,
        "diags": diags,
        "error": "" if quality != "LOW" else "validation quality did not pass minimum thresholds",
    }


def _current_feature_vector(feat: dict):
    vals = [feat.get("strength_gap"), feat.get("raw_scoring_margin"), feat.get("recent_gap")]
    if not all(np.isfinite(_num(x)) for x in vals) or not feat.get("site_verified"):
        return None
    site_sign = 0.0 if feat.get("neutral") is True else -1.0
    return np.asarray([[float(vals[0]), float(vals[1]), float(vals[2]), site_sign]], dtype=float)


def _probability_with_interval(x: np.ndarray, model: dict):
    beta = np.asarray(model["beta"], dtype=float)
    scales = np.asarray(model["scales"], dtype=float)
    covariance = np.asarray(model["covariance"], dtype=float)
    xs = x / scales
    logit = float(xs @ beta)
    raw = float(_sigmoid(logit))
    p = float(np.clip(raw, PROB_FLOOR, PROB_CEILING))
    var_logit = float(xs @ covariance @ xs.T)
    se = float(np.sqrt(max(var_logit, 0.0)))
    lo = float(np.clip(_sigmoid(logit - 1.96 * se), PROB_FLOOR, PROB_CEILING))
    hi = float(np.clip(_sigmoid(logit + 1.96 * se), PROB_FLOOR, PROB_CEILING))
    return p, lo, hi, raw


def _fmt_pct(value, digits=1):
    return "—" if not np.isfinite(_num(value)) else f"{100.0 * float(value):.{digits}f}%"


def _render_model_diagnostics(model: dict):
    v = model.get("validation") or {}
    with st.expander("📊 Step 4C calibration diagnostics", expanded=False):
        rows = [
            {"Diagnostic": "Calibration seasons", "Value": "2024-2025 regular season"},
            {"Diagnostic": "Chronological train", "Value": f"2024 • {model.get('train_rows', 0)} games"},
            {"Diagnostic": "Holdout validation", "Value": f"2025 • {model.get('valid_rows', 0)} games"},
            {"Diagnostic": "Final fit sample", "Value": f"{model.get('rows', 0)} games"},
            {"Diagnostic": "Holdout Brier score", "Value": f"{v.get('brier', np.nan):.3f}" if np.isfinite(_num(v.get('brier'))) else "—"},
            {"Diagnostic": "Holdout log loss", "Value": f"{v.get('logloss', np.nan):.3f}" if np.isfinite(_num(v.get('logloss'))) else "—"},
            {"Diagnostic": "Holdout calibration error", "Value": f"{v.get('ece', np.nan):.3f}" if np.isfinite(_num(v.get('ece'))) else "—"},
            {"Diagnostic": "Holdout accuracy", "Value": _fmt_pct(v.get('accuracy'))},
            {"Diagnostic": "Calibration quality", "Value": model.get("quality", "—")},
            {"Diagnostic": "Probability caps", "Value": f"{PROB_FLOOR:.0%} to {PROB_CEILING:.0%}"},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            "Validation is chronological: 2024 fits the holdout model and 2025 tests it. The final coefficients are then refit on both seasons for the current base prediction. "
            "No sportsbook odds are used. The probability interval shown on matchup cards reflects coefficient/parameter uncertainty only."
        )


def _render_step4c() -> bool:
    selected = st.session_state.get("nfl_v1_date", date.today())
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    schedule, diag = foundation.load_nfl_slate(day_str)
    pregame, _ = step1._pregame_partition(schedule, day_str, now_et=pd.Timestamp.now(tz=foundation.ET))
    feature_map = st.session_state.get("nfl_moneyline_v42_matchup_features") or {}

    st.markdown("### 🎯 Step 4C — Historical Win-Probability Calibration")
    st.caption(
        "Leakage-safe historical calibration ACTIVE • 2024 regular season train → 2025 chronological holdout → final 2024-25 refit • "
        "strength gap + offense/defense interaction + recent form + learned home/away effect • no sportsbook input."
    )

    if not diag.get("request_ok") or pregame.empty:
        st.warning("Step 4C cannot calculate because no verified pregame matchup is available.")
        return False
    if not feature_map or not st.session_state.get("nfl_moneyline_v42_matchup_ready"):
        st.warning("Step 4C cannot calculate until Step 4B matchup features are READY.")
        return False

    with st.spinner("Calibrating NFL win probability from completed historical regular-season games…"):
        model = _fit_calibration_model()

    if not model.get("ready"):
        st.warning(f"⚠️ STEP 4C CHECK • {model.get('error') or 'historical calibration did not pass validation.'} No probability is exposed.")
        _render_model_diagnostics(model) if model.get("validation") else None
        st.session_state["nfl_moneyline_v43_probability_ready"] = False
        return False

    ready_games = 0
    outputs = {}
    for _, row in pregame.iterrows():
        game = row.to_dict()
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        feat = feature_map.get(gid, {})
        x = _current_feature_vector(feat)
        if x is None:
            outputs[gid] = {"ready": False}
            continue
        away_p, lo, hi, raw = _probability_with_interval(x, model)
        outputs[gid] = {
            "ready": True,
            "away_p": away_p,
            "home_p": 1.0 - away_p,
            "away_lo": lo,
            "away_hi": hi,
            "raw_away_p": raw,
        }
        ready_games += 1

    all_ready = bool(len(pregame) and ready_games == len(pregame))
    a, b, c, d = st.columns(4)
    a.metric("Games calibrated", f"{ready_games}/{len(pregame)}")
    b.metric("Holdout games", str(model.get("valid_rows", 0)))
    c.metric("Brier", f"{model['validation']['brier']:.3f}")
    d.metric("Calibration", model.get("quality", "—"))

    if all_ready:
        st.success("✅ STEP 4C PASSED • base win probabilities calibrated from historical regular-season outcomes for every pregame matchup.")
    else:
        st.warning("⚠️ STEP 4C CHECK • at least one matchup could not be transformed into a calibrated probability.")

    for _, row in pregame.iterrows():
        game = row.to_dict()
        away = _safe(game.get("away_team"), "Away")
        home = _safe(game.get("home_team"), "Home")
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        out = outputs.get(gid, {})
        st.markdown(f"#### Base calibrated probability — {escape(away)} @ {escape(home)}")
        if not out.get("ready"):
            st.warning("Probability unavailable because required Step 4B features are incomplete.")
            continue

        p1, p2, p3 = st.columns(3)
        p1.metric(f"{away} P(win)", _fmt_pct(out.get("away_p")))
        p2.metric(f"{home} P(win)", _fmt_pct(out.get("home_p")))
        p3.metric("Away parameter 95% band", f"{_fmt_pct(out.get('away_lo'))}–{_fmt_pct(out.get('away_hi'))}")

        preseason = _safe(game.get("season_type")).lower() == "preseason"
        gameplan_ready = bool(st.session_state.get("nfl_moneyline_v3_gameplan_ready"))
        if preseason and not gameplan_ready:
            st.warning(
                "🔒 PRESEASON FINAL-OUTPUT GATE • this is the calibrated historical BASE probability only. Step 3 game-plan/QB-rotation verification is not fully cleared, "
                "so this probability is not eligible for a final Moneyline recommendation."
            )
        else:
            st.info("Base calibrated probability is available. Sportsbook price comparison, Monte Carlo and final grading are still separate locked layers.")

    _render_model_diagnostics(model)
    st.session_state["nfl_moneyline_v43_probability_outputs"] = outputs
    st.session_state["nfl_moneyline_v43_calibration_model"] = {
        "quality": model.get("quality"),
        "rows": model.get("rows"),
        "train_rows": model.get("train_rows"),
        "valid_rows": model.get("valid_rows"),
        "validation": model.get("validation"),
    }
    st.session_state["nfl_moneyline_v43_probability_ready"] = all_ready
    return all_ready


def render_nfl_moneyline_hub():
    """Render V4.2 unchanged and inject Step 4C immediately before production locks."""
    real_markdown = st.markdown
    real_dataframe = st.dataframe
    real_caption = st.caption
    state = {"step4c_injected": False, "step4c_ready": False}

    def _markdown(body, *args, **kwargs):
        if isinstance(body, str):
            if '<span class="knfl-ml-chip">STEP 4B</span>' in body:
                body = body.replace(
                    '<span class="knfl-ml-chip">STEP 4B</span>',
                    '<span class="knfl-ml-chip">STEP 4C</span>',
                )
                body = body.replace(
                    "Step 4A baseline + Step 4B matchup features are active; calibrated win probability, sportsbook math and Monte Carlo remain off.",
                    "Steps 4A-4C are active: historical baseline, matchup features and base calibrated win probability. Sportsbook math and Monte Carlo remain off; preseason final output stays Step-3 gated.",
                )
            if body.strip() == "### 🔒 Moneyline production locks" and not state["step4c_injected"]:
                state["step4c_injected"] = True
                state["step4c_ready"] = _render_step4c()
        return real_markdown(body, *args, **kwargs)

    def _dataframe(data=None, *args, **kwargs):
        if isinstance(data, pd.DataFrame) and "Layer" in data.columns and "State" in data.columns:
            layers = set(data["Layer"].astype(str).tolist())
            if "Calibrated win probability" in layers:
                data = data.copy()
                mask = data["Layer"].astype(str) == "Calibrated win probability"
                data.loc[mask, "State"] = (
                    "STEP 4C BASE P(WIN) READY • PRESEASON FINAL GATE APPLIES"
                    if state.get("step4c_ready")
                    else "STEP 4C CHECK"
                )
        return real_dataframe(data, *args, **kwargs)

    def _caption(body, *args, **kwargs):
        if isinstance(body, str) and body.startswith("Step 4B adds opponent interaction"):
            body = (
                "Step 4C calibrates the Step 4A/4B feature stack against completed historical NFL regular-season outcomes with a chronological 2025 holdout. "
                "The base P(win) uses no sportsbook prices. Monte Carlo, no-vig edge/EV and final grading remain OFF. During preseason, Step 3 remains the final-output safety gate."
            )
        return real_caption(body, *args, **kwargs)

    st.markdown = _markdown
    st.dataframe = _dataframe
    st.caption = _caption
    try:
        return v42.render_nfl_moneyline_hub()
    finally:
        st.markdown = real_markdown
        st.dataframe = real_dataframe
        st.caption = real_caption


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
