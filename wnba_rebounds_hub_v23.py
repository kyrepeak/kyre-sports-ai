"""WNBA Rebounds V2.3 — Step 14 same-book no-vig market baseline.

Extends the verified V2.2.2 chain without changing Steps 1-13.

Step-14 rules:
- Consume only Step-13 exact same-book / same-line Over+Under rebound pairs.
- Convert each side's posted price to raw implied probability.
- Remove bookmaker margin with proportional two-way normalization:
  p_over_nv = p_over_raw / (p_over_raw + p_under_raw), same for Under.
- Never mix books, never mix rebound lines, never substitute consensus prices.
- Preserve players with no market or an unpaired market as verified market states;
  only actual paired rows receive no-vig probabilities.
- Record quote timestamp skew as a diagnostic; no stale side is silently replaced.
- No-vig is market context only. It does NOT feed the player rebound projection.
- No EV, Monte Carlo, final projection or recommendation is created here.
"""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v22 as marketmod
import wnba_rebounds_hub_v222 as base

MODEL_VERSION = "WNBA REBOUNDS V2.3 • STEP 14 SAME-BOOK NO-VIG"
SYNC_WINDOW_SECONDS = 5 * 60


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _implied_probability(raw):
    """Parse common American/decimal/fractional prices into implied probability."""
    text = str(raw or "").strip().upper().replace(",", "")
    if not text:
        return np.nan, ""
    if text in {"EVEN", "EVENS", "EV", "PK", "PICK"}:
        return 0.5, "AMERICAN"

    # Fractional format such as 10/11.
    if "/" in text:
        try:
            a, b = text.split("/", 1)
            frac = float(a) / float(b)
            decimal = 1.0 + frac
            if decimal > 1.0:
                return 1.0 / decimal, "FRACTIONAL"
        except Exception:
            return np.nan, ""

    cleaned = re.sub(r"[^0-9+\-.]", "", text)
    try:
        x = float(cleaned)
    except Exception:
        return np.nan, ""

    # Explicit sign, or magnitude >=100, is treated as American odds.
    if text.startswith(("+", "-")) or abs(x) >= 100.0:
        if x == 0:
            return np.nan, ""
        p = 100.0 / (x + 100.0) if x > 0 else (-x) / ((-x) + 100.0)
        return (p if 0.0 < p < 1.0 else np.nan), "AMERICAN"

    # Otherwise accept normal decimal-odds range.
    if 1.0 < x <= 100.0:
        p = 1.0 / x
        return (p if 0.0 < p < 1.0 else np.nan), "DECIMAL"

    return np.nan, ""


def _fair_american(prob):
    p = _num(prob)
    if not np.isfinite(p) or not (0.0 < p < 1.0):
        return np.nan
    if math.isclose(p, 0.5, abs_tol=1e-12):
        return 100.0
    if p > 0.5:
        return -100.0 * p / (1.0 - p)
    return 100.0 * (1.0 - p) / p


def _timestamp_skew_seconds(over_updated, under_updated):
    try:
        a = pd.to_datetime(over_updated, utc=True, errors="coerce")
        b = pd.to_datetime(under_updated, utc=True, errors="coerce")
        if pd.isna(a) or pd.isna(b):
            return np.nan
        return abs((a - b).total_seconds())
    except Exception:
        return np.nan


def _is_true(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _build_step14():
    players13 = pd.DataFrame(st.session_state.get("wnba_rebounds_step13_players") or [])
    quotes13 = pd.DataFrame(st.session_state.get("wnba_rebounds_step13_quotes") or [])
    step13_ready = bool(st.session_state.get("wnba_rebounds_step13_ready"))

    if players13.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": 0, "covered": 0,
            "pairs": 0, "valid_pairs": 0, "books": 0,
            "reason": "no verified Step-13 player state",
        }

    paired = quotes13.copy()
    if not paired.empty and "Paired O/U" in paired.columns:
        paired = paired[paired["Paired O/U"].map(_is_true)].copy()

    market_rows = []
    if not paired.empty:
        for _, q in paired.iterrows():
            over_raw, over_format = _implied_probability(q.get("Over odds"))
            under_raw, under_format = _implied_probability(q.get("Under odds"))
            raw_sum = over_raw + under_raw if np.isfinite(over_raw) and np.isfinite(under_raw) else np.nan
            valid = bool(np.isfinite(raw_sum) and raw_sum > 0 and raw_sum < 2.0)
            over_nv = over_raw / raw_sum if valid else np.nan
            under_nv = under_raw / raw_sum if valid else np.nan
            hold = raw_sum - 1.0 if valid else np.nan
            skew = _timestamp_skew_seconds(q.get("Over updated"), q.get("Under updated"))
            sync_state = (
                "SYNCED ≤5m" if np.isfinite(skew) and skew <= SYNC_WINDOW_SECONDS
                else "ASYNC >5m" if np.isfinite(skew)
                else "TIMESTAMP UNKNOWN"
            )

            market_rows.append({
                "Event ID": str(q.get("Event ID") or ""),
                "SportsGameOdds Player ID": str(q.get("SportsGameOdds Player ID") or ""),
                "Provider player": str(q.get("Provider player") or ""),
                "Player key": str(q.get("Player key") or marketmod._norm(q.get("Provider player"))),
                "Bookmaker ID": str(q.get("Bookmaker ID") or ""),
                "Book": str(q.get("Book") or q.get("Bookmaker ID") or ""),
                "Line": _num(q.get("Line")),
                "Over odds": str(q.get("Over odds") or ""),
                "Under odds": str(q.get("Under odds") or ""),
                "Over odds format": over_format,
                "Under odds format": under_format,
                "Over raw implied": over_raw,
                "Under raw implied": under_raw,
                "Book hold": hold,
                "Over no-vig": over_nv,
                "Under no-vig": under_nv,
                "Over fair odds": _fair_american(over_nv),
                "Under fair odds": _fair_american(under_nv),
                "Over updated": str(q.get("Over updated") or ""),
                "Under updated": str(q.get("Under updated") or ""),
                "Quote skew sec": skew,
                "Quote sync": sync_state,
                "No-vig state": "VERIFIED" if valid else "CHECK",
            })

    markets = pd.DataFrame(market_rows)

    # Join verified Step-13 player identity onto no-vig rows. This remains a
    # diagnostic market join only; no player projection is changed.
    player_lookup = {}
    for _, p in players13.iterrows():
        key = marketmod._norm(p.get("Player"))
        if key and key not in player_lookup:
            player_lookup[key] = {
                "Player": str(p.get("Player") or "Player"),
                "Team": str(p.get("Team") or ""),
                "Opponent": str(p.get("Opponent") or ""),
            }

    if not markets.empty:
        markets["Player"] = markets["Player key"].map(lambda k: player_lookup.get(str(k), {}).get("Player", ""))
        markets["Team"] = markets["Player key"].map(lambda k: player_lookup.get(str(k), {}).get("Team", ""))
        markets["Opponent"] = markets["Player key"].map(lambda k: player_lookup.get(str(k), {}).get("Opponent", ""))

    valid_by_key = {}
    if not markets.empty:
        good = markets[markets["No-vig state"].eq("VERIFIED")]
        if not good.empty:
            for key, part in good.groupby("Player key", sort=False):
                valid_by_key[str(key)] = int(len(part))

    player_rows = []
    for _, p in players13.iterrows():
        out = p.to_dict()
        key = marketmod._norm(p.get("Player"))
        market_state = str(p.get("SGO market state") or "")
        pair_count = int(valid_by_key.get(key, 0))

        if str(p.get("Step13 state") or "") != "VERIFIED":
            state = "CHECK"
            verified = False
        elif pair_count > 0:
            state = "NO-VIG FOUND"
            verified = True
        elif market_state == "VERIFIED NO MARKET":
            state = "VERIFIED NO MARKET"
            verified = True
        elif market_state == "MARKET FOUND":
            # The player market exists, but there is no exact paired row that can
            # support two-way no-vig. Preserve that fact instead of inventing one.
            state = "VERIFIED UNPAIRED MARKET"
            verified = True
        else:
            state = "CHECK"
            verified = False

        out.update({
            "Step14 valid no-vig pairs": pair_count,
            "Step14 market state": state,
            "Step14 state": "VERIFIED" if verified else "CHECK",
        })
        player_rows.append(out)

    players14 = pd.DataFrame(player_rows)
    covered = int(players14["Step14 state"].eq("VERIFIED").sum()) if not players14.empty else 0
    valid_pairs = int(markets["No-vig state"].eq("VERIFIED").sum()) if not markets.empty else 0
    books = int(markets.loc[markets["No-vig state"].eq("VERIFIED"), "Bookmaker ID"].nunique()) if valid_pairs else 0
    parsing_errors = int(markets["No-vig state"].eq("CHECK").sum()) if not markets.empty else 0
    holds = pd.to_numeric(markets.loc[markets["No-vig state"].eq("VERIFIED"), "Book hold"], errors="coerce") if valid_pairs else pd.Series(dtype=float)
    median_hold = float(holds.median()) if not holds.empty else np.nan

    ready = bool(
        step13_ready
        and not players14.empty
        and covered == len(players14)
        and valid_pairs > 0
        and parsing_errors == 0
    )

    return players14, markets, {
        "ready": ready,
        "players": int(len(players14)),
        "covered": covered,
        "pairs": int(len(markets)),
        "valid_pairs": valid_pairs,
        "books": books,
        "parsing_errors": parsing_errors,
        "median_hold": median_hold,
        "method": "two-way proportional no-vig normalization",
        "projection_influence": False,
    }


def _render_step14():
    st.markdown("## 🧮 Step 14 — Same-Book No-Vig")
    st.caption(
        "This layer removes sportsbook margin only from the exact Step-13 Over+Under pair posted by the SAME bookmaker "
        "at the SAME rebound line. Raw implied probabilities are normalized within that two-way market. Books and lines "
        "are never blended. The no-vig result is a market comparison baseline only and does not influence the rebound projection."
    )

    players14, markets, info = _build_step14()
    ready = bool(info.get("ready"))

    st.session_state["wnba_rebounds_step14_ready"] = ready
    st.session_state["wnba_rebounds_step14_players"] = players14.to_dict("records") if not players14.empty else []
    st.session_state["wnba_rebounds_step14_quotes"] = markets.to_dict("records") if not markets.empty else []

    a, b, c, d = st.columns(4)
    a.metric("Player states", f"{info.get('covered',0)}/{info.get('players',0)}")
    b.metric("Valid no-vig pairs", info.get("valid_pairs", 0))
    c.metric("Books", info.get("books", 0))
    hold = info.get("median_hold")
    d.metric("Median hold", f"{100.0*hold:.2f}%" if np.isfinite(_num(hold)) else "—")

    if ready:
        st.success(
            "✅ STEP 14 PASSED • every Step-13 player retains a verified market state and every exact paired quote was "
            "successfully converted to a same-book/same-line no-vig probability. Step 15 (market-independent rebound "
            "projection synthesis) is unlocked. No sportsbook probability has been fed into the player projection."
        )
    else:
        if not st.session_state.get("wnba_rebounds_step13_ready"):
            st.error("⛔ STEP 14 CHECK • Step 13 is not verified. No-vig remains locked.")
        elif info.get("valid_pairs", 0) <= 0:
            st.warning("⚠️ STEP 14 MARKET WAIT • there is no valid exact paired market to de-vig right now.")
        elif info.get("parsing_errors", 0) > 0:
            st.error(
                "⛔ STEP 14 CHECK • at least one exact paired sportsbook price could not be parsed safely. "
                "The app will not guess its odds format."
            )
        else:
            st.error("⛔ STEP 14 CHECK • at least one Step-14 player state is incomplete.")

    if not players14.empty:
        keep = [c for c in [
            "Player", "Team", "Opponent", "SGO market state",
            "Step14 valid no-vig pairs", "Step14 market state", "Step14 state",
        ] if c in players14.columns]
        st.dataframe(players14[keep], hide_index=True, use_container_width=True)

    with st.expander("🧮 Same-book no-vig quote board"):
        if markets.empty:
            st.info("No Step-13 exact paired quote rows are available.")
        else:
            show = markets.copy()
            for col in ["Line", "Over raw implied", "Under raw implied", "Book hold", "Over no-vig", "Under no-vig", "Over fair odds", "Under fair odds", "Quote skew sec"]:
                if col in show.columns:
                    show[col] = pd.to_numeric(show[col], errors="coerce")
            for col in ["Over raw implied", "Under raw implied", "Over no-vig", "Under no-vig"]:
                show[col] = (100.0 * show[col]).round(2)
            show["Book hold"] = (100.0 * show["Book hold"]).round(2)
            show["Over fair odds"] = show["Over fair odds"].round(0)
            show["Under fair odds"] = show["Under fair odds"].round(0)
            show["Quote skew sec"] = show["Quote skew sec"].round(0)
            cols = [c for c in [
                "Player", "Team", "Opponent", "Book", "Line", "Over odds", "Under odds",
                "Over raw implied", "Under raw implied", "Book hold",
                "Over no-vig", "Under no-vig", "Over fair odds", "Under fair odds",
                "Quote sync", "Quote skew sec", "No-vig state",
            ] if c in show.columns]
            st.dataframe(show[cols], hide_index=True, use_container_width=True)

    with st.expander("🧮 Step-14 methodology / diagnostics"):
        st.write({
            "source": "Step-13 exact SportsGameOdds same-book/same-line O/U pairs",
            "method": info.get("method"),
            "formula": "p_no_vig(side) = p_raw(side) / [p_raw(over) + p_raw(under)]",
            "books_blended": False,
            "lines_blended": False,
            "consensus_substitution": False,
            "quote_timestamp_skew_diagnostic_seconds": SYNC_WINDOW_SECONDS,
            "unpaired_market_rule": "verified market state preserved; no no-vig value invented",
            "no_market_rule": "verified no-market state preserved",
            "applied_to_player_projection": False,
            "ev_calculated": False,
            "monte_carlo_used": False,
            "final_projection_created": False,
        })
        if not markets.empty and markets["No-vig state"].eq("CHECK").any():
            st.dataframe(
                markets.loc[markets["No-vig state"].eq("CHECK"), [
                    "Provider player", "Book", "Line", "Over odds", "Under odds",
                    "Over odds format", "Under odds format", "No-vig state",
                ]],
                hide_index=True,
                use_container_width=True,
            )

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
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ BASELINE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 16), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V2.3 Step 14 only • Steps 1–13 preserved • proportional same-book/same-line no-vig • "
        "timestamp-skew diagnostics • no book/line blending • market probabilities remain isolated from projection • "
        "no EV/Monte Carlo/final rebound projection."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step13_ready"):
        _render_step14()
    else:
        st.info("Step 14 remains locked until Step 13 is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]