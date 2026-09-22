"""WNBA Assists V18 — Step 18 line-specific O/U probability + fair odds.

Preserves Assists Steps 1–17 and performs the first controlled join between the
validated independent model branch and the exact current sportsbook line branch.

Architecture:
MODEL:  Steps 1–12 -> 15 -> 16 -> 17 ----\
                                          -> Step 18 -> Step 19 -> Step 20
MARKET: Steps 13 -> 14 ------------------/

Step 18 rules:
- current Step 13 and Step 14 must both be market-ready on THIS render;
- the saved Step-17 Monte Carlo snapshot must match the current Step-16
  distribution fingerprint and must have convergence=PASS;
- exact current player/team/book/line identity only; no fuzzy player matching;
- line-specific probabilities come from the actual 5,000,000-trial Step-17 MC
  PMF for that exact player;
- P(Over) = P(assists > line), P(Under) = P(assists < line), and integer lines
  retain an explicit push probability;
- model fair odds remove push by conditioning only on win/loss outcomes;
- Step-14 no-vig probabilities are displayed as a separate market reference but
  never alter the model probabilities or model fair odds;
- quote freshness is rechecked from the already-captured Step-13 timestamps;
- individual market rows fail closed when identity, PMF, convergence, freshness
  or same-book no-vig pairing cannot be verified;
- no EV, expected profit, edge ranking or Top-5 qualification is calculated here.

Step 19 owns model-vs-market edge + EV. Step 20 owns risk-adjusted qualification.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v17 as v17

MODEL_VERSION = "WNBA ASSISTS V18 • STEP 18 LINE-SPECIFIC O/U PROBABILITY + FAIR ODDS"
_ET = ZoneInfo("America/New_York")
MAX_QUOTE_AGE_SECONDS = 15 * 60


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


def _norm_name(value: Any) -> str:
    try:
        return str(v17.v16.v15.step13.sgo._norm(value) or "")
    except Exception:
        return " ".join(str(value or "").lower().split())


def _team_key(value: Any) -> str:
    try:
        return str(v17.v16.v15.step13.sgo._team_key(value) or "")
    except Exception:
        return " ".join(str(value or "").upper().split())


def _american_from_prob(prob: Any) -> float:
    p = _num(prob)
    if not np.isfinite(p) or p <= 0.0 or p >= 1.0:
        return np.nan
    if p >= 0.5:
        return float(round(-100.0 * p / (1.0 - p)))
    return float(round(100.0 * (1.0 - p) / p))


def _fmt_odds(value: Any) -> str:
    x = _num(value)
    return "—" if not np.isfinite(x) else f"{int(round(x)):+d}"


def _actual_quote_age_seconds(row: pd.Series) -> float:
    """Recompute freshness from the older side timestamp without a network call."""
    ages: list[float] = []
    now = datetime.now(timezone.utc)
    for col in ("OVER_UPDATED", "UNDER_UPDATED"):
        raw = str(row.get(col) or "").strip()
        if not raw:
            return np.nan
        try:
            ts = pd.to_datetime(raw, utc=True, errors="raise").to_pydatetime()
            ages.append(max(0.0, (now - ts).total_seconds()))
        except Exception:
            return np.nan
    return max(ages) if ages else np.nan


def _market_key(row: pd.Series) -> tuple[str, str, str, str, float, str, str]:
    return (
        _norm_name(row.get("PLAYER_NAME")),
        _team_key(row.get("TEAM")),
        _team_key(row.get("OPPONENT")),
        str(row.get("BOOK") or "").strip().lower(),
        round(_num(row.get("LINE")), 6),
        str(row.get("EVENT_ID") or "").strip(),
        str(row.get("GAME_ID") or "").strip(),
    )


def _current_step17_snapshot(day_str: str) -> tuple[dict[str, Any] | None, bool, str]:
    distribution = st.session_state.get(f"wnba_assists_v16_distribution::{day_str}")
    if not isinstance(distribution, pd.DataFrame) or distribution.empty:
        return None, False, "EMPTY"
    snapshot, fingerprint, valid = v17._current_snapshot(distribution, day_str)
    if not valid or not isinstance(snapshot, dict):
        return snapshot if isinstance(snapshot, dict) else None, False, fingerprint
    diag = snapshot.get("diag") if isinstance(snapshot.get("diag"), dict) else {}
    return snapshot, bool(diag.get("ready")), fingerprint


def _probabilities_from_mc_pmf(pmf: dict[Any, Any], line: float) -> tuple[float, float, float, float]:
    if not isinstance(pmf, dict) or not np.isfinite(line):
        return np.nan, np.nan, np.nan, np.nan
    over = 0.0
    under = 0.0
    push = 0.0
    total = 0.0
    integer_line = abs(line - round(line)) <= 1e-9
    integer_value = int(round(line)) if integer_line else None
    for key, value in pmf.items():
        try:
            count = int(key)
            p = float(value)
        except Exception:
            continue
        if not np.isfinite(p) or p < 0:
            continue
        total += p
        if count > line:
            over += p
        elif count < line:
            under += p
        elif integer_line and count == integer_value:
            push += p
    if total <= 0:
        return np.nan, np.nan, np.nan, np.nan
    # MC PMFs are expected to sum to 1. Normalize only microscopic numerical drift.
    if abs(total - 1.0) <= 1e-6:
        over /= total
        under /= total
        push /= total
        total = 1.0
    return float(over), float(under), float(push), float(total)


def _build_step18_line_probabilities(
    exact_lines: pd.DataFrame,
    novig_rows: pd.DataFrame,
    step13_market_ready: bool,
    step14_market_ready: bool,
    snapshot: dict[str, Any] | None,
    step17_ready: bool,
    day_str: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not step17_ready or not isinstance(snapshot, dict):
        return pd.DataFrame(), {
            "ready": False,
            "state": "LOCKED",
            "reason": "current Step-17 5M snapshot is missing, stale, or not converged",
            "market_rows": 0,
            "graded_rows": 0,
        }
    if not step13_market_ready or not step14_market_ready:
        return pd.DataFrame(), {
            "ready": False,
            "state": "LOCKED",
            "reason": "current Step-13/14 exact market branch is not ready",
            "market_rows": 0 if exact_lines is None else len(exact_lines),
            "graded_rows": 0,
        }
    if exact_lines is None or exact_lines.empty or novig_rows is None or novig_rows.empty:
        return pd.DataFrame(), {
            "ready": False,
            "state": "CHECK",
            "reason": "current exact lines or no-vig rows are empty",
            "market_rows": 0 if exact_lines is None else len(exact_lines),
            "graded_rows": 0,
        }

    diag17 = snapshot.get("diag") if isinstance(snapshot.get("diag"), dict) else {}
    summary = snapshot.get("summary")
    mc_pmfs = diag17.get("mc_pmfs") if isinstance(diag17.get("mc_pmfs"), dict) else {}
    if not isinstance(summary, pd.DataFrame) or summary.empty or not mc_pmfs:
        return pd.DataFrame(), {
            "ready": False,
            "state": "CHECK",
            "reason": "Step-17 snapshot lacks simulation summary or empirical PMFs",
            "market_rows": len(exact_lines),
            "graded_rows": 0,
        }

    # Exact converged simulation identity map. Ambiguities are rejected, never fuzzy-matched.
    sim_buckets: dict[tuple[str, str], list[pd.Series]] = {}
    for _, row in summary.iterrows():
        if not bool(row.get("CONVERGED")):
            continue
        key = (_norm_name(row.get("PLAYER_NAME")), _team_key(row.get("TEAM")))
        if key[0] and key[1]:
            sim_buckets.setdefault(key, []).append(row)
    sim_map = {key: rows[0] for key, rows in sim_buckets.items() if len(rows) == 1}
    ambiguous_sim_keys = {key for key, rows in sim_buckets.items() if len(rows) != 1}

    novig_map: dict[tuple[str, str, str, str, float, str, str], pd.Series] = {}
    novig_dupes: set[tuple[str, str, str, str, float, str, str]] = set()
    for _, row in novig_rows.iterrows():
        key = _market_key(row)
        if key in novig_map:
            novig_dupes.add(key)
        else:
            novig_map[key] = row
    for key in novig_dupes:
        novig_map.pop(key, None)

    rows: list[dict[str, Any]] = []
    blocked = {
        "stale": 0,
        "identity": 0,
        "novig": 0,
        "pmf": 0,
        "probability": 0,
    }
    integer_push_rows = 0
    max_mc_prob_se = 0.0

    for _, market in exact_lines.iterrows():
        line = _num(market.get("LINE"))
        if not np.isfinite(line) or line < 0:
            blocked["probability"] += 1
            continue

        age = _actual_quote_age_seconds(market)
        if not np.isfinite(age):
            # Step 13 already had a validated provider age. Use it only when the
            # provider timestamp format itself cannot be re-parsed here.
            age = _num(market.get("QUOTE_AGE_SECONDS"))
        if not np.isfinite(age) or age > MAX_QUOTE_AGE_SECONDS:
            blocked["stale"] += 1
            continue

        player_key = (_norm_name(market.get("PLAYER_NAME")), _team_key(market.get("TEAM")))
        if player_key in ambiguous_sim_keys or player_key not in sim_map:
            blocked["identity"] += 1
            continue
        sim = sim_map[player_key]
        player_id = _safe_int(sim.get("PLAYER_ID"))
        pmf = mc_pmfs.get(player_id)
        if pmf is None:
            pmf = mc_pmfs.get(str(player_id))
        if not isinstance(pmf, dict):
            blocked["pmf"] += 1
            continue

        mkey = _market_key(market)
        novig = novig_map.get(mkey)
        if novig is None:
            blocked["novig"] += 1
            continue

        p_over, p_under, p_push, p_total = _probabilities_from_mc_pmf(pmf, float(line))
        if (
            not np.isfinite(p_over)
            or not np.isfinite(p_under)
            or not np.isfinite(p_push)
            or not np.isfinite(p_total)
            or abs(p_total - 1.0) > 1e-5
            or abs((p_over + p_under + p_push) - 1.0) > 1e-5
        ):
            blocked["probability"] += 1
            continue

        action_prob = p_over + p_under
        if action_prob <= 1e-12:
            blocked["probability"] += 1
            continue
        fair_over_prob = p_over / action_prob
        fair_under_prob = p_under / action_prob
        fair_over_odds = _american_from_prob(fair_over_prob)
        fair_under_odds = _american_from_prob(fair_under_prob)

        n = int(diag17.get("base_sims_per_player") or v17.BASE_SIMS)
        over_se = math.sqrt(max(0.0, p_over * (1.0 - p_over) / max(n, 1)))
        under_se = math.sqrt(max(0.0, p_under * (1.0 - p_under) / max(n, 1)))
        max_mc_prob_se = max(max_mc_prob_se, over_se, under_se)
        if p_push > 0:
            integer_push_rows += 1

        rows.append({
            "PLAYER_ID": player_id,
            "PLAYER_NAME": str(market.get("PLAYER_NAME") or ""),
            "TEAM": str(market.get("TEAM") or ""),
            "OPPONENT": str(market.get("OPPONENT") or ""),
            "BOOK": str(market.get("BOOK") or ""),
            "LINE": float(line),
            "OVER_ODDS": _safe_int(market.get("OVER_ODDS")),
            "UNDER_ODDS": _safe_int(market.get("UNDER_ODDS")),
            "MODEL_OVER_PROB": p_over,
            "MODEL_UNDER_PROB": p_under,
            "MODEL_PUSH_PROB": p_push,
            "MODEL_FAIR_OVER_PROB": fair_over_prob,
            "MODEL_FAIR_UNDER_PROB": fair_under_prob,
            "MODEL_FAIR_OVER_ODDS": int(round(fair_over_odds)) if np.isfinite(fair_over_odds) else np.nan,
            "MODEL_FAIR_UNDER_ODDS": int(round(fair_under_odds)) if np.isfinite(fair_under_odds) else np.nan,
            "NOVIG_OVER_PROB": _num(novig.get("NOVIG_OVER_PROB")),
            "NOVIG_UNDER_PROB": _num(novig.get("NOVIG_UNDER_PROB")),
            "MARKET_FAIR_OVER_ODDS": _num(novig.get("MARKET_FAIR_OVER_ODDS")),
            "MARKET_FAIR_UNDER_ODDS": _num(novig.get("MARKET_FAIR_UNDER_ODDS")),
            "EXPECTED_ASSISTS": _num(sim.get("EXPECTED_ASSISTS")),
            "MC_MEAN": _num(sim.get("MC_MEAN")),
            "MC_MEDIAN": _num(sim.get("MC_MEDIAN")),
            "MC_MODE": _num(sim.get("MC_MODE")),
            "MC_SD": _num(sim.get("MC_SD")),
            "MC_OVER_SE": over_se,
            "MC_UNDER_SE": under_se,
            "SIMULATIONS": n,
            "CONVERGED": True,
            "QUOTE_AGE_SECONDS_STEP18": age,
            "OVER_UPDATED": str(market.get("OVER_UPDATED") or ""),
            "UNDER_UPDATED": str(market.get("UNDER_UPDATED") or ""),
            "EVENT_ID": str(market.get("EVENT_ID") or ""),
            "GAME_ID": str(market.get("GAME_ID") or ""),
            "TIP_ET": str(market.get("TIP_ET") or ""),
            "MARKET": "Assists",
            "MODEL_PROBABILITY_SOURCE": "Step-17 empirical 5M Monte Carlo PMF",
            "MARKET_REFERENCE_SOURCE": "Step-14 same-book proportional no-vig",
            "MODEL_VERSION_STEP18": MODEL_VERSION,
            "GATE": "PASS",
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(
            ["PLAYER_NAME", "LINE", "BOOK", "QUOTE_AGE_SECONDS_STEP18"],
            ascending=[True, True, True, True],
        ).reset_index(drop=True)

    ready = bool(not out.empty)
    return out, {
        "ready": ready,
        "state": "VERIFIED" if ready else "CHECK",
        "reason": "" if ready else "no current exact market row survived the Step-18 model/market join gates",
        "market_rows": len(exact_lines),
        "novig_rows": len(novig_rows),
        "graded_rows": len(out),
        "players_graded": int(out["PLAYER_NAME"].nunique()) if not out.empty else 0,
        "books_graded": int(out["BOOK"].nunique()) if not out.empty else 0,
        "integer_push_rows": integer_push_rows,
        "stale_blocked": blocked["stale"],
        "identity_blocked": blocked["identity"],
        "novig_blocked": blocked["novig"],
        "pmf_blocked": blocked["pmf"],
        "probability_blocked": blocked["probability"],
        "max_mc_probability_se": max_mc_prob_se,
        "base_sims_per_player": int(diag17.get("base_sims_per_player") or v17.BASE_SIMS),
        "step17_fingerprint": str(snapshot.get("fingerprint") or ""),
        "step17_seed": diag17.get("base_seed"),
        "step17_checked_at_et": str(snapshot.get("checked_at_et") or ""),
        "model_probability_influence_from_market": 0.0,
        "h2h_weight": 0.0,
        "edge_calculations": 0,
        "ev_calculations": 0,
    }


def _render_step18(
    exact_lines: pd.DataFrame,
    novig_rows: pd.DataFrame,
    step13_market_ready: bool,
    step14_market_ready: bool,
    day_str: str,
) -> tuple[bool, pd.DataFrame, dict[str, Any]]:
    st.markdown("### 🎯 Step 18 — Line-Specific O/U Probability + Fair Odds")
    st.caption(
        "First controlled model/market join. The exact current Step-13 assist line is applied to the converged Step-17 empirical 5M distribution. Step-14 no-vig is shown only as a separate market reference; it cannot change the model probability or model fair odds."
    )

    snapshot, step17_ready, fingerprint = _current_step17_snapshot(day_str)
    result, diag = _build_step18_line_probabilities(
        exact_lines,
        novig_rows,
        step13_market_ready,
        step14_market_ready,
        snapshot,
        step17_ready,
        day_str,
    )
    ready = bool(diag.get("ready"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Exact market rows", int(diag.get("market_rows") or 0))
    c2.metric("Lines graded", int(diag.get("graded_rows") or 0))
    c3.metric("Players graded", int(diag.get("players_graded") or 0))
    c4.metric("5M convergence", "PASS" if step17_ready else "LOCKED")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Push-capable rows", int(diag.get("integer_push_rows") or 0))
    d2.metric("Max probability SE", f"{100.0 * float(diag.get('max_mc_probability_se') or 0.0):.3f}%")
    d3.metric("Model ← market", "0%")
    d4.metric("EV calculations", "0")

    if ready:
        st.success(
            "✅ STEP 18 PASSED • current exact Assist lines were applied to the converged Step-17 5M empirical distributions. Integer-line push probability is preserved, and model fair odds are computed conditional on action. No edge, EV or ranking has been calculated yet."
        )
    else:
        st.warning(
            f"⚠️ STEP 18 CHECK • {diag.get('reason') or 'model/market join incomplete'}. Step 19 remains locked."
        )

    blocked_total = sum(int(diag.get(k) or 0) for k in (
        "stale_blocked", "identity_blocked", "novig_blocked", "pmf_blocked", "probability_blocked"
    ))
    if blocked_total:
        st.caption(
            "Row-level holds • "
            f"stale {int(diag.get('stale_blocked') or 0)} • "
            f"identity {int(diag.get('identity_blocked') or 0)} • "
            f"no-vig pair {int(diag.get('novig_blocked') or 0)} • "
            f"MC PMF {int(diag.get('pmf_blocked') or 0)} • "
            f"probability math {int(diag.get('probability_blocked') or 0)}"
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
        view["Model O"] = (100.0 * pd.to_numeric(view["MODEL_OVER_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
        view["Push"] = (100.0 * pd.to_numeric(view["MODEL_PUSH_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
        view["Model U"] = (100.0 * pd.to_numeric(view["MODEL_UNDER_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
        view["Model fair O"] = view["MODEL_FAIR_OVER_ODDS"].map(_fmt_odds)
        view["Model fair U"] = view["MODEL_FAIR_UNDER_ODDS"].map(_fmt_odds)
        view["No-vig O"] = (100.0 * pd.to_numeric(view["NOVIG_OVER_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
        view["No-vig U"] = (100.0 * pd.to_numeric(view["NOVIG_UNDER_PROB"], errors="coerce")).map(lambda x: f"{x:.2f}%")
        view["Expected AST"] = pd.to_numeric(view["EXPECTED_ASSISTS"], errors="coerce").round(2)
        view["Quote age"] = pd.to_numeric(view["QUOTE_AGE_SECONDS_STEP18"], errors="coerce").map(
            lambda x: "—" if pd.isna(x) else (f"{int(x)}s" if x < 120 else f"{int(x // 60)}m")
        )
        st.dataframe(
            view[[
                "Player", "Team", "Opponent", "Book", "Line", "Posted O", "Posted U",
                "Expected AST", "Model O", "Push", "Model U", "Model fair O", "Model fair U",
                "No-vig O", "No-vig U", "Quote age",
            ]],
            hide_index=True,
            use_container_width=True,
        )

        st.session_state[f"wnba_assists_v18_line_probs::{day_str}"] = result.copy()
        st.session_state[f"wnba_assists_v18_diag::{day_str}"] = dict(diag)

    with st.expander("🧪 Step-18 probability / settlement methodology", expanded=False):
        st.write("• Model probability source: empirical Step-17 5,000,000-trial PMF for the exact player.")
        st.write("• Exact market identity: current Step-13 player + team + opponent + sportsbook + line + event/game IDs.")
        st.write("• Over wins only when assists > line; Under wins only when assists < line.")
        st.write("• Integer lines preserve P(push) = P(assists = line). Half-lines naturally have 0% push.")
        st.write("• Model fair odds condition on action: p_fair_over = P(over)/(P(over)+P(under)); the push is refunded and is not treated as a loss.")
        st.write("• Step-14 no-vig probability is market reference only and contributes 0% to the model probability/fair odds.")
        st.write("• Quote freshness is rechecked from the already-captured Step-13 timestamps; Step 18 makes no sportsbook request.")
        st.write("• Player matching is exact normalized identity + exact current team; no fuzzy matching.")
        st.write("• H2H influence: 0%.")
        st.write("• Edge calculations: 0 — Step 19.")
        st.write("• EV calculations: 0 — Step 19.")
        st.write("• Qualification / Top 5: NO — Step 20.")
        st.write(f"• Step-17 fingerprint: {fingerprint}")
        st.write(f"• Step-17 seed: {diag.get('step17_seed')}")
        st.write(f"• Step-17 snapshot time: {diag.get('step17_checked_at_et') or '—'}")

    return ready, result, diag


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day_str = datetime.now(_ET).strftime("%Y-%m-%d")
    runtime: dict[str, Any] = {
        "rendered": False,
        "ready": False,
        "diag": {},
        "step13_market_ready": False,
        "step14_market_ready": False,
        "exact_lines": pd.DataFrame(),
        "novig_rows": pd.DataFrame(),
    }

    original_button = st.button
    original_card = v17.v16.v15.step3._layer_card
    original_caption = st.caption
    original_markdown = st.markdown
    original_step13 = v17.v16.v15.step13._render_step13
    original_step14 = v17.v16.v15._render_step14_with_correct_dependency

    def capture_step13(*args, **kwargs):
        result = original_step13(*args, **kwargs)
        try:
            layer_ready, market_ready, exact_lines, diag = result
            runtime["step13_market_ready"] = bool(layer_ready and market_ready)
            runtime["exact_lines"] = exact_lines.copy() if isinstance(exact_lines, pd.DataFrame) else pd.DataFrame()
            runtime["step13_diag"] = dict(diag or {})
        except Exception:
            runtime["step13_market_ready"] = False
            runtime["exact_lines"] = pd.DataFrame()
        return result

    def capture_step14(*args, **kwargs):
        result = original_step14(*args, **kwargs)
        try:
            layer_ready, market_ready, novig_rows, diag = result
            runtime["step14_market_ready"] = bool(layer_ready and market_ready)
            runtime["novig_rows"] = novig_rows.copy() if isinstance(novig_rows, pd.DataFrame) else pd.DataFrame()
            runtime["step14_diag"] = dict(diag or {})
        except Exception:
            runtime["step14_market_ready"] = False
            runtime["novig_rows"] = pd.DataFrame()
        return result

    def ensure_step18():
        if runtime["rendered"]:
            return
        ready, rows, diag = _render_step18(
            runtime["exact_lines"],
            runtime["novig_rows"],
            bool(runtime["step13_market_ready"]),
            bool(runtime["step14_market_ready"]),
            day_str,
        )
        runtime.update({"rendered": True, "ready": bool(ready), "rows": rows, "diag": dict(diag or {})})

    def fixed_button(label, *args, **kwargs):
        text = str(label)
        if text == "🔄 RECHECK ASSISTS STEPS 2–17":
            ensure_step18()
            text = "🔄 RECHECK ASSISTS STEPS 2–18"
            clicked = original_button(text, *args, **kwargs)
            if clicked:
                st.session_state.pop(f"wnba_assists_v18_line_probs::{day_str}", None)
                st.session_state.pop(f"wnba_assists_v18_diag::{day_str}", None)
            return clicked
        return original_button(label, *args, **kwargs)

    def fixed_card(step, label, card_state, note=""):
        number = int(step)
        if number == 18:
            if runtime["ready"]:
                card_state = "✅ LIVE"
                note = "5M line-specific O/U + push-aware model fair odds"
            else:
                snapshot, step17_ready, _ = _current_step17_snapshot(day_str)
                market_ready = bool(runtime["step13_market_ready"] and runtime["step14_market_ready"])
                card_state = "⚠️ CHECK" if step17_ready and market_ready else "🔒 LOCKED"
                note = "Requires current Step-17 PASS + exact Step-13/14 market"
        elif number == 19:
            card_state = "➡️ NEXT" if runtime["ready"] else "🔒 LOCKED"
            note = "Model-vs-market edge + exact posted-price EV"
        elif number == 20:
            card_state = "🔒 LOCKED"
        return original_card(step, label, card_state, note)

    def fixed_caption(body, *args, **kwargs):
        text = str(body)
        if text.startswith("⚡ WNBA Assists V17 Step 17"):
            text = text.replace("WNBA Assists V17 Step 17", "WNBA Assists V18 Step 18", 1)
            if "Step 17 PASS" in text:
                text += f" • Step 18 {'PASS' if runtime['ready'] else 'CHECK'} • line-specific model O/U + fair odds • EV 0"
        return original_caption(text, *args, **kwargs)

    def fixed_markdown(body, *args, **kwargs):
        text = body
        if isinstance(text, str) and "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 17" in text:
            text = text.replace(
                "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 17",
                "KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 18",
            )
            text = text.replace(
                "Steps 1–16 remain intact. Step 17 validates the calibrated assist-count model with an actual reproducible 5,000,000-trial Monte Carlo per player, convergence gates and sensitivity checks. Sportsbook lines/no-vig remain separate.",
                "Steps 1–17 remain intact. Step 18 performs the first controlled join: the exact current Assist line is applied to the converged 5M player distribution to create push-aware model O/U probabilities and model fair odds. Edge/EV remain locked for Step 19.",
            )
            text = text.replace(
                "🧠 model branch: Steps 1–12 → 15 → 16 → 17",
                "🧠 model: 1–12 → 15 → 16 → 17 • market: 13–14 → join at 18",
            )
        return original_markdown(text, *args, **kwargs)

    st.button = fixed_button
    v17.v16.v15.step3._layer_card = fixed_card
    st.caption = fixed_caption
    st.markdown = fixed_markdown
    v17.v16.v15.step13._render_step13 = capture_step13
    v17.v16.v15._render_step14_with_correct_dependency = capture_step14
    try:
        v17.render_wnba_assists_hub(section_header, status_info, team_logo, h)
        if not runtime["rendered"]:
            ensure_step18()
    finally:
        st.button = original_button
        v17.v16.v15.step3._layer_card = original_card
        st.caption = original_caption
        st.markdown = original_markdown
        v17.v16.v15.step13._render_step13 = original_step13
        v17.v16.v15._render_step14_with_correct_dependency = original_step14


__all__ = [
    "MODEL_VERSION",
    "_build_step18_line_probabilities",
    "_render_step18",
    "render_wnba_assists_hub",
]
