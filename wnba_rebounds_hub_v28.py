"""WNBA Rebounds V2.8 — Step 19 model-vs-market edge + expected value.

Extends the verified V2.7 chain without changing Steps 1-18.

Step-19 rules:
- Consume only VERIFIED Step-18 exact bookmaker/line rows.
- Keep player projection/distribution market-independent; Step 19 only compares the
  already-computed model probabilities with the exact posted market.
- Edge is model decision probability minus Step-14 same-book/same-line no-vig.
- Expected value uses the exact posted price and unconditional win/loss/push
  probabilities; pushes return stake and therefore contribute zero profit/loss.
- Preserve Over and Under separately for every exact bookmaker/line.
- Use Step-18 ±5% probability sensitivity to flag robust vs fragile edge.
- No staking, bet sizing, forced ranking, or final recommendation is created here.
"""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v27 as base

MODEL_VERSION = "WNBA REBOUNDS V2.8 • STEP 19 MODEL-VS-MARKET EDGE + EXPECTED VALUE"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _price_terms(raw):
    """Return decimal odds, profit per 1 unit risked, and raw implied probability."""
    text = str(raw or "").strip().upper().replace(",", "")
    if not text:
        return {"ok": False}
    if text in {"EVEN", "EVENS", "EV", "PK", "PICK"}:
        return {"ok": True, "decimal": 2.0, "profit": 1.0, "implied": 0.5, "format": "AMERICAN"}

    if "/" in text:
        try:
            a, b = text.split("/", 1)
            frac = float(a) / float(b)
            dec = 1.0 + frac
            if dec > 1.0:
                return {"ok": True, "decimal": dec, "profit": frac, "implied": 1.0 / dec, "format": "FRACTIONAL"}
        except Exception:
            return {"ok": False}

    cleaned = re.sub(r"[^0-9+\-.]", "", text)
    try:
        x = float(cleaned)
    except Exception:
        return {"ok": False}

    if text.startswith(("+", "-")) or abs(x) >= 100.0:
        if x == 0:
            return {"ok": False}
        if x > 0:
            profit = x / 100.0
        else:
            profit = 100.0 / (-x)
        dec = 1.0 + profit
        return {"ok": True, "decimal": dec, "profit": profit, "implied": 1.0 / dec, "format": "AMERICAN"}

    if 1.0 < x <= 100.0:
        return {"ok": True, "decimal": x, "profit": x - 1.0, "implied": 1.0 / x, "format": "DECIMAL"}

    return {"ok": False}


def _american_from_prob(prob):
    p = _num(prob)
    if not np.isfinite(p) or not (0.0 < p < 1.0):
        return np.nan
    if math.isclose(p, 0.5, abs_tol=1e-12):
        return 100.0
    return (-100.0 * p / (1.0 - p)) if p > 0.5 else (100.0 * (1.0 - p) / p)


def _side_row(q: pd.Series, side: str):
    over = side == "OVER"
    odds_raw = q.get("Over odds") if over else q.get("Under odds")
    price = _price_terms(odds_raw)

    p_win = _num(q.get("Model P(Over win)" if over else "Model P(Under win)"))
    p_loss = _num(q.get("Model P(Under win)" if over else "Model P(Over win)"))
    p_push = _num(q.get("Model P(Push)"), 0.0)
    p_decision = _num(q.get("Model Over decision prob" if over else "Model Under decision prob"))
    market_nv = _num(q.get("Market Over no-vig" if over else "Market Under no-vig"))

    sens_over_low = _num(q.get("Over probability sensitivity low"))
    sens_over_high = _num(q.get("Over probability sensitivity high"))
    if over:
        sens_low = sens_over_low
        sens_high = sens_over_high
    else:
        sens_low = 1.0 - sens_over_high if np.isfinite(sens_over_high) else np.nan
        sens_high = 1.0 - sens_over_low if np.isfinite(sens_over_low) else np.nan

    valid_prob = bool(
        np.isfinite(p_win) and np.isfinite(p_loss) and np.isfinite(p_push)
        and p_win >= 0 and p_loss >= 0 and p_push >= 0
        and abs((p_win + p_loss + p_push) - 1.0) <= 1e-8
        and np.isfinite(p_decision) and 0.0 <= p_decision <= 1.0
        and np.isfinite(market_nv) and 0.0 < market_nv < 1.0
    )
    valid = bool(price.get("ok") and valid_prob)

    profit = _num(price.get("profit"))
    ev = p_win * profit - p_loss if valid else np.nan
    roi = ev if valid else np.nan
    raw_implied = _num(price.get("implied"))
    edge_nv = p_decision - market_nv if valid else np.nan
    edge_raw = p_decision - raw_implied if valid and np.isfinite(raw_implied) else np.nan
    worst_edge = sens_low - market_nv if valid and np.isfinite(sens_low) else np.nan
    best_edge = sens_high - market_nv if valid and np.isfinite(sens_high) else np.nan

    if valid and ev > 0 and np.isfinite(worst_edge) and worst_edge > 0:
        robustness = "POSITIVE • ROBUST"
    elif valid and ev > 0:
        robustness = "POSITIVE • SENSITIVITY RISK"
    elif valid and ev <= 0:
        robustness = "NON-POSITIVE"
    else:
        robustness = "CHECK"

    return {
        "Player": str(q.get("Player") or ""),
        "Team": str(q.get("Team") or ""),
        "Opponent": str(q.get("Opponent") or ""),
        "Bookmaker ID": str(q.get("Bookmaker ID") or ""),
        "Book": str(q.get("Book") or q.get("Bookmaker ID") or ""),
        "Line": _num(q.get("Line")),
        "Side": side,
        "Posted odds": str(odds_raw or ""),
        "Odds format": str(price.get("format") or ""),
        "Posted decimal": _num(price.get("decimal")),
        "Posted raw implied": raw_implied,
        "Model P(win)": p_win,
        "Model P(loss)": p_loss,
        "Model P(push)": p_push,
        "Model decision probability": p_decision,
        "Model fair American": _american_from_prob(p_decision),
        "Market no-vig probability": market_nv,
        "No-vig edge": edge_nv,
        "Raw-price edge": edge_raw,
        "Expected value / unit": ev,
        "Expected ROI": roi,
        "Sensitivity decision low": sens_low,
        "Sensitivity decision high": sens_high,
        "Sensitivity worst edge": worst_edge,
        "Sensitivity best edge": best_edge,
        "Edge robustness": robustness,
        "Projection market input": False,
        "Step19 side state": "VERIFIED" if valid else "CHECK",
    }


def _build_step19():
    players18 = pd.DataFrame(st.session_state.get("wnba_rebounds_step18_players") or [])
    lines18 = pd.DataFrame(st.session_state.get("wnba_rebounds_step18_lines") or [])
    step18_ready = bool(st.session_state.get("wnba_rebounds_step18_ready"))

    if players18.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": 0, "player_states": 0,
            "market_rows": 0, "verified_market_rows": 0, "sides": 0,
            "verified_sides": 0, "reason": "verified Step-18 player state unavailable",
        }

    verified_lines = lines18.copy()
    if not verified_lines.empty:
        verified_lines = verified_lines[verified_lines.get("Step18 line state", "").astype(str).eq("VERIFIED")].copy()

    side_rows = []
    line_good = {}
    line_total = {}
    for idx, q in verified_lines.iterrows():
        key = (
            str(q.get("Player") or ""), str(q.get("Team") or ""),
            str(q.get("Bookmaker ID") or ""), _num(q.get("Line")),
        )
        line_total[key] = 2
        rows = [_side_row(q, "OVER"), _side_row(q, "UNDER")]
        side_rows.extend(rows)
        line_good[key] = sum(r["Step19 side state"] == "VERIFIED" for r in rows)

    sides = pd.DataFrame(side_rows)
    verified_sides = int(sides["Step19 side state"].eq("VERIFIED").sum()) if not sides.empty else 0
    verified_market_rows = sum(1 for k in line_total if line_good.get(k, 0) == 2)

    player_market_counts = {}
    player_market_good = {}
    for _, q in verified_lines.iterrows():
        pk = (str(q.get("Player") or ""), str(q.get("Team") or ""))
        player_market_counts[pk] = player_market_counts.get(pk, 0) + 1
        key = (pk[0], pk[1], str(q.get("Bookmaker ID") or ""), _num(q.get("Line")))
        if line_good.get(key, 0) == 2:
            player_market_good[pk] = player_market_good.get(pk, 0) + 1

    player_rows = []
    for _, p in players18.iterrows():
        out = p.to_dict()
        pk = (str(p.get("Player") or ""), str(p.get("Team") or ""))
        expected = int(player_market_counts.get(pk, 0))
        good = int(player_market_good.get(pk, 0))
        pstate = str(p.get("Step18 probability state") or "")

        if str(p.get("Step18 state") or "") != "VERIFIED":
            state = "CHECK"
            verified = False
        elif pstate in {"VERIFIED NO MARKET", "VERIFIED UNPAIRED MARKET"}:
            state = pstate
            verified = True
        elif pstate == "LINE PROBABILITY FOUND" and expected > 0 and good == expected:
            state = "EDGE + EV FOUND"
            verified = True
        else:
            state = "CHECK"
            verified = False

        out.update({
            "Step19 market rows": expected,
            "Step19 verified market rows": good,
            "Step19 value state": state,
            "Step19 state": "VERIFIED" if verified else "CHECK",
        })
        player_rows.append(out)

    players19 = pd.DataFrame(player_rows)
    player_states = int(players19["Step19 state"].eq("VERIFIED").sum()) if not players19.empty else 0
    parsing_errors = int(sides["Step19 side state"].eq("CHECK").sum()) if not sides.empty else 0
    positive_ev = int(pd.to_numeric(sides.get("Expected value / unit"), errors="coerce").fillna(-999).gt(0).sum()) if not sides.empty else 0
    robust_positive = int(sides.get("Edge robustness", pd.Series(dtype=str)).eq("POSITIVE • ROBUST").sum()) if not sides.empty else 0

    ready = bool(
        step18_ready
        and not players19.empty and player_states == len(players19)
        and not verified_lines.empty
        and verified_market_rows == len(verified_lines)
        and verified_sides == 2 * len(verified_lines)
        and parsing_errors == 0
        and sides["Projection market input"].eq(False).all()
    )

    return players19, sides, {
        "ready": ready,
        "players": int(len(players19)),
        "player_states": player_states,
        "market_rows": int(len(verified_lines)),
        "verified_market_rows": int(verified_market_rows),
        "sides": int(len(sides)),
        "verified_sides": verified_sides,
        "positive_ev_sides": positive_ev,
        "robust_positive_sides": robust_positive,
        "parsing_errors": parsing_errors,
        "projection_market_input": False,
    }


def _render_step19():
    st.markdown("## 💹 Step 19 — Model-vs-Market Edge + Expected Value")
    st.caption(
        "This layer compares the verified Step-18 model probability with the exact same-book/same-line market. "
        "No-vig edge uses the Step-14 market baseline; EV uses the exact posted price plus the model's unconditional "
        "win/loss/push probabilities. Pushes return stake. The player projection itself remains market-independent."
    )

    players, sides, info = _build_step19()
    ready = bool(info.get("ready"))
    st.session_state["wnba_rebounds_step19_ready"] = ready
    st.session_state["wnba_rebounds_step19_players"] = players.to_dict("records") if not players.empty else []
    st.session_state["wnba_rebounds_step19_sides"] = sides.to_dict("records") if not sides.empty else []

    a, b, c, d = st.columns(4)
    a.metric("Player states", f"{info.get('player_states',0)}/{info.get('players',0)}")
    b.metric("Market rows", f"{info.get('verified_market_rows',0)}/{info.get('market_rows',0)}")
    c.metric("Positive-EV sides", info.get("positive_ev_sides", 0))
    d.metric("Robust +EV sides", info.get("robust_positive_sides", 0))

    if ready:
        st.success(
            "✅ STEP 19 PASSED • every verified Step-18 market has exact posted-price EV and model-vs-no-vig edge for "
            "both Over and Under, with sensitivity robustness labeled. Step 20 (risk-adjusted qualification + ranking / "
            "final card) is unlocked. No staking or recommendation has been created yet."
        )
    else:
        st.error(
            "⛔ STEP 19 CHECK • at least one verified Step-18 line could not be priced safely or reconciled to both sides. "
            "The app will not guess an odds format, mix books, or advance to rankings until all value rows verify."
        )

    if not sides.empty:
        show = sides.copy()
        pct_cols = [
            "Model decision probability", "Posted raw implied", "Market no-vig probability",
            "No-vig edge", "Raw-price edge", "Expected ROI",
            "Sensitivity decision low", "Sensitivity decision high", "Sensitivity worst edge",
        ]
        for c in pct_cols:
            if c in show.columns:
                show[c] = (100.0 * pd.to_numeric(show[c], errors="coerce")).round(2)
        if "Expected value / unit" in show.columns:
            show["Expected value / unit"] = pd.to_numeric(show["Expected value / unit"], errors="coerce").round(4)
        if "Model fair American" in show.columns:
            show["Model fair American"] = pd.to_numeric(show["Model fair American"], errors="coerce").round(0)
        cols = [c for c in [
            "Player", "Team", "Opponent", "Book", "Line", "Side", "Posted odds",
            "Model decision probability", "Market no-vig probability", "No-vig edge",
            "Expected value / unit", "Expected ROI", "Model fair American",
            "Sensitivity worst edge", "Edge robustness", "Step19 side state",
        ] if c in show.columns]
        st.dataframe(show[cols], hide_index=True, use_container_width=True)

    with st.expander("💹 Exact price / EV diagnostics"):
        if sides.empty:
            st.info("No verified Step-18 market rows are available.")
        else:
            cols = [c for c in [
                "Player", "Book", "Line", "Side", "Posted odds", "Odds format", "Posted decimal",
                "Model P(win)", "Model P(loss)", "Model P(push)", "Posted raw implied",
                "Market no-vig probability", "No-vig edge", "Expected value / unit",
                "Sensitivity decision low", "Sensitivity decision high", "Sensitivity worst edge",
                "Step19 side state",
            ] if c in sides.columns]
            diag = sides[cols].copy()
            st.dataframe(diag, hide_index=True, use_container_width=True)

    with st.expander("💹 Step-19 methodology / diagnostics"):
        st.write({
            "edge": "model decision probability − same-book/same-line Step-14 no-vig probability",
            "ev_per_1_unit": "P(win) × posted profit-per-unit − P(loss); push contributes 0",
            "push_handling": "stake refunded; explicit Step-18 push probability retained",
            "sensitivity": "Step-18 ±5% decision-probability range compared with the same no-vig market",
            "books_blended": False,
            "lines_blended": False,
            "projection_market_input": False,
            "staking": False,
            "ranking": False,
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
        "Risk-adjusted qualification + ranking / final card",
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ BASELINE",
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 21), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V2.8 Step 19 only • Steps 1–18 preserved • exact same-book/same-line no-vig edge + posted-price EV • "
        "explicit push handling • ±5% robustness • zero new network requests • projection market input NONE • no ranking yet."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step18_ready"):
        _render_step19()
    else:
        st.info("Step 19 remains locked until Step 18 is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
