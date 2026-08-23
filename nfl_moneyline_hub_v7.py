"""Kyre Sports AI — NFL Moneyline V7 Step-7 model-vs-market edge + EV layer.

Builds on V6 without changing Steps 1-6. Step 7 compares the independent
Step-6 5M BASE-model Monte Carlo probability with Step-5 same-book no-vig market
probability and best available usable Moneyline price.

Outputs for both sides:
- Monte Carlo model probability;
- same-book cross-book no-vig consensus probability;
- model-minus-market probability edge;
- fair American Moneyline from the model probability;
- best available usable sportsbook Moneyline;
- expected return per unit at that best price;
- uncertainty-floor probability/edge/EV using Step-6 sampled-P tails.

Sportsbook prices never feed back into Steps 4C/6. This layer performs comparison
math only and does NOT issue a final pick or recommendation. During preseason,
Step 3 game-plan/QB-rotation integrity remains the final-output safety gate; a
calculated edge/EV is explicitly diagnostic until that gate clears.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v1 as step1
import nfl_moneyline_hub_v6 as v6
import nfl_moneyline_hub_v51 as v51

MODEL_VERSION = "NFL MONEYLINE V7.0 • STEP 7 NO-VIG EDGE + EV DIAGNOSTICS"


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


def _finite(value) -> bool:
    return bool(np.isfinite(_num(value)))


def _fmt_pct(value, digits=1) -> str:
    n = _num(value)
    return "—" if not np.isfinite(n) else f"{100.0 * n:.{digits}f}%"


def _fmt_pp(value, digits=1) -> str:
    n = _num(value)
    if not np.isfinite(n):
        return "—"
    sign = "+" if n > 0 else ""
    return f"{sign}{100.0 * n:.{digits}f} pp"


def _fmt_ev(value, digits=1) -> str:
    n = _num(value)
    if not np.isfinite(n):
        return "—"
    sign = "+" if n > 0 else ""
    return f"{sign}{100.0 * n:.{digits}f}%"


def _fmt_american(value) -> str:
    n = _num(value)
    if not np.isfinite(n):
        return "—"
    rounded = int(round(n))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _fair_american(probability):
    p = _num(probability)
    if not np.isfinite(p) or p <= 0.0 or p >= 1.0:
        return np.nan
    if p >= 0.5:
        return float(-100.0 * p / (1.0 - p))
    return float(100.0 * (1.0 - p) / p)


def _profit_multiple(american):
    price = _num(american)
    if not np.isfinite(price) or price == 0:
        return np.nan
    return float(price / 100.0) if price > 0 else float(100.0 / abs(price))


def _expected_return(probability, american):
    p = _num(probability)
    profit = _profit_multiple(american)
    if not np.isfinite(p) or not np.isfinite(profit) or p < 0.0 or p > 1.0:
        return np.nan
    return float(p * profit - (1.0 - p))


def _side_output(*, side: str, model_p, market_p, conservative_p, best: dict) -> dict:
    p = _num(model_p)
    mkt = _num(market_p)
    floor_p = _num(conservative_p)
    price = _num((best or {}).get("price"))
    ready = all(np.isfinite(x) for x in (p, mkt, floor_p, price))
    if not ready:
        return {
            "ready": False,
            "side": side,
            "error": "model probability, market probability, uncertainty floor or best price is missing",
        }
    return {
        "ready": True,
        "side": side,
        "model_p": float(p),
        "market_p": float(mkt),
        "edge": float(p - mkt),
        "fair_ml": _fair_american(p),
        "best_price": float(price),
        "best_book": _safe((best or {}).get("book"), "—"),
        "ev": _expected_return(p, price),
        "conservative_p": float(floor_p),
        "conservative_edge": float(floor_p - mkt),
        "conservative_ev": _expected_return(floor_p, price),
    }


def _build_game_output(game: dict, snap: dict, mc_out: dict) -> dict:
    if not snap or not snap.get("ready"):
        return {"ready": False, "error": "Step-5 usable no-vig market is unavailable"}
    if not mc_out or not mc_out.get("ready") or not mc_out.get("converged"):
        return {"ready": False, "error": "Step-6 converged Monte Carlo output is unavailable"}

    away_p = _num(mc_out.get("away_win_rate"))
    home_p = _num(mc_out.get("home_win_rate"))
    away_floor = _num(mc_out.get("p05_probability"))
    away_ceiling = _num(mc_out.get("p95_probability"))
    if not np.isfinite(home_p) and np.isfinite(away_p):
        home_p = 1.0 - away_p

    # Home's conservative lower tail is the complement of away's upper tail.
    home_floor = 1.0 - away_ceiling if np.isfinite(away_ceiling) else np.nan

    away = _side_output(
        side="away",
        model_p=away_p,
        market_p=snap.get("consensus_away_no_vig"),
        conservative_p=away_floor,
        best=snap.get("best_away") or {},
    )
    home = _side_output(
        side="home",
        model_p=home_p,
        market_p=snap.get("consensus_home_no_vig"),
        conservative_p=home_floor,
        best=snap.get("best_home") or {},
    )
    return {
        "ready": bool(away.get("ready") and home.get("ready")),
        "away": away,
        "home": home,
        "market_quality": _safe(snap.get("quality"), "—"),
        "mc_se": _num(mc_out.get("mc_se")),
        "mc_batches": int(mc_out.get("batches") or 0),
        "mc_simulations": int(mc_out.get("simulations") or 0),
        "error": "" if away.get("ready") and home.get("ready") else "one or both comparison sides are incomplete",
    }


def _render_side(team: str, out: dict):
    st.markdown(f"##### {team}")
    if not out.get("ready"):
        st.warning(f"Comparison unavailable • {out.get('error') or 'incomplete inputs'}")
        return

    a, b, c, d = st.columns(4)
    a.metric("5M model P(win)", _fmt_pct(out.get("model_p")))
    b.metric("Market no-vig", _fmt_pct(out.get("market_p")))
    c.metric("Probability edge", _fmt_pp(out.get("edge")))
    d.metric("Model fair ML", _fmt_american(out.get("fair_ml")))

    x, y, z = st.columns(3)
    x.metric(
        "Best available ML",
        _fmt_american(out.get("best_price")),
        help=f"Usable Step-5 price • {out.get('best_book') or '—'}",
    )
    y.metric("Expected return / 1u", _fmt_ev(out.get("ev")))
    z.metric("Uncertainty-floor P", _fmt_pct(out.get("conservative_p")))

    r1, r2 = st.columns(2)
    r1.metric("Uncertainty-floor edge", _fmt_pp(out.get("conservative_edge")))
    r2.metric("Uncertainty-floor EV", _fmt_ev(out.get("conservative_ev")))

    st.caption(
        f"Best-price book: {out.get('best_book') or '—'} • fair ML is derived only from the Step-6 model probability • "
        "EV uses that probability against the displayed best usable American price."
    )


def _render_game(game: dict, out: dict):
    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    st.markdown(f"#### Model vs market — {away} @ {home}")

    if not out.get("ready"):
        st.warning(f"⚠️ Step 7 unavailable • {out.get('error') or 'comparison inputs incomplete'}")
        return

    left, right = st.columns(2)
    with left:
        _render_side(away, out.get("away") or {})
    with right:
        _render_side(home, out.get("home") or {})

    preseason = _safe(game.get("season_type")).lower() == "preseason"
    gameplan_ready = bool(st.session_state.get("nfl_moneyline_v3_gameplan_ready"))
    if preseason and not gameplan_ready:
        st.warning(
            "🔒 PRESEASON FINAL-GRADE GATE • the edge and EV above are BASE-model diagnostics only. "
            "Step 3 has not fully verified QB participation/rotation, so these values cannot be promoted to a final Moneyline grade or recommendation."
        )
    else:
        st.info(
            "Step 7 comparison math is available. Final grading/recommendation remains a separate layer and is not issued here."
        )

    st.info(
        "NO-VIG / EV FIREWALL • market probabilities and prices are comparison targets only. "
        "They do not alter Step-4C calibration or Step-6 Monte Carlo probabilities."
    )


def _render_step7() -> bool:
    selected = st.session_state.get("nfl_v1_date", date.today())
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    schedule, diag = foundation.load_nfl_slate(day_str)
    pregame, _ = step1._pregame_partition(
        schedule,
        day_str,
        now_et=pd.Timestamp.now(tz=foundation.ET),
    )
    snapshots = st.session_state.get("nfl_moneyline_v5_market_snapshots") or {}
    mc_outputs = st.session_state.get("nfl_moneyline_v6_mc_outputs") or {}

    st.markdown("### 🎯 Step 7 — No-Vig Edge + Expected Value")
    st.caption(
        "5M BASE-model P(win) vs Step-5 same-book no-vig consensus • model fair Moneyline • best-price EV • "
        "Step-6 uncertainty-floor edge/EV • comparison math only • final grading remains separately gated."
    )

    if not diag.get("request_ok") or pregame.empty:
        st.warning("Step 7 cannot compare model and market because no verified pregame NFL matchup is available.")
        st.session_state["nfl_moneyline_v7_edge_ready"] = False
        return False
    if not st.session_state.get("nfl_moneyline_v5_market_ready"):
        st.warning("Step 7 cannot run until Step 5 has a usable same-book Moneyline market.")
        st.session_state["nfl_moneyline_v7_edge_ready"] = False
        return False
    if not st.session_state.get("nfl_moneyline_v6_mc_ready"):
        st.warning("Step 7 cannot run until Step 6 Monte Carlo is READY and converged.")
        st.session_state["nfl_moneyline_v7_edge_ready"] = False
        return False

    outputs = {}
    ready_games = 0
    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        out = _build_game_output(game, snapshots.get(gid, {}), mc_outputs.get(gid, {}))
        outputs[gid] = out
        if out.get("ready"):
            ready_games += 1

    all_ready = bool(len(pregame) and ready_games == len(pregame))
    a, b, c, d = st.columns(4)
    a.metric("Games compared", f"{ready_games}/{len(pregame)}")
    b.metric("Market input", "READY" if st.session_state.get("nfl_moneyline_v5_market_ready") else "CHECK")
    c.metric("5M model input", "READY" if st.session_state.get("nfl_moneyline_v6_mc_ready") else "CHECK")
    d.metric("Final grade", "GATED")

    if all_ready:
        st.success("✅ STEP 7 PASSED • no-vig edge, fair-price and EV diagnostics calculated for every verified pregame matchup.")
    else:
        st.warning("⚠️ STEP 7 CHECK • at least one matchup lacks a complete Step-5 market or converged Step-6 model output.")

    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        _render_game(game, outputs.get(gid, {}))

    with st.expander("🧮 Step 7 calculation definitions", expanded=False):
        st.markdown(
            "**Probability edge** = 5M Monte Carlo P(win) − same-book no-vig consensus P(win).  \n"
            "**Fair ML** = American odds mathematically equivalent to the model P(win).  \n"
            "**Expected return / 1u** = model win probability × sportsbook profit multiple − loss probability.  \n"
            "**Uncertainty-floor** uses the Step-6 sampled-P 5th percentile for the away team and the complement of the away 95th percentile for the home team."
        )
        st.caption(
            "The uncertainty-floor is a conservative model-parameter tail diagnostic, not a guarantee or a complete preseason game-plan uncertainty model."
        )

    st.session_state["nfl_moneyline_v7_edge_outputs"] = outputs
    st.session_state["nfl_moneyline_v7_edge_ready"] = all_ready
    return all_ready


def render_nfl_moneyline_hub():
    """Render V6 unchanged and inject Step 7 after Step 6, before production locks."""
    real_markdown = st.markdown
    real_dataframe = st.dataframe
    real_caption = st.caption
    state = {"injected": False, "ready": False}

    def _markdown(body, *args, **kwargs):
        if isinstance(body, str):
            if '<span class="knfl-ml-chip">STEP 6</span>' in body:
                body = body.replace(
                    '<span class="knfl-ml-chip">STEP 6</span>',
                    '<span class="knfl-ml-chip">STEP 7</span>',
                )
            if body.strip() == "### 🔒 Moneyline production locks" and not state["injected"]:
                state["injected"] = True
                state["ready"] = _render_step7()
        return real_markdown(body, *args, **kwargs)

    def _dataframe(data=None, *args, **kwargs):
        if isinstance(data, pd.DataFrame) and "Layer" in data.columns and "State" in data.columns:
            layers = set(data["Layer"].astype(str).tolist())
            if "No-vig edge / EV / final grading" in layers:
                data = data.copy()
                mask = data["Layer"].astype(str) == "No-vig edge / EV / final grading"
                data.loc[mask, "State"] = (
                    "STEP 7 EDGE/EV READY • FINAL GRADE GATED"
                    if state.get("ready")
                    else "STEP 7 CHECK"
                )
        return real_dataframe(data, *args, **kwargs)

    def _caption(body, *args, **kwargs):
        if isinstance(body, str) and body.startswith("Step 6 adds"):
            body = (
                "Step 7 compares the independent 5M model probability with the Step-5 no-vig market and best usable price to calculate fair odds, probability edge and EV. "
                "Market data never feeds back into the model. Final grading/recommendation remains separately gated; during preseason Step 3 remains the final-output safety gate."
            )
        return real_caption(body, *args, **kwargs)

    st.markdown = _markdown
    st.dataframe = _dataframe
    st.caption = _caption
    try:
        return v6.render_nfl_moneyline_hub()
    finally:
        st.markdown = real_markdown
        st.dataframe = real_dataframe
        st.caption = real_caption


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
