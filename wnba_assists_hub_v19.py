"""WNBA Assists V19 — Step 19 model-vs-market edge + exact posted-price EV.

Preserves Assists Steps 1–18 and adds deterministic market grading only.

Architecture:
MODEL:  Steps 1–12 -> 15 -> 16 -> 17 ----\
                                          -> Step 18 -> Step 19 -> Step 20
MARKET: Steps 13 -> 14 ------------------/

Step 19 rules:
- Step 18 must PASS on the current render; no stale session-only Step-18 payload
  can unlock this layer;
- use Step-18 push-aware model probabilities and Step-14 no-vig probabilities
  exactly as supplied; Step 19 never changes the projection or distribution;
- probability edge is model fair action probability minus same-book no-vig
  probability, so integer-line push/refund is not incorrectly treated as loss;
- exact posted-price EV per $100 stake is push-aware:
      EV = P(win)*profit_per_$100 - P(loss)*$100
  with P(push) contributing $0 profit/loss because stake is returned;
- Over and Under are graded independently at their exact posted American prices;
- quote freshness and scheduled tip are rechecked without making a new market
  request; stale or started-game rows fail closed;
- preserve Monte Carlo probability SE for Step-20 risk adjustment;
- no ranking, recommendation threshold, Kelly sizing or Top-5 selection here.

Step 20 owns risk-adjusted qualification + Top 5 and may reject positive-EV rows.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v18 as v18

MODEL_VERSION = "WNBA ASSISTS V19 • STEP 19 MODEL-VS-MARKET EDGE + EXACT POSTED-PRICE EV"
_ET = ZoneInfo("America/New_York")
MAX_QUOTE_AGE_SECONDS = 15 * 60


def _num(value: Any, default: float = np.nan) -> float:
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _valid_american(value: Any) -> bool:
    x = _num(value)
    return bool(np.isfinite(x) and abs(x) >= 100.0)


def _implied_prob(american: Any) -> float:
    odds = _num(american)
    if not _valid_american(odds):
        return np.nan
    if odds > 0:
        return float(100.0 / (odds + 100.0))
    return float((-odds) / ((-odds) + 100.0))


def _profit_per_100(american: Any) -> float:
    odds = _num(american)
    if not _valid_american(odds):
        return np.nan
    if odds > 0:
        return float(odds)
    return float(10000.0 / abs(odds))


def _fmt_odds(value: Any) -> str:
    x = _num(value)
    return "—" if not np.isfinite(x) else f"{int(round(x)):+d}"


def _tip_is_upcoming(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        ts = pd.to_datetime(raw, errors="raise")
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.tz_localize(_ET)
        else:
            ts = ts.tz_convert(_ET)
        return bool(ts.to_pydatetime() > datetime.now(_ET))
    except Exception:
        return False


def _build_step19_edge_ev(
    step18_rows: pd.DataFrame,
    step18_ready: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not step18_ready:
        return pd.DataFrame(), {
            "ready": False,
            "state": "LOCKED",
            "reason": "current Step 18 has not passed",
            "rows_received": 0 if step18_rows is None else len(step18_rows),
            "rows_graded": 0,
        }
    if step18_rows is None or step18_rows.empty:
        return pd.DataFrame(), {
            "ready": False,
            "state": "CHECK",
            "reason": "Step 18 passed but supplied no current line-probability rows",
            "rows_received": 0,
            "rows_graded": 0,
        }

    rows: list[dict[str, Any]] = []
    blocked = {
        "stale": 0,
        "started": 0,
        "identity": 0,
        "probability": 0,
        "price": 0,
        "novig": 0,
    }
    positive_over = 0
    positive_under = 0
    positive_any = 0
    max_abs_edge = 0.0
    max_ev = -np.inf

    for _, src in step18_rows.iterrows():
        # Step 18 already verified these fields. Requiring them again prevents a
        # malformed/stale session row from being silently graded by Step 19.
        player = str(src.get("PLAYER_NAME") or "").strip()
        team = str(src.get("TEAM") or "").strip()
        opponent = str(src.get("OPPONENT") or "").strip()
        book = str(src.get("BOOK") or "").strip()
        event_id = str(src.get("EVENT_ID") or "").strip()
        game_id = str(src.get("GAME_ID") or "").strip()
        line = _num(src.get("LINE"))
        if not player or not team or not opponent or not book or not event_id or not game_id or not np.isfinite(line):
            blocked["identity"] += 1
            continue

        age = v18._actual_quote_age_seconds(src)
        if not np.isfinite(age):
            age = _num(src.get("QUOTE_AGE_SECONDS_STEP18"))
        if not np.isfinite(age) or age > MAX_QUOTE_AGE_SECONDS:
            blocked["stale"] += 1
            continue
        if not _tip_is_upcoming(src.get("TIP_ET")):
            blocked["started"] += 1
            continue

        over_odds = _num(src.get("OVER_ODDS"))
        under_odds = _num(src.get("UNDER_ODDS"))
        if not _valid_american(over_odds) or not _valid_american(under_odds):
            blocked["price"] += 1
            continue

        p_over = _num(src.get("MODEL_OVER_PROB"))
        p_under = _num(src.get("MODEL_UNDER_PROB"))
        p_push = _num(src.get("MODEL_PUSH_PROB"))
        fair_over = _num(src.get("MODEL_FAIR_OVER_PROB"))
        fair_under = _num(src.get("MODEL_FAIR_UNDER_PROB"))
        if any(not np.isfinite(x) for x in (p_over, p_under, p_push, fair_over, fair_under)):
            blocked["probability"] += 1
            continue
        if min(p_over, p_under, p_push, fair_over, fair_under) < -1e-10:
            blocked["probability"] += 1
            continue
        if abs((p_over + p_under + p_push) - 1.0) > 1e-5 or abs((fair_over + fair_under) - 1.0) > 1e-5:
            blocked["probability"] += 1
            continue

        novig_over = _num(src.get("NOVIG_OVER_PROB"))
        novig_under = _num(src.get("NOVIG_UNDER_PROB"))
        if (
            not np.isfinite(novig_over)
            or not np.isfinite(novig_under)
            or min(novig_over, novig_under) <= 0.0
            or abs((novig_over + novig_under) - 1.0) > 1e-5
        ):
            blocked["novig"] += 1
            continue

        posted_over_implied = _implied_prob(over_odds)
        posted_under_implied = _implied_prob(under_odds)
        over_profit = _profit_per_100(over_odds)
        under_profit = _profit_per_100(under_odds)
        if any(not np.isfinite(x) for x in (posted_over_implied, posted_under_implied, over_profit, under_profit)):
            blocked["price"] += 1
            continue

        # Fair/action edge compares like-for-like two-way probabilities. This is
        # essential on integer lines because the model push is a refund, not loss.
        over_edge = fair_over - novig_over
        under_edge = fair_under - novig_under

        # Exact posted-price EV per $100 staked. Push contributes zero net profit.
        over_ev = p_over * over_profit - p_under * 100.0
        under_ev = p_under * under_profit - p_over * 100.0
        over_roi = over_ev / 100.0
        under_roi = under_ev / 100.0

        if over_ev > 0:
            positive_over += 1
        if under_ev > 0:
            positive_under += 1
        if max(over_ev, under_ev) > 0:
            positive_any += 1
        max_abs_edge = max(max_abs_edge, abs(over_edge), abs(under_edge))
        max_ev = max(max_ev, over_ev, under_ev)

        if abs(over_ev - under_ev) <= 1e-9:
            higher_side = "TIE"
            higher_ev = over_ev
        elif over_ev > under_ev:
            higher_side = "OVER"
            higher_ev = over_ev
        else:
            higher_side = "UNDER"
            higher_ev = under_ev

        positive_sides = []
        if over_ev > 0:
            positive_sides.append("OVER")
        if under_ev > 0:
            positive_sides.append("UNDER")

        rows.append({
            "PLAYER_ID": src.get("PLAYER_ID"),
            "PLAYER_NAME": player,
            "TEAM": team,
            "OPPONENT": opponent,
            "BOOK": book,
            "LINE": float(line),
            "OVER_ODDS": int(round(over_odds)),
            "UNDER_ODDS": int(round(under_odds)),
            "POSTED_OVER_IMPLIED": posted_over_implied,
            "POSTED_UNDER_IMPLIED": posted_under_implied,
            "MODEL_OVER_PROB": p_over,
            "MODEL_UNDER_PROB": p_under,
            "MODEL_PUSH_PROB": p_push,
            "MODEL_FAIR_OVER_PROB": fair_over,
            "MODEL_FAIR_UNDER_PROB": fair_under,
            "MODEL_FAIR_OVER_ODDS": src.get("MODEL_FAIR_OVER_ODDS"),
            "MODEL_FAIR_UNDER_ODDS": src.get("MODEL_FAIR_UNDER_ODDS"),
            "NOVIG_OVER_PROB": novig_over,
            "NOVIG_UNDER_PROB": novig_under,
            "OVER_EDGE_VS_NOVIG": over_edge,
            "UNDER_EDGE_VS_NOVIG": under_edge,
            "OVER_PROFIT_PER_100": over_profit,
            "UNDER_PROFIT_PER_100": under_profit,
            "OVER_EV_PER_100": over_ev,
            "UNDER_EV_PER_100": under_ev,
            "OVER_ROI": over_roi,
            "UNDER_ROI": under_roi,
            "HIGHER_EV_SIDE": higher_side,
            "HIGHER_EV_PER_100": higher_ev,
            "POSITIVE_EV_SIDES": ", ".join(positive_sides) if positive_sides else "NONE",
            "EXPECTED_ASSISTS": _num(src.get("EXPECTED_ASSISTS")),
            "MC_MEAN": _num(src.get("MC_MEAN")),
            "MC_SD": _num(src.get("MC_SD")),
            "MC_OVER_SE": _num(src.get("MC_OVER_SE")),
            "MC_UNDER_SE": _num(src.get("MC_UNDER_SE")),
            "SIMULATIONS": int(_num(src.get("SIMULATIONS"), 0)),
            "CONVERGED": bool(src.get("CONVERGED")),
            "QUOTE_AGE_SECONDS_STEP19": float(age),
            "OVER_UPDATED": str(src.get("OVER_UPDATED") or ""),
            "UNDER_UPDATED": str(src.get("UNDER_UPDATED") or ""),
            "EVENT_ID": event_id,
            "GAME_ID": game_id,
            "TIP_ET": str(src.get("TIP_ET") or ""),
            "MARKET": "Assists",
            "EDGE_SOURCE": "Step-18 model fair action probability minus Step-14 same-book no-vig",
            "EV_SOURCE": "Step-18 raw win/loss/push probabilities × exact Step-13 posted price",
            "MODEL_VERSION_STEP19": MODEL_VERSION,
            "GRADE_STATE": "PASS",
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(
            ["PLAYER_NAME", "LINE", "BOOK", "QUOTE_AGE_SECONDS_STEP19"],
            ascending=[True, True, True, True],
        ).reset_index(drop=True)

    ready = bool(not out.empty)
    return out, {
        "ready": ready,
        "state": "VERIFIED" if ready else "CHECK",
        "reason": "" if ready else "no current Step-18 row survived Step-19 freshness/identity/probability/price gates",
        "rows_received": len(step18_rows),
        "rows_graded": len(out),
        "players_graded": int(out["PLAYER_NAME"].nunique()) if not out.empty else 0,
        "books_graded": int(out["BOOK"].nunique()) if not out.empty else 0,
        "positive_over_rows": positive_over,
        "positive_under_rows": positive_under,
        "positive_any_rows": positive_any,
        "max_abs_edge": max_abs_edge,
        "max_ev_per_100": max_ev if np.isfinite(max_ev) else np.nan,
        "stale_blocked": blocked["stale"],
        "started_blocked": blocked["started"],
        "identity_blocked": blocked["identity"],
        "probability_blocked": blocked["probability"],
        "price_blocked": blocked["price"],
        "novig_blocked": blocked["novig"],
        "new_simulations": 0,
        "projection_changes": 0,
        "ranking_calculations": 0,
        "qualification_calculations": 0,
    }


def _render_step19(
    step18_rows: pd.DataFrame,
    step18_ready: bool,
    day_str: str,
) -> tuple[bool, pd.DataFrame, dict[str, Any]]:
    st.markdown("### 💹 Step 19 — Model-vs-Market Edge + Exact Posted-Price EV")
    st.caption(
        "Pure grading layer. Step 19 does not change expected assists, the calibrated distribution, or the 5M Monte Carlo result. It compares Step-18 model fair action probabilities with Step-14 same-book no-vig, then prices exact push-aware EV at the current Step-13 posted odds."
    )

    result, diag = _build_step19_edge_ev(step18_rows, step18_ready)
    ready = bool(diag.get("ready"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Step-18 rows", int(diag.get("rows_received") or 0))
    c2.metric("Rows graded", int(diag.get("rows_graded") or 0))
    c3.metric("Players graded", int(diag.get("players_graded") or 0))
    c4.metric("New simulations", "0")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Positive-EV markets", int(diag.get("positive_any_rows") or 0))
    d2.metric("Max |no-vig edge|", f"{100.0 * float(diag.get('max_abs_edge') or 0.0):.2f}%")
    max_ev = _num(diag.get("max_ev_per_100"))
    d3.metric("Max EV / $100", "—" if not np.isfinite(max_ev) else f"${max_ev:+.2f}")
    d4.metric("Ranking / qualification", "0 / 0")

    if ready:
        st.success(
            "✅ STEP 19 PASSED • every displayed market was graded against the frozen model at its exact current posted price. Integer-line pushes are refunds in EV math. Step 19 does not rank, recommend or qualify picks."
        )
    else:
        st.warning(
            f"⚠️ STEP 19 CHECK • {diag.get('reason') or 'edge/EV grading incomplete'}. Step 20 remains locked."
        )

    blocked_total = sum(int(diag.get(k) or 0) for k in (
        "stale_blocked", "started_blocked", "identity_blocked", "probability_blocked", "price_blocked", "novig_blocked"
    ))
    if blocked_total:
        st.caption(
            "Row-level holds • "
            f"stale {int(diag.get('stale_blocked') or 0)} • "
            f"started {int(diag.get('started_blocked') or 0)} • "
            f"identity {int(diag.get('identity_blocked') or 0)} • "
            f"probability {int(diag.get('probability_blocked') or 0)} • "
            f"price {int(diag.get('price_blocked') or 0)} • "
            f"no-vig {int(diag.get('novig_blocked') or 0)}"
        )

    if result is not None and not result.empty:
        view = result.copy()
        view["Player"] = view["PLAYER_NAME"].astype(str)
        view["Team"] = view["TEAM"].astype(str)
        view["Opponent"] = view["OPPONENT"].astype(str)
        view["Book"] = view["BOOK"].astype(str)
        view["Line"] = pd.to_numeric(view["LINE"], errors="coerce")
        view["Posted O"] = view["OVER_ODDS"].map(_fmt_odds)
        view["Posted U"] = view["UNDER_ODDS"].map(_fmt_odds)
        view["Model O fair"] = (100.0 * pd.to_numeric(view["MODEL_FAIR_OVER_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
        view["No-vig O"] = (100.0 * pd.to_numeric(view["NOVIG_OVER_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
        view["O edge"] = (100.0 * pd.to_numeric(view["OVER_EDGE_VS_NOVIG"], errors="coerce")).map(lambda x: f"{x:+.2f}%")
        view["O EV/$100"] = pd.to_numeric(view["OVER_EV_PER_100"], errors="coerce").map(lambda x: f"${x:+.2f}")
        view["Model U fair"] = (100.0 * pd.to_numeric(view["MODEL_FAIR_UNDER_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
        view["No-vig U"] = (100.0 * pd.to_numeric(view["NOVIG_UNDER_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
        view["U edge"] = (100.0 * pd.to_numeric(view["UNDER_EDGE_VS_NOVIG"], errors="coerce")).map(lambda x: f"{x:+.2f}%")
        view["U EV/$100"] = pd.to_numeric(view["UNDER_EV_PER_100"], errors="coerce").map(lambda x: f"${x:+.2f}")
        view["Push"] = (100.0 * pd.to_numeric(view["MODEL_PUSH_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
        view["Higher EV"] = view["HIGHER_EV_SIDE"].astype(str)
        view["Quote age"] = pd.to_numeric(view["QUOTE_AGE_SECONDS_STEP19"], errors="coerce").map(
            lambda x: "—" if pd.isna(x) else (f"{int(x)}s" if x < 120 else f"{int(x // 60)}m")
        )
        st.dataframe(
            view[[
                "Player", "Team", "Opponent", "Book", "Line", "Posted O", "Posted U",
                "Model O fair", "No-vig O", "O edge", "O EV/$100", "Push",
                "Model U fair", "No-vig U", "U edge", "U EV/$100", "Higher EV", "Quote age",
            ]],
            hide_index=True,
            use_container_width=True,
        )

        st.session_state[f"wnba_assists_v19_edge_ev::{day_str}"] = result.copy()
        st.session_state[f"wnba_assists_v19_diag::{day_str}"] = dict(diag)

    with st.expander("🧪 Step-19 edge / EV methodology", expanded=False):
        st.write("• Projection/model probability is frozen at Step 18; Step 19 cannot move it.")
        st.write("• No-vig edge uses like-for-like action probabilities: model fair Over/Under probability minus Step-14 same-book no-vig probability.")
        st.write("• Integer-line push is excluded from the fair/action edge because push is a refund, not a win or loss.")
        st.write("• Exact posted-price EV per $100: P(win) × win-profit − P(loss) × $100. P(push) × $0.")
        st.write("• American odds profit on $100: +A wins $A; −A wins $10,000/|A|.")
        st.write("• Over and Under are graded independently at the exact Step-13 posted prices.")
        st.write("• Quote age is recomputed from the captured Over/Under timestamps; no new sportsbook request is made here.")
        st.write("• Exact scheduled tip is rechecked; a started game cannot remain gradeable.")
        st.write("• Monte Carlo probability SE is preserved in the output for Step-20 risk adjustment.")
        st.write("• New simulations: 0.")
        st.write("• Ranking: NO — Step 20.")
        st.write("• Qualification / Top 5: NO — Step 20.")

    return ready, result, diag


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day_str = datetime.now(_ET).strftime("%Y-%m-%d")
    runtime: dict[str, Any] = {
        "step18_rendered": False,
        "step18_ready": False,
        "step18_rows": pd.DataFrame(),
        "step18_diag": {},
        "step19_rendered": False,
        "step19_ready": False,
        "step19_rows": pd.DataFrame(),
        "step19_diag": {},
    }

    original_button = st.button
    original_card = v18.v17.v16.v15.step3._layer_card
    original_caption = st.caption
    original_markdown = st.markdown
    original_step18 = v18._render_step18

    def capture_step18(*args, **kwargs):
        result = original_step18(*args, **kwargs)
        try:
            ready, rows, diag = result
            runtime["step18_rendered"] = True
            runtime["step18_ready"] = bool(ready)
            runtime["step18_rows"] = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame()
            runtime["step18_diag"] = dict(diag or {})
        except Exception:
            runtime["step18_rendered"] = True
            runtime["step18_ready"] = False
            runtime["step18_rows"] = pd.DataFrame()
            runtime["step18_diag"] = {}
        return result

    def ensure_step19():
        if runtime["step19_rendered"]:
            return
        ready, rows, diag = _render_step19(
            runtime["step18_rows"],
            bool(runtime["step18_ready"]),
            day_str,
        )
        runtime.update({
            "step19_rendered": True,
            "step19_ready": bool(ready),
            "step19_rows": rows,
            "step19_diag": dict(diag or {}),
        })

    def fixed_button(label, *args, **kwargs):
        text = str(label)
        if text == "🔄 RECHECK ASSISTS STEPS 2–18":
            ensure_step19()
            text = "🔄 RECHECK ASSISTS STEPS 2–19"
            clicked = original_button(text, *args, **kwargs)
            if clicked:
                st.session_state.pop(f"wnba_assists_v19_edge_ev::{day_str}", None)
                st.session_state.pop(f"wnba_assists_v19_diag::{day_str}", None)
            return clicked
        return original_button(label, *args, **kwargs)

    def fixed_card(step, label, card_state, note=""):
        number = int(step)
        if number == 19:
            if runtime["step19_ready"]:
                card_state = "✅ LIVE"
                note = "Push-aware no-vig edge + exact posted-price EV"
            else:
                card_state = "⚠️ CHECK" if runtime["step18_ready"] else "🔒 LOCKED"
                note = "Requires current Step-18 PASS"
        elif number == 20:
            card_state = "➡️ NEXT" if runtime["step19_ready"] else "🔒 LOCKED"
            note = "Risk-adjusted qualification + Top 5 • never force five"
        return original_card(step, label, card_state, note)

    def fixed_caption(body, *args, **kwargs):
        text = str(body)
        if text.startswith("⚡ WNBA Assists V18 Step 18"):
            text = text.replace("WNBA Assists V18 Step 18", "WNBA Assists V19 Step 19", 1)
            if "Step 18 PASS" in text:
                text += f" • Step 19 {'PASS' if runtime['step19_ready'] else 'CHECK'} • exact no-vig edge + posted-price EV • ranking 0"
        return original_caption(text, *args, **kwargs)

    def fixed_markdown(body, *args, **kwargs):
        text = body
        if isinstance(text, str) and "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 18" in text:
            text = text.replace(
                "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 18",
                "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 19",
            )
            text = text.replace(
                "Steps 1–17 remain intact. Step 18 performs the first controlled join: the exact current Assist line is applied to the converged 5M player distribution to create push-aware model O/U probabilities and model fair odds. Edge/EV remain locked for Step 19.",
                "Steps 1–18 remain intact. Step 19 grades the frozen push-aware model probability against the same-book no-vig market and exact current posted price. Projection/simulation math is unchanged; ranking and qualification remain locked for Step 20.",
            )
        return original_markdown(text, *args, **kwargs)

    st.button = fixed_button
    v18.v17.v16.v15.step3._layer_card = fixed_card
    st.caption = fixed_caption
    st.markdown = fixed_markdown
    v18._render_step18 = capture_step18
    try:
        v18.render_wnba_assists_hub(section_header, status_info, team_logo, h)
        if not runtime["step19_rendered"]:
            ensure_step19()
    finally:
        st.button = original_button
        v18.v17.v16.v15.step3._layer_card = original_card
        st.caption = original_caption
        st.markdown = original_markdown
        v18._render_step18 = original_step18


__all__ = [
    "MODEL_VERSION",
    "_build_step19_edge_ev",
    "_render_step19",
    "render_wnba_assists_hub",
]
