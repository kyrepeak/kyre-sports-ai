"""WNBA Game Total V1.1 — exact sportsbook total verification.

Preserves Game Total V1.0 Steps 1-3 exactly and adds Step 4 only:
- read WNBA full-game total markets from the existing SportsGameOdds bridge;
- keep only clock-safe pregame-eligible game IDs;
- require one same-book two-sided Over/Under row with a numeric full-game total;
- require both Over and Under prices; no opposite side or price is inferred;
- reject implausible totals and stale/unknown quote ages for production readiness.

No projected total, Over/Under probability, fair total, recommendation, Monte Carlo,
final grading or Daily Picks output is introduced here. Existing PRA, Points,
Rebounds, Assists, Spread, Moneyline, MLB and Daily Picks systems remain untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_game_total_hub_v10 as prior
import wnba_sportsgameodds_v1 as sgo

MODEL_VERSION = "WNBA GAME TOTAL V1.1 • EXACT SPORTSBOOK TOTAL VERIFICATION"
ET = prior.ET
foundation = prior.foundation
clock = prior.clock
spread_current = prior.spread_current

FRESH_SECONDS = 300.0
MAX_READY_AGE_SECONDS = 900.0
MIN_PLAUSIBLE_TOTAL = 80.0
MAX_PLAUSIBLE_TOTAL = 300.0


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _freshness(age):
    x = _num(age, np.nan)
    if pd.isna(x):
        return "UNKNOWN"
    if x <= FRESH_SECONDS:
        return "FRESH"
    if x <= MAX_READY_AGE_SECONDS:
        return "AGING"
    return "STALE"


def _age_label(age):
    x = _num(age, np.nan)
    if pd.isna(x):
        return "—"
    if x < 60:
        return f"{int(round(x))}s"
    if x < 3600:
        return f"{x/60.0:.1f}m"
    return f"{x/3600.0:.1f}h"


def _fmt_total(value):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.1f}"


def _fmt_price(value):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{int(round(x)):+d}"


def _total_market_snapshot(day_str: str, pregame: pd.DataFrame):
    """Return production-ready, same-book, two-sided full-game total rows."""
    empty_meta = {
        "state": "N/A",
        "provider_state": "N/A",
        "pregame_games": int(len(pregame) if isinstance(pregame, pd.DataFrame) else 0),
        "covered_games": 0,
        "exact_pairs": 0,
        "ready_pairs": 0,
        "raw_rows": 0,
        "rejected_rows": 0,
        "missing_games": [],
        "provider_error": None,
        "bookmakers": sgo.get_bookmakers(),
    }
    if pregame is None or pregame.empty:
        return pd.DataFrame(), pd.DataFrame(), empty_meta

    try:
        snap = sgo.market_snapshot(day_str)
    except Exception as exc:
        meta = dict(empty_meta)
        meta.update({
            "state": "CHECK",
            "provider_state": "PROVIDER_ERROR",
            "provider_error": f"{type(exc).__name__}: {exc}",
        })
        return pd.DataFrame(), pd.DataFrame(), meta

    provider_state = str(snap.get("state") or "CHECK").upper()
    game_lines = snap.get("game_lines")
    if not isinstance(game_lines, pd.DataFrame):
        game_lines = pd.DataFrame()

    pregame_ids = set(pregame.get("game_id", pd.Series(dtype=object)).astype(str).tolist())
    team_map = {
        str(r.get("game_id") or ""): {
            "away_team": str(r.get("away_team") or "Away"),
            "home_team": str(r.get("home_team") or "Home"),
            "first_tip_et": str(r.get("first_tip_et") or "—"),
        }
        for _, r in pregame.iterrows()
    }

    if game_lines.empty or "game_id" not in game_lines.columns:
        meta = dict(empty_meta)
        meta.update({
            "state": "CHECK",
            "provider_state": provider_state,
            "provider_error": snap.get("error"),
            "missing_games": [
                f"{team_map[g]['away_team']} @ {team_map[g]['home_team']}"
                for g in pregame_ids if g in team_map
            ],
        })
        return pd.DataFrame(), pd.DataFrame(), meta

    raw = game_lines.loc[game_lines["game_id"].astype(str).isin(pregame_ids)].copy()
    if raw.empty:
        meta = dict(empty_meta)
        meta.update({
            "state": "CHECK",
            "provider_state": provider_state,
            "provider_error": snap.get("error"),
            "missing_games": [
                f"{team_map[g]['away_team']} @ {team_map[g]['home_team']}"
                for g in pregame_ids if g in team_map
            ],
        })
        return pd.DataFrame(), pd.DataFrame(), meta

    for c in ("total", "over_price", "under_price", "age_seconds"):
        if c not in raw.columns:
            raw[c] = np.nan
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    if "book" not in raw.columns:
        raw["book"] = ""
    if "updated_at" not in raw.columns:
        raw["updated_at"] = None

    raw["away_team"] = raw["game_id"].astype(str).map(lambda g: team_map.get(g, {}).get("away_team", "Away"))
    raw["home_team"] = raw["game_id"].astype(str).map(lambda g: team_map.get(g, {}).get("home_team", "Home"))
    raw["first_tip_et"] = raw["game_id"].astype(str).map(lambda g: team_map.get(g, {}).get("first_tip_et", "—"))
    raw["freshness"] = raw["age_seconds"].map(_freshness)

    two_sided = raw["total"].notna() & raw["over_price"].notna() & raw["under_price"].notna()
    plausible = raw["total"].between(MIN_PLAUSIBLE_TOTAL, MAX_PLAUSIBLE_TOTAL, inclusive="both")
    named_book = raw["book"].astype(str).str.strip().ne("")
    raw["exact_pair"] = two_sided & plausible & named_book
    raw["ready_pair"] = raw["exact_pair"] & raw["freshness"].isin(["FRESH", "AGING"])

    def reject_reason(r):
        if pd.isna(r.get("total")):
            return "missing full-game total"
        if pd.isna(r.get("over_price")) or pd.isna(r.get("under_price")):
            return "missing Over or Under price"
        t = _num(r.get("total"), np.nan)
        if not np.isfinite(t) or not (MIN_PLAUSIBLE_TOTAL <= t <= MAX_PLAUSIBLE_TOTAL):
            return "implausible full-game total"
        if not str(r.get("book") or "").strip():
            return "missing sportsbook identity"
        if str(r.get("freshness")) == "STALE":
            return "stale market quote"
        if str(r.get("freshness")) == "UNKNOWN":
            return "market age unavailable"
        return ""

    raw["reject_reason"] = raw.apply(reject_reason, axis=1)
    exact = raw.loc[raw["exact_pair"]].copy()
    rejected = raw.loc[~raw["ready_pair"]].copy()
    ready = raw.loc[raw["ready_pair"]].copy()

    covered_ids = set(ready.get("game_id", pd.Series(dtype=object)).astype(str).tolist())
    missing_ids = sorted(pregame_ids - covered_ids)
    missing_games = [
        f"{team_map[g]['away_team']} @ {team_map[g]['home_team']}"
        for g in missing_ids if g in team_map
    ]
    market_ready = bool(pregame_ids and pregame_ids.issubset(covered_ids))

    meta = {
        "state": "READY" if market_ready else "CHECK",
        "provider_state": provider_state,
        "pregame_games": int(len(pregame_ids)),
        "covered_games": int(len(covered_ids)),
        "exact_pairs": int(len(exact)),
        "ready_pairs": int(len(ready)),
        "raw_rows": int(len(raw)),
        "rejected_rows": int(len(rejected)),
        "missing_games": missing_games,
        "provider_error": snap.get("error"),
        "bookmakers": str(snap.get("bookmakers") or sgo.get_bookmakers()),
    }
    return ready.reset_index(drop=True), rejected.reset_index(drop=True), meta


def _render_step4(day_str: str, pregame: pd.DataFrame, foundation_ready: bool):
    st.markdown("### 🎯 Step 4 — Exact Sportsbook Game Total Verification")
    st.caption(
        "SportsGameOdds full-game total only • same sportsbook + one numeric game total + both Over and Under prices required. "
        "No opposite side or price is inferred. Quotes older than 15 minutes or with unknown age cannot unlock Step 5."
    )

    if pregame is None or pregame.empty:
        st.info("ℹ️ STEP 4 NOT APPLICABLE • no clock-safe pregame games remain, so no sportsbook request is made.")
        return pd.DataFrame(), {
            "state": "N/A", "pregame_games": 0, "covered_games": 0,
            "exact_pairs": 0, "ready_pairs": 0, "provider_state": "N/A",
            "missing_games": [], "market_ready": False,
        }

    if not foundation_ready:
        st.warning("🔒 STEP 4 LOCKED • slate/context/availability must all be verified before sportsbook totals can become production-ready.")

    with st.spinner("🎯 Matching exact WNBA full-game totals by game + sportsbook…"):
        ready, rejected, meta = _total_market_snapshot(day_str, pregame)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SportsGameOdds", str(meta.get("provider_state") or "CHECK").replace("_", " ").title())
    c2.metric("Game coverage", f"{int(meta.get('covered_games', 0))}/{int(meta.get('pregame_games', 0))}")
    c3.metric("Exact pairs", int(meta.get("exact_pairs", 0)))
    c4.metric("Ready pairs", int(meta.get("ready_pairs", 0)))

    market_ready = bool(foundation_ready and str(meta.get("state")) == "READY")
    if market_ready:
        st.success("✅ STEP 4 PASSED • every pregame-eligible game has at least one current exact same-book two-sided Game Total row.")
    else:
        missing = meta.get("missing_games") or []
        if meta.get("provider_error"):
            st.warning(f"⚠️ STEP 4 CHECK • provider error: {meta.get('provider_error')}")
        elif missing:
            st.warning("⚠️ STEP 4 CHECK • no production-ready exact Game Total row for: " + "; ".join(missing))
        else:
            st.warning("⚠️ STEP 4 CHECK • exact Game Total coverage is incomplete or quotes are stale/unknown. Nothing is inferred or forced.")

    if ready is not None and not ready.empty:
        show = ready.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Total"] = show["total"].map(_fmt_total)
        show["Over"] = show["over_price"].map(_fmt_price)
        show["Under"] = show["under_price"].map(_fmt_price)
        show["Age"] = show["age_seconds"].map(_age_label)
        st.dataframe(
            show[["Game", "first_tip_et", "book", "Total", "Over", "Under", "Age", "freshness"]].rename(
                columns={"first_tip_et": "Tip ET", "book": "Book", "freshness": "Freshness"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    if rejected is not None and not rejected.empty:
        with st.expander("🔎 Step 4 rejected / non-ready Game Total rows", expanded=False):
            show = rejected.copy()
            show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
            show["Total"] = show["total"].map(_fmt_total)
            show["Over"] = show["over_price"].map(_fmt_price)
            show["Under"] = show["under_price"].map(_fmt_price)
            show["Age"] = show["age_seconds"].map(_age_label)
            st.dataframe(
                show[["Game", "book", "Total", "Over", "Under", "Age", "freshness", "reject_reason"]].rename(
                    columns={"book": "Book", "freshness": "Freshness", "reject_reason": "Reason"}
                ),
                use_container_width=True,
                hide_index=True,
            )

    return ready, {**meta, "market_ready": market_ready}


def render_wnba_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🧮 WNBA Game Total Command Center")
    st.caption(
        "V1.1 • verified slate → clock-safe pregame guard → total-scoring team context → exact-day availability → "
        "exact same-book two-sided sportsbook Game Total verification. Independent projected total and Monte Carlo remain OFF."
    )

    default_day = st.session_state.get("wnba_game_total_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input(
        "Game Total slate date",
        value=pd.to_datetime(default_day).date(),
        key="wnba_game_total_v1_date_picker",
    )
    st.session_state["wnba_game_total_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("📅 Verifying WNBA Game Total slate + clock-safe pregame eligibility…"):
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
    c4.metric("Model state", "STEP 4")
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
        with st.expander("🚫 Games excluded from Game Total pregame production", expanded=False):
            cols = [c for c in [
                "away_team", "home_team", "first_tip_et", "scheduled_tip_guard_et",
                "status", "status_text", "exclusion_reason",
            ] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    with st.spinner("📊 Building verified total-scoring team context…"):
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
        st.success("✅ STEP 2 PASSED • scoring form/defense/recent pace are verified; advanced ratings are used only where real samples exist.")
    else:
        st.warning("⚠️ STEP 2 CHECK • some total-scoring context is incomplete. Missing advanced fields remain neutral/missing; nothing is invented.")

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
        st.warning("⚠️ STEP 3 CHECK • availability is not fully verified for every pregame-eligible game. Future Game Total production remains locked.")

    st.markdown("### 🧩 Pregame-Eligible Game Total Foundation")
    if pregame.empty:
        st.info("No pregame-eligible games remain to display.")
    else:
        for _, game in pregame.iterrows():
            prior._render_game_context(game, contexts, av_map)

    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)
    market_rows, market_meta = _render_step4(day_str, pregame, foundation_ready)
    market_ready = bool(market_meta.get("market_ready", False))

    st.session_state["wnba_game_total_v1_day"] = day_str
    st.session_state["wnba_game_total_v1_foundation_ready"] = foundation_ready
    st.session_state["wnba_game_total_v1_schedule"] = schedule.to_dict("records")
    st.session_state["wnba_game_total_v1_pregame"] = pregame.to_dict("records")
    st.session_state["wnba_game_total_v1_availability"] = av.to_dict("records") if not av.empty else []
    st.session_state["wnba_game_total_v11_market_rows"] = market_rows.to_dict("records") if isinstance(market_rows, pd.DataFrame) and not market_rows.empty else []
    st.session_state["wnba_game_total_v11_market_meta"] = dict(market_meta)
    st.session_state["wnba_game_total_v11_market_ready"] = market_ready

    st.markdown("### 🔒 Game Total Production Locks")
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Total-scoring team context", "State": "READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if expected_coverage == 0 else "CHECK")},
        {"Layer": "Exact sportsbook game total", "State": "READY" if market_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Independent projected game total", "State": "NEXT" if market_ready else "LOCKED"},
        {"Layer": "Over/Under probability / fair total", "State": "LOCKED"},
        {"Layer": "5M Monte Carlo", "State": "OFF"},
        {"Layer": "Final Game Total grading", "State": "OFF"},
        {"Layer": "Daily Picks connector", "State": "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.1 makes no Game Total pick. Step 4 only verifies current exact sportsbook full-game totals. "
        "Independent projected total is the next model layer; Over/Under probability, Monte Carlo, grading and Daily Picks remain OFF."
    )
