"""WNBA Assists V14 — Step 14 same-book no-vig market math.

Preserves Assists Steps 1–13 and adds only deterministic same-book vig removal
for exact SportsGameOdds Assist Over/Under pairs already verified by Step 13.

Step 14 rules:
- Step 13 owns sportsbook transport, player identity, exact matchup, pregame,
  same-book/same-line pairing and quote freshness;
- Step 14 never requests sportsbook data itself;
- Over and Under prices must come from the exact same Step-13 row/book/line;
- convert posted American prices to raw implied probabilities;
- remove vig only by proportional normalization within that exact two-way pair;
- report raw implied probabilities, book hold, no-vig Over/Under probabilities
  and market-fair American prices;
- provider fairOdds/fairOverUnder fields remain ignored;
- no player projection, matchup signal or H2H value may influence no-vig math;
- when Step 13 is VERIFIED EMPTY, Step 14 is also VERIFIED EMPTY and performs
  zero market calculations; Step 15 remains locked until real no-vig rows exist.

No final assist projection, model probability, EV, ranking or Monte Carlo is
enabled in this step.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v13 as step13

step12 = step13.step12
step11 = step13.step11
step3 = step13.step3
step4 = step13.step4
step5 = step13.step5
step6 = step13.step6
step7 = step13.step7
step8 = step13.step8
step9 = step13.step9
step10 = step13.step10
players = step13.players
sgo = step13.sgo

MODEL_VERSION = "WNBA ASSISTS V14 • STEP 14 SAME-BOOK NO-VIG"
_ET = ZoneInfo("America/New_York")


def _num(value: Any, default: float = np.nan) -> float:
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _implied_prob(american: Any) -> float:
    try:
        odds = float(american)
    except Exception:
        return np.nan
    if not np.isfinite(odds) or abs(odds) < 100:
        return np.nan
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return (-odds) / ((-odds) + 100.0)


def _fair_american(prob: Any) -> float:
    p = _num(prob)
    if not np.isfinite(p) or p <= 0.0 or p >= 1.0:
        return np.nan
    if p >= 0.5:
        return float(round(-100.0 * p / (1.0 - p)))
    return float(round(100.0 * (1.0 - p) / p))


def _build_step14_novig(
    exact_lines: pd.DataFrame,
    step13_layer_ready: bool,
    step13_market_ready: bool,
    step13_diag: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    state13 = str((step13_diag or {}).get("state") or "CHECK")

    if state13 == "VERIFIED EMPTY":
        return pd.DataFrame(), {
            "layer_ready": True,
            "market_ready": False,
            "state": "VERIFIED EMPTY",
            "reason": "Step 13 has no upcoming pregame Assist market pairs",
            "pairs_received": 0,
            "pairs_calculated": 0,
            "invalid_pairs": 0,
            "calculations": 0,
        }

    if not step13_layer_ready or not step13_market_ready:
        return pd.DataFrame(), {
            "layer_ready": False,
            "market_ready": False,
            "state": "LOCKED" if not step13_layer_ready else "CHECK",
            "reason": "Step 13 does not have verified exact Assist O/U pairs",
            "pairs_received": 0 if exact_lines is None else len(exact_lines),
            "pairs_calculated": 0,
            "invalid_pairs": 0,
            "calculations": 0,
        }

    if exact_lines is None or exact_lines.empty:
        return pd.DataFrame(), {
            "layer_ready": False,
            "market_ready": False,
            "state": "CHECK",
            "reason": "Step 13 reported market-ready but supplied no exact pairs",
            "pairs_received": 0,
            "pairs_calculated": 0,
            "invalid_pairs": 0,
            "calculations": 0,
        }

    rows: list[dict[str, Any]] = []
    invalid = 0

    for _, row in exact_lines.iterrows():
        over_odds = _num(row.get("OVER_ODDS"))
        under_odds = _num(row.get("UNDER_ODDS"))
        line = _num(row.get("LINE"))
        book = str(row.get("BOOK") or "").strip()

        p_over_raw = _implied_prob(over_odds)
        p_under_raw = _implied_prob(under_odds)
        raw_sum = p_over_raw + p_under_raw if np.isfinite(p_over_raw) and np.isfinite(p_under_raw) else np.nan

        # This is intentionally a broad sanity gate. Negative-hold/arbitrage pairs
        # are allowed; only mathematically implausible two-way pairs are rejected.
        if (
            not book
            or not np.isfinite(line)
            or not np.isfinite(raw_sum)
            or raw_sum < 0.75
            or raw_sum > 1.35
            or p_over_raw <= 0.0
            or p_under_raw <= 0.0
        ):
            invalid += 1
            continue

        p_over_novig = p_over_raw / raw_sum
        p_under_novig = p_under_raw / raw_sum
        hold = raw_sum - 1.0
        fair_over = _fair_american(p_over_novig)
        fair_under = _fair_american(p_under_novig)

        rows.append({
            "PLAYER_NAME": str(row.get("PLAYER_NAME") or ""),
            "TEAM": str(row.get("TEAM") or ""),
            "OPPONENT": str(row.get("OPPONENT") or ""),
            "BOOK": book,
            "LINE": float(line),
            "OVER_ODDS": int(round(over_odds)),
            "UNDER_ODDS": int(round(under_odds)),
            "RAW_OVER_PROB": float(p_over_raw),
            "RAW_UNDER_PROB": float(p_under_raw),
            "BOOK_HOLD": float(hold),
            "NOVIG_OVER_PROB": float(p_over_novig),
            "NOVIG_UNDER_PROB": float(p_under_novig),
            "MARKET_FAIR_OVER_ODDS": int(round(fair_over)) if np.isfinite(fair_over) else np.nan,
            "MARKET_FAIR_UNDER_ODDS": int(round(fair_under)) if np.isfinite(fair_under) else np.nan,
            "QUOTE_AGE_SECONDS": _num(row.get("QUOTE_AGE_SECONDS")),
            "OVER_UPDATED": str(row.get("OVER_UPDATED") or ""),
            "UNDER_UPDATED": str(row.get("UNDER_UPDATED") or ""),
            "EVENT_ID": str(row.get("EVENT_ID") or ""),
            "GAME_ID": str(row.get("GAME_ID") or ""),
            "TIP_ET": str(row.get("TIP_ET") or ""),
            "MARKET": "Assists",
            "SOURCE": "SportsGameOdds • same-book proportional no-vig",
            "GATE": "PASS",
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(
            ["PLAYER_NAME", "LINE", "BOOK", "QUOTE_AGE_SECONDS"],
            ascending=[True, True, True, True],
        ).reset_index(drop=True)

    market_ready = bool(not out.empty)
    return out, {
        "layer_ready": market_ready,
        "market_ready": market_ready,
        "state": "VERIFIED" if market_ready else "CHECK",
        "reason": "" if market_ready else "no mathematically valid same-book no-vig pairs survived Step 14",
        "pairs_received": len(exact_lines),
        "pairs_calculated": len(out),
        "invalid_pairs": invalid,
        "calculations": len(out),
    }


def _render_step14(
    exact_lines: pd.DataFrame,
    step13_layer_ready: bool,
    step13_market_ready: bool,
    step13_diag: dict[str, Any],
    day_str: str,
) -> tuple[bool, bool, pd.DataFrame, dict[str, Any]]:
    st.markdown("### ⚖️ Step 14 — Same-Book No-Vig")
    st.caption(
        "Pure market math only. Step 14 consumes the exact same-book/same-line Over + Under pairs already verified by Step 13, converts posted American prices to raw implied probability, then proportionally removes vig. No player projection enters this calculation."
    )

    novig, diag = _build_step14_novig(
        exact_lines,
        step13_layer_ready,
        step13_market_ready,
        step13_diag,
    )
    state = str(diag.get("state") or "CHECK")
    layer_ready = bool(diag.get("layer_ready"))
    market_ready = bool(diag.get("market_ready"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Step-13 pairs", int(diag.get("pairs_received") or 0))
    c2.metric("No-vig pairs", int(diag.get("pairs_calculated") or 0))
    c3.metric("Invalid pairs", int(diag.get("invalid_pairs") or 0))
    c4.metric("Projection influence", "0%")

    if state == "VERIFIED EMPTY":
        st.info(
            "✅ STEP 14 VERIFIED EMPTY • Step 13 has no eligible pregame Assist O/U pairs, so no no-vig calculation is performed. The layer is armed and Step 15 remains locked until a real same-day market exists."
        )
    elif layer_ready and market_ready:
        st.success(
            "✅ STEP 14 PASSED • every displayed row is a same-book, same-line two-way Assist market with vig removed by proportional normalization. Market probabilities remain completely separate from the player projection."
        )
    else:
        st.warning(f"⚠️ STEP 14 CHECK • {diag.get('reason') or 'same-book no-vig verification incomplete'}. Step 15 remains locked.")

    if novig is not None and not novig.empty:
        view = novig.copy()
        view["Player"] = view["PLAYER_NAME"].astype(str)
        view["Team"] = view["TEAM"].astype(str)
        view["Opponent"] = view["OPPONENT"].astype(str)
        view["Book"] = view["BOOK"].astype(str)
        view["Line"] = pd.to_numeric(view["LINE"], errors="coerce")
        view["Over"] = view["OVER_ODDS"].apply(lambda x: f"{int(x):+d}")
        view["Under"] = view["UNDER_ODDS"].apply(lambda x: f"{int(x):+d}")
        view["Raw O"] = (100.0 * view["RAW_OVER_PROB"]).map(lambda x: f"{x:.1f}%")
        view["Raw U"] = (100.0 * view["RAW_UNDER_PROB"]).map(lambda x: f"{x:.1f}%")
        view["Hold"] = (100.0 * view["BOOK_HOLD"]).map(lambda x: f"{x:+.2f}%")
        view["No-vig O"] = (100.0 * view["NOVIG_OVER_PROB"]).map(lambda x: f"{x:.1f}%")
        view["No-vig U"] = (100.0 * view["NOVIG_UNDER_PROB"]).map(lambda x: f"{x:.1f}%")
        view["Fair O"] = view["MARKET_FAIR_OVER_ODDS"].apply(lambda x: "—" if pd.isna(x) else f"{int(x):+d}")
        view["Fair U"] = view["MARKET_FAIR_UNDER_ODDS"].apply(lambda x: "—" if pd.isna(x) else f"{int(x):+d}")
        st.dataframe(
            view[["Player", "Team", "Opponent", "Book", "Line", "Over", "Under", "Raw O", "Raw U", "Hold", "No-vig O", "No-vig U", "Fair O", "Fair U"]],
            hide_index=True,
            use_container_width=True,
        )
        st.session_state[f"wnba_assists_v14_novig::{day_str}"] = novig.copy()

    with st.expander("🧪 Step-14 no-vig methodology / diagnostics", expanded=False):
        st.write("• Input source: Step-13 exact SportsGameOdds Assist O/U pairs only.")
        st.write("• No sportsbook/API request is made by Step 14 itself.")
        st.write("• American implied probability: +A → 100/(A+100); -A → |A|/(|A|+100).")
        st.write("• Same-book vig removal: p_no_vig = p_raw / (p_raw_over + p_raw_under).")
        st.write("• Book hold = raw Over implied + raw Under implied − 100%.")
        st.write("• Negative hold/arbitrage is not silently converted into positive hold; mathematically valid pairs are normalized as posted.")
        st.write("• Provider fairOdds/fairOverUnder used: NO.")
        st.write("• H2H influence: 0%")
        st.write("• Player projection influence: 0%")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• Exact pairs received: {int(diag.get('pairs_received') or 0)}")
        st.write(f"• No-vig pairs calculated: {int(diag.get('pairs_calculated') or 0)}")
        st.write(f"• Invalid mathematical pairs blocked: {int(diag.get('invalid_pairs') or 0)}")

    return layer_ready, market_ready, novig, diag


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    slate = step3.schedule.load_verified_wnba_slate(slate_day)
    verification = str(slate.get("verification") or "")

    st.markdown(
        """
        <style>
        .ks-ast-hero{padding:25px 27px;margin:4px 0 18px;border:1px solid rgba(56,189,248,.34);border-radius:24px;background:linear-gradient(135deg,rgba(6,28,44,.99),rgba(12,22,48,.99));box-shadow:0 14px 38px rgba(0,0,0,.16);}
        .ks-ast-kicker{color:#67e8f9;font-size:.69rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase;}
        .ks-ast-title{margin-top:9px;color:#f8fafc;font-size:2.05rem;line-height:1.08;font-weight:950;}
        .ks-ast-sub{margin-top:12px;color:#9fb0c6;font-size:.91rem;line-height:1.62;font-weight:650;}
        .ks-ast-chip{display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="ks-ast-hero">
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 14</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–13 remain intact. Step 14 adds only same-book vig removal for exact Step-13 Assist O/U pairs. Market math remains isolated from the independent assist projection and simulations.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">✅ Steps 1–13 preserved</span>
          <span class="ks-ast-chip">⚖️ proportional no-vig</span>
          <span class="ks-ast-chip">🚫 projection influence 0%</span>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("### 📅 Step 2 — Verified Daily WNBA Slate")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selected date", slate_day)
    c2.metric("Verification", verification or "CHECK")
    c3.metric("Games found", int(slate.get("games_found", 0)))
    c4.metric("WNBA teams validated", int(slate.get("teams_validated", 0)))
    if verification == "VERIFIED":
        st.success(f"✅ STEP 2 PASSED • {slate.get('games_found', 0)} same-day WNBA game(s) verified by the preserved Step-2 reconciliation layer.")
    elif verification == "NO GAMES":
        st.info(f"ℹ️ STEP 2 VERIFIED EMPTY • No WNBA games for {slate_day} ET.")
    else:
        st.error("⛔ STEP 2 CHECK • Same-day slate verification is incomplete.")

    st.markdown("### 🩺 Step 3 — Current Rosters + Same-Day Injury / Status")
    step3_ready_ui = step3._render_step3(slate, slate_day)
    merged, step3_diag = step4._step3_snapshot(slate, slate_day)
    step3_ready = bool(step3_ready_ui and step3_diag.get("ready"))
    step4_ready, minutes = step4._render_step4(slate, slate_day, merged, step3_ready)
    step5_ready, roles = step5._render_step5(slate, slate_day, minutes, step4_ready)
    step6_ready, form = step6._render_step6(slate, slate_day, roles, step5_ready)
    step7_ready, opportunity = step7._render_step7(slate, slate_day, form, step6_ready)
    step8_ready, conversion = step8._render_step8(slate, slate_day, opportunity, step7_ready)
    step9_ready, environment = step9._render_step9(slate, slate_day, conversion, step8_ready)
    step10_ready, position_rows = step10._render_step10(slate, slate_day, environment, step9_ready)
    step11_ready, pace_rows = step11._render_step11(slate, slate_day, position_rows, step10_ready)
    step12_ready, h2h_rows = step12._render_step12(slate, slate_day, pace_rows, step11_ready)
    step13_ready, step13_market_ready, exact_lines, step13_diag = step13._render_step13(slate, slate_day, h2h_rows, step12_ready)
    step14_ready, step14_market_ready, _, step14_diag = _render_step14(
        exact_lines, step13_ready, step13_market_ready, step13_diag, slate_day
    )

    if st.button("🔄 RECHECK ASSISTS STEPS 2–14", use_container_width=True, key="assists_step14_recheck"):
        for fn in (
            step3.schedule.load_verified_wnba_slate,
            step3._current_rosters,
            step3._injury_feed,
            step4._season_schedule,
            step4._rotation_history,
            step5._creation_history,
            step5._official_usage_table,
            step6._season_form_pool,
            step6._recent_assist_history,
            step7._tracking_windows,
            step8._shooting_history,
            step8._raw_shooting_summary,
            step9._official_windows,
            step9._espn_environment,
            step10._position_history,
            step11._pace_history,
            step11._raw_team_possessions,
            step12._h2h_game_pool,
        ):
            try:
                fn.clear()
            except Exception:
                pass
        try:
            sgo.clear_cache()
        except Exception:
            pass
        try:
            players._espn_roster.clear()
            players._espn_season_schedule.clear()
            players._espn_game_summary.clear()
        except Exception:
            pass
        st.rerun()

    st.markdown("### 🧱 Assists Build Order — Current")
    state13 = str(step13_diag.get("state") or "CHECK")
    state14 = str(step14_diag.get("state") or "CHECK")
    note13 = "Verified empty — no upcoming pregame" if state13 == "VERIFIED EMPTY" else "Exact same-book O/U • start/freshness gated"
    note14 = "Verified empty — awaits exact pregame pairs" if state14 == "VERIFIED EMPTY" else "Proportional same-book vig removal"
    layers = [
        (1, "Isolated Assists page", "✅ LIVE", "Display shell preserved"),
        (2, "Verified daily WNBA slate", "✅ LIVE" if verification in {"VERIFIED", "NO GAMES"} else "⚠️ CHECK", "Exact ET date + provider reconciliation"),
        (3, "Current rosters + injuries/status", "✅ LIVE" if step3_ready else "⚠️ CHECK", "Fail-closed current identity + same-day status"),
        (4, "Projected minutes + rotation", "✅ LIVE" if step4_ready else "⚠️ CHECK", "L3/L5/L10 rotation + 200-minute team allocation"),
        (5, "Assist role + ball-handling / usage", "✅ LIVE" if step5_ready else "⚠️ CHECK", "Empirical creation responsibility + usage context"),
        (6, "Recent + season assist form", "✅ LIVE" if step6_ready else "⚠️ CHECK", "Season + L3/L5/L10 • regression protected"),
        (7, "Potential assists / passes / creation chances", "✅ LIVE" if step7_ready else "⚠️ CHECK", "Official tracking when available; honest proxy fallback"),
        (8, "Teammate shot-making + lineup conversion", "✅ LIVE" if step8_ready else "⚠️ CHECK", "Projected active finisher environment"),
        (9, "Opponent assist environment", "✅ LIVE" if step9_ready else "⚠️ CHECK", "Season + L10/L5/L3 assists allowed + AST/FGM"),
        (10, "Position matchup — Guard / Wing / Big", "✅ LIVE" if step10_ready else "⚠️ CHECK", "Exact-opponent position-tagged AST/40 context"),
        (11, "Pace + expected possession volume", "✅ LIVE" if step11_ready else "⚠️ CHECK", "Season + L10/L5/L3 possession environment"),
        (12, "Player vs opponent assist history", "✅ LIVE" if step12_ready else "⚠️ CHECK", "Exact-ID descriptive H2H • 0% projection influence"),
        (13, "Exact SportsGameOdds assist lines", "✅ LIVE" if step13_ready else ("⚠️ CHECK" if step12_ready else "🔒 LOCKED"), note13),
        (14, "Same-book no-vig", "✅ LIVE" if step14_ready else ("⚠️ CHECK" if step13_ready else "🔒 LOCKED"), note14),
        (15, "Market-independent assist projection", "➡️ NEXT" if step14_market_ready else "🔒 LOCKED", "Expected assists before market grading"),
        (16, "Uncertainty + distribution calibration", "🔒 LOCKED", "Discrete assist count distribution"),
        (17, "5M Monte Carlo + convergence / sensitivity", "🔒 LOCKED", "Actual simulations only"),
        (18, "Line-specific O/U probability + fair odds", "🔒 LOCKED", "Threshold probabilities from model distribution"),
        (19, "Model-vs-market edge + EV", "🔒 LOCKED", "Exact posted price grading"),
        (20, "Risk-adjusted qualification + Top 5", "🔒 LOCKED", "Never force five"),
    ]
    for start in range(0, len(layers), 4):
        cols = st.columns(4, gap="small")
        for col, item in zip(cols, layers[start:start + 4]):
            with col:
                st.markdown(step3._layer_card(*item), unsafe_allow_html=True)

    footer13 = "EMPTY" if state13 == "VERIFIED EMPTY" else ("PASS" if step13_market_ready else "CHECK")
    footer14 = "EMPTY" if state14 == "VERIFIED EMPTY" else ("PASS" if step14_market_ready else "CHECK")
    st.caption(
        f"⚡ WNBA Assists V14 Step 14 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'CHECK'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • Step 5 {'PASS' if step5_ready else 'CHECK'} • Step 6 {'PASS' if step6_ready else 'CHECK'} • Step 7 {'PASS' if step7_ready else 'CHECK'} • Step 8 {'PASS' if step8_ready else 'CHECK'} • Step 9 {'PASS' if step9_ready else 'CHECK'} • Step 10 {'PASS' if step10_ready else 'CHECK'} • Step 11 {'PASS' if step11_ready else 'CHECK'} • Step 12 {'PASS' if step12_ready else 'CHECK'} • Step 13 {footer13} • Step 14 {footer14} • no player projection/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
