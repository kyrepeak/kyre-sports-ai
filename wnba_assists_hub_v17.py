"""WNBA Assists V17 — Step 17 5M Monte Carlo + convergence / sensitivity.

Preserves Assists Steps 1–16 and adds the actual simulation validation layer on
the independent model branch.

Architecture:
MODEL:  Steps 1–12 -> Step 15 -> Step 16 -> Step 17
MARKET: Steps 13–14 --------------------------------> joins at Steps 18/19

Step 17 rules:
- Step 16 must pass; sportsbook availability is irrelevant;
- run exactly 5,000,000 base Monte Carlo trials PER active calibrated player;
- execute in 20 deterministic 250,000-trial batches with a reportable seed;
- use multinomial aggregation of the Step-16 discrete PMF, which is exactly
  equivalent to drawing every categorical trial individually but avoids storing
  millions of samples in memory;
- verify simulated mean, variance and PMF against the Step-16 analytical model;
- report Monte Carlo SE, batch-to-batch mean range, max PMF error and convergence;
- fail closed when any core rotation distribution fails convergence;
- run deterministic sensitivity re-parameterization for minutes +/-10%,
  dispersion +/-15%, and a status-risk downside scenario without adding random
  samples or changing the base 5M simulation count;
- H2H and sportsbook inputs remain 0% influence;
- no line-specific Over/Under probability, fair model odds, EV or ranking yet.

Step 18 remains the first line-specific probability layer.
"""
from __future__ import annotations

import hashlib
import math
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v16 as v16

MODEL_VERSION = "WNBA ASSISTS V17 • STEP 17 5M MONTE CARLO + CONVERGENCE / SENSITIVITY"
_ET = ZoneInfo("America/New_York")
BASE_SIMS = 5_000_000
BATCH_SIZE = 250_000
BATCHES = BASE_SIMS // BATCH_SIZE
MC_MAX_K = 100
CORE_MINUTES = 10.0
ZERO_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}
RISK_STATUSES = {"QUESTIONABLE", "PROBABLE", "REPORTED", "DAY-TO-DAY"}


def _num(value: Any, default: float = np.nan) -> float:
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _distribution_fingerprint(distribution: pd.DataFrame, day_str: str) -> str:
    if distribution is None or distribution.empty:
        return "EMPTY"
    passed = distribution.loc[
        distribution.get("DISTRIBUTION_STATE", pd.Series("", index=distribution.index))
        .astype(str).str.upper().eq("PASS")
    ].copy()
    if passed.empty:
        return "EMPTY"
    passed["_pid_sort"] = pd.to_numeric(
        passed.get("PLAYER_ID", pd.Series(0, index=passed.index)), errors="coerce"
    ).fillna(0).astype(int)
    passed = passed.sort_values(["_pid_sort", "PLAYER_NAME"])
    rows = []
    for _, row in passed.iterrows():
        rows.append("|".join([
            str(_safe_int(row.get("PLAYER_ID"))),
            str(row.get("PLAYER_NAME") or ""),
            f"{_num(row.get('EXPECTED_ASSISTS')):.10f}",
            f"{_num(row.get('CALIBRATED_VARIANCE')):.10f}",
            str(row.get("DISTRIBUTION_FAMILY") or ""),
            f"{_num(row.get('DIST_PARAM_1')):.10f}",
            f"{_num(row.get('DIST_PARAM_2')):.10f}",
            str(row.get("DISTRIBUTION_VERSION") or ""),
            str(row.get("PROJECTION_VERSION") or ""),
        ]))
    payload = f"{day_str}|{MODEL_VERSION}|" + "||".join(rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _base_seed(day_str: str, fingerprint: str) -> int:
    digest = hashlib.sha256(
        f"KYRE-ASSISTS-MC|{day_str}|{fingerprint}|{BASE_SIMS}|{BATCH_SIZE}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _player_seed(base_seed: int, player_id: int, ordinal: int) -> int:
    digest = hashlib.sha256(f"{base_seed}|{int(player_id)}|{int(ordinal)}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _expanded_family_pmf(row: pd.Series):
    family = str(row.get("DISTRIBUTION_FAMILY") or "").upper().strip()
    mu = _num(row.get("EXPECTED_ASSISTS"))
    p1 = _num(row.get("DIST_PARAM_1"))
    p2 = _num(row.get("DIST_PARAM_2"))
    probs = np.zeros(MC_MAX_K + 1, dtype=float)
    if not np.isfinite(mu) or mu < 0:
        return np.array([]), np.array([]), np.nan
    if family == "DEGENERATE ZERO" or mu <= 1e-12:
        probs[0] = 1.0
    elif family == "POISSON":
        probs[0] = math.exp(-mu)
        for k in range(MC_MAX_K):
            probs[k + 1] = probs[k] * mu / float(k + 1)
    elif family == "NEGATIVE BINOMIAL":
        r, p = p1, p2
        if not np.isfinite(r) or not np.isfinite(p) or r <= 0 or not (0 < p < 1):
            return np.array([]), np.array([]), np.nan
        q = 1.0 - p
        probs[0] = math.exp(r * math.log(max(p, 1e-300)))
        for k in range(MC_MAX_K):
            probs[k + 1] = probs[k] * ((k + r) / float(k + 1)) * q
    elif family == "BINOMIAL":
        n = int(round(p1)); p = p2
        if n < 0 or n > MC_MAX_K or not np.isfinite(p) or not (0 <= p <= 1):
            return np.array([]), np.array([]), np.nan
        if p <= 0:
            probs[0] = 1.0
        elif p >= 1:
            probs[n] = 1.0
        else:
            q = 1.0 - p
            probs[0] = q ** n
            for k in range(n):
                probs[k + 1] = probs[k] * ((n - k) / float(k + 1)) * (p / q)
    else:
        return np.array([]), np.array([]), np.nan
    probs = np.where(np.isfinite(probs) & (probs > 0), probs, 0.0)
    subtotal = float(probs.sum())
    if subtotal > 1.0 + 1e-10:
        probs /= subtotal
        subtotal = 1.0
    tail = max(0.0, 1.0 - subtotal)
    full_probs = np.concatenate([probs, np.array([tail], dtype=float)])
    full_probs /= float(full_probs.sum())
    values = np.arange(MC_MAX_K + 2, dtype=float)
    return values, full_probs, tail


def _step16_reference_vector(row: pd.Series) -> np.ndarray:
    pmf = row.get("ASSIST_PMF") if isinstance(row.get("ASSIST_PMF"), dict) else {}
    ref = np.zeros(62, dtype=float)
    for k in range(61):
        ref[k] = max(0.0, float(pmf.get(k, 0.0)))
    ref[61] = max(0.0, 1.0 - float(ref[:61].sum()))
    total = float(ref.sum())
    if total > 0:
        ref /= total
    return ref


def _compress_mc_vector(counts: np.ndarray) -> np.ndarray:
    out = np.zeros(62, dtype=np.int64)
    out[:61] = counts[:61]
    out[61] = int(counts[61:].sum())
    return out


def _quantile_from_counts(counts: np.ndarray, q: float) -> int:
    n = int(counts.sum())
    if n <= 0:
        return 0
    target = float(q) * n
    cumulative = np.cumsum(counts)
    idx = int(np.searchsorted(cumulative, target, side="left"))
    return min(idx, MC_MAX_K + 1)


def _simulate_player(row: pd.Series, seed: int):
    values, probabilities, expanded_tail = _expanded_family_pmf(row)
    if values.size == 0 or probabilities.size == 0:
        return {"CONVERGED": False, "CONVERGENCE_REASON": "invalid analytical distribution family/parameters", "SIMULATIONS": 0}, {}
    if expanded_tail > 1e-6:
        return {"CONVERGED": False, "CONVERGENCE_REASON": f"expanded analytical tail too large ({expanded_tail:.6%})", "SIMULATIONS": 0}, {}
    rng = np.random.default_rng(seed)
    total_counts = np.zeros(len(probabilities), dtype=np.int64)
    batch_means = []
    for _ in range(BATCHES):
        counts = rng.multinomial(BATCH_SIZE, probabilities)
        total_counts += counts
        batch_means.append(float(np.dot(counts, values) / BATCH_SIZE))
    n = int(total_counts.sum())
    if n != BASE_SIMS:
        return {"CONVERGED": False, "CONVERGENCE_REASON": f"simulation count mismatch ({n} != {BASE_SIMS})", "SIMULATIONS": n}, {}
    mean = float(np.dot(total_counts, values) / n)
    centered2 = float(np.dot(total_counts, values * values) / n - mean * mean)
    variance = max(0.0, centered2 * n / max(1, n - 1))
    sd = math.sqrt(variance)
    mc_se = sd / math.sqrt(n)
    median = _quantile_from_counts(total_counts, 0.50)
    mode = int(np.argmax(total_counts))
    p10 = _quantile_from_counts(total_counts, 0.10)
    p90 = _quantile_from_counts(total_counts, 0.90)
    batch_range = float(max(batch_means) - min(batch_means)) if batch_means else np.nan
    batch_se = sd / math.sqrt(BATCH_SIZE)
    expected = _num(row.get("EXPECTED_ASSISTS"))
    expected_variance = _num(row.get("CALIBRATED_VARIANCE"))
    mean_error = abs(mean - expected) if np.isfinite(expected) else np.inf
    variance_rel_error = abs(variance - expected_variance) / max(expected_variance, 1e-9) if np.isfinite(expected_variance) else np.inf
    compressed = _compress_mc_vector(total_counts)
    sim_ref = compressed.astype(float) / n
    analytic_ref = _step16_reference_vector(row)
    max_pmf_error = float(np.max(np.abs(sim_ref - analytic_ref)))
    mean_tol = max(0.010, 8.0 * mc_se)
    batch_tol = max(0.040, 10.0 * batch_se)
    variance_tol = 0.030
    pmf_tol = 0.0030
    checks = {
        "mean": mean_error <= mean_tol,
        "variance": variance_rel_error <= variance_tol,
        "batch": batch_range <= batch_tol,
        "pmf": max_pmf_error <= pmf_tol,
    }
    converged = bool(all(checks.values()))
    failed = [name for name, ok in checks.items() if not ok]
    mc_pmf = {int(k): float(c / n) for k, c in enumerate(total_counts) if c > 0 and k <= MC_MAX_K}
    overflow_prob = float(total_counts[-1] / n)
    if overflow_prob > 0:
        mc_pmf[MC_MAX_K + 1] = overflow_prob
    summary = {
        "PLAYER_ID": _safe_int(row.get("PLAYER_ID")),
        "PLAYER_NAME": str(row.get("PLAYER_NAME") or ""),
        "TEAM": str(row.get("TEAM_ABBREVIATION") or row.get("TEAM_NAME") or ""),
        "OPPONENT": str(row.get("OPPONENT") or ""),
        "PROJ_MIN": _num(row.get("PROJ_MIN")),
        "EXPECTED_ASSISTS": expected,
        "ANALYTICAL_VARIANCE": expected_variance,
        "ANALYTICAL_SD": _num(row.get("DISTRIBUTION_SD")),
        "ANALYTICAL_MEDIAN": _num(row.get("MEDIAN_ASSISTS")),
        "ANALYTICAL_MODE": _num(row.get("MODE_ASSISTS")),
        "DISTRIBUTION_FAMILY": str(row.get("DISTRIBUTION_FAMILY") or ""),
        "MC_MEAN": mean,
        "MC_VARIANCE": variance,
        "MC_SD": sd,
        "MC_MEDIAN": median,
        "MC_MODE": mode,
        "MC_P10": p10,
        "MC_P90": p90,
        "MC_SE_MEAN": mc_se,
        "MEAN_ABS_ERROR": mean_error,
        "VARIANCE_REL_ERROR": variance_rel_error,
        "MAX_BATCH_MEAN_DIFF": batch_range,
        "MAX_PMF_ABS_ERROR": max_pmf_error,
        "SIMULATIONS": n,
        "BATCHES": BATCHES,
        "BATCH_SIZE": BATCH_SIZE,
        "PLAYER_SEED": int(seed),
        "CONVERGED": converged,
        "CONVERGENCE_REASON": "" if converged else "failed " + ", ".join(failed),
    }
    return summary, mc_pmf


def _scenario_summary(mu: float, variance: float):
    probs, pars = v16._distribution_pmf(max(0.0, mu), max(0.02, variance))
    return {
        "mean": float(max(0.0, mu)),
        "variance": float(pars.get("actual_variance") or 0.0),
        "family": str(pars.get("family") or ""),
        "median": int(v16._quantile(probs, 0.50)),
        "p10": int(v16._quantile(probs, 0.10)),
        "p90": int(v16._quantile(probs, 0.90)),
    }


def _build_sensitivity(distribution: pd.DataFrame) -> pd.DataFrame:
    if distribution is None or distribution.empty:
        return pd.DataFrame()
    passed = distribution.loc[
        distribution.get("DISTRIBUTION_STATE", pd.Series("", index=distribution.index)).astype(str).str.upper().eq("PASS")
    ].copy()
    rows = []
    for _, row in passed.iterrows():
        mu = max(0.0, _num(row.get("EXPECTED_ASSISTS"), 0.0))
        variance = max(0.02, _num(row.get("CALIBRATED_VARIANCE"), max(mu, 0.02)))
        base = {"Player": str(row.get("PLAYER_NAME") or ""), "Team": str(row.get("TEAM_ABBREVIATION") or row.get("TEAM_NAME") or "")}
        scenarios = [
            ("Minutes -10%", 0.90 * mu, 0.90 * variance),
            ("Minutes +10%", 1.10 * mu, 1.10 * variance),
            ("Dispersion -15%", mu, max(0.45 * max(mu, 0.02), 0.85 * variance)),
            ("Dispersion +15%", mu, 1.15 * variance),
        ]
        status = str(row.get("AVAILABILITY") or "").upper().strip()
        risk = status in RISK_STATUSES or str(row.get("STATUS_RISK") or "").upper() == "YES"
        if risk:
            scenarios.append(("Status-risk downside", 0.90 * mu, 1.20 * variance))
        for label, smu, svar in scenarios:
            s = _scenario_summary(smu, svar)
            rows.append({**base, "Scenario": label, "Mean AST": s["mean"], "Median": s["median"], "P10": s["p10"], "P90": s["p90"], "Variance": s["variance"], "Family": s["family"], "Extra random draws": 0})
    return pd.DataFrame(rows)


def _run_monte_carlo(distribution: pd.DataFrame, day_str: str, progress_callback=None):
    if distribution is None or distribution.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "state": "CHECK", "reason": "Step 16 supplied no calibrated distributions", "base_sims_per_player": BASE_SIMS, "total_base_draws": 0}
    passed = distribution.loc[
        distribution.get("DISTRIBUTION_STATE", pd.Series("", index=distribution.index)).astype(str).str.upper().eq("PASS")
    ].copy()
    if passed.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "state": "CHECK", "reason": "no Step-16 PASS distributions", "base_sims_per_player": BASE_SIMS, "total_base_draws": 0}
    passed["_pid_sort"] = pd.to_numeric(passed.get("PLAYER_ID", pd.Series(0, index=passed.index)), errors="coerce").fillna(0).astype(int)
    passed = passed.sort_values(["_pid_sort", "PLAYER_NAME"]).reset_index(drop=True)
    fingerprint = _distribution_fingerprint(passed, day_str)
    seed = _base_seed(day_str, fingerprint)
    summaries = []
    pmfs = {}
    core_total = 0
    core_converged = 0
    start = time.perf_counter()
    for ordinal, (_, row) in enumerate(passed.iterrows()):
        availability = str(row.get("AVAILABILITY") or "").upper().strip()
        is_core = _num(row.get("PROJ_MIN"), 0.0) >= CORE_MINUTES and availability not in ZERO_STATUSES
        if is_core:
            core_total += 1
        pseed = _player_seed(seed, _safe_int(row.get("PLAYER_ID")), ordinal)
        summary, pmf = _simulate_player(row, pseed)
        summary["IS_CORE"] = bool(is_core)
        summaries.append(summary)
        if summary.get("CONVERGED") and is_core:
            core_converged += 1
        if pmf:
            pmfs[_safe_int(row.get("PLAYER_ID"))] = pmf
        if progress_callback is not None:
            progress_callback((ordinal + 1) / max(1, len(passed)), row, summary)
    elapsed = float(time.perf_counter() - start)
    summary_df = pd.DataFrame(summaries)
    sensitivity = _build_sensitivity(passed)
    all_players_converged = bool(not summary_df.empty and summary_df["CONVERGED"].fillna(False).astype(bool).all())
    core_ready = bool(core_total > 0 and core_converged == core_total)
    ready = bool(all_players_converged and core_ready)
    max_se = float(pd.to_numeric(summary_df.get("MC_SE_MEAN"), errors="coerce").max()) if not summary_df.empty else np.nan
    max_batch = float(pd.to_numeric(summary_df.get("MAX_BATCH_MEAN_DIFF"), errors="coerce").max()) if not summary_df.empty else np.nan
    max_pmf = float(pd.to_numeric(summary_df.get("MAX_PMF_ABS_ERROR"), errors="coerce").max()) if not summary_df.empty else np.nan
    failed_players = summary_df.loc[~summary_df["CONVERGED"].fillna(False), "PLAYER_NAME"].astype(str).tolist() if not summary_df.empty else []
    total_draws = int(pd.to_numeric(summary_df.get("SIMULATIONS"), errors="coerce").fillna(0).sum())
    diag = {
        "ready": ready,
        "state": "CONVERGED" if ready else "CHECK",
        "reason": "" if ready else "one or more player simulations failed convergence",
        "fingerprint": fingerprint,
        "base_seed": int(seed),
        "base_sims_per_player": BASE_SIMS,
        "batch_size": BATCH_SIZE,
        "batches_per_player": BATCHES,
        "players_simulated": len(summary_df),
        "core_players": core_total,
        "core_converged": core_converged,
        "all_players_converged": all_players_converged,
        "total_base_draws": total_draws,
        "elapsed_seconds": elapsed,
        "max_mc_se": max_se,
        "max_batch_mean_diff": max_batch,
        "max_pmf_abs_error": max_pmf,
        "failed_players": failed_players[:12],
        "sensitivity_extra_random_draws": 0,
        "market_influence": 0.0,
        "h2h_weight": 0.0,
        "simulation_method": "20 x 250,000 multinomial categorical batches per player",
        "mc_pmfs": pmfs,
    }
    return summary_df, sensitivity, diag


def _snapshot_key(day_str: str) -> str:
    return f"wnba_assists_v17_mc::{day_str}"


def _current_snapshot(distribution: pd.DataFrame, day_str: str):
    fingerprint = _distribution_fingerprint(distribution, day_str)
    snapshot = st.session_state.get(_snapshot_key(day_str))
    if not isinstance(snapshot, dict):
        return None, fingerprint, False
    valid = snapshot.get("fingerprint") == fingerprint and int(snapshot.get("base_sims_per_player") or 0) == BASE_SIMS
    return snapshot, fingerprint, bool(valid)


def _render_saved_summary(snapshot: dict[str, Any]):
    summary = snapshot.get("summary")
    if not isinstance(summary, pd.DataFrame) or summary.empty:
        return
    view = summary.copy()
    view["Player"] = view["PLAYER_NAME"].astype(str)
    view["Team"] = view["TEAM"].astype(str)
    view["Expected AST"] = pd.to_numeric(view["EXPECTED_ASSISTS"], errors="coerce").round(3)
    view["MC mean"] = pd.to_numeric(view["MC_MEAN"], errors="coerce").round(3)
    view["MC median"] = pd.to_numeric(view["MC_MEDIAN"], errors="coerce").round(0).astype("Int64")
    view["MC mode"] = pd.to_numeric(view["MC_MODE"], errors="coerce").round(0).astype("Int64")
    view["MC SD"] = pd.to_numeric(view["MC_SD"], errors="coerce").round(3)
    view["MC SE"] = pd.to_numeric(view["MC_SE_MEAN"], errors="coerce").map(lambda x: f"{x:.5f}")
    view["Mean error"] = pd.to_numeric(view["MEAN_ABS_ERROR"], errors="coerce").map(lambda x: f"{x:.5f}")
    view["Max batch Δ"] = pd.to_numeric(view["MAX_BATCH_MEAN_DIFF"], errors="coerce").map(lambda x: f"{x:.4f}")
    view["Max PMF error"] = pd.to_numeric(view["MAX_PMF_ABS_ERROR"], errors="coerce").map(lambda x: f"{100*x:.3f}%")
    view["Converged"] = view["CONVERGED"].map(lambda x: "✅" if bool(x) else "⛔")
    view = view.sort_values(["CONVERGED", "EXPECTED_ASSISTS"], ascending=[True, False])
    st.dataframe(view[["Player", "Team", "Expected AST", "MC mean", "MC median", "MC mode", "MC SD", "MC SE", "Mean error", "Max batch Δ", "Max PMF error", "Converged"]], hide_index=True, use_container_width=True)


def _render_sensitivity(snapshot: dict[str, Any]):
    sensitivity = snapshot.get("sensitivity")
    if not isinstance(sensitivity, pd.DataFrame) or sensitivity.empty:
        return
    with st.expander("🧪 Step-17 sensitivity scenarios", expanded=False):
        view = sensitivity.copy()
        view["Mean AST"] = pd.to_numeric(view["Mean AST"], errors="coerce").round(2)
        view["Variance"] = pd.to_numeric(view["Variance"], errors="coerce").round(2)
        st.dataframe(view, hide_index=True, use_container_width=True)
        st.caption("Sensitivity uses deterministic re-parameterization of the calibrated count family. It draws 0 extra random samples, so the reported base Monte Carlo count remains exactly 5,000,000 per player.")


def _render_step17(distribution: pd.DataFrame, step16_ready: bool, day_str: str):
    st.markdown("### 🎲 Step 17 — 5M Monte Carlo + Convergence / Sensitivity")
    st.caption("Actual simulation validation only. Step 17 runs exactly 5,000,000 categorical trials per active Step-16 distribution in 20 × 250,000 batches, reports a reproducible seed and convergence diagnostics, and does not read sportsbook lines or no-vig probabilities.")
    if not step16_ready or distribution is None or distribution.empty:
        st.warning("⚠️ STEP 17 LOCKED • Step 16 must pass before any Monte Carlo simulation can run.")
        return False, {"ready": False, "state": "LOCKED", "reason": "Step 16 not ready"}
    passed = distribution.loc[distribution.get("DISTRIBUTION_STATE", pd.Series("", index=distribution.index)).astype(str).str.upper().eq("PASS")].copy()
    snapshot, fingerprint, valid_snapshot = _current_snapshot(distribution, day_str)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Distributions ready", len(passed))
    c2.metric("Base sims / player", f"{BASE_SIMS:,}")
    c3.metric("Batches / player", f"{BATCHES} × {BATCH_SIZE:,}")
    c4.metric("Market influence", "0%")
    if snapshot is not None and not valid_snapshot:
        st.warning("⚠️ STEP 17 STALE • the saved Monte Carlo snapshot no longer matches the current Step-16 distribution fingerprint. It will not unlock downstream modeling until 5M is rerun.")
    if valid_snapshot:
        diag = snapshot.get("diag") if isinstance(snapshot.get("diag"), dict) else {}
        ready = bool(diag.get("ready"))
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Players simulated", int(diag.get("players_simulated") or 0))
        d2.metric("Total base draws", f"{int(diag.get('total_base_draws') or 0):,}")
        d3.metric("Base seed", str(diag.get("base_seed") or "—"))
        d4.metric("Convergence", "PASSED" if ready else "CHECK")
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Max MC SE", f"{float(diag.get('max_mc_se') or 0.0):.5f}")
        e2.metric("Max batch Δ", f"{float(diag.get('max_batch_mean_diff') or 0.0):.4f} AST")
        e3.metric("Max PMF error", f"{100.0*float(diag.get('max_pmf_abs_error') or 0.0):.3f}%")
        e4.metric("Runtime", f"{float(diag.get('elapsed_seconds') or 0.0):.2f}s")
        if ready:
            st.success("✅ STEP 17 PASSED • every simulated player converged across 5,000,000 base trials. Mean, variance and count probabilities agree with the Step-16 analytical distribution inside the fail-closed tolerances.")
        else:
            st.error("⛔ STEP 17 CHECK • at least one 5M simulation failed convergence. Step 18 remains locked.")
            if diag.get("failed_players"):
                st.caption("Convergence holds: " + " • ".join(diag["failed_players"][:8]))
        _render_saved_summary(snapshot)
        _render_sensitivity(snapshot)
        st.caption(f"Monte Carlo fingerprint {fingerprint} • saved {snapshot.get('checked_at_et') or '—'} • base trials/player {BASE_SIMS:,} • sensitivity extra random draws 0")
    else:
        ready = False
        st.info("🎲 STEP 17 ARMED • no current 5M snapshot exists for this Step-16 distribution. Run the simulation below. Nothing is auto-simulated on page load.")
    if st.button("▶️ RUN 5,000,000 ASSISTS MONTE CARLO — STEP 17", use_container_width=True, key=f"assists_step17_run::{day_str}", help="Runs 5,000,000 base categorical trials per active calibrated player in 20 deterministic batches. No sportsbook request is made."):
        progress = st.progress(0.0, text="Preparing Step-17 Monte Carlo…")
        def progress_callback(frac, row, summary):
            player = str(row.get("PLAYER_NAME") or "player")
            state = "converged" if summary.get("CONVERGED") else "checking"
            progress.progress(min(1.0, max(0.0, float(frac))), text=f"5M Monte Carlo • {player} • {state}")
        summary, sensitivity, diag = _run_monte_carlo(distribution, day_str, progress_callback=progress_callback)
        progress.empty()
        snapshot = {
            "fingerprint": fingerprint,
            "base_sims_per_player": BASE_SIMS,
            "summary": summary,
            "sensitivity": sensitivity,
            "diag": diag,
            "checked_at_et": datetime.now(_ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
        }
        st.session_state[_snapshot_key(day_str)] = snapshot
        st.session_state[f"wnba_assists_v17_diag::{day_str}"] = dict(diag)
        st.session_state[f"wnba_assists_v17_summary::{day_str}"] = summary.copy()
        st.rerun()
    with st.expander("🧪 Step-17 Monte Carlo methodology / convergence gates", expanded=False):
        st.write(f"• Base trials per active calibrated player: {BASE_SIMS:,}.")
        st.write(f"• Batching: {BATCHES} × {BATCH_SIZE:,} trials per player.")
        st.write("• Simulation method: batched multinomial aggregation of the exact calibrated discrete PMF. A multinomial count draw is mathematically equivalent to individually drawing every categorical trial, but avoids retaining millions of samples in memory.")
        st.write("• Seed: deterministic from ET slate date + exact Step-16 distribution fingerprint, with a derived player seed for reproducibility.")
        st.write("• Monte Carlo SE = simulated SD / sqrt(5,000,000).")
        st.write("• Convergence checks: mean error, variance error, max batch-mean range and max count-PMF error vs Step 16.")
        st.write("• Mean tolerance = max(0.010 AST, 8 × Monte Carlo SE).")
        st.write("• Variance relative-error tolerance = 3%.")
        st.write("• Batch mean-range tolerance = max(0.040 AST, 10 × batch SE).")
        st.write("• Maximum PMF absolute-error tolerance = 0.30 percentage points.")
        st.write("• Core rotation convergence is fail-closed; any failed player prevents Step 17 PASS.")
        st.write("• Sensitivity: minutes ±10%, dispersion ±15%, plus status-risk downside when applicable.")
        st.write("• Sensitivity extra random draws: 0; sensitivity re-parameterizes the analytical count family and does not alter the 5M base Monte Carlo result.")
        st.write("• H2H influence: 0%.")
        st.write("• SportsGameOdds / line / price / no-vig influence: 0%.")
        st.write("• Line-specific Over/Under probability: NO — Step 18.")
        st.write("• EV / ranking / Top 5: NO — Steps 19–20.")
    return ready, (snapshot.get("diag") if valid_snapshot and isinstance(snapshot, dict) else {"ready": False, "state": "ARMED"})


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day_str = datetime.now(_ET).strftime("%Y-%m-%d")
    runtime = {"rendered": False, "ready": False, "diag": {}}
    original_button = st.button
    original_card = v16.v15.step3._layer_card
    original_caption = st.caption
    original_markdown = st.markdown
    def ensure_step17():
        if runtime["rendered"]:
            return
        distribution = st.session_state.get(f"wnba_assists_v16_distribution::{day_str}")
        diag16 = st.session_state.get(f"wnba_assists_v16_diag::{day_str}") or {}
        if not isinstance(distribution, pd.DataFrame):
            distribution = pd.DataFrame()
        step16_ready = bool(diag16.get("ready") and not distribution.empty)
        ready, diag = _render_step17(distribution, step16_ready, day_str)
        runtime.update({"rendered": True, "ready": bool(ready), "diag": dict(diag or {})})
    def fixed_button(label, *args, **kwargs):
        text = str(label)
        if text == "🔄 RECHECK ASSISTS STEPS 2–16":
            ensure_step17()
            text = "🔄 RECHECK ASSISTS STEPS 2–17"
            clicked = original_button(text, *args, **kwargs)
            if clicked:
                st.session_state.pop(_snapshot_key(day_str), None)
                st.session_state.pop(f"wnba_assists_v17_diag::{day_str}", None)
                st.session_state.pop(f"wnba_assists_v17_summary::{day_str}", None)
            return clicked
        return original_button(label, *args, **kwargs)
    def fixed_card(step, label, card_state, note=""):
        number = int(step)
        if number == 17:
            if runtime["ready"]:
                card_state = "✅ LIVE"
                note = "5M actual simulations/player • convergence passed"
            else:
                distribution = st.session_state.get(f"wnba_assists_v16_distribution::{day_str}")
                card_state = "➡️ NEXT" if isinstance(distribution, pd.DataFrame) and not distribution.empty else "🔒 LOCKED"
                note = "5M actual simulations + convergence / sensitivity"
        elif number == 18:
            card_state = "🔒 LOCKED"
            note = "Requires Step-17 PASS + exact Step-13 market line"
        return original_card(step, label, card_state, note)
    def fixed_caption(body, *args, **kwargs):
        text = str(body)
        if text.startswith("⚡ WNBA Assists V16 Step 16"):
            text = text.replace("WNBA Assists V16 Step 16", "WNBA Assists V17 Step 17", 1)
            marker = "Step 16 PASS • analytical distribution • Monte Carlo 0"
            if marker in text:
                state17 = "PASS" if runtime["ready"] else "ARMED"
                text = text.replace(marker, f"Step 16 PASS • Step 17 {state17} • 5M base Monte Carlo/player • market influence 0% • H2H weight 0%")
        return original_caption(text, *args, **kwargs)
    def fixed_markdown(body, *args, **kwargs):
        text = body
        if isinstance(text, str) and "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 16" in text:
            text = text.replace("KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 16", "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 17")
            text = text.replace(
                "Steps 1–15 remain intact. Step 16 calibrates analytical assist-count uncertainty around the independent Step-15 mean. Sportsbook lines/no-vig remain separate and Monte Carlo stays locked for Step 17.",
                "Steps 1–16 remain intact. Step 17 validates the calibrated assist-count model with an actual reproducible 5,000,000-trial Monte Carlo per player, convergence gates and sensitivity checks. Sportsbook lines/no-vig remain separate.",
            )
            text = text.replace("🧠 model branch: Steps 1–12 → 15 → 16", "🧠 model branch: Steps 1–12 → 15 → 16 → 17")
        return original_markdown(text, *args, **kwargs)
    st.button = fixed_button
    v16.v15.step3._layer_card = fixed_card
    st.caption = fixed_caption
    st.markdown = fixed_markdown
    try:
        v16.render_wnba_assists_hub(section_header, status_info, team_logo, h)
        if not runtime["rendered"]:
            ensure_step17()
    finally:
        st.button = original_button
        v16.v15.step3._layer_card = original_card
        st.caption = original_caption
        st.markdown = original_markdown


__all__ = ["MODEL_VERSION", "BASE_SIMS", "BATCH_SIZE", "BATCHES", "_distribution_fingerprint", "_run_monte_carlo", "_render_step17", "render_wnba_assists_hub"]
