"""WNBA Rebounds V2.9 — Step 20 risk-adjusted qualification + ranking / final card.

Extends the verified V2.8 chain without changing Steps 1-19.

Rules:
- Consume only VERIFIED Step-19 exact bookmaker/line side rows.
- Keep the rebound projection market-independent; Step 20 only qualifies/ranks.
- Require robust positive edge, >=3% no-vig edge, >=3% posted-price EV,
  positive adverse-sensitivity edge, and a model decision probability >=50%.
- Preserve exact book, line and posted odds. Never blend books or lines.
- Deduplicate to one best exact quote per player on the final card and on each
  side-specific board. Never force five selections.
- No staking or bet sizing is created here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v28 as base

MODEL_VERSION = "WNBA REBOUNDS V2.9 • STEP 20 RISK-ADJUSTED QUALIFICATION + FINAL CARD"

MIN_NO_VIG_EDGE = 0.030
MIN_EV = 0.030
MIN_WORST_EDGE = 0.0
MIN_DECISION_PROB = 0.500
MAX_SENSITIVITY_WIDTH = 0.120
MAX_FINAL_CARD = 5


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _rank_score(row: pd.Series) -> float:
    edge = _num(row.get("No-vig edge"), -999.0)
    worst = _num(row.get("Sensitivity worst edge"), -999.0)
    ev = _num(row.get("Expected ROI"), -999.0)
    prob = _num(row.get("Model decision probability"), 0.0)
    sens_low = _num(row.get("Sensitivity decision low"))
    sens_high = _num(row.get("Sensitivity decision high"))
    push = max(0.0, _num(row.get("Model P(push)"), 0.0))
    width = sens_high - sens_low if np.isfinite(sens_low) and np.isfinite(sens_high) else 1.0
    prob_lift = max(0.0, prob - 0.50)
    return float(
        0.35 * worst
        + 0.25 * edge
        + 0.20 * ev
        + 0.20 * prob_lift
        - 0.10 * max(0.0, width)
        - 0.05 * push
    )


def _qualification(row: pd.Series):
    if str(row.get("Step19 side state") or "") != "VERIFIED":
        return False, "UNVERIFIED"

    edge = _num(row.get("No-vig edge"))
    ev = _num(row.get("Expected ROI"))
    worst = _num(row.get("Sensitivity worst edge"))
    prob = _num(row.get("Model decision probability"))
    sens_low = _num(row.get("Sensitivity decision low"))
    sens_high = _num(row.get("Sensitivity decision high"))
    robustness = str(row.get("Edge robustness") or "")

    if not all(np.isfinite(x) for x in [edge, ev, worst, prob, sens_low, sens_high]):
        return False, "CHECK"

    reasons = []
    width = sens_high - sens_low
    if robustness != "POSITIVE • ROBUST":
        reasons.append("NOT ROBUST")
    if edge < MIN_NO_VIG_EDGE:
        reasons.append("EDGE <3%")
    if ev < MIN_EV:
        reasons.append("EV <3%")
    if worst <= MIN_WORST_EDGE:
        reasons.append("WORST EDGE ≤0")
    if prob < MIN_DECISION_PROB:
        reasons.append("P <50%")
    if width > MAX_SENSITIVITY_WIDTH:
        reasons.append("SENSITIVITY WIDE")
    return len(reasons) == 0, ("QUALIFIED" if not reasons else " • ".join(reasons))


def _confidence_grade(row: pd.Series) -> str:
    edge = _num(row.get("No-vig edge"), 0.0)
    worst = _num(row.get("Sensitivity worst edge"), 0.0)
    ev = _num(row.get("Expected ROI"), 0.0)
    prob = _num(row.get("Model decision probability"), 0.0)
    if edge >= 0.075 and worst >= 0.035 and ev >= 0.08 and prob >= 0.60:
        return "A"
    if edge >= 0.050 and worst >= 0.020 and ev >= 0.05 and prob >= 0.56:
        return "B"
    return "C"


def _best_per_player(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    work = work.sort_values(
        ["Risk-adjusted score", "Sensitivity worst edge", "No-vig edge", "Expected ROI", "Model decision probability"],
        ascending=[False, False, False, False, False],
        kind="mergesort",
    )
    return work.drop_duplicates(subset=["Player"], keep="first").copy()


def _rank_board(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.head(MAX_FINAL_CARD).reset_index(drop=True).copy()
    out.insert(0, "Rank", np.arange(1, len(out) + 1))
    return out


def _build_step20():
    players19 = pd.DataFrame(st.session_state.get("wnba_rebounds_step19_players") or [])
    sides19 = pd.DataFrame(st.session_state.get("wnba_rebounds_step19_sides") or [])
    step19_ready = bool(st.session_state.get("wnba_rebounds_step19_ready"))

    if players19.empty or sides19.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": 0, "player_states": 0, "verified_sides": 0,
            "qualified_sides": 0, "final_card": 0,
            "reason": "verified Step-19 state unavailable",
        }

    verified = sides19[sides19.get("Step19 side state", "").astype(str).eq("VERIFIED")].copy()
    if verified.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": int(len(players19)), "player_states": 0,
            "verified_sides": 0, "qualified_sides": 0, "final_card": 0,
            "reason": "no verified Step-19 side rows",
        }

    qualifications, reasons, scores, grades = [], [], [], []
    for _, row in verified.iterrows():
        ok, reason = _qualification(row)
        qualifications.append(bool(ok))
        reasons.append(reason)
        scores.append(_rank_score(row))
        grades.append(_confidence_grade(row) if ok else "—")

    verified["Step20 qualified"] = qualifications
    verified["Qualification reason"] = reasons
    verified["Risk-adjusted score"] = scores
    verified["Confidence grade"] = grades

    qualified = verified[verified["Step20 qualified"]].copy()
    if not qualified.empty:
        qualified = qualified.sort_values(
            ["Risk-adjusted score", "Sensitivity worst edge", "No-vig edge", "Expected ROI", "Model decision probability"],
            ascending=[False, False, False, False, False],
            kind="mergesort",
        )

    final = _rank_board(_best_per_player(qualified))
    if not final.empty:
        final["Final card state"] = "QUALIFIED"

    over_board = _rank_board(_best_per_player(
        qualified[qualified["Side"].astype(str).eq("OVER")].copy()
    )) if not qualified.empty else pd.DataFrame()
    under_board = _rank_board(_best_per_player(
        qualified[qualified["Side"].astype(str).eq("UNDER")].copy()
    )) if not qualified.empty else pd.DataFrame()

    boards = []
    if not over_board.empty:
        boards.append(over_board.assign(Board="OVER"))
    if not under_board.empty:
        boards.append(under_board.assign(Board="UNDER"))
    side_boards = pd.concat(boards, ignore_index=True, sort=False) if boards else pd.DataFrame()

    player_states = int(players19.get("Step19 state", pd.Series(dtype=str)).astype(str).eq("VERIFIED").sum())
    ready = bool(
        step19_ready
        and player_states == len(players19)
        and len(verified) == len(sides19)
        and verified["Projection market input"].eq(False).all()
    )

    return verified, qualified, final, side_boards, {
        "ready": ready,
        "players": int(len(players19)),
        "player_states": player_states,
        "verified_sides": int(len(verified)),
        "qualified_sides": int(len(qualified)),
        "qualified_overs": int(len(over_board)),
        "qualified_unders": int(len(under_board)),
        "final_card": int(len(final)),
        "forced_five": False,
        "staking": False,
        "projection_market_input": False,
    }


def _render_board(title: str, frame: pd.DataFrame):
    st.markdown(title)
    if frame is None or frame.empty:
        st.info("No sides currently meet every qualification gate. The model will not force a pick.")
        return
    show = frame.copy()
    for col in [
        "Model decision probability", "Market no-vig probability", "No-vig edge",
        "Expected ROI", "Sensitivity worst edge", "Sensitivity decision low",
        "Sensitivity decision high", "Risk-adjusted score",
    ]:
        if col in show.columns:
            show[col] = (100.0 * pd.to_numeric(show[col], errors="coerce")).round(2)
    if "Model fair American" in show.columns:
        show["Model fair American"] = pd.to_numeric(show["Model fair American"], errors="coerce").round(0)
    cols = [c for c in [
        "Rank", "Player", "Team", "Opponent", "Book", "Line", "Side", "Posted odds",
        "Model decision probability", "Market no-vig probability", "No-vig edge",
        "Expected ROI", "Sensitivity worst edge", "Risk-adjusted score",
        "Model fair American", "Confidence grade",
    ] if c in show.columns]
    st.dataframe(show[cols], hide_index=True, use_container_width=True)


def _render_step20():
    st.markdown("## 🏆 Step 20 — Risk-Adjusted Qualification + Ranking / Final Card")
    st.caption(
        "This final layer does not change the rebound projection. It qualifies only verified Step-19 exact sportsbook "
        "sides. A side must retain positive edge in the adverse ±5% sensitivity scenario, carry at least a 3% no-vig "
        "edge and +3% expected ROI, and pass every prior verification gate. Duplicate books/lines collapse to one best "
        "exact quote per player. Five selections are never forced."
    )

    verified, qualified, final, side_boards, info = _build_step20()
    ready = bool(info.get("ready"))

    st.session_state["wnba_rebounds_step20_ready"] = ready
    st.session_state["wnba_rebounds_step20_all_sides"] = verified.to_dict("records") if not verified.empty else []
    st.session_state["wnba_rebounds_step20_qualified"] = qualified.to_dict("records") if not qualified.empty else []
    st.session_state["wnba_rebounds_step20_final_card"] = final.to_dict("records") if not final.empty else []

    a, b, c, d = st.columns(4)
    a.metric("Verified side rows", info.get("verified_sides", 0))
    b.metric("Qualified sides", info.get("qualified_sides", 0))
    c.metric("Final card", f"{info.get('final_card',0)}/{MAX_FINAL_CARD}")
    d.metric("Forced picks", "NO")

    if ready:
        if info.get("final_card", 0) > 0:
            st.success(
                f"✅ STEP 20 PASSED • {info.get('final_card',0)} risk-adjusted side(s) qualify for the final card. "
                "The card uses one exact quote per player and never forces a fifth selection."
            )
        else:
            st.success(
                "✅ STEP 20 PASSED • the full model/market chain is verified, but no current side clears every "
                "risk-adjusted qualification gate. FINAL CARD: NO QUALIFIED PLAY."
            )
    else:
        st.error(
            "⛔ STEP 20 CHECK • Step 19 or one of its exact side rows is not fully verified. Rankings remain blocked "
            "instead of using partial or guessed data."
        )

    _render_board("### 🏆 Final Qualified Card — Best Available Exact Quote", final)

    over_board = side_boards[side_boards.get("Board", pd.Series(dtype=str)).astype(str).eq("OVER")].copy() if not side_boards.empty else pd.DataFrame()
    under_board = side_boards[side_boards.get("Board", pd.Series(dtype=str)).astype(str).eq("UNDER")].copy() if not side_boards.empty else pd.DataFrame()
    _render_board("### 📈 Top Qualified Rebound Overs", over_board)
    _render_board("### 📉 Top Qualified Rebound Unders", under_board)

    with st.expander("🏆 Qualification audit — every verified side"):
        if verified.empty:
            st.info("No verified Step-19 side rows are available.")
        else:
            audit = verified.copy()
            for col in [
                "Model decision probability", "No-vig edge", "Expected ROI",
                "Sensitivity worst edge", "Sensitivity decision low", "Sensitivity decision high",
                "Risk-adjusted score",
            ]:
                if col in audit.columns:
                    audit[col] = (100.0 * pd.to_numeric(audit[col], errors="coerce")).round(2)
            cols = [c for c in [
                "Player", "Book", "Line", "Side", "Posted odds", "Model decision probability",
                "No-vig edge", "Expected ROI", "Sensitivity worst edge", "Edge robustness",
                "Risk-adjusted score", "Step20 qualified", "Qualification reason",
            ] if c in audit.columns]
            st.dataframe(audit[cols], hide_index=True, use_container_width=True)

    with st.expander("🏆 Step-20 methodology / diagnostics"):
        st.write({
            "qualification_gates": {
                "minimum_no_vig_edge": MIN_NO_VIG_EDGE,
                "minimum_expected_roi": MIN_EV,
                "minimum_worst_case_sensitivity_edge": "> 0",
                "minimum_model_decision_probability": MIN_DECISION_PROB,
                "maximum_sensitivity_width": MAX_SENSITIVITY_WIDTH,
                "required_step19_robustness": "POSITIVE • ROBUST",
            },
            "risk_adjusted_score": (
                "35% sensitivity-worst edge + 25% no-vig edge + 20% EV + "
                "20% probability lift above 50% − sensitivity-width penalty − push penalty"
            ),
            "deduplication": "one best exact quote per player",
            "maximum_final_card": MAX_FINAL_CARD,
            "force_five": False,
            "staking_or_bet_sizing": False,
            "projection_market_input": False,
            "new_network_requests": 0,
        })

    st.markdown("## 🧱 Rebounds Build Order — Complete")
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
        "✅ LIVE", "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 21), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V2.9 Step 20 • full Steps 1–20 chain • transparent risk-adjusted qualification • one best exact quote/player • "
        "no forced five • no staking/bet sizing • zero new network requests • projection remains market-independent."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step19_ready"):
        _render_step20()
    else:
        st.info("Step 20 remains locked until Step 19 is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
