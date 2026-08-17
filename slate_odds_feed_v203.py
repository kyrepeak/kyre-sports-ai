"""V20.3 pregame/live sportsbook snapshots for the MLB Slate.

Fixes baseball total-market parsing (providers may label the same market as
Totals or Over/Under), keeps raw line/price fields, computes best listed prices
across the selected books, and tracks movement between slate refreshes without
spending extra API calls.
"""

from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from live_odds_feed import (
    decimal_to_american,
    fetch_multi_odds,
    _age_seconds,
    _iso_dt,
)
from slate_odds_feed_v201 import fetch_mlb_events, _window_for_games, _match_event


def _american(value):
    return decimal_to_american(value)


def _float(value):
    try:
        return float(value)
    except Exception:
        return None


def _market_key(name):
    return " ".join(str(name or "").strip().lower().replace("/", " ").replace("_", " ").split())


def _first_usable_odds(market):
    rows = (market or {}).get("odds") or []
    return next((x for x in rows if isinstance(x, dict)), {})


def _fmt_american(value):
    try:
        return f"{int(value):+d}"
    except Exception:
        return "—"


def parse_event_odds_v203(payload):
    """Parse ML, run line and totals while accepting provider naming variants."""
    rows = []
    bookmakers = payload.get("bookmakers") or {}
    if not isinstance(bookmakers, dict):
        return {"rows": [], "home_spread": None, "total_line": None}

    for book, markets in bookmakers.items():
        item = {
            "Book": str(book),
            "Away ML": None,
            "Home ML": None,
            "Away RL": None,
            "Home RL": None,
            "Over": None,
            "Under": None,
            "away_rl_line": None,
            "home_rl_line": None,
            "away_rl_price": None,
            "home_rl_price": None,
            "total_line": None,
            "over_price": None,
            "under_price": None,
            "updatedAt": None,
        }
        newest = None

        for market in markets or []:
            key = _market_key((market or {}).get("name"))
            odds0 = _first_usable_odds(market)
            updated = (market or {}).get("updatedAt")
            if updated:
                dt = _iso_dt(updated)
                if dt and (newest is None or dt > newest):
                    newest = dt
                    item["updatedAt"] = updated

            if key in {"ml", "moneyline", "money line", "match winner"}:
                item["Away ML"] = _american(odds0.get("away"))
                item["Home ML"] = _american(odds0.get("home"))

            elif key in {"spread", "spreads", "run line", "runline", "asian handicap"}:
                home_line = _float(odds0.get("hdp"))
                if home_line is None:
                    home_line = _float(odds0.get("line"))
                if home_line is not None:
                    away_line = -home_line
                    away_price = _american(odds0.get("away"))
                    home_price = _american(odds0.get("home"))
                    item["away_rl_line"] = away_line
                    item["home_rl_line"] = home_line
                    item["away_rl_price"] = away_price
                    item["home_rl_price"] = home_price
                    item["Away RL"] = f"{away_line:+g} ({_fmt_american(away_price)})"
                    item["Home RL"] = f"{home_line:+g} ({_fmt_american(home_price)})"

            elif key in {"totals", "total", "over under", "o u", "game total"}:
                # Odds-API.io documents Over/Under with the line in `max`.
                # Some feeds/markets expose the same line as hdp/line/total.
                total_line = None
                for field in ("max", "hdp", "line", "total"):
                    total_line = _float(odds0.get(field))
                    if total_line is not None:
                        break
                if total_line is not None:
                    over_price = _american(odds0.get("over"))
                    under_price = _american(odds0.get("under"))
                    item["total_line"] = total_line
                    item["over_price"] = over_price
                    item["under_price"] = under_price
                    item["Over"] = f"O {total_line:g} ({_fmt_american(over_price)})"
                    item["Under"] = f"U {total_line:g} ({_fmt_american(under_price)})"

        item["age_seconds"] = _age_seconds(item.get("updatedAt"))
        rows.append(item)

    home_spreads = [r["home_rl_line"] for r in rows if r.get("home_rl_line") is not None]
    totals = [r["total_line"] for r in rows if r.get("total_line") is not None]
    return {
        "rows": rows,
        "home_spread": float(np.median(home_spreads)) if home_spreads else None,
        "total_line": float(np.median(totals)) if totals else None,
        "away": payload.get("away"),
        "home": payload.get("home"),
        "event_id": payload.get("id"),
    }


def _best_price(rows, field):
    candidates = [(r.get(field), r.get("Book")) for r in rows if r.get(field) is not None]
    if not candidates:
        return None
    value, book = max(candidates, key=lambda x: float(x[0]))
    return {"price": int(value), "book": str(book)}


def _consensus_line(rows, field):
    vals = [float(r[field]) for r in rows if r.get(field) is not None]
    if not vals:
        return None
    counts = Counter(round(v, 4) for v in vals)
    top_count = max(counts.values())
    modes = sorted([v for v, c in counts.items() if c == top_count])
    return float(np.median(modes))


def _best_at_line(rows, line_field, price_field, target_line):
    if target_line is None:
        return None
    candidates = []
    for r in rows:
        line = r.get(line_field)
        price = r.get(price_field)
        if line is None or price is None:
            continue
        if abs(float(line) - float(target_line)) <= 1e-6:
            candidates.append((int(price), str(r.get("Book"))))
    if not candidates:
        return None
    price, book = max(candidates, key=lambda x: x[0])
    return {"line": float(target_line), "price": int(price), "book": book}


def _best_board(rows):
    home_rl = _consensus_line(rows, "home_rl_line")
    total = _consensus_line(rows, "total_line")
    away_rl = -home_rl if home_rl is not None else None
    return {
        "away_ml": _best_price(rows, "Away ML"),
        "home_ml": _best_price(rows, "Home ML"),
        "away_rl": _best_at_line(rows, "away_rl_line", "away_rl_price", away_rl),
        "home_rl": _best_at_line(rows, "home_rl_line", "home_rl_price", home_rl),
        "over": _best_at_line(rows, "total_line", "over_price", total),
        "under": _best_at_line(rows, "total_line", "under_price", total),
        "consensus_home_rl": home_rl,
        "consensus_total": total,
    }


def _movement(current, previous):
    if not previous:
        return {}
    out = {}
    for key in ("away_ml", "home_ml"):
        c, p = current.get(key), previous.get(key)
        if c and p:
            out[key] = {"price_delta": int(c["price"]) - int(p["price"])}
    for key in ("away_rl", "home_rl", "over", "under"):
        c, p = current.get(key), previous.get(key)
        if c and p:
            out[key] = {
                "line_delta": round(float(c["line"]) - float(p["line"]), 2),
                "price_delta": int(c["price"]) - int(p["price"]),
            }
    return out


def _attach_best_and_movement(snapshot):
    rows = snapshot.get("rows") or []
    best = _best_board(rows)
    event_id = snapshot.get("event_id") or (snapshot.get("event") or {}).get("id")
    state_key = f"v203_odds_prev_{event_id}"
    previous = st.session_state.get(state_key)
    snapshot["best"] = best
    snapshot["movement"] = _movement(best, previous)
    snapshot["movement_label"] = "since last odds refresh" if previous else "movement starts after next refresh"
    st.session_state[state_key] = best
    return snapshot


def slate_snapshots_for_games_v203(games_df, api_key, bookmakers):
    """Return corrected, enriched pregame/live snapshots keyed by MLB gamePk."""
    if not api_key or games_df is None or getattr(games_df, "empty", True):
        return {}

    start_iso, end_iso = _window_for_games(games_df)
    events = fetch_mlb_events(api_key, start_iso, end_iso)

    matches = {}
    event_ids = []
    for _, row in games_df.iterrows():
        try:
            pk = int(row.get("game_pk"))
        except Exception:
            continue
        event = _match_event(events, row)
        if not event or event.get("id") is None:
            continue
        matches[pk] = event
        event_ids.append(event.get("id"))

    if not event_ids:
        return {}

    payloads = fetch_multi_odds(api_key, tuple(event_ids), bookmakers)
    by_id = {
        str(x.get("id")): x
        for x in payloads
        if isinstance(x, dict) and x.get("id") is not None
    }

    out = {}
    for pk, event in matches.items():
        payload = by_id.get(str(event.get("id")))
        if not payload:
            continue
        parsed = parse_event_odds_v203(payload)
        parsed["event"] = event
        parsed["event_status"] = event.get("status")
        parsed["event_date"] = event.get("date")
        out[pk] = _attach_best_and_movement(parsed)
    return out
