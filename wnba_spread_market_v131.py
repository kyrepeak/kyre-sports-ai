"""WNBA Spread V1.3.1 — spread-specific SportsGameOdds integrity adapter.

This adapter exists because the shared WNBA SportsGameOdds bridge stores one
`updated_at` timestamp per game/book row across moneyline, spread and total.
That is fine for transport display, but a production spread gate must measure the
age of the two spread sides themselves. It also must never accept a reversed team
orientation and then accidentally label provider HOME/AWAY prices as the opposite
schedule side.

V1.3.1 therefore:
- fetches through the existing cached SportsGameOdds transport (no extra provider
  policy and no change to API credentials/bookmakers);
- matches schedule away/home orientation exactly, never reversed;
- parses only full-game spread odds;
- retains side-specific updated timestamps and uses the older side as pair age;
- requires both spread sides, both prices, mirrored lines and current market age;
- remains pregame-only because callers pass the V1.2 clock-safe schedule.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

import wnba_sportsgameodds_v1 as sgo

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


def _age_seconds(value):
    if not value:
        return np.nan
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return np.nan


def _newer(candidate, current):
    if not current:
        return True
    if not candidate:
        return False
    try:
        a = datetime.fromisoformat(str(candidate).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(current).replace("Z", "+00:00"))
        return a > b
    except Exception:
        return False


def _freshness(age):
    x = _num(age, np.nan)
    if pd.isna(x):
        return "UNKNOWN"
    if x <= FRESH_SECONDS:
        return "FRESH"
    if x <= MAX_READY_AGE_SECONDS:
        return "AGING"
    return "STALE"


def _event_local_date(event):
    try:
        dt = sgo._event_start(event)
        return dt.astimezone(sgo.ET).strftime("%Y-%m-%d") if dt else ""
    except Exception:
        return ""


def _exact_event(events, schedule_row, day_str):
    away_key = sgo._team_key(schedule_row.get("away_team") or schedule_row.get("away_tricode"))
    home_key = sgo._team_key(schedule_row.get("home_team") or schedule_row.get("home_tricode"))
    candidates = []
    for event in events or []:
        ea = sgo._team_key(sgo._event_team_name(event, "away"))
        eh = sgo._team_key(sgo._event_team_name(event, "home"))
        if ea != away_key or eh != home_key:
            continue
        local_date = _event_local_date(event)
        if local_date and local_date != str(day_str):
            continue
        candidates.append(event)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # Same teams can theoretically appear more than once inside the broad API
    # time window. Choose the provider event nearest the verified scheduled tip.
    try:
        tip = str(schedule_row.get("first_tip_et") or "").replace(" ET", "").strip()
        target = pd.Timestamp(f"{day_str} {tip}").tz_localize(sgo.ET).tz_convert("UTC")
    except Exception:
        target = None
    if target is None:
        return candidates[0]

    def distance(event):
        try:
            dt = sgo._event_start(event)
            if dt is None:
                return float("inf")
            return abs((pd.Timestamp(dt) - target).total_seconds())
        except Exception:
            return float("inf")

    return min(candidates, key=distance)


def _parse_spread_only(event, schedule_row):
    game_id = str(schedule_row.get("game_id") or "")
    away_team = str(schedule_row.get("away_team") or "Away")
    home_team = str(schedule_row.get("home_team") or "Home")
    tip = str(schedule_row.get("first_tip_et") or "—")
    by_book = {}
    odds = (event or {}).get("odds") or {}
    if not isinstance(odds, dict):
        return []

    for odd in odds.values():
        if not isinstance(odd, dict):
            continue
        if str(odd.get("periodID") or "").lower() != "game":
            continue
        if str(odd.get("betTypeID") or "").lower() != "sp":
            continue
        side = str(odd.get("sideID") or "").lower()
        if side not in {"away", "home"}:
            continue
        stat_entity = str(odd.get("statEntityID") or "").lower()
        if stat_entity not in {"away", "home", "all"}:
            continue
        by_bookmaker = odd.get("byBookmaker") or {}
        if not isinstance(by_bookmaker, dict):
            continue

        for book_id, book_data in by_bookmaker.items():
            if not isinstance(book_data, dict) or book_data.get("available") is False:
                continue
            line = sgo._float(book_data.get("spread"))
            price = sgo._american(book_data.get("odds"))
            updated = book_data.get("lastUpdatedAt")
            if line is None and price is None:
                continue
            book_key = sgo._book_id(book_id)
            row = by_book.setdefault(book_key, {
                "game_id": game_id,
                "away_team": away_team,
                "home_team": home_team,
                "first_tip_et": tip,
                "book": sgo._BOOK_ALIASES.get(book_key, str(book_id)),
                "away_spread": np.nan,
                "home_spread": np.nan,
                "away_spread_price": np.nan,
                "home_spread_price": np.nan,
                "away_updated_at": None,
                "home_updated_at": None,
                "away_age_seconds": np.nan,
                "home_age_seconds": np.nan,
            })
            current_updated = row.get(f"{side}_updated_at")
            if current_updated and not _newer(updated, current_updated):
                continue
            row[f"{side}_spread"] = np.nan if line is None else float(line)
            row[f"{side}_spread_price"] = np.nan if price is None else int(price)
            row[f"{side}_updated_at"] = updated
            row[f"{side}_age_seconds"] = _age_seconds(updated)

    rows = []
    for row in by_book.values():
        side_ages = [row.get("away_age_seconds"), row.get("home_age_seconds")]
        if all(pd.notna(x) for x in side_ages):
            # Use the OLDER of the two sides (largest age), not the newest update
            # from an unrelated ML/total market.
            row["age_seconds"] = float(max(side_ages))
        else:
            row["age_seconds"] = np.nan
        row["freshness"] = _freshness(row["age_seconds"])
        rows.append(row)
    return rows


def spread_market_snapshot(day_str: str, pregame: pd.DataFrame):
    pregame_count = int(len(pregame) if isinstance(pregame, pd.DataFrame) else 0)
    empty_meta = {
        "state": "N/A", "provider_state": "N/A", "pregame_games": pregame_count,
        "covered_games": 0, "exact_pairs": 0, "ready_pairs": 0,
        "raw_rows": 0, "rejected_rows": 0, "missing_games": [],
        "provider_error": None, "bookmakers": sgo.get_bookmakers(),
        "events_received": 0, "matched_games": 0,
    }
    if pregame is None or pregame.empty:
        return pd.DataFrame(), pd.DataFrame(), empty_meta

    key = sgo.get_api_key()
    if not key:
        meta = dict(empty_meta)
        meta.update({"state": "CHECK", "provider_state": "NO_API_KEY"})
        return pd.DataFrame(), pd.DataFrame(), meta

    try:
        starts_after, starts_before = sgo._slate_window(day_str)
        books = sgo.get_bookmakers()
        events = sgo._fetch_events(key, starts_after, starts_before, books)
    except Exception as exc:
        meta = dict(empty_meta)
        meta.update({"state": "CHECK", "provider_state": "PROVIDER_ERROR", "provider_error": f"{type(exc).__name__}: {exc}"})
        return pd.DataFrame(), pd.DataFrame(), meta

    rows = []
    matched = 0
    unmatched_games = []
    for _, game in pregame.iterrows():
        event = _exact_event(events, game, day_str)
        if event is None:
            unmatched_games.append(f"{game.get('away_team','Away')} @ {game.get('home_team','Home')}")
            continue
        matched += 1
        rows.extend(_parse_spread_only(event, game))

    raw = pd.DataFrame(rows)
    provider_state = "CONNECTED" if matched else ("NO_OPEN_WNBA_MARKETS" if not events else "MATCH_FAILURE")
    pregame_ids = set(pregame.get("game_id", pd.Series(dtype=object)).astype(str).tolist())
    team_map = {
        str(r.get("game_id") or ""): f"{r.get('away_team','Away')} @ {r.get('home_team','Home')}"
        for _, r in pregame.iterrows()
    }

    if raw.empty:
        meta = dict(empty_meta)
        meta.update({
            "state": "CHECK", "provider_state": provider_state,
            "events_received": int(len(events)), "matched_games": int(matched),
            "missing_games": sorted(set(unmatched_games) | set(team_map.values())),
        })
        return pd.DataFrame(), pd.DataFrame(), meta

    for c in ("away_spread", "home_spread", "away_spread_price", "home_spread_price", "age_seconds"):
        raw[c] = pd.to_numeric(raw.get(c), errors="coerce")

    two_sided = (
        raw["away_spread"].notna() & raw["home_spread"].notna()
        & raw["away_spread_price"].notna() & raw["home_spread_price"].notna()
    )
    mirrored = (raw["away_spread"] + raw["home_spread"]).abs().le(MIRROR_TOLERANCE)
    plausible = raw["away_spread"].abs().le(MAX_ABS_SPREAD) & raw["home_spread"].abs().le(MAX_ABS_SPREAD)
    named_book = raw["book"].astype(str).str.strip().ne("")
    raw["exact_pair"] = two_sided & mirrored & plausible & named_book
    raw["ready_pair"] = raw["exact_pair"] & raw["freshness"].isin(["FRESH", "AGING"])

    def reason(r):
        if pd.isna(r.get("away_spread")) or pd.isna(r.get("home_spread")):
            return "missing one side of spread"
        if pd.isna(r.get("away_spread_price")) or pd.isna(r.get("home_spread_price")):
            return "missing one side price"
        if abs(_num(r.get("away_spread"), 999) + _num(r.get("home_spread"), 999)) > MIRROR_TOLERANCE:
            return "away/home spreads are not mirrored"
        if abs(_num(r.get("away_spread"), 999)) > MAX_ABS_SPREAD or abs(_num(r.get("home_spread"), 999)) > MAX_ABS_SPREAD:
            return "implausible spread value"
        if not str(r.get("book") or "").strip():
            return "bookmaker missing"
        if str(r.get("freshness")) == "STALE":
            return "stale spread pair"
        if str(r.get("freshness")) == "UNKNOWN":
            return "one/both spread timestamps unavailable"
        return ""

    raw["reject_reason"] = raw.apply(reason, axis=1)
    exact = raw.loc[raw["exact_pair"]].copy()
    ready = raw.loc[raw["ready_pair"]].copy()
    rejected = raw.loc[~raw["ready_pair"]].copy()

    covered_ids = set(ready.get("game_id", pd.Series(dtype=object)).astype(str).tolist())
    missing_ids = sorted(pregame_ids - covered_ids)
    missing_games = [team_map[g] for g in missing_ids if g in team_map]
    state = "READY" if pregame_ids and pregame_ids.issubset(covered_ids) else "CHECK"

    meta = {
        "state": state,
        "provider_state": provider_state,
        "pregame_games": int(len(pregame_ids)),
        "covered_games": int(len(covered_ids)),
        "exact_pairs": int(len(exact)),
        "ready_pairs": int(len(ready)),
        "raw_rows": int(len(raw)),
        "rejected_rows": int(len(rejected)),
        "missing_games": missing_games,
        "provider_error": None,
        "bookmakers": books,
        "events_received": int(len(events)),
        "matched_games": int(matched),
    }
    return ready.reset_index(drop=True), rejected.reset_index(drop=True), meta


__all__ = ["spread_market_snapshot"]
