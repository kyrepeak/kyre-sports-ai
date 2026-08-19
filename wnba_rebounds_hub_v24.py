"""WNBA Rebounds V2.4 — Step 15 market-independent rebound projection synthesis.

Extends the verified V2.3 chain without changing Steps 1-14.

Step-15 rules:
- Build a player rebound mean projection from verified basketball inputs only.
- Sportsbook lines, prices and Step-14 no-vig probabilities are NEVER projection inputs.
- Use the already minute-scaled Step-6/11 capture baseline as the anchor; do not
  re-apply minutes, role or recent-form adjustments that are already embedded.
- Use atomic matchup context only to avoid double counting:
    * Step-10 pace-adjusted opponent missed-shot volume,
    * Step-8 rebound-allowed/capture context,
    * Step-9 opponent same-position competition,
    * Step-11 teammate lineup competition,
    * Step-12 H2H history with strong sample shrinkage.
- Do NOT multiply Step-9's composite position-context index because it already
  contains Step-7/8 information and would double-count environment.
- Clamp every context input and the final context multiplier so one noisy layer
  cannot dominate the baseline.
- This step creates a deterministic expected-rebound mean only. Median,
  distribution tails, Over/Under probability and Monte Carlo are deferred.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v23 as base

MODEL_VERSION = "WNBA REBOUNDS V2.4 • STEP 15 MARKET-INDEPENDENT PROJECTION SYNTHESIS"

# Conservative exponents. Baseline remains dominant.
W_MISS = 0.45
W_ALLOWED = 0.15
W_OPP_POSITION = 0.15
W_LINEUP = 0.15
W_H2H_MAX = 0.10
CONTEXT_MIN = 0.88
CONTEXT_MAX = 1.12


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _clip(value, low, high, default=np.nan):
    x = _num(value, default)
    if not np.isfinite(x):
        return default
    return float(min(high, max(low, x)))


def _positive_factor(value, low, high):
    x = _clip(value, low, high)
    return x if np.isfinite(x) and x > 0 else np.nan


def _inverse_competition_factor(value):
    """Convert a competition index into a bounded opportunity factor.

    A structural zero is valid, but projection arithmetic must not divide by
    zero. We use a 0.50 diagnostic floor and then cap the resulting factor to
    0.85..1.15, so zero competition can never create an outsized projection.
    """
    raw = _num(value)
    if not np.isfinite(raw) or raw < 0:
        return np.nan
    comp = min(1.50, max(0.50, raw))
    inv = 1.0 / comp
    return float(min(1.15, max(0.85, inv)))


def _h2h_factor(row: pd.Series):
    gp = int(max(0, _num(row.get("H2H GP"), 0.0)))
    ratio = _num(row.get("H2H vs current baseline"))
    if gp <= 0 or not np.isfinite(ratio) or ratio <= 0:
        return 1.0, 0.0, "NO SAMPLE"

    ratio = float(min(1.20, max(0.80, ratio)))
    weight = W_H2H_MAX * min(gp, 6) / 6.0
    return ratio, weight, f"{gp} GP • shrunk"


def _projection_components(row: pd.Series):
    baseline = _num(row.get("Capture baseline"))
    miss = _positive_factor(row.get("Step10 expected miss-volume index"), 0.85, 1.15)
    allowed = _positive_factor(row.get("Step8 allowed index"), 0.85, 1.15)
    opp_pos = _inverse_competition_factor(row.get("Same-position competition index"))
    lineup = _inverse_competition_factor(row.get("Lineup competition index"))
    h2h, h2h_weight, h2h_label = _h2h_factor(row)

    core_ok = bool(
        np.isfinite(baseline) and baseline >= 0
        and np.isfinite(miss) and miss > 0
        and np.isfinite(allowed) and allowed > 0
        and np.isfinite(opp_pos) and opp_pos > 0
        and np.isfinite(lineup) and lineup > 0
    )
    if not core_ok:
        return {
            "ok": False,
            "baseline": baseline,
            "miss": miss,
            "allowed": allowed,
            "opp_pos": opp_pos,
            "lineup": lineup,
            "h2h": h2h,
            "h2h_weight": h2h_weight,
            "h2h_label": h2h_label,
            "factor": np.nan,
            "projection": np.nan,
        }

    # Weighted log-space synthesis keeps effects symmetric and prevents one
    # multiplicative layer from dominating the baseline.
    log_factor = (
        W_MISS * math.log(miss)
        + W_ALLOWED * math.log(allowed)
        + W_OPP_POSITION * math.log(opp_pos)
        + W_LINEUP * math.log(lineup)
        + h2h_weight * math.log(h2h)
    )
    factor = float(math.exp(log_factor))
    factor = float(min(CONTEXT_MAX, max(CONTEXT_MIN, factor)))
    projection = float(max(0.0, baseline * factor))

    return {
        "ok": True,
        "baseline": baseline,
        "miss": miss,
        "allowed": allowed,
        "opp_pos": opp_pos,
        "lineup": lineup,
        "h2h": h2h,
        "h2h_weight": h2h_weight,
        "h2h_label": h2h_label,
        "factor": factor,
        "projection": projection,
    }


def _build_step15():
    # Intentionally source Step 12 rather than Step 14. Step 14 is only the gate
    # proving market context is available; its line/price/no-vig data never enter
    # this calculation.
    players12 = pd.DataFrame(st.session_state.get("wnba_rebounds_step12_players") or [])
    step14_ready = bool(st.session_state.get("wnba_rebounds_step14_ready"))

    if players12.empty:
        return pd.DataFrame(), {
            "ready": False,
            "players": 0,
            "covered": 0,
            "market_isolation": True,
            "reason": "no verified Step-12 player frame",
        }

    rows = []
    for _, p in players12.iterrows():
        comp = _projection_components(p)
        base_ok = str(p.get("Step12 state") or "") == "VERIFIED"
        verified = bool(base_ok and comp.get("ok"))

        out = p.to_dict()
        out.update({
            "Projection baseline REB": comp.get("baseline"),
            "Projection miss factor": comp.get("miss"),
            "Projection allowed factor": comp.get("allowed"),
            "Projection opponent-position factor": comp.get("opp_pos"),
            "Projection lineup factor": comp.get("lineup"),
            "Projection H2H factor": comp.get("h2h"),
            "Projection H2H weight": comp.get("h2h_weight"),
            "Projection H2H sample": comp.get("h2h_label"),
            "Projection context factor": comp.get("factor"),
            "Expected REB": comp.get("projection"),
            "Projection market input": False,
            "Step15 state": "VERIFIED" if verified else "CHECK",
        })
        rows.append(out)

    frame = pd.DataFrame(rows)
    covered = int(frame["Step15 state"].eq("VERIFIED").sum()) if not frame.empty else 0
    ready = bool(
        step14_ready
        and not frame.empty
        and covered == len(frame)
        and frame["Projection market input"].eq(False).all()
    )

    expected = pd.to_numeric(frame.get("Expected REB"), errors="coerce") if not frame.empty else pd.Series(dtype=float)
    context = pd.to_numeric(frame.get("Projection context factor"), errors="coerce") if not frame.empty else pd.Series(dtype=float)
    return frame, {
        "ready": ready,
        "players": int(len(frame)),
        "covered": covered,
        "market_isolation": True,
        "mean_projection": float(expected.mean()) if expected.notna().any() else np.nan,
        "min_context": float(context.min()) if context.notna().any() else np.nan,
        "max_context": float(context.max()) if context.notna().any() else np.nan,
        "method": "bounded log-space synthesis anchored to verified minute-scaled rebound baseline",
    }


def _render_step15():
    st.markdown("## 🧠 Step 15 — Market-Independent Rebound Projection Synthesis")
    st.caption(
        "This is the first layer that creates a player expected-rebound mean. The anchor is the already verified, "
        "minute-scaled rebound baseline from the basketball model. Matchup context is added conservatively in log space. "
        "Sportsbook lines, prices and Step-14 no-vig probabilities are explicitly excluded from every projection calculation."
    )

    frame, info = _build_step15()
    ready = bool(info.get("ready"))

    st.session_state["wnba_rebounds_step15_ready"] = ready
    st.session_state["wnba_rebounds_step15_players"] = frame.to_dict("records") if not frame.empty else []

    a, b, c, d = st.columns(4)
    a.metric("Player projections", f"{info.get('covered',0)}/{info.get('players',0)}")
    b.metric("Market isolation", "PASS" if info.get("market_isolation") else "CHECK")
    mean_projection = _num(info.get("mean_projection"))
    c.metric("Slate avg expected REB", f"{mean_projection:.2f}" if np.isfinite(mean_projection) else "—")
    d.metric("New network", "NONE")

    if ready:
        st.success(
            "✅ STEP 15 PASSED • every verified rotation player has a market-independent expected-rebound mean. "
            "Sportsbook/no-vig data remained fully isolated. Step 16 (uncertainty + rebound distribution calibration) "
            "is unlocked. No Over/Under probability or Monte Carlo result exists yet."
        )
    else:
        if not st.session_state.get("wnba_rebounds_step14_ready"):
            st.error("⛔ STEP 15 CHECK • Step 14 is not verified, so the build-order gate remains closed.")
        else:
            st.error(
                "⛔ STEP 15 CHECK • at least one player lacks a verified basketball projection component. "
                "Missing model inputs are not guessed and sportsbook data is not used as a substitute."
            )

    if not frame.empty:
        show = frame.copy()
        for col in [
            "Proj MIN", "Projection baseline REB", "Projection miss factor",
            "Projection allowed factor", "Projection opponent-position factor",
            "Projection lineup factor", "Projection H2H factor",
            "Projection H2H weight", "Projection context factor", "Expected REB",
        ]:
            if col in show.columns:
                show[col] = pd.to_numeric(show[col], errors="coerce").round(3)
        cols = [c for c in [
            "Player", "Team", "Opponent", "Position bucket", "Proj MIN",
            "Projection baseline REB", "Projection context factor", "Expected REB",
            "Projection H2H sample", "Step15 state",
        ] if c in show.columns]
        st.dataframe(show[cols], hide_index=True, use_container_width=True)

    with st.expander("🧠 Projection component board"):
        if frame.empty:
            st.info("No Step-15 player projection rows available.")
        else:
            comp = frame.copy()
            for col in [
                "Projection baseline REB", "Projection miss factor", "Projection allowed factor",
                "Projection opponent-position factor", "Projection lineup factor",
                "Projection H2H factor", "Projection H2H weight",
                "Projection context factor", "Expected REB",
            ]:
                comp[col] = pd.to_numeric(comp[col], errors="coerce").round(4)
            cols = [c for c in [
                "Player", "Team", "Projection baseline REB", "Projection miss factor",
                "Projection allowed factor", "Projection opponent-position factor",
                "Projection lineup factor", "Projection H2H factor", "Projection H2H weight",
                "Projection context factor", "Expected REB", "Step15 state",
            ] if c in comp.columns]
            st.dataframe(comp[cols], hide_index=True, use_container_width=True)

    with st.expander("🧠 Step-15 methodology / diagnostics"):
        st.write({
            "anchor": "Step-6/11 verified minute-scaled capture baseline",
            "formula": "baseline × bounded weighted geometric context factor",
            "weights": {
                "Step10 expected opponent miss-volume index": W_MISS,
                "Step8 rebound-allowed/capture index": W_ALLOWED,
                "Step9 inverse same-position competition": W_OPP_POSITION,
                "Step11 inverse lineup competition": W_LINEUP,
                "Step12 H2H": f"0..{W_H2H_MAX} based on GP / 6",
            },
            "input_caps": {
                "miss": "0.85..1.15",
                "allowed": "0.85..1.15",
                "opponent_position_factor": "0.85..1.15",
                "lineup_factor": "0.85..1.15",
                "H2H": "0.80..1.20 with sample shrinkage",
                "final_context": f"{CONTEXT_MIN:.2f}..{CONTEXT_MAX:.2f}",
            },
            "double_count_guard": (
                "Step9 composite position-context index is NOT used because it already contains Step7/8; "
                "Step10 miss-volume replaces separate Step7 miss-index application."
            ),
            "sportsbook_line_used": False,
            "no_vig_used": False,
            "market_probability_used": False,
            "new_network_requests": 0,
            "monte_carlo_used": False,
            "distribution_created": False,
        })
        if not frame.empty and frame["Step15 state"].eq("CHECK").any():
            cols = [c for c in [
                "Player", "Team", "Projection baseline REB", "Projection miss factor",
                "Projection allowed factor", "Projection opponent-position factor",
                "Projection lineup factor", "Step15 state",
            ] if c in frame.columns]
            st.dataframe(frame.loc[frame["Step15 state"].eq("CHECK"), cols], hide_index=True, use_container_width=True)

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
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ BASELINE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 17), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V2.4 Step 15 only • Steps 1–14 preserved • market-independent expected-rebound mean • "
        "double-count guards + bounded context factors • zero new network requests • "
        "no sportsbook input / no Monte Carlo / no Over-Under probability yet."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step14_ready"):
        _render_step15()
    else:
        st.info("Step 15 remains locked until Step 14 is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
