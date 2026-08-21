"""WNBA Moneyline V1.3 — Step 6 no-vig market comparison + model fair odds.

Preserves Moneyline V1.2 Steps 1-5 and adds Step 6 only.

Step 6 joins each verified Step-4 SAME-BOOK two-sided Moneyline pair to the
market-independent Step-5 win distribution for the same game. It then:
- converts each posted American price to raw implied probability;
- removes same-book vig proportionally across the two verified sides;
- converts the frozen Step-5 model win probabilities to model fair American odds;
- reports model-vs-market probability edge for both sides;
- carries Step-5 READY/MONITOR state forward without changing it.

Critical isolation rule: sportsbook prices are comparison inputs only. They never
feed back into the Step-5 projected score, projected margin, empirical sigma or
model win probability. V1.3 runs no Monte Carlo and publishes no Moneyline pick.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_moneyline_hub_v12 as prior

MODEL_VERSION = "WNBA MONEYLINE V1.3 • NO-VIG + MODEL FAIR ODDS"
ET = prior.ET
foundation = prior.foundation
clock = prior.clock
spread_current = prior.spread_current


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _american_implied(odds) -> float:
    x = _num(odds, np.nan)
    if not np.isfinite(x) or x == 0:
        return np.nan
    if x > 0:
        return 100.0 / (x + 100.0)
    return (-x) / ((-x) + 100.0)


def _fair_american(probability) -> float:
    p = _num(probability, np.nan)
    if not np.isfinite(p) or p <= 0.0 or p >= 1.0:
        return np.nan
    if p >= 0.5:
        return -100.0 * p / (1.0 - p)
    return 100.0 * (1.0 - p) / p


def _fmt_price(value):
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    return f"{int(round(x)):+d}"


def _fmt_pct(value, digits=1):
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    return f"{100.0 * x:.{digits}f}%"


def _fmt_edge(value):
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    return f"{x:+.1f} pp"


def _novig_fair_board(win_board: pd.DataFrame, ready_ml: pd.DataFrame):
    """Compare frozen Step-5 probabilities to exact Step-4 same-book prices."""
    empty_meta = {
        "state": "N/A",
        "games": 0,
        "covered_games": 0,
        "rows": 0,
        "ready": 0,
        "monitor": 0,
        "blocked": 0,
        "comparison_ready": False,
        "sportsbook_projection_inputs": 0,
    }
    if win_board is None or win_board.empty or ready_ml is None or ready_ml.empty:
        return pd.DataFrame(), empty_meta

    models = {
        str(r.get("game_id") or ""): r
        for _, r in win_board.iterrows()
    }
    model_ids = set(models)
    rows = []
    covered_ids = set()

    for _, market in ready_ml.iterrows():
        gid = str(market.get("game_id") or "")
        model = models.get(gid)
        if model is None:
            continue

        away_price = _num(market.get("away_ml"), np.nan)
        home_price = _num(market.get("home_ml"), np.nan)
        away_model = _num(model.get("away_win_prob"), np.nan)
        home_model = _num(model.get("home_win_prob"), np.nan)

        away_imp = _american_implied(away_price)
        home_imp = _american_implied(home_price)
        denom = away_imp + home_imp if np.isfinite(away_imp) and np.isfinite(home_imp) else np.nan
        if not np.isfinite(denom) or denom <= 0:
            continue
        if not np.isfinite(away_model) or not np.isfinite(home_model):
            continue

        # Normalize the frozen Step-5 probabilities defensively. They should already
        # sum to one; this guard prevents floating-point drift from entering fair odds.
        model_total = away_model + home_model
        if not np.isfinite(model_total) or model_total <= 0:
            continue
        away_model = float(np.clip(away_model / model_total, 0.0, 1.0))
        home_model = float(np.clip(home_model / model_total, 0.0, 1.0))

        away_market = float(away_imp / denom)
        home_market = float(home_imp / denom)
        model_state = str(model.get("state") or "MONITOR").upper()
        state = "READY" if model_state == "READY" else "MONITOR"

        rows.append({
            "game_id": gid,
            "away_team": str(model.get("away_team") or market.get("away_team") or "Away"),
            "home_team": str(model.get("home_team") or market.get("home_team") or "Home"),
            "first_tip_et": str(model.get("first_tip_et") or market.get("first_tip_et") or "—"),
            "book": str(market.get("book") or ""),
            "away_price": float(away_price),
            "home_price": float(home_price),
            "age_seconds": _num(market.get("age_seconds"), np.nan),
            "freshness": str(market.get("freshness") or ""),
            "away_raw_implied": float(away_imp),
            "home_raw_implied": float(home_imp),
            "market_overround": float(denom - 1.0),
            "away_market_novig": away_market,
            "home_market_novig": home_market,
            "away_model_prob": away_model,
            "home_model_prob": home_model,
            "away_fair_odds": _fair_american(away_model),
            "home_fair_odds": _fair_american(home_model),
            "away_edge_pp": 100.0 * (away_model - away_market),
            "home_edge_pp": 100.0 * (home_model - home_market),
            "projected_home_margin": _num(model.get("projected_home_margin"), np.nan),
            "sigma": _num(model.get("sigma"), np.nan),
            "projection_state": str(model.get("projection_state") or model_state),
            "state": state,
            "reason": str(model.get("reason") or ""),
            "sportsbook_projection_inputs": 0,
            "vig_method": "same-book proportional normalization",
            "model_probability_source": "frozen Step-5 independent win distribution",
        })
        covered_ids.add(gid)

    frame = pd.DataFrame(rows)
    states = frame.get("state", pd.Series(dtype=object)).astype(str).str.upper() if not frame.empty else pd.Series(dtype=object)
    ready = int(states.eq("READY").sum()) if not frame.empty else 0
    monitor = int(states.eq("MONITOR").sum()) if not frame.empty else 0
    blocked = int(len(model_ids - covered_ids))
    comparison_ready = bool(model_ids and model_ids.issubset(covered_ids))
    meta = {
        "state": "READY" if comparison_ready else "CHECK",
        "games": int(len(model_ids)),
        "covered_games": int(len(model_ids & covered_ids)),
        "rows": int(len(frame)),
        "ready": ready,
        "monitor": monitor,
        "blocked": blocked,
        "comparison_ready": comparison_ready,
        "sportsbook_projection_inputs": 0,
    }
    return frame, meta


def _render_step6(win_board: pd.DataFrame, ready_ml: pd.DataFrame, win_ready: bool):
    st.markdown("### 📊 Step 6 — Same-Book No-Vig + Model Fair Odds")
    st.caption(
        "Step-5 win probability stays frozen • exact Step-4 same-book prices are converted to raw implied probability, "
        "vig is removed proportionally within that same book, and the independent model probability is converted to fair American odds. "
        "Sportsbook projection input = ZERO."
    )

    if not win_ready:
        st.warning("🔒 STEP 6 LOCKED • Step 5 must provide an independent win distribution for every pregame game first.")
        return pd.DataFrame(), {
            "state": "LOCKED", "games": 0, "covered_games": 0, "rows": 0,
            "ready": 0, "monitor": 0, "blocked": 0,
            "comparison_ready": False, "sportsbook_projection_inputs": 0,
        }
    if ready_ml is None or ready_ml.empty:
        st.warning("🔒 STEP 6 LOCKED • no current exact Step-4 same-book Moneyline pairs are available for comparison.")
        return pd.DataFrame(), {
            "state": "LOCKED", "games": int(len(win_board) if isinstance(win_board, pd.DataFrame) else 0),
            "covered_games": 0, "rows": 0, "ready": 0, "monitor": 0, "blocked": 0,
            "comparison_ready": False, "sportsbook_projection_inputs": 0,
        }

    board, meta = _novig_fair_board(win_board, ready_ml)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Game coverage", f"{int(meta.get('covered_games', 0))}/{int(meta.get('games', 0))}")
    c2.metric("Comparison rows", int(meta.get("rows", 0)))
    c3.metric("READY", int(meta.get("ready", 0)))
    c4.metric("MONITOR", int(meta.get("monitor", 0)))

    comparison_ready = bool(meta.get("comparison_ready", False))
    if comparison_ready:
        st.success(
            "✅ STEP 6 PASSED • every Step-5 game is reconciled to at least one exact same-book Moneyline pair; "
            "no-vig probabilities, model fair odds and analytical edge are available without changing the model probability."
        )
    else:
        st.warning(
            "⚠️ STEP 6 CHECK • at least one Step-5 game has no valid same-book two-sided Moneyline comparison row. "
            "5M Monte Carlo remains locked."
        )

    if board is not None and not board.empty:
        show = board.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Away market"] = show.apply(lambda r: f"{r['away_team']} {_fmt_price(r['away_price'])}", axis=1)
        show["Home market"] = show.apply(lambda r: f"{r['home_team']} {_fmt_price(r['home_price'])}", axis=1)
        show["Away model"] = show["away_model_prob"].map(_fmt_pct)
        show["Home model"] = show["home_model_prob"].map(_fmt_pct)
        show["Away no-vig"] = show["away_market_novig"].map(_fmt_pct)
        show["Home no-vig"] = show["home_market_novig"].map(_fmt_pct)
        show["Away fair odds"] = show["away_fair_odds"].map(_fmt_price)
        show["Home fair odds"] = show["home_fair_odds"].map(_fmt_price)
        show["Away edge"] = show["away_edge_pp"].map(_fmt_edge)
        show["Home edge"] = show["home_edge_pp"].map(_fmt_edge)
        st.dataframe(
            show[[
                "Game", "first_tip_et", "book", "Away market", "Home market",
                "Away model", "Home model", "Away no-vig", "Home no-vig",
                "Away fair odds", "Home fair odds", "Away edge", "Home edge", "state",
            ]].rename(columns={"first_tip_et": "Tip ET", "book": "Book", "state": "State"}),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("🧮 Step 6 probability audit — implied probability + vig removal", expanded=False):
            audit = show.copy()
            audit["Away raw implied"] = audit["away_raw_implied"].map(_fmt_pct)
            audit["Home raw implied"] = audit["home_raw_implied"].map(_fmt_pct)
            audit["Book overround"] = audit["market_overround"].map(lambda x: _fmt_pct(x, 2))
            audit["Projected home margin"] = audit["projected_home_margin"].map(lambda x: "—" if not np.isfinite(_num(x, np.nan)) else f"{x:+.1f}")
            audit["Model σ"] = audit["sigma"].map(lambda x: "—" if not np.isfinite(_num(x, np.nan)) else f"{x:.1f}")
            audit["Sportsbook projection inputs"] = audit.get("sportsbook_projection_inputs", 0)
            st.dataframe(
                audit[[
                    "Game", "Book", "Away raw implied", "Home raw implied", "Book overround",
                    "Away no-vig", "Home no-vig", "Away model", "Home model",
                    "Projected home margin", "Model σ", "Sportsbook projection inputs", "State",
                ]] if "Book" in audit.columns else audit.assign(Book=audit["book"], State=audit["state"])[[
                    "Game", "Book", "Away raw implied", "Home raw implied", "Book overround",
                    "Away no-vig", "Home no-vig", "Away model", "Home model",
                    "Projected home margin", "Model σ", "Sportsbook projection inputs", "State",
                ]],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "No-vig uses only the two prices from the same verified sportsbook row. The model column is copied from Step 5 and is never re-fit to the market. "
                "Edge is model probability minus same-book no-vig probability; it is analytical only until the 5M production simulation is built."
            )

        st.session_state["wnba_moneyline_v13_step6_board"] = board.copy()
        st.session_state["wnba_moneyline_v13_step6_meta"] = dict(meta)

    return board, {**dict(meta), "comparison_ready": comparison_ready}


def render_wnba_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 💰 WNBA Moneyline Command Center")
    st.caption(
        "V1.3 • verified slate → clock-safe pregame guard → team context → exact-day availability → exact sportsbook Moneyline → "
        "independent win probability → same-book no-vig + model fair odds. 5M Monte Carlo remains OFF."
    )

    default_day = st.session_state.get("wnba_moneyline_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input(
        "Moneyline slate date",
        value=pd.to_datetime(default_day).date(),
        key="wnba_moneyline_v1_date_picker",
    )
    st.session_state["wnba_moneyline_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("📅 Verifying WNBA Moneyline slate + clock-safe pregame eligibility…"):
        schedule = foundation._schedule(day_str)
        pregame = clock._pregame_schedule(schedule, now_et=now_et)
        excluded = clock._excluded_schedule(schedule, now_et=now_et)

    teams = 0
    if not schedule.empty:
        team_ids = set()
        for col in ("away_team_id", "home_team_id"):
            if col in schedule.columns:
                team_ids.update(pd.to_numeric(schedule[col], errors="coerce").dropna().astype(int).tolist())
        teams = len(team_ids)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(len(schedule)))
    c2.metric("Pregame eligible", int(len(pregame)))
    c3.metric("Excluded / locked", int(len(excluded)))
    c4.metric("Model state", "STEP 6")
    st.caption(f"Pregame eligibility clock • {now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')}")

    if schedule.empty:
        st.warning("No verified WNBA games were returned for this Eastern-date slate. Nothing is projected or fabricated.")
        return

    st.success(f"✅ STEP 1 PASSED • verified WNBA slate loaded for {day_str}.")
    if len(pregame):
        st.success(f"✅ PREGAME ELIGIBILITY PASSED • {len(pregame)} game(s) are still before scheduled tip and provider-safe.")
    else:
        st.info("ℹ️ No games on this slate remain pregame-eligible. Passed-tip/live/final/uncertain-tip games are locked out.")

    if not excluded.empty:
        with st.expander("🚫 Games excluded from Moneyline pregame production", expanded=False):
            cols = [c for c in [
                "away_team", "home_team", "first_tip_et", "scheduled_tip_guard_et",
                "status", "status_text", "exclusion_reason",
            ] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    with st.spinner("📊 Building verified team form + matchup context…"):
        try:
            contexts, cdiag = foundation.context.slate_context(day_str)
        except Exception as exc:
            contexts, cdiag = {}, {"state": "CHECK", "reason": type(exc).__name__}

    context_state = str(cdiag.get("state") or "CHECK").upper()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Context state", context_state)
    d2.metric("Records verified", f"{int(cdiag.get('records_verified', 0) or 0)}/{int(cdiag.get('teams', teams) or teams)}")
    d3.metric("Advanced teams", int(cdiag.get("advanced_teams", 0) or 0))
    d4.metric("H2H samples", int(cdiag.get("h2h_samples", 0) or 0))
    if context_state == "VERIFIED":
        st.success("✅ STEP 2 PASSED • team records/recent form are verified; advanced pace/ratings are used only where real samples exist.")
    else:
        st.warning("⚠️ STEP 2 CHECK • some team context is incomplete. Missing advanced fields remain neutral/missing; nothing is invented.")

    with st.spinner("🩺 Verifying exact-day current team availability for pregame-eligible games…"):
        av = spread_current._availability_snapshot_exact_day(day_str, pregame)
    av_map = {str(r.get("game_id") or ""): r.to_dict() for _, r in av.iterrows()} if not av.empty else {}

    covered = int(pd.to_numeric(av.get("covered_teams", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0
    expected_coverage = int(2 * len(pregame))
    unverified = int(pd.to_numeric(av.get("unverified", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Availability coverage", f"{covered}/{expected_coverage}" if expected_coverage else "0/0")
    a2.metric("Hard OUT", int(pd.to_numeric(av.get("hard_out", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0)
    a3.metric("Status uncertain", int(pd.to_numeric(av.get("uncertain", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0)
    a4.metric("Unverified players", unverified)

    availability_ready = bool(expected_coverage > 0 and covered == expected_coverage and unverified == 0)
    if availability_ready:
        st.success("✅ STEP 3 PASSED • current availability coverage is complete for every pregame-eligible game.")
    elif expected_coverage == 0:
        st.info("ℹ️ STEP 3 NOT APPLICABLE • there are no remaining pregame-eligible games on this slate.")
    else:
        st.warning("⚠️ STEP 3 CHECK • availability is not fully verified for every pregame-eligible game. Future Moneyline production remains locked.")

    st.markdown("### 🧩 Pregame-Eligible Moneyline Foundation")
    if pregame.empty:
        st.info("No pregame-eligible games remain to display.")
    else:
        for _, game in pregame.iterrows():
            prior.prior.prior._render_game_context(game, contexts, av_map)

    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)
    ready_ml, market_meta = prior.prior._render_step4(day_str, pregame, foundation_ready)
    market_ready = bool(market_meta.get("market_ready"))

    win_board, step5 = prior._render_step5(day_str, pregame, contexts, market_ready)
    win_ready = bool(step5.get("model_ready", False))

    compare_board, step6 = _render_step6(win_board, ready_ml, win_ready)
    comparison_ready = bool(step6.get("comparison_ready", False))

    st.session_state["wnba_moneyline_v1_day"] = day_str
    st.session_state["wnba_moneyline_v1_foundation_ready"] = foundation_ready
    st.session_state["wnba_moneyline_v1_schedule"] = schedule.to_dict("records")
    st.session_state["wnba_moneyline_v1_pregame"] = pregame.to_dict("records")
    st.session_state["wnba_moneyline_v1_availability"] = av.to_dict("records") if not av.empty else []
    st.session_state["wnba_moneyline_v11_market_ready"] = market_ready
    st.session_state["wnba_moneyline_v11_market_rows"] = ready_ml.to_dict("records") if not ready_ml.empty else []
    st.session_state["wnba_moneyline_v11_market_meta"] = market_meta
    st.session_state["wnba_moneyline_v12_model_ready"] = win_ready
    st.session_state["wnba_moneyline_v13_comparison_ready"] = comparison_ready
    st.session_state["wnba_moneyline_v13_comparison_rows"] = compare_board.to_dict("records") if not compare_board.empty else []

    st.markdown("### 🔒 Moneyline Production Locks")
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Team context", "State": "READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Exact sportsbook moneyline", "State": "READY" if market_ready else ("CHECK" if foundation_ready else "LOCKED")},
        {"Layer": "Independent win probability", "State": "READY" if win_ready else ("CHECK" if market_ready else "LOCKED")},
        {"Layer": "No-vig / fair odds", "State": "READY" if comparison_ready else ("CHECK" if win_ready else "LOCKED")},
        {"Layer": "5M Monte Carlo", "State": "NEXT" if comparison_ready else "LOCKED"},
        {"Layer": "Final Moneyline grading", "State": "OFF"},
        {"Layer": "Daily Picks connector", "State": "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.3 makes no Moneyline pick. Step 6 compares the frozen Step-5 probability with exact same-book no-vig market probability and model fair odds. "
        "The actual 5,000,000-draw Moneyline Monte Carlo is the next production layer."
    )


__all__ = [
    "MODEL_VERSION",
    "render_wnba_moneyline_hub",
    "_novig_fair_board",
    "_render_step6",
    "_american_implied",
    "_fair_american",
]
