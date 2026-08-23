"""Kyre Sports AI — NFL Moneyline V5 Step-5 sportsbook market layer.

Builds on V4.3.1 without changing Steps 1-4C. Step 5 connects pregame NFL
Moneyline prices through the isolated NFL transport:
- SportsGameOdds primary;
- Odds-API.io fallback;
- same-book implied + no-vig probabilities;
- quote freshness and stale-price exclusion;
- best usable price and cross-book no-vig market consensus.

The Step-4C base model probability is display-only beside the market. Sportsbook
prices do not feed back into the model. Edge/EV, Monte Carlo, final grading and
recommendations remain locked. Preseason Step 3 remains the final-output gate.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v1 as step1
import nfl_moneyline_hub_v431 as v431
import nfl_moneyline_market_v1 as market

MODEL_VERSION = "NFL MONEYLINE V5.0 • STEP 5 SPORTSBOOK MONEYLINE MARKET"


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


def _fmt_pp(value):
    return "—" if not np.isfinite(_num(value)) else f"{100.0 * float(value):.1f} pp"


def _market_table(rows):
    display = []
    for row in rows or []:
        display.append({
            "Book": row.get("book") or "—",
            "Away ML": market.fmt_american(row.get("away_ml")),
            "Home ML": market.fmt_american(row.get("home_ml")),
            "Away implied": market.fmt_pct(row.get("away_implied")),
            "Home implied": market.fmt_pct(row.get("home_implied")),
            "Away no-vig": market.fmt_pct(row.get("away_no_vig")),
            "Home no-vig": market.fmt_pct(row.get("home_no_vig")),
            "Hold": market.fmt_pct(row.get("overround")),
            "Age": market.fmt_age(row.get("age_seconds")),
            "Freshness": row.get("freshness") or "UNKNOWN",
            "Provider": row.get("provider") or "—",
        })
    return pd.DataFrame(display)


def _render_game(game: dict, snap: dict, model_out: dict):
    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    st.markdown(f"#### Market — {away} @ {home}")

    if not snap:
        st.warning("No sportsbook event matched this verified NFL game.")
        return

    rows = snap.get("rows") or []
    if not rows:
        st.warning("Sportsbook event matched, but no full-game Moneyline quotes were returned.")
        return

    usable = int(snap.get("usable_books") or 0)
    quality = _safe(snap.get("quality"), "UNAVAILABLE")
    providers = " + ".join(snap.get("providers") or []) or "—"

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Usable books", str(usable))
    q2.metric("Market quality", quality)
    q3.metric("Freshest quote", market.fmt_age(snap.get("freshest_age")))
    q4.metric("Market disagreement", _fmt_pp(snap.get("disagreement")))

    ba = snap.get("best_away") or {}
    bh = snap.get("best_home") or {}
    a, b = st.columns(2)
    a.metric(
        f"Best {away} ML",
        market.fmt_american(ba.get("price")),
        help=f"Best non-stale complete same-book price • {ba.get('book') or '—'}",
    )
    b.metric(
        f"Best {home} ML",
        market.fmt_american(bh.get("price")),
        help=f"Best non-stale complete same-book price • {bh.get('book') or '—'}",
    )
    st.caption(
        f"Best-price books: {away} — {ba.get('book') or '—'} • {home} — {bh.get('book') or '—'} • "
        f"Provider path: {providers}"
    )

    st.dataframe(_market_table(rows), use_container_width=True, hide_index=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{away} market no-vig", market.fmt_pct(snap.get("consensus_away_no_vig")))
    c2.metric(f"{home} market no-vig", market.fmt_pct(snap.get("consensus_home_no_vig")))
    c3.metric(f"{away} Step-4C base", market.fmt_pct(model_out.get("away_p")) if model_out.get("ready") else "—")
    c4.metric(f"{home} Step-4C base", market.fmt_pct(model_out.get("home_p")) if model_out.get("ready") else "—")

    if snap.get("ready"):
        st.success(
            "✅ Same-book no-vig market summary is usable. Stale or timestamp-unknown rows remain visible for audit but are excluded from the best-price/no-vig summary."
        )
    else:
        st.warning(
            "⚠️ No non-stale timestamped sportsbook has both Moneyline sides available. Market grading stays locked."
        )

    if snap.get("fallback_used"):
        st.info("🔄 SportsGameOdds was incomplete for this matchup; Odds-API.io supplied fallback market rows.")

    st.info(
        "MODEL / MARKET SEPARATION • Step 4C probability and sportsbook no-vig probability are shown side-by-side only. "
        "Step 5 does not subtract them, calculate edge/EV, alter P(win), or issue a pick."
    )


def _render_step5() -> bool:
    selected = st.session_state.get("nfl_v1_date", date.today())
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    schedule, diag = foundation.load_nfl_slate(day_str)
    pregame, _ = step1._pregame_partition(
        schedule,
        day_str,
        now_et=pd.Timestamp.now(tz=foundation.ET),
    )
    model_outputs = st.session_state.get("nfl_moneyline_v43_probability_outputs") or {}

    st.markdown("### 💰 Step 5 — Sportsbook Moneyline Market")
    st.caption(
        "Pregame full-game ML only • SportsGameOdds primary → Odds-API.io fallback • "
        "FanDuel / DraftKings / BetMGM / Caesars when available • same-book no-vig • "
        "FRESH ≤60s • AGING 1–3m • STALE >3m excluded from usable summaries."
    )

    if not diag.get("request_ok") or pregame.empty:
        st.warning("Step 5 cannot request a Moneyline market because no verified pregame NFL matchup is available.")
        st.session_state["nfl_moneyline_v5_market_ready"] = False
        return False

    connection = market.connection_state()
    if not connection.get("sgo") and not connection.get("legacy"):
        st.warning(
            "⚠️ STEP 5 CHECK • no sportsbook provider key is connected. "
            "SPORTSGAMEODDS_API_KEY is primary; the existing ODDS_API_IO_KEY can act as fallback."
        )
        st.session_state["nfl_moneyline_v5_market_ready"] = False
        return False

    try:
        with st.spinner("💰 Pulling current NFL Moneyline prices…"):
            snapshots, mdiag = market.fetch_nfl_moneyline_markets(pregame, day_str)
    except Exception as exc:
        st.warning(
            f"⚠️ STEP 5 CHECK • sportsbook runtime firewall caught {type(exc).__name__}: {str(exc)[:220]}. "
            "Steps 1–4C remain valid and no market value is fabricated."
        )
        st.session_state["nfl_moneyline_v5_market_ready"] = False
        return False

    ready_games = int(mdiag.get("games_with_market") or 0)
    all_ready = bool(len(pregame) and ready_games == len(pregame))

    total_usable = sum(int(x.get("usable_books") or 0) for x in snapshots.values())
    used_fallback = any(bool(x.get("fallback_used")) for x in snapshots.values())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Games priced", f"{ready_games}/{len(pregame)}")
    m2.metric("Usable book-pairs", str(total_usable))
    m3.metric("Primary", "SportsGameOdds" if connection.get("sgo") else "OFF")
    m4.metric("Fallback", "USED" if used_fallback else ("READY" if connection.get("legacy") else "OFF"))

    if mdiag.get("sgo_error"):
        st.warning(f"SportsGameOdds detail: {mdiag.get('sgo_error')}")
    if mdiag.get("fallback_error"):
        st.warning(f"Odds-API.io fallback detail: {mdiag.get('fallback_error')}")

    if all_ready:
        st.success("✅ STEP 5 PASSED • at least one usable same-book Moneyline pair is available for every verified pregame matchup.")
    else:
        st.warning(
            "⚠️ STEP 5 CHECK • at least one verified pregame matchup lacks a non-stale complete Moneyline pair. "
            "Missing/stale prices are not filled or promoted."
        )

    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        _render_game(game, snapshots.get(gid, {}), model_outputs.get(gid, {}))

    st.session_state["nfl_moneyline_v5_market_snapshots"] = snapshots
    st.session_state["nfl_moneyline_v5_market_diag"] = mdiag
    st.session_state["nfl_moneyline_v5_market_ready"] = all_ready
    return all_ready


def render_nfl_moneyline_hub():
    """Render V4.3.1 and inject Step 5 after Step 4C, before production locks."""
    real_markdown = st.markdown
    real_dataframe = st.dataframe
    real_caption = st.caption
    state = {"injected": False, "ready": False}

    def _markdown(body, *args, **kwargs):
        if isinstance(body, str):
            if '<span class="knfl-ml-chip">STEP 4C</span>' in body:
                body = body.replace(
                    '<span class="knfl-ml-chip">STEP 4C</span>',
                    '<span class="knfl-ml-chip">STEP 5</span>',
                )
                body = body.replace(
                    "Steps 4A-4C are active: historical baseline, matchup features and base calibrated win probability. Sportsbook math and Monte Carlo remain off; preseason final output stays Step-3 gated.",
                    "Steps 4A-4C + Step 5 market are active: calibrated base P(win) stays model-only while sportsbook ML/no-vig is a separate market layer. Monte Carlo, edge/EV and final grading remain off; preseason final output stays Step-3 gated.",
                )
            if body.strip() == "### 🔒 Moneyline production locks" and not state["injected"]:
                state["injected"] = True
                state["ready"] = _render_step5()
        return real_markdown(body, *args, **kwargs)

    def _dataframe(data=None, *args, **kwargs):
        if isinstance(data, pd.DataFrame) and "Layer" in data.columns and "State" in data.columns:
            layers = set(data["Layer"].astype(str).tolist())
            if "Sportsbook Moneyline prices" in layers:
                data = data.copy()
                mask = data["Layer"].astype(str) == "Sportsbook Moneyline prices"
                data.loc[mask, "State"] = "STEP 5 READY • MARKET DISPLAY ONLY" if state.get("ready") else "STEP 5 CHECK"
                mc = data["Layer"].astype(str) == "Monte Carlo"
                if mc.any():
                    data.loc[mc, "State"] = "LOCKED — STEP 6 NEXT"
        return real_dataframe(data, *args, **kwargs)

    def _caption(body, *args, **kwargs):
        if isinstance(body, str) and body.startswith("Step 4C calibrates the Step 4A/4B feature stack"):
            body = (
                "Step 5 adds current sportsbook Moneyline transport, quote freshness, same-book implied/no-vig probabilities and best usable prices. "
                "The Step-4C base P(win) is not altered by the market. Monte Carlo, edge/EV and final grading remain OFF; Step 3 remains the preseason final-output safety gate."
            )
        return real_caption(body, *args, **kwargs)

    st.markdown = _markdown
    st.dataframe = _dataframe
    st.caption = _caption
    try:
        return v431.render_nfl_moneyline_hub()
    finally:
        st.markdown = real_markdown
        st.dataframe = real_dataframe
        st.caption = real_caption


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
