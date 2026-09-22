"""WNBA Assists V16 — Step 16 uncertainty + discrete distribution calibration.

Preserves Assists Steps 1–15 and adds an analytical assist-count distribution
on the independent model branch.

Architecture:
MODEL:  Steps 1–12 -> Step 15 -> Step 16 -> Step 17
MARKET: Steps 13–14 -----------------------------> joins at Steps 18/19

Step 16 rules:
- Step 15 must pass; sportsbook availability is irrelevant;
- preserve Step-15 EXPECTED_ASSISTS exactly as the distribution mean;
- calibrate variance from empirical recent assist volatility, minute volatility,
  status risk and Step-15 confidence;
- shrink noisy empirical dispersion toward a Poisson count-process prior;
- use an analytical Binomial / Poisson / Negative-Binomial family depending on
  calibrated under/neutral/over-dispersion;
- expose median, mode, SD, P10/P25/P75/P90/P95 and exact assist-count PMF;
- core rotation players require empirical assist-volatility evidence or the gate
  fails closed;
- H2H remains 0% mean/distribution influence;
- sportsbook line, posted odds and no-vig probabilities remain 0% influence;
- no Monte Carlo samples are drawn here. Step 17 owns actual 5M simulation,
  convergence and sensitivity testing.

No Over/Under grading, fair model odds, EV or ranking is enabled in this step.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v15 as v15

MODEL_VERSION = "WNBA ASSISTS V16 • STEP 16 UNCERTAINTY + DISTRIBUTION CALIBRATION"
_ET = ZoneInfo("America/New_York")
CORE_MINUTES = 10.0
ZERO_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}
RISK_STATUSES = {"QUESTIONABLE", "PROBABLE", "REPORTED", "DAY-TO-DAY"}
MAX_PMF_K = 60


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


def _clip(value: float, lo: float, hi: float) -> float:
    if not np.isfinite(value):
        return float(lo)
    return float(np.clip(value, lo, hi))


def _variance_target(row: pd.Series, mu: float) -> tuple[float, dict[str, Any]]:
    """Empirical count variance shrunk toward a Poisson prior, then risk-adjusted."""
    sd10 = _num(row.get("AST_SD10"))
    hist_mean = _num(row.get("L10_AST"))
    games = _safe_int(row.get("FORM_GAMES"))

    empirical_ok = bool(np.isfinite(sd10) and sd10 >= 0.0 and games >= 5)
    if empirical_ok and np.isfinite(hist_mean) and hist_mean > 0.35:
        raw_fano = (sd10 * sd10) / hist_mean
        raw_fano = _clip(raw_fano, 0.45, 3.50)
        reliability = _clip(0.25 + 0.055 * max(0, min(games, 10) - 5), 0.25, 0.525)
        shrunk_fano = 1.0 + reliability * (raw_fano - 1.0)
    elif empirical_ok:
        raw_fano = 1.0
        reliability = 0.25
        shrunk_fano = 1.0
    else:
        raw_fano = np.nan
        reliability = 0.0
        shrunk_fano = 1.0

    variance = max(0.02, mu * shrunk_fano)

    # Minute uncertainty contributes additional game-level dispersion without
    # moving the Step-15 mean. The coefficient is deliberately conservative.
    min_sd = _num(row.get("MIN_SD10"))
    proj_min = max(0.0, _num(row.get("PROJ_MIN"), 0.0))
    minute_cv = 0.0
    if np.isfinite(min_sd) and min_sd >= 0.0 and proj_min > 1.0:
        minute_cv = _clip(min_sd / max(proj_min, 8.0), 0.0, 0.40)
        variance += (mu * 0.65 * minute_cv) ** 2

    status = str(row.get("AVAILABILITY") or "").upper().strip()
    status_risk = status in RISK_STATUSES or str(row.get("STATUS_RISK") or "").upper() == "YES"
    if status_risk:
        variance *= 1.16

    projection_conf = str(row.get("PROJECTION_CONFIDENCE") or "").upper()
    if projection_conf == "MEDIUM":
        variance *= 1.04
    elif projection_conf == "LOW":
        variance *= 1.10

    if str(row.get("OPPORTUNITY_MODE") or "").upper() != "OFFICIAL WNBA PASSING TRACKING":
        variance *= 1.035

    total_context = abs(_num(row.get("TOTAL_CONTEXT_EFFECT"), 0.0))
    if total_context >= 0.145:
        variance *= 1.03

    # Keep the target physically reasonable for a single-game WNBA assist count.
    lower = max(0.02, 0.45 * mu)
    upper = max(mu + 4.0, 4.0 * mu + 1.0)
    variance = _clip(variance, lower, upper)

    return variance, {
        "empirical_ok": empirical_ok,
        "raw_fano": raw_fano,
        "shrunk_fano": shrunk_fano,
        "reliability": reliability,
        "minute_cv": minute_cv,
        "status_risk": status_risk,
    }


def _poisson_pmf(mu: float) -> tuple[list[float], dict[str, Any]]:
    probs = [float(math.exp(-mu))]
    for k in range(MAX_PMF_K):
        probs.append(probs[-1] * mu / float(k + 1))
    return probs, {"family": "POISSON", "parameter_1": mu, "parameter_2": np.nan}


def _negative_binomial_pmf(mu: float, variance: float) -> tuple[list[float], dict[str, Any]]:
    extra = variance - mu
    if extra <= 1e-9:
        return _poisson_pmf(mu)
    r = (mu * mu) / extra
    if not np.isfinite(r) or r > 2500.0:
        return _poisson_pmf(mu)
    p = r / (r + mu)
    q = 1.0 - p
    p0 = float(math.exp(r * math.log(max(p, 1e-15))))
    probs = [p0]
    for k in range(MAX_PMF_K):
        nxt = probs[-1] * ((k + r) / float(k + 1)) * q
        probs.append(float(max(0.0, nxt)))
    return probs, {
        "family": "NEGATIVE BINOMIAL",
        "parameter_1": float(r),
        "parameter_2": float(p),
    }


def _binomial_pmf(mu: float, variance: float) -> tuple[list[float], dict[str, Any]]:
    denom = max(mu - variance, 1e-9)
    n_float = (mu * mu) / denom
    n = int(max(math.ceil(mu + 1e-9), round(n_float)))
    n = max(n, 1)
    n = min(n, MAX_PMF_K)
    p = _clip(mu / float(n), 1e-9, 1.0 - 1e-9)
    q = 1.0 - p
    probs = [float(q ** n)]
    for k in range(n):
        nxt = probs[-1] * ((n - k) / float(k + 1)) * (p / q)
        probs.append(float(max(0.0, nxt)))
    if len(probs) < MAX_PMF_K + 1:
        probs.extend([0.0] * (MAX_PMF_K + 1 - len(probs)))
    return probs[: MAX_PMF_K + 1], {
        "family": "BINOMIAL",
        "parameter_1": int(n),
        "parameter_2": float(p),
    }


def _distribution_pmf(mu: float, target_variance: float):
    if mu <= 1e-10:
        probs = [1.0] + [0.0] * MAX_PMF_K
        return probs, {
            "family": "DEGENERATE ZERO",
            "parameter_1": 0.0,
            "parameter_2": np.nan,
            "actual_variance": 0.0,
        }

    ratio = target_variance / mu
    if ratio >= 1.08:
        probs, pars = _negative_binomial_pmf(mu, target_variance)
        if pars["family"] == "NEGATIVE BINOMIAL":
            actual_variance = target_variance
        else:
            actual_variance = mu
    elif ratio <= 0.90 and mu >= 0.25:
        probs, pars = _binomial_pmf(mu, target_variance)
        n = float(pars["parameter_1"])
        p = float(pars["parameter_2"])
        actual_variance = n * p * (1.0 - p)
    else:
        probs, pars = _poisson_pmf(mu)
        actual_variance = mu

    total = float(sum(probs))
    tail = max(0.0, 1.0 - total)
    # Numerical recurrence can accumulate microscopic error. Only scale down when
    # the truncated total exceeds one; never scale up and erase a legitimate tail.
    if total > 1.0 + 1e-10:
        probs = [p / total for p in probs]
        tail = 0.0

    pars["actual_variance"] = float(actual_variance)
    pars["tail"] = float(tail)
    return probs, pars


def _quantile(probs: list[float], q: float) -> int:
    cumulative = 0.0
    for k, p in enumerate(probs):
        cumulative += float(p)
        if cumulative >= q:
            return int(k)
    return int(len(probs) - 1)


def _distribution_confidence(row: pd.Series, empirical_ok: bool, tail: float) -> tuple[float, str]:
    score = _num(row.get("PROJECTION_CONFIDENCE_SCORE"), 65.0)
    games = _safe_int(row.get("FORM_GAMES"))
    if not empirical_ok:
        score -= 12.0
    elif games >= 8:
        score += 2.0
    else:
        score -= 2.0

    min_sd = _num(row.get("MIN_SD10"))
    if np.isfinite(min_sd):
        if min_sd >= 9.0:
            score -= 7.0
        elif min_sd >= 6.5:
            score -= 3.0

    if tail > 0.001:
        score -= 4.0
    score = float(np.clip(score, 30.0, 95.0))
    if score >= 82.0:
        label = "HIGH"
    elif score >= 67.0:
        label = "MEDIUM"
    else:
        label = "LOW"
    return score, label


def _build_step16_distribution(
    projection_rows: pd.DataFrame,
    step15_ready: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not step15_ready:
        return pd.DataFrame(), {
            "ready": False,
            "state": "LOCKED",
            "reason": "Step 15 has not passed",
            "core_players": 0,
            "core_distributions": 0,
            "simulations": 0,
        }
    if projection_rows is None or projection_rows.empty:
        return pd.DataFrame(), {
            "ready": False,
            "state": "CHECK",
            "reason": "Step 15 supplied no projection rows",
            "core_players": 0,
            "core_distributions": 0,
            "simulations": 0,
        }

    out = projection_rows.copy()
    for col in (
        "TARGET_VARIANCE", "CALIBRATED_VARIANCE", "DISTRIBUTION_SD",
        "DISPERSION_RATIO", "P10_ASSISTS", "P25_ASSISTS", "MEDIAN_ASSISTS",
        "P75_ASSISTS", "P90_ASSISTS", "P95_ASSISTS", "MODE_ASSISTS",
        "DIST_PARAM_1", "DIST_PARAM_2", "DIST_TAIL_PROB",
        "DISTRIBUTION_CONFIDENCE_SCORE",
    ):
        out[col] = np.nan
    out["DISTRIBUTION_FAMILY"] = "UNAVAILABLE"
    out["DISTRIBUTION_CONFIDENCE"] = "UNAVAILABLE"
    out["DISTRIBUTION_STATE"] = "CHECK"
    out["DISTRIBUTION_REASON"] = ""
    out["ASSIST_PMF"] = None
    out["DISTRIBUTION_SOURCE"] = (
        "Step 15 mean + Step 6 assist volatility + Step 4 minute volatility • analytical count distribution"
    )
    out["DISTRIBUTION_VERSION"] = MODEL_VERSION
    out["MARKET_INFLUENCE_STEP16"] = "0%"
    out["H2H_INFLUENCE_STEP16"] = "0%"

    core_total = 0
    core_done = 0
    active_done = 0
    missing_core: list[str] = []
    family_counts: dict[str, int] = {}
    conf_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    empirical_count = 0
    max_tail = 0.0

    for idx, row in out.iterrows():
        availability = str(row.get("AVAILABILITY") or "UNKNOWN").upper().strip()
        proj_min = _num(row.get("PROJ_MIN"), 0.0)
        projection_state = str(row.get("PROJECTION_STATE") or "").upper()
        is_active = bool(proj_min > 0.25 and availability not in ZERO_STATUSES and projection_state == "PASS")
        is_core = bool(proj_min >= CORE_MINUTES and availability not in ZERO_STATUSES)
        if is_core:
            core_total += 1

        if not is_active:
            if projection_state.startswith("ZERO") or availability in ZERO_STATUSES or proj_min <= 0.25:
                out.at[idx, "DISTRIBUTION_STATE"] = "ZERO / INACTIVE"
                out.at[idx, "DISTRIBUTION_REASON"] = "no active Step-15 projection"
            else:
                out.at[idx, "DISTRIBUTION_REASON"] = "Step-15 projection not PASS"
                if is_core:
                    missing_core.append(f"{row.get('PLAYER_NAME', 'Player')}: Step-15 projection not PASS")
            continue

        mu = _num(row.get("EXPECTED_ASSISTS"))
        if not np.isfinite(mu) or mu < 0.0:
            out.at[idx, "DISTRIBUTION_REASON"] = "invalid Step-15 expected assists"
            if is_core:
                missing_core.append(f"{row.get('PLAYER_NAME', 'Player')}: invalid expected assists")
            continue

        target_variance, vdiag = _variance_target(row, float(mu))
        if is_core and not bool(vdiag.get("empirical_ok")):
            out.at[idx, "DISTRIBUTION_REASON"] = "missing empirical recent assist volatility"
            missing_core.append(f"{row.get('PLAYER_NAME', 'Player')}: missing empirical assist volatility")
            continue

        probs, pars = _distribution_pmf(float(mu), float(target_variance))
        tail = float(pars.get("tail") or 0.0)
        actual_variance = float(pars.get("actual_variance") or 0.0)
        sd = math.sqrt(max(0.0, actual_variance))
        median = _quantile(probs, 0.50)
        mode = int(np.argmax(np.asarray(probs, dtype=float)))
        p10 = _quantile(probs, 0.10)
        p25 = _quantile(probs, 0.25)
        p75 = _quantile(probs, 0.75)
        p90 = _quantile(probs, 0.90)
        p95 = _quantile(probs, 0.95)
        conf_score, conf_label = _distribution_confidence(row, bool(vdiag.get("empirical_ok")), tail)

        family = str(pars.get("family") or "UNAVAILABLE")
        pmf_dict = {int(k): float(p) for k, p in enumerate(probs) if p > 1e-12}

        out.at[idx, "TARGET_VARIANCE"] = target_variance
        out.at[idx, "CALIBRATED_VARIANCE"] = actual_variance
        out.at[idx, "DISTRIBUTION_SD"] = sd
        out.at[idx, "DISPERSION_RATIO"] = actual_variance / mu if mu > 1e-9 else 0.0
        out.at[idx, "P10_ASSISTS"] = p10
        out.at[idx, "P25_ASSISTS"] = p25
        out.at[idx, "MEDIAN_ASSISTS"] = median
        out.at[idx, "P75_ASSISTS"] = p75
        out.at[idx, "P90_ASSISTS"] = p90
        out.at[idx, "P95_ASSISTS"] = p95
        out.at[idx, "MODE_ASSISTS"] = mode
        out.at[idx, "DIST_PARAM_1"] = _num(pars.get("parameter_1"))
        out.at[idx, "DIST_PARAM_2"] = _num(pars.get("parameter_2"))
        out.at[idx, "DIST_TAIL_PROB"] = tail
        out.at[idx, "DISTRIBUTION_CONFIDENCE_SCORE"] = conf_score
        out.at[idx, "DISTRIBUTION_FAMILY"] = family
        out.at[idx, "DISTRIBUTION_CONFIDENCE"] = conf_label
        out.at[idx, "DISTRIBUTION_STATE"] = "PASS"
        out.at[idx, "DISTRIBUTION_REASON"] = ""
        out.at[idx, "ASSIST_PMF"] = pmf_dict

        active_done += 1
        if is_core:
            core_done += 1
        if bool(vdiag.get("empirical_ok")):
            empirical_count += 1
        family_counts[family] = family_counts.get(family, 0) + 1
        conf_counts[conf_label] = conf_counts.get(conf_label, 0) + 1
        max_tail = max(max_tail, tail)

    ready = bool(core_total > 0 and core_done == core_total and not missing_core)
    return out, {
        "ready": ready,
        "state": "VERIFIED" if ready else "CHECK",
        "reason": "" if ready else "one or more core rotation players lack a calibrated assist distribution",
        "core_players": core_total,
        "core_distributions": core_done,
        "active_distributions": active_done,
        "empirical_volatility_players": empirical_count,
        "family_counts": family_counts,
        "high_confidence": conf_counts.get("HIGH", 0),
        "medium_confidence": conf_counts.get("MEDIUM", 0),
        "low_confidence": conf_counts.get("LOW", 0),
        "missing_core": missing_core[:12],
        "max_tail_probability": max_tail,
        "market_influence": 0.0,
        "h2h_weight": 0.0,
        "simulations": 0,
    }


def _render_exact_probability_expander(distribution: pd.DataFrame):
    passed = distribution.loc[distribution.get("DISTRIBUTION_STATE", pd.Series("", index=distribution.index)).eq("PASS")].copy()
    if passed.empty:
        return
    with st.expander("🔢 Step-16 exact assist-count probability table", expanded=False):
        rows: list[dict[str, Any]] = []
        for _, row in passed.iterrows():
            pmf = row.get("ASSIST_PMF") if isinstance(row.get("ASSIST_PMF"), dict) else {}
            rec: dict[str, Any] = {
                "Player": str(row.get("PLAYER_NAME") or ""),
                "Team": str(row.get("TEAM_ABBREVIATION") or row.get("TEAM_NAME") or ""),
            }
            for k in range(0, 11):
                rec[f"P({k})"] = f"{100.0 * float(pmf.get(k, 0.0)):.1f}%"
            eleven_plus = max(0.0, 1.0 - sum(float(pmf.get(k, 0.0)) for k in range(0, 11)))
            rec["P(11+)"] = f"{100.0 * eleven_plus:.1f}%"
            rows.append(rec)
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("Exact integer-count probabilities only. These are not sportsbook Over/Under probabilities; line-specific grading remains locked until Step 18.")


def _render_step16(
    projection_rows: pd.DataFrame,
    step15_ready: bool,
    day_str: str,
) -> tuple[bool, pd.DataFrame, dict[str, Any]]:
    st.markdown("### 🎛️ Step 16 — Uncertainty + Distribution Calibration")
    st.caption(
        "Step 16 keeps the Step-15 expected-assists mean fixed and calibrates only uncertainty around it. Recent assist volatility, minute volatility and availability/confidence risk determine an analytical discrete count distribution. No sportsbook line and no Monte Carlo sample enters this layer."
    )

    distribution, diag = _build_step16_distribution(projection_rows, step15_ready)
    ready = bool(diag.get("ready"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Core projections", int(diag.get("core_players") or 0))
    c2.metric(
        "Core distributions",
        f"{int(diag.get('core_distributions') or 0)}/{int(diag.get('core_players') or 0)}",
    )
    c3.metric("Market influence", "0%")
    c4.metric("Simulations", "0")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Active distributions", int(diag.get("active_distributions") or 0))
    d2.metric("Empirical volatility", int(diag.get("empirical_volatility_players") or 0))
    d3.metric("High confidence", int(diag.get("high_confidence") or 0))
    d4.metric("Max PMF tail", f"{100.0 * float(diag.get('max_tail_probability') or 0.0):.3f}%")

    if ready:
        st.success(
            "✅ STEP 16 PASSED • every core rotation projection now has a calibrated discrete assist-count distribution. Step-15 means were preserved exactly; sportsbook/H2H influence remains 0%, and no Monte Carlo samples were drawn."
        )
    else:
        st.warning(
            f"⚠️ STEP 16 CHECK • {diag.get('reason') or 'distribution inputs incomplete'}. Step 17 remains locked."
        )
        if diag.get("missing_core"):
            st.caption("Core distribution holds: " + " • ".join(diag["missing_core"][:6]))

    if distribution is not None and not distribution.empty:
        view = distribution.loc[distribution["DISTRIBUTION_STATE"].eq("PASS")].copy()
        if not view.empty:
            view["Player"] = view["PLAYER_NAME"].astype(str)
            view["Team"] = view.get("TEAM_ABBREVIATION", view.get("TEAM_NAME", pd.Series("", index=view.index))).astype(str)
            view["Opponent"] = view.get("OPPONENT", pd.Series("", index=view.index)).astype(str)
            view["Expected AST"] = pd.to_numeric(view["EXPECTED_ASSISTS"], errors="coerce").round(2)
            view["Median"] = pd.to_numeric(view["MEDIAN_ASSISTS"], errors="coerce").round(0).astype("Int64")
            view["Mode"] = pd.to_numeric(view["MODE_ASSISTS"], errors="coerce").round(0).astype("Int64")
            view["SD"] = pd.to_numeric(view["DISTRIBUTION_SD"], errors="coerce").round(2)
            view["P10"] = pd.to_numeric(view["P10_ASSISTS"], errors="coerce").round(0).astype("Int64")
            view["P90"] = pd.to_numeric(view["P90_ASSISTS"], errors="coerce").round(0).astype("Int64")
            view["P95"] = pd.to_numeric(view["P95_ASSISTS"], errors="coerce").round(0).astype("Int64")
            view["Dispersion"] = pd.to_numeric(view["DISPERSION_RATIO"], errors="coerce").round(2)
            view["Family"] = view["DISTRIBUTION_FAMILY"].astype(str)
            view["Confidence"] = view["DISTRIBUTION_CONFIDENCE"].astype(str)
            view = view.sort_values(["EXPECTED_ASSISTS", "DISTRIBUTION_CONFIDENCE_SCORE"], ascending=[False, False])
            st.dataframe(
                view[["Player", "Team", "Opponent", "Expected AST", "Median", "Mode", "SD", "P10", "P90", "P95", "Dispersion", "Family", "Confidence"]],
                hide_index=True,
                use_container_width=True,
            )
            _render_exact_probability_expander(distribution)

    if distribution is not None and not distribution.empty and ready:
        st.session_state[f"wnba_assists_v16_distribution::{day_str}"] = distribution.copy()
        st.session_state[f"wnba_assists_v16_diag::{day_str}"] = dict(diag)

    with st.expander("🧪 Step-16 uncertainty / calibration methodology", expanded=False):
        st.write("• Mean is copied exactly from Step 15; Step 16 cannot move EXPECTED_ASSISTS.")
        st.write("• Empirical recent assist variance comes from Step-6 AST_SD10 and is shrunk toward a Poisson variance prior according to sample size.")
        st.write("• Step-4 minute volatility adds a conservative variance component without changing the mean.")
        st.write("• Same-day status risk and lower Step-15 confidence widen uncertainty; they do not change the mean.")
        st.write("• Under-dispersed targets use an analytical Binomial family; near-Poisson targets use Poisson; over-dispersed targets use Negative Binomial.")
        st.write("• Core players require empirical recent assist-volatility evidence; no silent synthetic core variance fallback is allowed.")
        st.write("• P10/P25/median/P75/P90/P95 are integer quantiles from the analytical PMF.")
        st.write("• H2H influence: 0%.")
        st.write("• SportsGameOdds / line / price / no-vig influence: 0%.")
        st.write("• Over/Under probability created: NO — Step 18 after the exact market line exists.")
        st.write("• Monte Carlo runs: 0 — Step 17 owns actual 5,000,000-run simulation + convergence/sensitivity.")
        st.write(f"• Distribution families: {diag.get('family_counts', {})}")
        st.write(f"• Core holds: {diag.get('missing_core', [])}")

    return ready, distribution, diag


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Render V15 intact and inject Step 16 immediately before the preserved recheck/build-order block."""
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    runtime: dict[str, Any] = {
        "rendered": False,
        "ready": False,
        "distribution": pd.DataFrame(),
        "diag": {},
    }

    original_button = st.button
    original_card = v15.step3._layer_card
    original_caption = st.caption
    original_markdown = st.markdown

    def ensure_step16():
        if runtime["rendered"]:
            return
        projection = st.session_state.get(f"wnba_assists_v15_projection::{slate_day}")
        diag15 = st.session_state.get(f"wnba_assists_v15_diag::{slate_day}") or {}
        if not isinstance(projection, pd.DataFrame):
            projection = pd.DataFrame()
        step15_ready = bool(diag15.get("ready") and not projection.empty)
        ready, distribution, diag = _render_step16(projection, step15_ready, slate_day)
        runtime.update({
            "rendered": True,
            "ready": bool(ready),
            "distribution": distribution,
            "diag": dict(diag or {}),
        })

    def fixed_button(label, *args, **kwargs):
        text = str(label)
        if text == "🔄 RECHECK ASSISTS STEPS 2–15":
            ensure_step16()
            text = "🔄 RECHECK ASSISTS STEPS 2–16"
            clicked = original_button(text, *args, **kwargs)
            if clicked:
                st.session_state.pop(f"wnba_assists_v16_distribution::{slate_day}", None)
                st.session_state.pop(f"wnba_assists_v16_diag::{slate_day}", None)
            return clicked
        return original_button(label, *args, **kwargs)

    def fixed_card(step, label, card_state, note=""):
        number = int(step)
        if number == 16:
            if runtime["ready"]:
                card_state = "✅ LIVE"
                note = "Analytical discrete assist distribution • market influence 0%"
            else:
                projection = st.session_state.get(f"wnba_assists_v15_projection::{slate_day}")
                card_state = "⚠️ CHECK" if isinstance(projection, pd.DataFrame) and not projection.empty else "🔒 LOCKED"
        elif number == 17:
            card_state = "➡️ NEXT" if runtime["ready"] else "🔒 LOCKED"
            note = "5M actual simulations + convergence / sensitivity"
        return original_card(step, label, card_state, note)

    def fixed_caption(body, *args, **kwargs):
        text = str(body)
        if text.startswith("⚡ WNBA Assists V15 Step 15"):
            text = text.replace("WNBA Assists V15 Step 15", "WNBA Assists V16 Step 16", 1)
            text = text.replace(
                "market influence 0% • H2H weight 0% • no distribution/Monte Carlo yet",
                f"market influence 0% • H2H weight 0% • Step 16 {'PASS' if runtime['ready'] else 'CHECK'} • analytical distribution • Monte Carlo 0",
            )
        return original_caption(text, *args, **kwargs)

    def fixed_markdown(body, *args, **kwargs):
        text = body
        if isinstance(text, str) and "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 15" in text:
            text = text.replace(
                "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 15",
                "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 16",
            )
            text = text.replace(
                "Steps 1–14 remain intact. Step 15 activates the independent expected-assists model from verified basketball inputs only. Sportsbook lines/no-vig stay on their separate market branch and have 0% influence on the projection.",
                "Steps 1–15 remain intact. Step 16 calibrates analytical assist-count uncertainty around the independent Step-15 mean. Sportsbook lines/no-vig remain separate and Monte Carlo stays locked for Step 17.",
            )
            text = text.replace(
                "🧠 model branch: Steps 1–12 → 15",
                "🧠 model branch: Steps 1–12 → 15 → 16",
            )
        return original_markdown(text, *args, **kwargs)

    st.button = fixed_button
    v15.step3._layer_card = fixed_card
    st.caption = fixed_caption
    st.markdown = fixed_markdown
    try:
        v15.render_wnba_assists_hub(section_header, status_info, team_logo, h)
        # Defensive fallback: if the preserved button path ever changes, still
        # render Step 16 once rather than silently skipping the layer.
        if not runtime["rendered"]:
            ensure_step16()
    finally:
        st.button = original_button
        v15.step3._layer_card = original_card
        st.caption = original_caption
        st.markdown = original_markdown


__all__ = [
    "MODEL_VERSION",
    "_build_step16_distribution",
    "_render_step16",
    "render_wnba_assists_hub",
]
