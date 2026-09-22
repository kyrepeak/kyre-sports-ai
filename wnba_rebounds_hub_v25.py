"""WNBA Rebounds V2.5 — Step 16 uncertainty + rebound distribution calibration.

Extends the verified V2.4.1 chain without changing Steps 1-15.

Step-16 rules:
- Start from the verified Step-15 market-independent expected rebound mean.
- Reconcile recent/season rebound-rate anchors directly from the verified Step-5
  player frame by unique Player+Team identity; never guess ambiguous identities.
- Estimate model uncertainty from disagreement across verified season/L10/L5/
  Step-4 rebound-rate anchors, scaled to projected minutes.
- Add a small structural count-variance floor so the count distribution is not
  unrealistically narrow when rate windows happen to agree exactly.
- Build a non-negative integer count distribution analytically (Negative Binomial
  when overdispersed; Poisson only when variance is effectively equal to mean).
- Preserve the Step-15 expected mean; validate PMF normalization and mean
  reconciliation before a player is marked VERIFIED.
- Sportsbook lines/no-vig remain excluded. No Monte Carlo is run in this step.
"""
from __future__ import annotations

import math
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v241 as base

MODEL_VERSION = "WNBA REBOUNDS V2.5 • STEP 16 UNCERTAINTY + REBOUND DISTRIBUTION CALIBRATION"
STRUCTURAL_VARIANCE_MULT = 1.10
MAX_VARIANCE_RATIO = 3.00
PMF_MAX_K = 80
MEAN_TOLERANCE = 0.05


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


def _unique_lookup(frame: pd.DataFrame, name_col: str, team_col: str):
    if frame is None or frame.empty:
        return {}
    buckets = {}
    for idx, row in frame.iterrows():
        key = (_norm(row.get(name_col)), _norm(row.get(team_col)))
        if key[0] and key[1]:
            buckets.setdefault(key, []).append(idx)
    return {key: frame.loc[idxs[0]] for key, idxs in buckets.items() if len(idxs) == 1}


def _rate_anchor_stats(step5_row: pd.Series | None, proj_min: float):
    if step5_row is None:
        return {
            "source_ok": False,
            "anchor_count": 0,
            "rate_sd36": np.nan,
            "count_sd": np.nan,
            "source": "CHECK",
        }

    candidates = []
    labels = []
    for col, label in (
        ("FORM_SEASON_REB36", "SEASON"),
        ("FORM_L10_REB36", "L10"),
        ("FORM_L5_REB36", "L5"),
        ("FORM_STEP4_RECENT_REB36", "STEP4"),
        ("REB36", "STEP4 ROLE"),
    ):
        v = _num(step5_row.get(col))
        if np.isfinite(v) and v >= 0:
            # Avoid adding the same Step-4 rate twice when compatibility columns match.
            if not candidates or not any(math.isclose(v, x, rel_tol=0.0, abs_tol=1e-9) for x in candidates):
                candidates.append(float(v))
                labels.append(label)

    anchor_count = len(candidates)
    if anchor_count >= 2:
        rate_sd36 = float(np.std(np.asarray(candidates, dtype=float), ddof=1))
        count_sd = rate_sd36 * max(0.0, proj_min) / 36.0
        source = " + ".join(labels)
    elif anchor_count == 1:
        rate_sd36 = 0.0
        count_sd = 0.0
        source = labels[0] + " • structural variance floor"
    else:
        rate_sd36 = np.nan
        count_sd = np.nan
        source = "VERIFIED PLAYER ID • structural variance floor only"

    return {
        "source_ok": True,
        "anchor_count": anchor_count,
        "rate_sd36": rate_sd36,
        "count_sd": count_sd,
        "source": source,
    }


def _variance_target(mu: float, count_sd: float):
    if not np.isfinite(mu) or mu < 0:
        return np.nan
    if mu <= 1e-9:
        return 0.0

    structural = STRUCTURAL_VARIANCE_MULT * mu
    disagreement_var = count_sd * count_sd if np.isfinite(count_sd) and count_sd >= 0 else 0.0
    raw = structural + disagreement_var
    upper = max(structural, MAX_VARIANCE_RATIO * mu)
    return float(min(upper, max(mu, raw)))


def _poisson_pmf(mu: float, kmax: int):
    if mu <= 1e-12:
        out = np.zeros(kmax + 1, dtype=float)
        out[0] = 1.0
        return out
    ks = np.arange(kmax + 1, dtype=float)
    logs = -mu + ks * math.log(mu) - np.array([math.lgamma(k + 1.0) for k in ks])
    pmf = np.exp(logs)
    s = float(pmf.sum())
    return pmf / s if s > 0 else pmf


def _nb_pmf(mu: float, var: float, kmax: int):
    extra = var - mu
    if mu <= 1e-12 or extra <= 1e-12:
        return _poisson_pmf(mu, kmax), np.nan
    r = mu * mu / extra
    p = r / (r + mu)
    ks = np.arange(kmax + 1, dtype=float)
    logs = np.array([
        math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1.0)
        + r * math.log(p) + k * math.log(1.0 - p)
        for k in ks
    ])
    pmf = np.exp(logs)
    s = float(pmf.sum())
    if s > 0:
        pmf = pmf / s
    return pmf, float(r)


def _quantile_from_pmf(pmf: np.ndarray, q: float):
    if pmf is None or len(pmf) == 0:
        return np.nan
    cdf = np.cumsum(pmf)
    idx = int(np.searchsorted(cdf, q, side="left"))
    return int(min(len(pmf) - 1, max(0, idx)))


def _distribution(mu: float, var: float):
    if not np.isfinite(mu) or mu < 0 or not np.isfinite(var) or var < 0:
        return {"ok": False}

    sd = math.sqrt(max(0.0, var))
    kmax = int(min(PMF_MAX_K, max(30, math.ceil(mu + 8.0 * sd + 8.0))))

    if mu <= 1e-9:
        pmf = np.zeros(kmax + 1, dtype=float)
        pmf[0] = 1.0
        model = "DEGENERATE ZERO"
        nb_size = np.nan
    elif var > mu * 1.02:
        pmf, nb_size = _nb_pmf(mu, var, kmax)
        model = "NEGATIVE BINOMIAL"
    else:
        pmf = _poisson_pmf(mu, kmax)
        model = "POISSON"
        nb_size = np.nan

    if pmf is None or len(pmf) == 0:
        return {"ok": False}
    pmf_sum = float(np.sum(pmf))
    ks = np.arange(len(pmf), dtype=float)
    pmf_mean = float(np.sum(ks * pmf))
    pmf_var = float(np.sum(((ks - pmf_mean) ** 2) * pmf))
    mean_error = abs(pmf_mean - mu)
    ok = bool(
        np.isfinite(pmf_sum) and abs(pmf_sum - 1.0) <= 1e-6
        and np.isfinite(pmf_mean) and mean_error <= MEAN_TOLERANCE
    )

    return {
        "ok": ok,
        "model": model,
        "pmf": pmf,
        "pmf_sum": pmf_sum,
        "pmf_mean": pmf_mean,
        "pmf_var": pmf_var,
        "mean_error": mean_error,
        "sd": math.sqrt(max(0.0, pmf_var)),
        "nb_size": nb_size,
        "mode": int(np.argmax(pmf)),
        "q05": _quantile_from_pmf(pmf, 0.05),
        "q10": _quantile_from_pmf(pmf, 0.10),
        "q25": _quantile_from_pmf(pmf, 0.25),
        "q50": _quantile_from_pmf(pmf, 0.50),
        "q75": _quantile_from_pmf(pmf, 0.75),
        "q90": _quantile_from_pmf(pmf, 0.90),
        "q95": _quantile_from_pmf(pmf, 0.95),
    }


def _build_step16():
    step15 = pd.DataFrame(st.session_state.get("wnba_rebounds_step15_players") or [])
    step5 = pd.DataFrame(st.session_state.get("wnba_rebounds_step5_players") or [])
    step15_ready = bool(st.session_state.get("wnba_rebounds_step15_ready"))

    if step15.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False,
            "players": 0,
            "covered": 0,
            "source_joins": 0,
            "reason": "no verified Step-15 projection frame",
        }

    step5_lookup = _unique_lookup(step5, "PLAYER_NAME", "TEAM_NAME")
    rows = []
    pmf_rows = []
    source_joins = 0

    for _, p in step15.iterrows():
        key = (_norm(p.get("Player")), _norm(p.get("Team")))
        s5 = step5_lookup.get(key)
        source_ok = s5 is not None
        if source_ok:
            source_joins += 1

        mu = _num(p.get("Expected REB"))
        proj_min = _num(p.get("Proj MIN"), _num(s5.get("PROJ_MIN") if s5 is not None else np.nan, 0.0))
        anchor = _rate_anchor_stats(s5, proj_min)
        var = _variance_target(mu, anchor.get("count_sd"))
        dist = _distribution(mu, var)

        base_ok = str(p.get("Step15 state") or "") == "VERIFIED"
        verified = bool(base_ok and source_ok and anchor.get("source_ok") and dist.get("ok"))

        out = p.to_dict()
        out.update({
            "Uncertainty anchor count": int(anchor.get("anchor_count") or 0),
            "Uncertainty source": str(anchor.get("source") or "CHECK"),
            "Rate disagreement SD/36": _num(anchor.get("rate_sd36")),
            "Rate disagreement SD count": _num(anchor.get("count_sd")),
            "Distribution model": str(dist.get("model") or "CHECK"),
            "Distribution variance target": var,
            "Distribution SD": _num(dist.get("sd")),
            "Distribution mean check": _num(dist.get("pmf_mean")),
            "Distribution mean error": _num(dist.get("mean_error")),
            "Median REB": dist.get("q50", np.nan),
            "Mode REB": dist.get("mode", np.nan),
            "Floor REB P10": dist.get("q10", np.nan),
            "Ceiling REB P90": dist.get("q90", np.nan),
            "P05 REB": dist.get("q05", np.nan),
            "P95 REB": dist.get("q95", np.nan),
            "NB size": _num(dist.get("nb_size")),
            "Distribution market input": False,
            "Distribution Monte Carlo": False,
            "Step16 state": "VERIFIED" if verified else "CHECK",
        })
        rows.append(out)

        if verified:
            pmf = dist.get("pmf")
            for k, prob in enumerate(pmf):
                if prob > 1e-8:
                    pmf_rows.append({
                        "Player": str(p.get("Player") or "Player"),
                        "Team": str(p.get("Team") or ""),
                        "Rebounds": int(k),
                        "Probability": float(prob),
                    })

    frame = pd.DataFrame(rows)
    pmfs = pd.DataFrame(pmf_rows)
    covered = int(frame["Step16 state"].eq("VERIFIED").sum()) if not frame.empty else 0
    ready = bool(
        step15_ready
        and not frame.empty
        and covered == len(frame)
        and source_joins == len(frame)
        and frame["Distribution market input"].eq(False).all()
        and frame["Distribution Monte Carlo"].eq(False).all()
    )

    sd_vals = pd.to_numeric(frame.get("Distribution SD"), errors="coerce") if not frame.empty else pd.Series(dtype=float)
    return frame, pmfs, {
        "ready": ready,
        "players": int(len(frame)),
        "covered": covered,
        "source_joins": source_joins,
        "median_sd": float(sd_vals.median()) if sd_vals.notna().any() else np.nan,
        "method": "Step-15 mean + Step-5 multi-window rate disagreement + bounded structural count variance",
        "network_requests": 0,
        "market_input": False,
        "monte_carlo": False,
    }


def _render_step16():
    st.markdown("## 🎯 Step 16 — Uncertainty + Rebound Distribution Calibration")
    st.caption(
        "This layer turns each verified Step-15 expected-rebound mean into a calibrated non-negative integer count "
        "distribution. Uncertainty comes from disagreement across verified rebound-rate windows plus a small structural "
        "count-variance floor. Sportsbook lines and no-vig remain isolated, and Monte Carlo is still OFF."
    )

    frame, pmfs, info = _build_step16()
    ready = bool(info.get("ready"))

    st.session_state["wnba_rebounds_step16_ready"] = ready
    st.session_state["wnba_rebounds_step16_players"] = frame.to_dict("records") if not frame.empty else []
    st.session_state["wnba_rebounds_step16_pmf"] = pmfs.to_dict("records") if not pmfs.empty else []

    a, b, c, d = st.columns(4)
    a.metric("Player distributions", f"{info.get('covered',0)}/{info.get('players',0)}")
    b.metric("Step-5 source joins", f"{info.get('source_joins',0)}/{info.get('players',0)}")
    med_sd = _num(info.get("median_sd"))
    c.metric("Median distribution SD", f"{med_sd:.2f}" if np.isfinite(med_sd) else "—")
    d.metric("Monte Carlo", "OFF")

    if ready:
        st.success(
            "✅ STEP 16 PASSED • every Step-15 projection has a normalized integer rebound distribution, median/mode, "
            "and P10–P90 uncertainty range. Step 17 (Monte Carlo simulation + convergence/sensitivity) is unlocked. "
            "Sportsbook data remains outside the distribution model."
        )
    else:
        st.error(
            "⛔ STEP 16 CHECK • at least one player lacks a unique verified Step-5 uncertainty source or a valid "
            "normalized count distribution. Missing uncertainty inputs are not guessed."
        )

    if not frame.empty:
        show = frame.copy()
        for col in [
            "Expected REB", "Distribution SD", "Distribution mean check",
            "Distribution mean error", "Rate disagreement SD/36",
        ]:
            if col in show.columns:
                show[col] = pd.to_numeric(show[col], errors="coerce").round(3)
        cols = [c for c in [
            "Player", "Team", "Opponent", "Proj MIN", "Expected REB",
            "Distribution model", "Distribution SD", "Median REB", "Mode REB",
            "Floor REB P10", "Ceiling REB P90", "Uncertainty anchor count", "Step16 state",
        ] if c in show.columns]
        st.dataframe(show[cols], hide_index=True, use_container_width=True)

    with st.expander("🎯 Distribution diagnostics"):
        if frame.empty:
            st.info("No Step-16 distribution rows available.")
        else:
            cols = [c for c in [
                "Player", "Team", "Uncertainty source", "Uncertainty anchor count",
                "Rate disagreement SD/36", "Distribution variance target", "Distribution SD",
                "Distribution mean check", "Distribution mean error", "P05 REB", "P95 REB",
                "Step16 state",
            ] if c in frame.columns]
            diag = frame[cols].copy()
            for col in diag.columns:
                if col not in {"Player", "Team", "Uncertainty source", "Step16 state"}:
                    diag[col] = pd.to_numeric(diag[col], errors="coerce").round(4)
            st.dataframe(diag, hide_index=True, use_container_width=True)

    with st.expander("🎯 Step-16 methodology / diagnostics"):
        st.write({
            "mean_source": "verified Step-15 market-independent Expected REB",
            "uncertainty_source": "direct verified Step-5 Player+Team multi-window rebound-rate disagreement",
            "rate_windows": ["season REB/36", "L10 REB/36", "L5 REB/36", "Step-4 recent role REB/36"],
            "variance_formula": "1.10 × mean + squared minute-scaled rate-disagreement SD",
            "variance_cap": f"maximum {MAX_VARIANCE_RATIO:.2f} × mean",
            "count_model": "Negative Binomial when variance > mean; Poisson when approximately equidispersed",
            "mean_reconciliation_tolerance": MEAN_TOLERANCE,
            "sportsbook_line_used": False,
            "no_vig_used": False,
            "market_probability_used": False,
            "monte_carlo_used": False,
            "new_network_requests": 0,
        })
        if not frame.empty and frame["Step16 state"].eq("CHECK").any():
            bad_cols = [c for c in [
                "Player", "Team", "Expected REB", "Uncertainty source",
                "Uncertainty anchor count", "Distribution model", "Distribution mean error", "Step16 state",
            ] if c in frame.columns]
            st.dataframe(frame.loc[frame["Step16 state"].eq("CHECK"), bad_cols], hide_index=True, use_container_width=True)

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
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ BASELINE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 18), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V2.5 Step 16 only • Steps 1–15 preserved • analytic count distribution with verified uncertainty joins • "
        "zero new network requests • sportsbook/no-vig excluded • Monte Carlo still OFF."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step15_ready"):
        _render_step16()
    else:
        st.info("Step 16 remains locked until Step 15 is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
