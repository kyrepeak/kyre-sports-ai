"""WNBA Spread V1.3 — exact sportsbook spread verification.

Preserves the V1.2 clock-safe pregame foundation and adds Step 4 only:
- read WNBA full-game spread markets from the existing SportsGameOdds bridge;
- keep only currently pregame-eligible game IDs;
- require an exact same-book two-sided spread pair (away + home);
- require both prices and mirrored spread values; never infer the opposite side;
- track market age and refuse stale/unknown quotes for production readiness.

No projected margin, cover probability, fair spread, recommendation, or Monte
Carlo math is introduced here. Existing PRA/Points/Rebounds/Assists/MLB/Daily
Picks systems are untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_spread_hub_v12 as prior
import wnba_sportsgameodds_v1 as sgo

MODEL_VERSION = "WNBA SPREAD V1.3 • EXACT SPORTSBOOK SPREAD VERIFICATION"
ET = prior.ET
foundation = prior.base

FRESH_SECONDS = 300.0
MAX_READY_AGE_SECONDS = 900.0
MAX_ABS_SPREAD = 50.0
MIRROR_TOLERANCE = 0.05


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


def _fmt_line(value):
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    return f"{x:+.1f}"


def _fmt_price(value):
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    return f"{int(round(x)):+d}"


def _spread_market_snapshot(day_str: str, pregame: pd.DataFrame):
    """Return exact two-sided, pregame-only sportsbook spread rows.

    SportsGameOdds may return game markets for the full date. This function never
    trusts that transport boundary as a production boundary: it re-filters by the
    V1.2 clock-safe pregame game IDs before validating any spread row.
    """
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
        meta.update({"state": "CHECK", "provider_state": "PROVIDER_ERROR", "provider_error": f"{type(exc).__name__}: {exc}"})
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
            "missing_games": [f"{team_map[g]['away_team']} @ {team_map[g]['home_team']}" for g in pregame_ids if g in team_map],
        })
        return pd.DataFrame(), pd.DataFrame(), meta

    raw = game_lines.loc[game_lines["game_id"].astype(str).isin(pregame_ids)].copy()
    if raw.empty:
        meta = dict(empty_meta)
        meta.update({
            "state": "CHECK",
            "provider_state": provider_state,
            "provider_error": snap.get("error"),
            "missing_games": [f"{team_map[g]['away_team']} @ {team_map[g]['home_team']}" for g in pregame_ids if g in team_map],
        })
        return pd.DataFrame(), pd.DataFrame(), meta

    for c in ("away_spread", "home_spread", "away_spread_price", "home_spread_price", "age_seconds"):
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

    two_sided = (
        raw["away_spread"].notna()
        & raw["home_spread"].notna()
        & raw["away_spread_price"].notna()
        & raw["home_spread_price"].notna()
    )
    mirrored = (raw["away_spread"] + raw["home_spread"]).abs().le(MIRROR_TOLERANCE)
    plausible = raw["away_spread"].abs().le(MAX_ABS_SPREAD) & raw["home_spread"].abs().le(MAX_ABS_SPREAD)
    named_book = raw["book"].astype(str).str.strip().ne("")

    raw["exact_pair"] = two_sided & mirrored & plausible & named_book
    raw["ready_pair"] = raw["exact_pair"] & raw["freshness"].isin(["FRESH", "AGING"])

    def reject_reason(r):
        if not bool(r.get("exact_pair")):
            if pd.isna(r.get("away_spread")) or pd.isna(r.get("home_spread")):
                return "missing one side of spread"
            if pd.isna(r.get("away_spread_price")) or pd.isna(r.get("home_spread_price")):
                return "missing one side price"
            if abs(_num(r.get("away_spread"), 999) + _num(r.get("home_spread"), 999)) > MIRROR_TOLERANCE:
                return "away/home spreads are not mirrored"
            if abs(_num(r.get("away_spread"), 999)) > MAX_ABS_SPREAD or abs(_num(r.get("home_spread"), 999)) > MAX_ABS_SPREAD:
                return "implausible spread value"
            return "invalid exact pair"
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
    missing_games = [f"{team_map[g]['away_team']} @ {team_map[g]['home_team']}" for g in missing_ids if g in team_map]
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
    st.markdown("### 🎯 Step 4 — Exact Sportsbook Spread Verification")
    st.caption(
        "SportsGameOdds full-game spread only • same book + both teams + both prices + mirrored line required. "
        "No opposite side is inferred. Quotes older than 15 minutes or with unknown age cannot unlock Step 5."
    )

    if pregame is None or pregame.empty:
        st.info("ℹ️ STEP 4 NOT APPLICABLE • no clock-safe pregame games remain, so no sportsbook request is made.")
        return pd.DataFrame(), {"state": "N/A", "pregame_games": 0, "covered_games": 0, "exact_pairs": 0, "ready_pairs": 0, "provider_state": "N/A", "missing_games": []}

    if not foundation_ready:
        st.warning("🔒 STEP 4 LOCKED • slate/context/availability must all be verified before sportsbook spread rows can become production-ready.")

    with st.spinner("🎯 Matching exact WNBA spread lines by game + sportsbook…"):
        ready, rejected, meta = _spread_market_snapshot(day_str, pregame)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SportsGameOdds", str(meta.get("provider_state") or "CHECK").replace("_", " ").title())
    c2.metric("Game coverage", f"{int(meta.get('covered_games',0))}/{int(meta.get('pregame_games',0))}")
    c3.metric("Exact pairs", int(meta.get("exact_pairs", 0)))
    c4.metric("Ready pairs", int(meta.get("ready_pairs", 0)))

    market_ready = bool(foundation_ready and str(meta.get("state")) == "READY")
    if market_ready:
        st.success("✅ STEP 4 PASSED • every pregame-eligible game has at least one current exact two-sided sportsbook spread pair.")
    else:
        missing = meta.get("missing_games") or []
        if meta.get("provider_error"):
            st.warning(f"⚠️ STEP 4 CHECK • provider error: {meta.get('provider_error')}")
        elif missing:
            st.warning("⚠️ STEP 4 CHECK • no production-ready exact spread pair for: " + "; ".join(missing))
        else:
            st.warning("⚠️ STEP 4 CHECK • exact spread coverage is incomplete or quotes are stale/unknown. Nothing is inferred or forced.")

    if ready is not None and not ready.empty:
        show = ready.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Away"] = show.apply(lambda r: f"{r['away_team']} {_fmt_line(r['away_spread'])}", axis=1)
        show["Away price"] = show["away_spread_price"].map(_fmt_price)
        show["Home"] = show.apply(lambda r: f"{r['home_team']} {_fmt_line(r['home_spread'])}", axis=1)
        show["Home price"] = show["home_spread_price"].map(_fmt_price)
        show["Age"] = show["age_seconds"].map(_age_label)
        st.dataframe(
            show[["Game", "first_tip_et", "book", "Away", "Away price", "Home", "Home price", "Age", "freshness"]].rename(
                columns={"first_tip_et": "Tip ET", "book": "Book", "freshness": "Freshness"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    if rejected is not None and not rejected.empty:
        with st.expander("🔎 Step 4 rejected / non-ready spread rows", expanded=False):
            show = rejected.copy()
            show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
            show["Away line"] = show["away_spread"].map(_fmt_line)
            show["Home line"] = show["home_spread"].map(_fmt_line)
            show["Age"] = show["age_seconds"].map(_age_label)
            cols = ["Game", "book", "Away line", "Home line", "Age", "freshness", "reject_reason"]
            st.dataframe(show[cols].rename(columns={"book":"Book","freshness":"Freshness","reject_reason":"Reason"}), use_container_width=True, hide_index=True)

    return ready, {**meta, "market_ready": market_ready}


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🏀 WNBA Spread Command Center")
    st.caption(
        "V1.3 • verified slate → clock-safe pregame guard → team context → current availability → exact sportsbook spread verification. "
        "Projected margin and Monte Carlo remain OFF."
    )

    default_day = st.session_state.get("wnba_spread_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input("Spread slate date", value=pd.to_datetime(default_day).date(), key="wnba_spread_v1_date_picker")
    st.session_state["wnba_spread_v1_date"] = selected
    day_str = foundation._day(selected)
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("📅 Verifying WNBA spread slate + clock-safe pregame eligibility…"):
        schedule = foundation._schedule(day_str)
        pregame = prior._pregame_schedule(schedule, now_et=now_et)
        excluded = prior._excluded_schedule(schedule, now_et=now_et)

    teams = 0
    if not schedule.empty:
        tids = set()
        for col in ("away_team_id", "home_team_id"):
            if col in schedule.columns:
                tids.update(pd.to_numeric(schedule[col], errors="coerce").dropna().astype(int).tolist())
        teams = len(tids)

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
        with st.expander("🚫 Games excluded from pregame production", expanded=True):
            cols = [c for c in ["away_team", "home_team", "first_tip_et", "scheduled_tip_guard_et", "status", "status_text", "exclusion_reason"] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    with st.spinner("📊 Building verified team form + matchup context…"):
        try:
            contexts, cdiag = foundation.context.slate_context(day_str)
        except Exception as exc:
            contexts, cdiag = {}, {"state": "CHECK", "reason": type(exc).__name__}

    context_state = str(cdiag.get("state") or "CHECK").upper()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Context state", context_state)
    d2.metric("Records verified", f"{int(cdiag.get('records_verified',0) or 0)}/{int(cdiag.get('teams',teams) or teams)}")
    d3.metric("Advanced teams", int(cdiag.get("advanced_teams", 0) or 0))
    d4.metric("H2H samples", int(cdiag.get("h2h_samples", 0) or 0))
    if context_state == "VERIFIED":
        st.success("✅ STEP 2 PASSED • team records/recent form are verified; advanced pace/ratings are used only where real samples exist.")
    else:
        st.warning("⚠️ STEP 2 CHECK • some team context is incomplete. Missing advanced fields remain neutral/missing; nothing is invented.")

    with st.spinner("🩺 Verifying current team availability for pregame-eligible games…"):
        av = foundation._availability_snapshot(day_str, pregame)
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
        st.warning("⚠️ STEP 3 CHECK • availability is not fully verified for every pregame-eligible game. Future spread production remains locked.")

    st.markdown("### 🧩 Pregame-Eligible Game Foundation")
    if pregame.empty:
        st.info("No pregame-eligible games remain to display.")
    else:
        for _, game in pregame.iterrows():
            foundation._render_game_context(game, contexts, av_map)

    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)
    ready_lines, step4 = _render_step4(day_str, pregame, foundation_ready)
    market_ready = bool(step4.get("market_ready", False))

    st.markdown("### 🔒 Spread Production Locks")
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Team context", "State": "READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Exact sportsbook spread line", "State": "READY" if market_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Projected game margin", "State": "NEXT" if market_ready else "LOCKED"},
        {"Layer": "Cover probability / fair spread", "State": "LOCKED"},
        {"Layer": "5M Monte Carlo", "State": "OFF"},
        {"Layer": "Daily Picks connector", "State": "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.3 still makes no spread pick. Step 4 only verifies exact current sportsbook spread pairs. "
        "Projected margin is the next model layer."
    )


__all__ = [
    "MODEL_VERSION", "_spread_market_snapshot", "_render_step4", "render_wnba_spread_hub",
]
