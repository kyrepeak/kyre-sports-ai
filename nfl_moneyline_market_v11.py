"""NFL Moneyline market V1.1 — pregame quote-age/fallback repair.

Builds on nfl_moneyline_market_v1 without altering any NFL model probability.
SportsGameOdds remains primary and Odds-API.io remains fallback.

Important provider semantics: bookmaker `lastUpdatedAt` is the age of the last
price change, not the age of the HTTP response. A stable pregame line can be
perfectly current while its price-change timestamp is several minutes old.

V1.1 therefore uses a conservative pregame quote-age policy:
- FRESH: <= 3 minutes
- AGING: >3 and <=15 minutes
- STALE: >15 minutes

Timestamp-unknown or >15-minute rows remain visible but are excluded from usable
no-vig/best-price summaries. Fallback is now attempted whenever the primary has
no USABLE same-book pair (not merely when a pair is absent), and a fresher usable
fallback row can replace a stale/incomplete primary row for the same sportsbook.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

import nfl_moneyline_market_v1 as base

MODEL_VERSION = "NFL MONEYLINE MARKET V1.1 • PREGAME QUOTE-AGE + FALLBACK REPAIR"
FRESH_SECONDS = 180
STALE_SECONDS = 900

# Base parser helpers read these module globals at runtime, so patch only the
# transport freshness thresholds. No model/calibration state is touched.
base.FRESH_SECONDS = FRESH_SECONDS
base.STALE_SECONDS = STALE_SECONDS


def connection_state():
    return base.connection_state()


def freshness_label(age):
    return base.freshness_label(age)


def fmt_american(value):
    return base.fmt_american(value)


def fmt_pct(value, digits=1):
    return base.fmt_pct(value, digits=digits)


def fmt_age(age):
    return base.fmt_age(age)


def _row_rank(row):
    """Higher tuple wins when primary/fallback provide the same sportsbook."""
    row = dict(row or {})
    usable = 1 if row.get("usable") else 0
    complete = 1 if row.get("complete_pair") else 0
    timestamped = 1 if row.get("age_seconds") is not None else 0
    try:
        age = int(row.get("age_seconds"))
    except Exception:
        age = 10**9
    # Prefer usable, then complete, then timestamped, then younger quote age.
    return usable, complete, timestamped, -age


def _merge_best(primary, fallback):
    merged = {}
    for row in primary or []:
        merged[base._book_id(row.get("book"))] = dict(row)
    for row in fallback or []:
        key = base._book_id(row.get("book"))
        candidate = dict(row)
        current = merged.get(key)
        if current is None or _row_rank(candidate) > _row_rank(current):
            merged[key] = candidate
    return sorted(merged.values(), key=lambda x: str(x.get("book")))


def fetch_nfl_moneyline_markets(pregame: pd.DataFrame, day_str: str):
    """Primary SGO market fetch with usability-aware fallback replacement."""
    state = connection_state()
    snapshots = {}
    diag = {
        "sgo_connected": state["sgo"],
        "fallback_connected": state["legacy"],
        "sgo_error": "",
        "fallback_error": "",
        "games_requested": int(len(pregame)) if pregame is not None else 0,
        "games_with_market": 0,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "fresh_seconds": FRESH_SECONDS,
        "stale_seconds": STALE_SECONDS,
    }
    if pregame is None or pregame.empty:
        return snapshots, diag

    sgo_events = []
    if state["sgo"]:
        try:
            start, end = base._slate_window(day_str)
            sgo_events = base._fetch_sgo(
                base.get_sgo_api_key(), start, end, state["sgo_books"]
            )
        except Exception as exc:
            diag["sgo_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"

    needs_fallback = []
    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = str(
            game.get("game_id")
            or f"{game.get('away_abbr')}@{game.get('home_abbr')}"
        )
        event = base._match_event(sgo_events, game, sgo=True) if sgo_events else None
        rows = base._parse_sgo(event, gid) if event else []
        snapshots[gid] = {
            "game": game,
            "rows": rows,
            "primary_matched": bool(event),
            "fallback_used": False,
        }
        # V1 used complete_pair here. V1.1 correctly asks whether a usable pair
        # exists, so stale primary quotes can trigger the configured fallback.
        if not any(x.get("usable") for x in rows):
            needs_fallback.append((gid, game))

    if needs_fallback and state["legacy"]:
        try:
            found, event_ids = {}, []
            for gid, game in needs_fallback:
                query = str(game.get("away_team") or "").strip()
                events = base._legacy_search(base.get_legacy_api_key(), query) if query else []
                event = base._match_event(events, game, sgo=False) if events else None
                if event and event.get("id") is not None:
                    found[gid] = event
                    event_ids.append(event["id"])

            payloads = (
                base._legacy_multi(
                    base.get_legacy_api_key(),
                    tuple(event_ids),
                    state["legacy_books"],
                )
                if event_ids else []
            )
            by_id = {
                str(x.get("id")): x
                for x in payloads
                if isinstance(x, dict) and x.get("id") is not None
            }
            for gid, event in found.items():
                fallback_rows = base._parse_legacy(
                    by_id.get(str(event.get("id"))), gid
                )
                before = list(snapshots[gid].get("rows") or [])
                after = _merge_best(before, fallback_rows)
                snapshots[gid]["rows"] = after
                # Mark fallback as used only if it actually supplied/replaced at
                # least one sportsbook row in the final normalized board.
                fallback_books = {
                    base._book_id(x.get("book"))
                    for x in fallback_rows
                    if x.get("complete_pair")
                }
                final_fallback = any(
                    base._book_id(x.get("book")) in fallback_books
                    and x.get("provider") == "Odds-API.io"
                    for x in after
                )
                snapshots[gid]["fallback_used"] = bool(final_fallback)
        except Exception as exc:
            diag["fallback_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"

    for gid, snap in list(snapshots.items()):
        snap.update(base._summary(snap.get("rows")))
        snapshots[gid] = snap

    diag["games_with_market"] = sum(
        1 for snap in snapshots.values() if snap.get("ready")
    )
    return snapshots, diag


__all__ = [
    "MODEL_VERSION",
    "FRESH_SECONDS",
    "STALE_SECONDS",
    "fetch_nfl_moneyline_markets",
    "connection_state",
    "freshness_label",
    "fmt_american",
    "fmt_pct",
    "fmt_age",
]
