"""WNBA Assists V13 — Step 13 exact SportsGameOdds assist lines.

Preserves Assists Steps 1–12 and adds only a strict sportsbook transport / quote
verification layer for WNBA player Assists over/under markets.

Step 13 rules:
- Step 12 must pass first;
- exact matchup comes only from the verified Step-2 Eastern-date slate;
- started/live/final/delayed/cancelled games are not eligible;
- if every verified slate game has already started, Step 13 becomes VERIFIED
  EMPTY without calling SportsGameOdds and Step 14 remains locked;
- use the existing WNBA SportsGameOdds bridge and existing API secret;
- accept only stat_id=assists / market=Assists, full-game O/U;
- player identity uses exact normalized current-roster name only (no fuzzy match);
- current player team and exact opponent must agree with the provider-matched
  event and the Step-2 matchup;
- Over and Under must exist at the SAME sportsbook and SAME line;
- both posted prices and both quote timestamps must be present;
- the older side of the pair must be no more than 15 minutes old;
- repeated rows for the same exact quote are collapsed to the freshest row;
- provider fairOdds/fairOverUnder fields are ignored here.

No no-vig math, fair probability, final assist projection, EV or Monte Carlo is
enabled in this step.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v12 as step12
import wnba_sportsgameodds_v1 as sgo

step11 = step12.step11
step3 = step12.step3
step4 = step12.step4
step5 = step12.step5
step6 = step12.step6
step7 = step12.step7
step8 = step12.step8
step9 = step12.step9
step10 = step12.step10
players = step12.players

MODEL_VERSION = "WNBA ASSISTS V13 • STEP 13 EXACT SPORTSGAMEODDS ASSIST LINES"
_ET = ZoneInfo("America/New_York")
MAX_QUOTE_AGE_SECONDS = 15 * 60
ZERO_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}


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


def _tip_et(game: dict[str, Any]) -> datetime | None:
    value = str((game or {}).get("tip_iso_et") or "").strip()
    if not value:
        return None
    try:
        ts = pd.to_datetime(value, errors="raise")
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.tz_localize(_ET)
        else:
            ts = ts.tz_convert(_ET)
        return ts.to_pydatetime()
    except Exception:
        return None


def _game_pair(game: dict[str, Any]) -> tuple[str, str]:
    return (
        sgo._team_key((game or {}).get("away") or (game or {}).get("away_tricode")),
        sgo._team_key((game or {}).get("home") or (game or {}).get("home_tricode")),
    )


def _eligible_slate_games(slate: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = datetime.now(_ET)
    upcoming: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for game in (slate or {}).get("games", []) or []:
        if not isinstance(game, dict):
            continue
        status = str(game.get("status") or "").upper().strip()
        tip = _tip_et(game)
        reason = ""
        if status != "UPCOMING":
            reason = f"status {status or 'UNKNOWN'}"
        elif tip is None:
            reason = "missing exact tip time"
        elif tip <= now:
            reason = "scheduled tip has passed"
        if reason:
            row = dict(game)
            row["market_block_reason"] = reason
            blocked.append(row)
        else:
            upcoming.append(dict(game))
    return upcoming, blocked


def _sgo_schedule_map(day_str: str) -> dict[str, dict[str, Any]]:
    try:
        frame = sgo.schedule_engine.schedule_for_date(day_str)
    except Exception:
        frame = pd.DataFrame()
    out: dict[str, dict[str, Any]] = {}
    if frame is None or frame.empty:
        return out
    for _, row in frame.iterrows():
        gid = str(row.get("game_id") or "")
        if not gid:
            continue
        out[gid] = {
            "away_key": sgo._team_key(row.get("away_team") or row.get("away_tricode")),
            "home_key": sgo._team_key(row.get("home_team") or row.get("home_tricode")),
            "away": str(row.get("away_team") or row.get("away_tricode") or ""),
            "home": str(row.get("home_team") or row.get("home_tricode") or ""),
            "tip": str(row.get("first_tip_et") or ""),
            "status": str(row.get("status") or row.get("status_text") or ""),
        }
    return out


def _current_player_map(h2h_rows: pd.DataFrame) -> tuple[dict[str, pd.Series], set[str]]:
    if h2h_rows is None or h2h_rows.empty:
        return {}, set()
    buckets: dict[str, list[pd.Series]] = {}
    for _, row in h2h_rows.iterrows():
        key = sgo._norm(row.get("PLAYER_NAME"))
        if not key:
            continue
        buckets.setdefault(key, []).append(row)
    exact: dict[str, pd.Series] = {}
    ambiguous: set[str] = set()
    for key, rows in buckets.items():
        if len(rows) == 1:
            exact[key] = rows[0]
        else:
            ambiguous.add(key)
    return exact, ambiguous


def _valid_american(value: Any) -> bool:
    try:
        x = int(float(value))
        return abs(x) >= 100
    except Exception:
        return False


def _build_step13_market(
    slate: dict[str, Any],
    day_str: str,
    h2h_rows: pd.DataFrame,
    step12_ready: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not step12_ready:
        return pd.DataFrame(), {
            "layer_ready": False,
            "market_ready": False,
            "state": "LOCKED",
            "reason": "Step 12 has not passed",
        }

    upcoming, blocked_games = _eligible_slate_games(slate)
    if not upcoming:
        return pd.DataFrame(), {
            "layer_ready": True,
            "market_ready": False,
            "state": "VERIFIED EMPTY",
            "reason": "all verified same-day games have started or are no longer pregame eligible",
            "upcoming_games": 0,
            "blocked_games": len(blocked_games),
            "provider_called": False,
            "provider_state": "NOT CALLED",
            "pairs": 0,
            "players": 0,
            "books": 0,
            "stale_blocked": 0,
            "identity_blocked": 0,
            "started_quote_rows_blocked": 0,
            "duplicate_rows_removed": 0,
        }

    if not sgo.get_api_key():
        return pd.DataFrame(), {
            "layer_ready": False,
            "market_ready": False,
            "state": "CHECK",
            "reason": "SPORTSGAMEODDS_API_KEY is unavailable",
            "upcoming_games": len(upcoming),
            "blocked_games": len(blocked_games),
            "provider_called": False,
            "provider_state": "NO_API_KEY",
            "pairs": 0,
            "players": 0,
            "books": 0,
        }

    snapshot = sgo.market_snapshot(day_str)
    provider_state = str(snapshot.get("state") or "CHECK")
    props = snapshot.get("player_props")
    if props is None:
        props = pd.DataFrame()

    if provider_state != "CONNECTED":
        return pd.DataFrame(), {
            "layer_ready": False,
            "market_ready": False,
            "state": "CHECK",
            "reason": f"SportsGameOdds state {provider_state}: {snapshot.get('error') or 'no connected market'}",
            "upcoming_games": len(upcoming),
            "blocked_games": len(blocked_games),
            "provider_called": True,
            "provider_state": provider_state,
            "events_received": int(snapshot.get("events_received") or 0),
            "matched_games": int(snapshot.get("matched_games") or 0),
            "pairs": 0,
            "players": 0,
            "books": 0,
        }

    upcoming_pairs = {_game_pair(g): g for g in upcoming if all(_game_pair(g))}
    exact_players, ambiguous_players = _current_player_map(h2h_rows)
    provider_games = _sgo_schedule_map(day_str)

    if props.empty:
        return pd.DataFrame(), {
            "layer_ready": False,
            "market_ready": False,
            "state": "CHECK",
            "reason": "SportsGameOdds connected, but returned no WNBA player-prop rows",
            "upcoming_games": len(upcoming),
            "blocked_games": len(blocked_games),
            "provider_called": True,
            "provider_state": provider_state,
            "events_received": int(snapshot.get("events_received") or 0),
            "matched_games": int(snapshot.get("matched_games") or 0),
            "pairs": 0,
            "players": 0,
            "books": 0,
        }

    work = props.copy()
    market_mask = work.get("market", pd.Series("", index=work.index)).astype(str).str.upper().eq("ASSISTS")
    stat_mask = work.get("stat_id", pd.Series("", index=work.index)).astype(str).str.lower().eq("assists")
    work = work.loc[market_mask & stat_mask].copy()
    if work.empty:
        return pd.DataFrame(), {
            "layer_ready": False,
            "market_ready": False,
            "state": "CHECK",
            "reason": "SportsGameOdds connected, but no exact Assists O/U markets were returned",
            "upcoming_games": len(upcoming),
            "blocked_games": len(blocked_games),
            "provider_called": True,
            "provider_state": provider_state,
            "events_received": int(snapshot.get("events_received") or 0),
            "matched_games": int(snapshot.get("matched_games") or 0),
            "pairs": 0,
            "players": 0,
            "books": 0,
        }

    work["_age"] = pd.to_numeric(work.get("age_seconds"), errors="coerce")
    work["_line"] = pd.to_numeric(work.get("line"), errors="coerce")
    work["_player_key"] = work.get("player_name", pd.Series("", index=work.index)).map(sgo._norm)
    work["_side"] = work.get("side", pd.Series("", index=work.index)).astype(str).str.lower()
    work["_book"] = work.get("book", pd.Series("", index=work.index)).astype(str).str.strip()
    work["_game_id"] = work.get("game_id", pd.Series("", index=work.index)).astype(str)
    work["_event_id"] = work.get("event_id", pd.Series("", index=work.index)).astype(str)
    work["_sort_age"] = work["_age"].fillna(10**12)

    before = len(work)
    work = (
        work.sort_values("_sort_age", ascending=True)
        .drop_duplicates(subset=["_game_id", "_event_id", "_player_key", "_book", "_side", "_line"], keep="first")
        .reset_index(drop=True)
    )
    duplicate_rows_removed = max(0, before - len(work))

    started_quote_rows_blocked = 0
    identity_blocked = 0
    stale_blocked = 0
    malformed_blocked = 0
    matchup_blocked = 0
    paired_rows: list[dict[str, Any]] = []

    enriched: list[dict[str, Any]] = []
    for _, quote in work.iterrows():
        game_id = str(quote.get("_game_id") or "")
        game = provider_games.get(game_id)
        if not game:
            matchup_blocked += 1
            continue
        pair = (str(game.get("away_key") or ""), str(game.get("home_key") or ""))
        verified_game = upcoming_pairs.get(pair)
        if verified_game is None:
            # Provider can still return stale/live quotes from another game on the
            # same ET slate. They are never allowed into the Step-13 pairer.
            if pair[0] and pair[1]:
                started_quote_rows_blocked += 1
            else:
                matchup_blocked += 1
            continue

        pkey = str(quote.get("_player_key") or "")
        if not pkey or pkey in ambiguous_players or pkey not in exact_players:
            identity_blocked += 1
            continue
        prow = exact_players[pkey]
        status = str(prow.get("AVAILABILITY") or "").upper().strip()
        proj_min = _num(prow.get("PROJ_MIN"), 0.0)
        if status in ZERO_STATUSES or proj_min <= 0.25:
            identity_blocked += 1
            continue

        player_team_key = sgo._team_key(prow.get("TEAM_NAME") or prow.get("TEAM_ABBREVIATION"))
        player_opp_key = sgo._team_key(prow.get("OPPONENT"))
        if player_team_key == pair[0]:
            exact_opp_key = pair[1]
        elif player_team_key == pair[1]:
            exact_opp_key = pair[0]
        else:
            identity_blocked += 1
            continue
        if player_opp_key and player_opp_key != exact_opp_key:
            matchup_blocked += 1
            continue

        line = _num(quote.get("_line"))
        price = quote.get("odds")
        age = _num(quote.get("_age"))
        updated = str(quote.get("updated_at") or "").strip()
        if not np.isfinite(line) or line < 0 or not _valid_american(price) or not np.isfinite(age) or not updated:
            malformed_blocked += 1
            continue
        if age > MAX_QUOTE_AGE_SECONDS:
            stale_blocked += 1
            continue

        enriched.append({
            "game_id": game_id,
            "event_id": str(quote.get("_event_id") or ""),
            "player_key": pkey,
            "player_name": str(prow.get("PLAYER_NAME") or quote.get("player_name") or ""),
            "team": str(prow.get("TEAM_ABBREVIATION") or prow.get("TEAM_NAME") or ""),
            "opponent": str(prow.get("OPPONENT") or ""),
            "book": str(quote.get("_book") or ""),
            "side": str(quote.get("_side") or ""),
            "line": float(line),
            "odds": int(float(price)),
            "updated_at": updated,
            "age_seconds": float(age),
            "tip_et": str(verified_game.get("tip_et") or ""),
            "proj_min": float(proj_min),
            "availability": status or "NOT LISTED",
        })

    good = pd.DataFrame(enriched)
    if not good.empty:
        for (game_id, event_id, player_key, book, line), group in good.groupby(
            ["game_id", "event_id", "player_key", "book", "line"], dropna=False
        ):
            over = group.loc[group["side"].eq("over")].sort_values("age_seconds").head(1)
            under = group.loc[group["side"].eq("under")].sort_values("age_seconds").head(1)
            if over.empty or under.empty:
                continue
            o = over.iloc[0]
            u = under.iloc[0]
            pair_age = max(float(o["age_seconds"]), float(u["age_seconds"]))
            if pair_age > MAX_QUOTE_AGE_SECONDS:
                stale_blocked += 1
                continue
            paired_rows.append({
                "PLAYER_NAME": str(o["player_name"]),
                "TEAM": str(o["team"]),
                "OPPONENT": str(o["opponent"]),
                "BOOK": str(book),
                "LINE": float(line),
                "OVER_ODDS": int(o["odds"]),
                "UNDER_ODDS": int(u["odds"]),
                "OVER_UPDATED": str(o["updated_at"]),
                "UNDER_UPDATED": str(u["updated_at"]),
                "QUOTE_AGE_SECONDS": pair_age,
                "EVENT_ID": str(event_id),
                "GAME_ID": str(game_id),
                "TIP_ET": str(o["tip_et"]),
                "PROJ_MIN": float(o["proj_min"]),
                "AVAILABILITY": str(o["availability"]),
                "MARKET": "Assists",
                "SOURCE": "SportsGameOdds",
                "GATE": "PASS",
            })

    paired = pd.DataFrame(paired_rows)
    if not paired.empty:
        paired = paired.sort_values(
            ["PLAYER_NAME", "LINE", "BOOK", "QUOTE_AGE_SECONDS"],
            ascending=[True, True, True, True],
        ).reset_index(drop=True)

    market_ready = bool(not paired.empty)
    reason = "" if market_ready else "no exact same-book, same-line fresh Over/Under Assist pairs survived all identity/start/freshness gates"
    return paired, {
        "layer_ready": market_ready,
        "market_ready": market_ready,
        "state": "VERIFIED" if market_ready else "CHECK",
        "reason": reason,
        "upcoming_games": len(upcoming),
        "blocked_games": len(blocked_games),
        "provider_called": True,
        "provider_state": provider_state,
        "events_received": int(snapshot.get("events_received") or 0),
        "matched_games": int(snapshot.get("matched_games") or 0),
        "pairs": len(paired),
        "players": int(paired["PLAYER_NAME"].nunique()) if not paired.empty else 0,
        "books": int(paired["BOOK"].nunique()) if not paired.empty else 0,
        "stale_blocked": stale_blocked,
        "identity_blocked": identity_blocked,
        "matchup_blocked": matchup_blocked,
        "malformed_blocked": malformed_blocked,
        "started_quote_rows_blocked": started_quote_rows_blocked,
        "duplicate_rows_removed": duplicate_rows_removed,
        "bookmakers": str(snapshot.get("bookmakers") or sgo.get_bookmakers()),
    }


def _render_step13(
    slate: dict[str, Any],
    day_str: str,
    h2h_rows: pd.DataFrame,
    step12_ready: bool,
) -> tuple[bool, bool, pd.DataFrame, dict[str, Any]]:
    st.markdown("### 🎯 Step 13 — Exact SportsGameOdds Assist Lines")
    st.caption(
        "Sportsbook transport/verification only. Exact current player + exact verified matchup + exact book + exact line + same-book Over/Under pair + 15-minute freshness. No no-vig or projection math is performed here."
    )
    if not step12_ready:
        st.error("⛔ STEP 13 LOCKED • Step 12 has not passed, so sportsbook data cannot enter the Assists chain.")
        return False, False, pd.DataFrame(), {"state": "LOCKED"}

    with st.spinner("🎯 Verifying exact SportsGameOdds Assists markets…"):
        paired, diag = _build_step13_market(slate, day_str, h2h_rows, step12_ready)

    layer_ready = bool(diag.get("layer_ready"))
    market_ready = bool(diag.get("market_ready"))
    state = str(diag.get("state") or "CHECK")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Upcoming games", int(diag.get("upcoming_games") or 0))
    c2.metric("SportsGameOdds", str(diag.get("provider_state") or "NOT CALLED"))
    c3.metric("Exact O/U pairs", int(diag.get("pairs") or 0))
    c4.metric("Freshness gate", "≤15m")

    if state == "VERIFIED EMPTY":
        st.info(
            "✅ STEP 13 VERIFIED EMPTY • every verified same-day WNBA game has started or is no longer pregame-eligible. SportsGameOdds was not called, no stale/live quote was accepted, and Step 14 remains locked until an upcoming same-day market exists."
        )
    elif layer_ready and market_ready:
        st.success(
            "✅ STEP 13 PASSED • exact Assists Over/Under pairs survived current-roster identity, verified matchup, pregame status, same-book/same-line and ≤15-minute freshness gates. No no-vig math has been applied."
        )
    else:
        st.warning(f"⚠️ STEP 13 CHECK • {diag.get('reason') or 'exact assist market verification incomplete'}. Step 14 remains locked.")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Players", int(diag.get("players") or 0))
    d2.metric("Books", int(diag.get("books") or 0))
    d3.metric("Started rows blocked", int(diag.get("started_quote_rows_blocked") or 0))
    d4.metric("Stale rows blocked", int(diag.get("stale_blocked") or 0))

    if paired is not None and not paired.empty:
        view = paired.copy()
        view["Player"] = view["PLAYER_NAME"].astype(str)
        view["Team"] = view["TEAM"].astype(str)
        view["Opponent"] = view["OPPONENT"].astype(str)
        view["Book"] = view["BOOK"].astype(str)
        view["Line"] = pd.to_numeric(view["LINE"], errors="coerce")
        view["Over"] = view["OVER_ODDS"].apply(lambda x: f"{int(x):+d}")
        view["Under"] = view["UNDER_ODDS"].apply(lambda x: f"{int(x):+d}")
        view["Quote age"] = pd.to_numeric(view["QUOTE_AGE_SECONDS"], errors="coerce").apply(
            lambda x: "—" if pd.isna(x) else (f"{int(x)}s" if x < 120 else f"{int(x // 60)}m")
        )
        view["Tip ET"] = view["TIP_ET"].astype(str)
        view["Gate"] = view["GATE"].astype(str)
        st.dataframe(
            view[["Player", "Team", "Opponent", "Book", "Line", "Over", "Under", "Quote age", "Tip ET", "Gate"]],
            hide_index=True,
            use_container_width=True,
        )
        if market_ready:
            st.session_state[f"wnba_assists_v13_exact_lines::{day_str}"] = paired.copy()

    with st.expander("🧪 Step-13 market methodology / diagnostics", expanded=False):
        st.write("• Exact market only: SportsGameOdds stat_id=assists / market=Assists / full-game O/U.")
        st.write("• Exact Step-2 home/away matchup is mandatory; provider rows from other or started slate games are rejected.")
        st.write("• A game is pregame-eligible only when Step 2 says UPCOMING and its exact ET tip time is still in the future.")
        st.write("• If no verified game remains upcoming, the layer returns VERIFIED EMPTY without making a SportsGameOdds request.")
        st.write("• Player match is exact normalized current-roster name only. Fuzzy name matching and cross-team matching are not used.")
        st.write("• OUT / INACTIVE / DOUBTFUL or zero-minute players cannot enter the exact market pool.")
        st.write("• Over and Under must be from the same sportsbook and the exact same assist line.")
        st.write("• Both posted prices and both timestamps are required; freshness uses the OLDER side of the O/U pair and must be ≤15 minutes.")
        st.write("• Repeated exact quote rows are collapsed to the freshest provider row.")
        st.write("• Provider fairOdds/fairOverUnder ignored: YES — Step 14 owns no-vig math.")
        st.write("• No-vig calculations: 0")
        st.write("• Final assist projection created: NO")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• Provider called: {bool(diag.get('provider_called'))}")
        st.write(f"• Bookmakers requested: {diag.get('bookmakers', '—')}")
        st.write(f"• Identity rows blocked: {int(diag.get('identity_blocked') or 0)}")
        st.write(f"• Matchup rows blocked: {int(diag.get('matchup_blocked') or 0)}")
        st.write(f"• Malformed rows blocked: {int(diag.get('malformed_blocked') or 0)}")
        st.write(f"• Duplicate quote rows removed: {int(diag.get('duplicate_rows_removed') or 0)}")

    return layer_ready, market_ready, paired, diag


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
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 13</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–12 remain intact. Step 13 adds only exact SportsGameOdds Assist quotes with strict identity, matchup, pregame and freshness gates. No-vig math, final projection and simulations remain locked.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">✅ Steps 1–12 preserved</span>
          <span class="ks-ast-chip">🎯 exact Assist O/U</span>
          <span class="ks-ast-chip">🚫 zero simulations</span>
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
    step13_ready, step13_market_ready, _, step13_diag = _render_step13(slate, slate_day, h2h_rows, step12_ready)

    if st.button("🔄 RECHECK ASSISTS STEPS 2–13", use_container_width=True, key="assists_step13_recheck"):
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
    step13_state = str(step13_diag.get("state") or "CHECK")
    step13_note = "Verified empty — no upcoming pregame" if step13_state == "VERIFIED EMPTY" else "Exact same-book O/U • start/freshness gated"
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
        (13, "Exact SportsGameOdds assist lines", "✅ LIVE" if step13_ready else ("⚠️ CHECK" if step12_ready else "🔒 LOCKED"), step13_note),
        (14, "Same-book no-vig", "➡️ NEXT" if step13_market_ready else "🔒 LOCKED", "Market math stays separate from projection"),
        (15, "Market-independent assist projection", "🔒 LOCKED", "Expected assists before market grading"),
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

    footer13 = "EMPTY" if step13_state == "VERIFIED EMPTY" else ("PASS" if step13_market_ready else "CHECK")
    st.caption(
        f"⚡ WNBA Assists V13 Step 13 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'CHECK'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • Step 5 {'PASS' if step5_ready else 'CHECK'} • Step 6 {'PASS' if step6_ready else 'CHECK'} • Step 7 {'PASS' if step7_ready else 'CHECK'} • Step 8 {'PASS' if step8_ready else 'CHECK'} • Step 9 {'PASS' if step9_ready else 'CHECK'} • Step 10 {'PASS' if step10_ready else 'CHECK'} • Step 11 {'PASS' if step11_ready else 'CHECK'} • Step 12 {'PASS' if step12_ready else 'CHECK'} • Step 13 {footer13} • no no-vig/projection/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
