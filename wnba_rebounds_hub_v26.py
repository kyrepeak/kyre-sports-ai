"""WNBA Rebounds V2.6 — Step 17 Monte Carlo + convergence / sensitivity.

Extends the verified V2.5 chain without changing Steps 1-16.

Step-17 rules:
- Simulate only from the verified Step-16 market-independent rebound PMF.
- Base simulation count is 5,000,000 trials per player, matching the production
  standard analysis rule.
- Use deterministic player-specific seeds and 20 batches for reproducibility and
  convergence diagnostics.
- Multinomial occupancy sampling is used: it is mathematically equivalent to
  drawing N independent categorical rebound outcomes from the Step-16 PMF, but
  avoids allocating millions of individual draws in memory.
- Report Monte Carlo mean/SD/median/mode/P10/P90, Monte Carlo SE, maximum batch
  mean deviation, and total-variation distance versus the analytic PMF.
- Run bounded ±5% mean sensitivity scenarios while preserving the Step-16
  variance/mean ratio; these scenarios remain market-independent.
- Sportsbook lines/no-vig are not Monte Carlo inputs. Line-specific Over/Under
  probability remains deferred to the next layer.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v25 as base

MODEL_VERSION = "WNBA REBOUNDS V2.6 • STEP 17 MONTE CARLO + CONVERGENCE / SENSITIVITY"
BASE_SIMULATIONS = 5_000_000
BATCHES = 20
BATCH_SIZE = BASE_SIMULATIONS // BATCHES
SENSITIVITY_PCT = 0.05
MEAN_TOL_ABS = 0.03
TV_TOL = 0.01


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _seed_for(player: str, team: str) -> int:
    raw = f"WNBA-REB-V26|20260819|{player}|{team}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:8], "big") % (2**32 - 1)


def _quantile_from_counts(counts: np.ndarray, q: float):
    total = int(np.sum(counts))
    if total <= 0:
        return np.nan
    target = q * total
    cdf = np.cumsum(counts)
    return int(np.searchsorted(cdf, target, side="left"))


def _pmf_lookup():
    pmf_rows = pd.DataFrame(st.session_state.get("wnba_rebounds_step16_pmf") or [])
    if pmf_rows.empty:
        return {}
    buckets = {}
    for _, r in pmf_rows.iterrows():
        key = (_norm(r.get("Player")), _norm(r.get("Team")))
        if not key[0] or not key[1]:
            continue
        buckets.setdefault(key, []).append((int(r.get("Rebounds") or 0), _num(r.get("Probability"), 0.0)))

    out = {}
    for key, pairs in buckets.items():
        kmax = max(k for k, _ in pairs)
        pmf = np.zeros(kmax + 1, dtype=float)
        for k, p in pairs:
            if k >= 0 and np.isfinite(p) and p > 0:
                pmf[k] += float(p)
        s = float(pmf.sum())
        if s > 0:
            out[key] = pmf / s
    return out


def _simulate_from_pmf(pmf: np.ndarray, seed: int):
    if pmf is None or len(pmf) == 0 or not np.isfinite(pmf).all() or pmf.sum() <= 0:
        return {"ok": False}
    pmf = np.asarray(pmf, dtype=float)
    pmf = pmf / pmf.sum()
    rng = np.random.default_rng(int(seed))
    total_counts = np.zeros(len(pmf), dtype=np.int64)
    batch_means = []

    for _ in range(BATCHES):
        counts = rng.multinomial(BATCH_SIZE, pmf)
        total_counts += counts
        ks = np.arange(len(pmf), dtype=float)
        batch_means.append(float(np.dot(ks, counts) / BATCH_SIZE))

    n = int(total_counts.sum())
    ks = np.arange(len(pmf), dtype=float)
    empirical = total_counts.astype(float) / float(n)
    mean = float(np.dot(ks, empirical))
    var = float(np.dot((ks - mean) ** 2, empirical))
    sd = math.sqrt(max(0.0, var))
    se = sd / math.sqrt(float(n)) if n > 0 else np.nan
    median = _quantile_from_counts(total_counts, 0.50)
    p10 = _quantile_from_counts(total_counts, 0.10)
    p90 = _quantile_from_counts(total_counts, 0.90)
    mode = int(np.argmax(total_counts))
    max_batch_dev = max(abs(x - mean) for x in batch_means) if batch_means else np.nan
    tv = 0.5 * float(np.abs(empirical - pmf).sum())

    return {
        "ok": True,
        "counts": total_counts,
        "empirical": empirical,
        "n": n,
        "mean": mean,
        "var": var,
        "sd": sd,
        "se": se,
        "median": median,
        "mode": mode,
        "p10": p10,
        "p90": p90,
        "max_batch_dev": max_batch_dev,
        "tv": tv,
        "batch_means": batch_means,
    }


def _sensitivity(mu: float, variance: float):
    if not np.isfinite(mu) or mu < 0 or not np.isfinite(variance) or variance < 0:
        return {"ok": False}
    ratio = variance / mu if mu > 1e-9 else 1.0
    rows = []
    for label, mult in (("LOW -5%", 1.0 - SENSITIVITY_PCT), ("BASE", 1.0), ("HIGH +5%", 1.0 + SENSITIVITY_PCT)):
        m = max(0.0, mu * mult)
        v = max(m, ratio * m) if m > 0 else 0.0
        dist = base._distribution(m, v)
        rows.append({
            "Scenario": label,
            "Mean REB": m,
            "Variance": v,
            "Median REB": dist.get("q50", np.nan),
            "P10 REB": dist.get("q10", np.nan),
            "P90 REB": dist.get("q90", np.nan),
            "Model": dist.get("model", "CHECK"),
            "State": "VERIFIED" if dist.get("ok") else "CHECK",
        })
    return {"ok": all(r["State"] == "VERIFIED" for r in rows), "rows": rows}


def _build_step17():
    step16 = pd.DataFrame(st.session_state.get("wnba_rebounds_step16_players") or [])
    step16_ready = bool(st.session_state.get("wnba_rebounds_step16_ready"))
    pmfs = _pmf_lookup()

    if step16.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": 0, "covered": 0, "pmf_joins": 0,
            "simulations": 0, "reason": "no verified Step-16 frame",
        }

    rows = []
    sens_rows = []
    pmf_joins = 0

    for _, p in step16.iterrows():
        key = (_norm(p.get("Player")), _norm(p.get("Team")))
        pmf = pmfs.get(key)
        pmf_ok = pmf is not None
        if pmf_ok:
            pmf_joins += 1

        seed = _seed_for(str(p.get("Player") or ""), str(p.get("Team") or ""))
        sim = _simulate_from_pmf(pmf, seed) if pmf_ok else {"ok": False}
        analytic_mean = _num(p.get("Expected REB"))
        mean_error = abs(_num(sim.get("mean")) - analytic_mean) if sim.get("ok") and np.isfinite(analytic_mean) else np.nan
        batch_limit = max(0.05, 6.0 * _num(sim.get("sd"), 0.0) / math.sqrt(BATCH_SIZE)) if sim.get("ok") else np.nan

        convergence = bool(
            sim.get("ok")
            and np.isfinite(mean_error) and mean_error <= MEAN_TOL_ABS
            and np.isfinite(_num(sim.get("tv"))) and _num(sim.get("tv")) <= TV_TOL
            and np.isfinite(_num(sim.get("max_batch_dev"))) and _num(sim.get("max_batch_dev")) <= batch_limit
        )

        sens = _sensitivity(analytic_mean, _num(p.get("Distribution variance target")))
        base_ok = str(p.get("Step16 state") or "") == "VERIFIED"
        verified = bool(base_ok and pmf_ok and convergence and sens.get("ok"))

        out = p.to_dict()
        out.update({
            "MC simulations": int(sim.get("n") or 0),
            "MC batches": BATCHES if sim.get("ok") else 0,
            "MC batch size": BATCH_SIZE if sim.get("ok") else 0,
            "MC seed": seed,
            "MC mean REB": _num(sim.get("mean")),
            "MC SD": _num(sim.get("sd")),
            "MC median REB": sim.get("median", np.nan),
            "MC mode REB": sim.get("mode", np.nan),
            "MC P10 REB": sim.get("p10", np.nan),
            "MC P90 REB": sim.get("p90", np.nan),
            "MC SE mean": _num(sim.get("se")),
            "MC mean error": mean_error,
            "MC max batch mean dev": _num(sim.get("max_batch_dev")),
            "MC batch limit": batch_limit,
            "MC total variation": _num(sim.get("tv")),
            "MC convergence": "PASS" if convergence else "CHECK",
            "MC market input": False,
            "Step17 state": "VERIFIED" if verified else "CHECK",
        })
        rows.append(out)

        for r in sens.get("rows", []):
            sens_rows.append({
                "Player": str(p.get("Player") or "Player"),
                "Team": str(p.get("Team") or ""),
                **r,
            })

    frame = pd.DataFrame(rows)
    sensitivity = pd.DataFrame(sens_rows)
    covered = int(frame["Step17 state"].eq("VERIFIED").sum()) if not frame.empty else 0
    ready = bool(
        step16_ready
        and not frame.empty
        and covered == len(frame)
        and pmf_joins == len(frame)
        and frame["MC market input"].eq(False).all()
    )

    max_mean_error = pd.to_numeric(frame.get("MC mean error"), errors="coerce").max() if not frame.empty else np.nan
    max_tv = pd.to_numeric(frame.get("MC total variation"), errors="coerce").max() if not frame.empty else np.nan
    max_batch = pd.to_numeric(frame.get("MC max batch mean dev"), errors="coerce").max() if not frame.empty else np.nan

    return frame, sensitivity, {
        "ready": ready,
        "players": int(len(frame)),
        "covered": covered,
        "pmf_joins": pmf_joins,
        "simulations_per_player": BASE_SIMULATIONS,
        "batches": BATCHES,
        "max_mean_error": _num(max_mean_error),
        "max_tv": _num(max_tv),
        "max_batch_dev": _num(max_batch),
        "market_input": False,
        "network_requests": 0,
    }


def _render_step17():
    st.markdown("## 🎲 Step 17 — Monte Carlo Simulation + Convergence / Sensitivity")
    st.caption(
        "This layer runs 5,000,000 market-independent rebound trials per verified player from the Step-16 count "
        "distribution. Trials are aggregated with exact multinomial occupancy sampling in 20 reproducible batches, "
        "which is mathematically equivalent to five million independent categorical draws without storing every draw. "
        "Sportsbook lines and no-vig probabilities remain excluded."
    )

    frame, sensitivity, info = _build_step17()
    ready = bool(info.get("ready"))

    st.session_state["wnba_rebounds_step17_ready"] = ready
    st.session_state["wnba_rebounds_step17_players"] = frame.to_dict("records") if not frame.empty else []
    st.session_state["wnba_rebounds_step17_sensitivity"] = sensitivity.to_dict("records") if not sensitivity.empty else []

    a, b, c, d = st.columns(4)
    a.metric("Player simulations", f"{info.get('covered',0)}/{info.get('players',0)}")
    b.metric("Trials / player", f"{BASE_SIMULATIONS:,}")
    c.metric("Batches", BATCHES)
    d.metric("Market input", "NONE")

    if ready:
        st.success(
            "✅ STEP 17 PASSED • all verified players completed 5,000,000 simulations with convergence and ±5% "
            "sensitivity checks passing. Step 18 (line-specific Over/Under probability + fair odds) is unlocked."
        )
    else:
        st.error(
            "⛔ STEP 17 CHECK • at least one player failed PMF reconciliation, Monte Carlo convergence, or sensitivity. "
            "The app will not advance to line-specific probabilities until every simulated player passes."
        )

    if not frame.empty:
        show = frame.copy()
        for col in [
            "Expected REB", "MC mean REB", "MC SD", "MC SE mean", "MC mean error",
            "MC max batch mean dev", "MC total variation",
        ]:
            if col in show.columns:
                show[col] = pd.to_numeric(show[col], errors="coerce").round(4)
        cols = [c for c in [
            "Player", "Team", "Opponent", "Expected REB", "MC mean REB", "MC SD",
            "MC median REB", "MC mode REB", "MC P10 REB", "MC P90 REB",
            "MC SE mean", "MC max batch mean dev", "MC total variation",
            "MC convergence", "Step17 state",
        ] if c in show.columns]
        st.dataframe(show[cols], hide_index=True, use_container_width=True)

    with st.expander("🎲 Monte Carlo convergence diagnostics"):
        if frame.empty:
            st.info("No Step-17 simulation rows available.")
        else:
            cols = [c for c in [
                "Player", "Team", "MC simulations", "MC batches", "MC batch size", "MC seed",
                "MC mean error", "MC SE mean", "MC max batch mean dev", "MC batch limit",
                "MC total variation", "MC convergence", "Step17 state",
            ] if c in frame.columns]
            diag = frame[cols].copy()
            st.dataframe(diag, hide_index=True, use_container_width=True)

    with st.expander("🎲 ±5% projection sensitivity"):
        if sensitivity.empty:
            st.info("No sensitivity rows available.")
        else:
            s = sensitivity.copy()
            for col in ["Mean REB", "Variance"]:
                if col in s.columns:
                    s[col] = pd.to_numeric(s[col], errors="coerce").round(3)
            st.dataframe(s, hide_index=True, use_container_width=True)

    with st.expander("🎲 Step-17 methodology / diagnostics"):
        st.write({
            "base_simulations_per_player": BASE_SIMULATIONS,
            "batches": BATCHES,
            "batch_size": BATCH_SIZE,
            "sampling": "multinomial occupancy = exact aggregate of iid categorical draws from Step-16 PMF",
            "seed": "deterministic SHA-256 Player+Team seed",
            "convergence": {
                "absolute_mean_error_max": MEAN_TOL_ABS,
                "total_variation_max": TV_TOL,
                "batch_mean_limit": "max(0.05, 6 × batch mean SE)",
            },
            "sensitivity": "Expected REB ±5%; Step-16 variance/mean ratio preserved",
            "sportsbook_line_used": False,
            "no_vig_used": False,
            "market_probability_used": False,
            "new_network_requests": 0,
        })

    st.markdown("## 🧱 Rebounds Build Order — Current")
    layers = [
        "Verified daily WNBA slate",
        "Current rosters + injuries/status",
        "Projected minutes + rotation",
        "Offensive/defensive rebound role",
        "Recent + season rebound form",
        "Rebound chances/opportunities",
        "Opponent missed-shot environment",
        "Opponent rebounding allowed",
        "Position matchup — Guard/Wing/Big",
        "Pace + expected shot volume",
        "Lineup effects / rebound competition",
        "Player vs opponent rebound history",
        "Exact SportsGameOdds rebound lines",
        "Same-book no-vig",
        "Market-independent rebound projection synthesis",
        "Uncertainty + rebound distribution calibration",
        "Monte Carlo simulation + convergence / sensitivity",
        "Line-specific Over/Under probability + fair odds",
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ BASELINE",
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 19), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V2.6 Step 17 only • Steps 1–16 preserved • 5,000,000 simulations/player • 20 batches • "
        "deterministic seeds • convergence + ±5% sensitivity • zero new network requests • market input NONE."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step16_ready"):
        _render_step17()
    else:
        st.info("Step 17 remains locked until Step 16 is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
