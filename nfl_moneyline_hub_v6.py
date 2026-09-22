"""Kyre Sports AI — NFL Moneyline V6 Step-6 Monte Carlo uncertainty layer.

Builds on V5.1 without changing Steps 1-5. Step 6 propagates Step-4C model
parameter uncertainty through 5,000,000 deterministic Monte Carlo draws in 20
batches. The current verified Step-4B feature vector is held fixed; calibration
coefficients are sampled from the fitted covariance approximation and each draw
then produces a Bernoulli game outcome.

This is a BASE MODEL Monte Carlo layer only. Sportsbook prices never enter the
simulation. Unresolved preseason game-plan/QB-rotation uncertainty is not assigned
an invented numeric penalty; Step 3 remains the final-output gate. Edge/EV, final
grading and recommendations remain locked.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v1 as step1
import nfl_moneyline_hub_v431 as v431
import nfl_moneyline_hub_v51 as v51
import nfl_moneyline_mc_v1 as mc

MODEL_VERSION = "NFL MONEYLINE V6.0 • STEP 6 5M MONTE CARLO"


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


def _fmt_pct(value, digits=1):
    n = _num(value)
    return "—" if not np.isfinite(n) else f"{100.0 * n:.{digits}f}%"


def _fmt_pp(value, digits=3):
    n = _num(value)
    return "—" if not np.isfinite(n) else f"{100.0 * n:.{digits}f} pp"


def _run_game_mc(game: dict, feature: dict, model: dict, day_str: str) -> dict:
    gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
    x = v431.v43._current_feature_vector(feature)
    if x is None:
        return {"ready": False, "error": "Step-4B feature vector is incomplete"}

    beta = np.asarray(model.get("beta"), dtype=float).reshape(-1)
    scales = np.asarray(model.get("scales"), dtype=float).reshape(-1)
    covariance = np.asarray(model.get("covariance"), dtype=float)
    xv = np.asarray(x, dtype=float).reshape(-1)
    if beta.size == 0 or xv.size != beta.size or scales.size != beta.size or covariance.shape != (beta.size, beta.size):
        return {"ready": False, "error": "Step-4C calibration internals are incomplete"}

    seed = mc.deterministic_seed(gid, day_str)
    try:
        out = mc.run_parameter_monte_carlo(
            tuple(float(v) for v in xv),
            tuple(float(v) for v in beta),
            tuple(float(v) for v in scales),
            tuple(float(v) for v in covariance.reshape(-1)),
            float(v431.v43.PROB_FLOOR),
            float(v431.v43.PROB_CEILING),
            int(seed),
            mc.SIMULATIONS,
            mc.BATCHES,
        )
    except Exception as exc:
        return {
            "ready": False,
            "error": f"{type(exc).__name__}: {_safe(exc, 'Monte Carlo runtime error')[:220]}",
        }
    return dict(out)


def _render_diagnostics(out: dict):
    with st.expander("🎲 Step 6 Monte Carlo diagnostics", expanded=False):
        rows = [
            {"Diagnostic": "Model version", "Value": _safe(out.get("model_version"), mc.MODEL_VERSION)},
            {"Diagnostic": "Simulations", "Value": f"{int(out.get('simulations') or 0):,}"},
            {"Diagnostic": "Batches", "Value": str(int(out.get("batches") or 0))},
            {"Diagnostic": "Batch size", "Value": f"{int(out.get('batch_size') or 0):,}"},
            {"Diagnostic": "Random seed", "Value": str(int(out.get("seed") or 0))},
            {"Diagnostic": "Monte Carlo SE", "Value": _fmt_pp(out.get("mc_se"), 3)},
            {"Diagnostic": "Batch win-rate spread", "Value": _fmt_pp(out.get("batch_spread"), 3)},
            {"Diagnostic": "Max batch deviation", "Value": _fmt_pp(out.get("max_batch_deviation"), 3)},
            {"Diagnostic": "P(draw) standard deviation", "Value": _fmt_pp(out.get("probability_sd"), 2)},
            {"Diagnostic": "Convergence", "Value": "PASS" if out.get("converged") else "CHECK"},
            {"Diagnostic": "Uncertainty scope", "Value": _safe(out.get("uncertainty_scope"), "—")},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            "Step 6 samples Step-4C coefficient uncertainty and conditional game outcomes only. "
            "The verified Step-4B game features are held fixed. Sportsbook prices do not enter the simulation. "
            "When preseason Step 3 is unresolved, no made-up QB/game-plan shock is added; final output remains gated."
        )


def _render_game(game: dict, out: dict, base: dict):
    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    st.markdown(f"#### Monte Carlo — {away} @ {home}")

    if not out.get("ready"):
        st.warning(f"⚠️ Monte Carlo unavailable • {out.get('error') or 'simulation did not complete'}")
        return

    a, b, c, d = st.columns(4)
    a.metric(f"{away} MC win %", _fmt_pct(out.get("away_win_rate")))
    b.metric(f"{home} MC win %", _fmt_pct(out.get("home_win_rate")))
    c.metric("Median sampled P", _fmt_pct(out.get("median_probability")))
    d.metric("Convergence", "PASS" if out.get("converged") else "CHECK")

    x, y, z = st.columns(3)
    x.metric("Sampled-P 5th pct", _fmt_pct(out.get("p05_probability")))
    y.metric("Sampled-P 95th pct", _fmt_pct(out.get("p95_probability")))
    z.metric("MC standard error", _fmt_pp(out.get("mc_se"), 3))

    if base and base.get("ready"):
        base_p = _num(base.get("away_p"))
        mc_p = _num(out.get("away_win_rate"))
        diff = mc_p - base_p if np.isfinite(base_p) and np.isfinite(mc_p) else np.nan
        st.caption(
            f"Step-4C base {away}: {_fmt_pct(base_p)} • 5M Monte Carlo {away}: {_fmt_pct(mc_p)} • "
            f"MC minus base: {_fmt_pp(diff, 2)}"
        )

    preseason = _safe(game.get("season_type")).lower() == "preseason"
    gameplan_ready = bool(st.session_state.get("nfl_moneyline_v3_gameplan_ready"))
    if preseason and not gameplan_ready:
        st.warning(
            "🔒 PRESEASON FINAL-OUTPUT GATE • Step 6 is a BASE-model uncertainty simulation only. "
            "Verified preseason QB participation/rotation is still incomplete, so this Monte Carlo result is not eligible for final Moneyline grading or a recommendation."
        )
    elif out.get("converged"):
        st.success("✅ Monte Carlo convergence passed. Final edge/EV and grading remain separate locked layers.")
    else:
        st.warning("⚠️ Monte Carlo batch stability did not pass the convergence guard; downstream grading remains locked.")

    _render_diagnostics(out)


def _render_step6() -> bool:
    selected = st.session_state.get("nfl_v1_date", date.today())
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    schedule, diag = foundation.load_nfl_slate(day_str)
    pregame, _ = step1._pregame_partition(schedule, day_str, now_et=pd.Timestamp.now(tz=foundation.ET))
    feature_map = st.session_state.get("nfl_moneyline_v42_matchup_features") or {}
    base_outputs = st.session_state.get("nfl_moneyline_v43_probability_outputs") or {}

    st.markdown("### 🎲 Step 6 — Monte Carlo Uncertainty")
    st.caption(
        "5,000,000 simulations • 20 deterministic batches • Step-4C coefficient covariance + conditional game outcomes • "
        "Monte Carlo SE + batch stability + convergence • sportsbook market excluded from the simulation."
    )

    if not diag.get("request_ok") or pregame.empty:
        st.warning("Step 6 cannot run because no verified pregame NFL matchup is available.")
        st.session_state["nfl_moneyline_v6_mc_ready"] = False
        return False
    if not st.session_state.get("nfl_moneyline_v43_probability_ready") or not feature_map or not base_outputs:
        st.warning("Step 6 cannot run until Step 4B features and Step 4C calibrated base probabilities are READY.")
        st.session_state["nfl_moneyline_v6_mc_ready"] = False
        return False

    model = v431.v43._fit_calibration_model()
    if not model.get("ready"):
        st.warning("Step 6 cannot run because the validated Step-4C calibration model is not READY.")
        st.session_state["nfl_moneyline_v6_mc_ready"] = False
        return False

    outputs = {}
    ready_games = 0
    converged_games = 0
    with st.spinner("🎲 Running 5,000,000-draw NFL Moneyline Monte Carlo…"):
        for _, src in pregame.iterrows():
            game = src.to_dict()
            gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
            out = _run_game_mc(game, feature_map.get(gid, {}), model, day_str)
            outputs[gid] = out
            if out.get("ready"):
                ready_games += 1
            if out.get("ready") and out.get("converged"):
                converged_games += 1

    all_ready = bool(len(pregame) and ready_games == len(pregame) and converged_games == len(pregame))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Games simulated", f"{ready_games}/{len(pregame)}")
    m2.metric("Simulations/game", f"{mc.SIMULATIONS:,}")
    m3.metric("Batches", str(mc.BATCHES))
    m4.metric("Converged", f"{converged_games}/{len(pregame)}")

    if all_ready:
        st.success("✅ STEP 6 PASSED • 5M Monte Carlo completed and convergence guards passed for every verified pregame matchup.")
    else:
        st.warning("⚠️ STEP 6 CHECK • at least one matchup failed the Monte Carlo runtime or convergence guard. No downstream grade is unlocked.")

    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        _render_game(game, outputs.get(gid, {}), base_outputs.get(gid, {}))

    st.info(
        "MODEL / MARKET FIREWALL • Step 6 uses the calibrated model and its uncertainty only. "
        "Step-5 sportsbook prices are not simulation inputs. Edge/EV comparison remains locked for the next layer."
    )

    st.session_state["nfl_moneyline_v6_mc_outputs"] = outputs
    st.session_state["nfl_moneyline_v6_mc_ready"] = all_ready
    return all_ready


def render_nfl_moneyline_hub():
    """Render V5.1 and inject Step 6 after Step 5, before production locks."""
    real_markdown = st.markdown
    real_dataframe = st.dataframe
    real_caption = st.caption
    state = {"injected": False, "ready": False}

    def _markdown(body, *args, **kwargs):
        if isinstance(body, str):
            if '<span class="knfl-ml-chip">STEP 5</span>' in body:
                body = body.replace(
                    '<span class="knfl-ml-chip">STEP 5</span>',
                    '<span class="knfl-ml-chip">STEP 6</span>',
                )
            if body.strip() == "### 🔒 Moneyline production locks" and not state["injected"]:
                state["injected"] = True
                state["ready"] = _render_step6()
        return real_markdown(body, *args, **kwargs)

    def _dataframe(data=None, *args, **kwargs):
        if isinstance(data, pd.DataFrame) and "Layer" in data.columns and "State" in data.columns:
            layers = set(data["Layer"].astype(str).tolist())
            if "Monte Carlo" in layers:
                data = data.copy()
                mask = data["Layer"].astype(str) == "Monte Carlo"
                data.loc[mask, "State"] = (
                    "STEP 6 READY • 5M BASE MC • PRESEASON FINAL GATE APPLIES"
                    if state.get("ready")
                    else "STEP 6 CHECK"
                )
                final_mask = data["Layer"].astype(str) == "No-vig edge / EV / final grading"
                if final_mask.any():
                    data.loc[final_mask, "State"] = "LOCKED — STEP 7 NEXT"
        return real_dataframe(data, *args, **kwargs)

    def _caption(body, *args, **kwargs):
        if isinstance(body, str) and body.startswith("Step 5 adds current sportsbook Moneyline transport"):
            body = (
                "Step 6 adds a 5,000,000-draw model-only Monte Carlo layer with deterministic batching, coefficient-uncertainty propagation, MC standard error and convergence checks. "
                "Sportsbook prices remain outside the simulation. Edge/EV and final grading remain OFF; Step 3 remains the preseason final-output safety gate."
            )
        return real_caption(body, *args, **kwargs)

    st.markdown = _markdown
    st.dataframe = _dataframe
    st.caption = _caption
    try:
        return v51.render_nfl_moneyline_hub()
    finally:
        st.markdown = real_markdown
        st.dataframe = real_dataframe
        st.caption = real_caption


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
