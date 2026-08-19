"""WNBA Rebounds V2.7 — Step 18 line-specific O/U probability + fair odds.

Extends the verified V2.6 chain without changing Steps 1-17.

Step-18 rules:
- The Step-15/16/17 player distribution remains market-independent.
- Use only VERIFIED Step-14 same-book/same-line market rows as thresholds.
- Evaluate the verified Step-16 rebound PMF at each exact sportsbook line.
- For integer lines, report Push probability explicitly; fair two-way odds are
  computed from win probability conditional on a non-push result because a push
  is refunded. For non-integer lines Push = 0.
- Preserve sportsbook and line identity; never blend books or lines.
- Report ±5% mean-sensitivity probability ranges using the Step-16 variance/mean
  ratio. Sensitivity does not alter the base projection.
- Sportsbook/no-vig probabilities are reference columns only and never enter the
  model probability calculation.
- No EV, staking, ranking or recommendation is created here.
"""
from __future__ import annotations

import math
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v26 as base
import wnba_rebounds_hub_v25 as distmod

MODEL_VERSION = "WNBA REBOUNDS V2.7 • STEP 18 LINE-SPECIFIC O/U PROBABILITY + FAIR ODDS"
PROB_SUM_TOL = 1e-8
SENSITIVITY_PCT = 0.05


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


def _key(player, team):
    return (_norm(player), _norm(team))


def _fair_american(prob):
    p = _num(prob)
    if not np.isfinite(p) or not (0.0 < p < 1.0):
        return np.nan
    if math.isclose(p, 0.5, abs_tol=1e-12):
        return 100.0
    return (-100.0 * p / (1.0 - p)) if p > 0.5 else (100.0 * (1.0 - p) / p)


def _fair_decimal(prob):
    p = _num(prob)
    return 1.0 / p if np.isfinite(p) and 0.0 < p < 1.0 else np.nan


def _pmf_lookup():
    rows = pd.DataFrame(st.session_state.get("wnba_rebounds_step16_pmf") or [])
    if rows.empty:
        return {}
    buckets = {}
    for _, r in rows.iterrows():
        k = _key(r.get("Player"), r.get("Team"))
        if not k[0] or not k[1]:
            continue
        try:
            reb = int(r.get("Rebounds"))
        except Exception:
            continue
        prob = _num(r.get("Probability"), 0.0)
        if reb >= 0 and np.isfinite(prob) and prob > 0:
            buckets.setdefault(k, []).append((reb, float(prob)))

    out = {}
    for k, pairs in buckets.items():
        kmax = max(x for x, _ in pairs)
        pmf = np.zeros(kmax + 1, dtype=float)
        for reb, prob in pairs:
            pmf[reb] += prob
        s = float(pmf.sum())
        if s > 0 and np.isfinite(s):
            out[k] = pmf / s
    return out


def _prob_at_line(pmf: np.ndarray, line: float):
    if pmf is None or len(pmf) == 0 or not np.isfinite(line):
        return {"ok": False}
    p = np.asarray(pmf, dtype=float)
    if not np.isfinite(p).all() or p.sum() <= 0:
        return {"ok": False}
    p = p / p.sum()
    ks = np.arange(len(p), dtype=float)

    over = float(p[ks > line].sum())
    under = float(p[ks < line].sum())
    integer_line = math.isclose(line, round(line), abs_tol=1e-9)
    push = 0.0
    if integer_line:
        idx = int(round(line))
        if 0 <= idx < len(p):
            push = float(p[idx])

    total = over + under + push
    denom = over + under
    over_decision = over / denom if denom > 0 else np.nan
    under_decision = under / denom if denom > 0 else np.nan
    ok = bool(
        np.isfinite(total) and abs(total - 1.0) <= PROB_SUM_TOL
        and np.isfinite(over_decision) and np.isfinite(under_decision)
        and abs((over_decision + under_decision) - 1.0) <= PROB_SUM_TOL
    )
    return {
        "ok": ok,
        "over": over,
        "under": under,
        "push": push,
        "over_decision": over_decision,
        "under_decision": under_decision,
        "integer_line": integer_line,
        "sum": total,
    }


def _sensitivity_prob(mu: float, variance: float, line: float):
    if not np.isfinite(mu) or mu < 0 or not np.isfinite(variance) or variance < 0:
        return {"ok": False}
    ratio = variance / mu if mu > 1e-9 else 1.0
    vals = []
    details = []
    for label, mult in (("LOW -5%", 1.0 - SENSITIVITY_PCT), ("BASE", 1.0), ("HIGH +5%", 1.0 + SENSITIVITY_PCT)):
        m = max(0.0, mu * mult)
        v = max(m, ratio * m) if m > 0 else 0.0
        dist = distmod._distribution(m, v)
        if not dist.get("ok"):
            return {"ok": False}
        prob = _prob_at_line(dist.get("pmf"), line)
        if not prob.get("ok"):
            return {"ok": False}
        vals.append(float(prob["over_decision"]))
        details.append((label, float(prob["over_decision"]), float(prob["under_decision"])))
    return {
        "ok": True,
        "over_low": min(vals),
        "over_high": max(vals),
        "details": details,
    }


def _build_step18():
    step17 = pd.DataFrame(st.session_state.get("wnba_rebounds_step17_players") or [])
    players14 = pd.DataFrame(st.session_state.get("wnba_rebounds_step14_players") or [])
    markets14 = pd.DataFrame(st.session_state.get("wnba_rebounds_step14_quotes") or [])
    step17_ready = bool(st.session_state.get("wnba_rebounds_step17_ready"))
    step14_ready = bool(st.session_state.get("wnba_rebounds_step14_ready"))
    pmfs = _pmf_lookup()

    if step17.empty or players14.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": 0, "player_states": 0,
            "market_rows": 0, "covered_markets": 0, "reason": "verified Step-17/14 state unavailable",
        }

    model_lookup = {}
    for _, r in step17.iterrows():
        k = _key(r.get("Player"), r.get("Team"))
        if k[0] and k[1] and k not in model_lookup:
            model_lookup[k] = r

    valid_markets = markets14.copy()
    if not valid_markets.empty:
        valid_markets = valid_markets[valid_markets.get("No-vig state", "").astype(str).eq("VERIFIED")].copy()

    line_rows = []
    market_counts = {}
    market_good_counts = {}
    for _, q in valid_markets.iterrows():
        player = str(q.get("Player") or "")
        team = str(q.get("Team") or "")
        k = _key(player, team)
        line = _num(q.get("Line"))
        model = model_lookup.get(k)
        pmf = pmfs.get(k)
        market_counts[k] = market_counts.get(k, 0) + 1

        model_ok = bool(model is not None and str(model.get("Step17 state") or "") == "VERIFIED")
        prob = _prob_at_line(pmf, line) if model_ok and pmf is not None else {"ok": False}
        mu = _num(model.get("Expected REB")) if model is not None else np.nan
        variance = _num(model.get("Distribution variance target")) if model is not None else np.nan
        sens = _sensitivity_prob(mu, variance, line) if prob.get("ok") else {"ok": False}
        verified = bool(model_ok and prob.get("ok") and sens.get("ok"))
        if verified:
            market_good_counts[k] = market_good_counts.get(k, 0) + 1

        line_rows.append({
            "Player": player,
            "Team": team,
            "Opponent": str(q.get("Opponent") or ""),
            "Bookmaker ID": str(q.get("Bookmaker ID") or ""),
            "Book": str(q.get("Book") or q.get("Bookmaker ID") or ""),
            "Line": line,
            "Over odds": str(q.get("Over odds") or ""),
            "Under odds": str(q.get("Under odds") or ""),
            "Market Over no-vig": _num(q.get("Over no-vig")),
            "Market Under no-vig": _num(q.get("Under no-vig")),
            "Model P(Over win)": _num(prob.get("over")),
            "Model P(Under win)": _num(prob.get("under")),
            "Model P(Push)": _num(prob.get("push"), 0.0),
            "Model Over decision prob": _num(prob.get("over_decision")),
            "Model Under decision prob": _num(prob.get("under_decision")),
            "Model Over fair American": _fair_american(prob.get("over_decision")),
            "Model Under fair American": _fair_american(prob.get("under_decision")),
            "Model Over fair decimal": _fair_decimal(prob.get("over_decision")),
            "Model Under fair decimal": _fair_decimal(prob.get("under_decision")),
            "Over probability sensitivity low": _num(sens.get("over_low")),
            "Over probability sensitivity high": _num(sens.get("over_high")),
            "Integer line / push eligible": bool(prob.get("integer_line", False)),
            "Probability sum": _num(prob.get("sum")),
            "Projection market input": False,
            "Line threshold input": True,
            "Step18 line state": "VERIFIED" if verified else "CHECK",
        })

    lines = pd.DataFrame(line_rows)
    covered_markets = int(lines["Step18 line state"].eq("VERIFIED").sum()) if not lines.empty else 0

    player_rows = []
    for _, p in players14.iterrows():
        out = p.to_dict()
        k = _key(p.get("Player"), p.get("Team"))
        model = model_lookup.get(k)
        model_ok = bool(model is not None and str(model.get("Step17 state") or "") == "VERIFIED")
        market_state = str(p.get("Step14 market state") or "")
        expected = int(market_counts.get(k, 0))
        good = int(market_good_counts.get(k, 0))

        if str(p.get("Step14 state") or "") != "VERIFIED" or not model_ok:
            state = "CHECK"
            verified = False
        elif market_state in {"VERIFIED NO MARKET", "VERIFIED UNPAIRED MARKET"}:
            state = market_state
            verified = True
        elif market_state == "NO-VIG FOUND" and expected > 0 and good == expected:
            state = "LINE PROBABILITY FOUND"
            verified = True
        else:
            state = "CHECK"
            verified = False

        out.update({
            "Step18 line rows": expected,
            "Step18 verified line rows": good,
            "Step18 probability state": state,
            "Step18 state": "VERIFIED" if verified else "CHECK",
        })
        player_rows.append(out)

    players18 = pd.DataFrame(player_rows)
    player_states = int(players18["Step18 state"].eq("VERIFIED").sum()) if not players18.empty else 0
    parsing_errors = int(lines["Step18 line state"].eq("CHECK").sum()) if not lines.empty else 0
    pushes = int(pd.to_numeric(lines.get("Model P(Push)"), errors="coerce").fillna(0).gt(0).sum()) if not lines.empty else 0

    ready = bool(
        step17_ready and step14_ready
        and not players18.empty and player_states == len(players18)
        and not lines.empty and covered_markets == len(lines)
        and parsing_errors == 0
        and lines["Projection market input"].eq(False).all()
    )

    return players18, lines, {
        "ready": ready,
        "players": int(len(players18)),
        "player_states": player_states,
        "market_rows": int(len(lines)),
        "covered_markets": covered_markets,
        "push_eligible_rows": pushes,
        "parsing_errors": parsing_errors,
        "projection_market_input": False,
        "threshold_market_input": True,
    }


def _render_step18():
    st.markdown("## 📐 Step 18 — Line-Specific Over/Under Probability + Fair Odds")
    st.caption(
        "This layer evaluates the already-verified market-independent rebound distribution at each exact Step-14 sportsbook "
        "line. The line is only a threshold; it never changes the player projection. Books/lines remain separate. Integer "
        "lines report Push probability explicitly, and fair odds condition on a non-push result because pushes are refunded."
    )

    players, lines, info = _build_step18()
    ready = bool(info.get("ready"))
    st.session_state["wnba_rebounds_step18_ready"] = ready
    st.session_state["wnba_rebounds_step18_players"] = players.to_dict("records") if not players.empty else []
    st.session_state["wnba_rebounds_step18_lines"] = lines.to_dict("records") if not lines.empty else []

    a, b, c, d = st.columns(4)
    a.metric("Player states", f"{info.get('player_states',0)}/{info.get('players',0)}")
    b.metric("Line probabilities", f"{info.get('covered_markets',0)}/{info.get('market_rows',0)}")
    c.metric("Push-eligible lines", info.get("push_eligible_rows", 0))
    d.metric("Projection market input", "NONE")

    if ready:
        st.success(
            "✅ STEP 18 PASSED • every exact paired sportsbook line has a verified model Over/Under/Push probability and "
            "model fair odds, while players without paired markets retain explicit verified no-market/unpaired states. "
            "Step 19 (model-vs-market edge + expected value) is unlocked."
        )
    else:
        st.error(
            "⛔ STEP 18 CHECK • at least one verified market line could not be reconciled to a converged player distribution, "
            "or a player market state is incomplete. The app will not guess probabilities or blend books/lines."
        )

    if not lines.empty:
        show = lines.copy()
        pct_cols = [
            "Model P(Over win)", "Model P(Under win)", "Model P(Push)",
            "Model Over decision prob", "Model Under decision prob",
            "Market Over no-vig", "Market Under no-vig",
            "Over probability sensitivity low", "Over probability sensitivity high",
        ]
        for c in pct_cols:
            if c in show.columns:
                show[c] = (100.0 * pd.to_numeric(show[c], errors="coerce")).round(2)
        for c in ["Line", "Model Over fair American", "Model Under fair American"]:
            if c in show.columns:
                show[c] = pd.to_numeric(show[c], errors="coerce").round(1 if c == "Line" else 0)
        cols = [c for c in [
            "Player", "Team", "Opponent", "Book", "Line",
            "Model P(Over win)", "Model P(Under win)", "Model P(Push)",
            "Model Over decision prob", "Model Under decision prob",
            "Model Over fair American", "Model Under fair American",
            "Over probability sensitivity low", "Over probability sensitivity high",
            "Step18 line state",
        ] if c in show.columns]
        st.dataframe(show[cols], hide_index=True, use_container_width=True)

    with st.expander("📐 Player market-state reconciliation"):
        if players.empty:
            st.info("No Step-18 player states available.")
        else:
            cols = [c for c in [
                "Player", "Team", "Opponent", "Step14 market state", "Step18 line rows",
                "Step18 verified line rows", "Step18 probability state", "Step18 state",
            ] if c in players.columns]
            st.dataframe(players[cols], hide_index=True, use_container_width=True)

    with st.expander("📐 Step-18 methodology / diagnostics"):
        st.write({
            "distribution_source": "verified Step-16 PMF; Step-17 convergence is a required gate",
            "market_source": "verified Step-14 same-book/same-line exact O/U rows",
            "over_win_rule": "P(rebounds > line)",
            "under_win_rule": "P(rebounds < line)",
            "push_rule": "P(rebounds = line) only when the line is an integer",
            "fair_odds_rule": "conditional win probability excluding pushes because pushes are refunded",
            "sensitivity": "recompute exact line probability at Step-17 ±5% mean scenarios with variance/mean ratio preserved",
            "sportsbook_line_changes_projection": False,
            "no_vig_changes_projection": False,
            "sportsbook_probability_used_in_model_probability": False,
            "EV_calculated": False,
            "ranking_created": False,
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
        "Model-vs-market edge + expected value",
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ BASELINE",
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(pd.DataFrame({"Step": range(1, 20), "Layer": layers, "Status": statuses}), hide_index=True, use_container_width=True)
    st.caption(
        "⚡ V2.7 Step 18 only • Steps 1–17 preserved • exact same-book/same-line thresholds • explicit push probability • "
        "fair odds from market-independent PMF • ±5% probability sensitivity • zero new network requests • no EV/ranking yet."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step17_ready"):
        _render_step18()
    else:
        st.info("Step 18 remains locked until Step 17 is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
