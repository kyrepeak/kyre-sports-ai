"""MLB Pitcher Strikeouts O/U V1.0.2 odds compatibility bridge.

Keeps the V1.0 workload/K model and V1.0.1 compile fixes, while making the
Odds-API.io player-prop layer compatible with the app's existing odds helper.
"""
import requests

import mlb_pitcher_k_hub_v101 as base
from live_odds_feed import ODDS_BASE, fetch_multi_odds, get_api_key, get_bookmakers
from slate_odds_feed_v201 import fetch_mlb_events, _match_event, _window_for_games

MODEL_VERSION = "Pitcher K V1.0.2"


def _configured_odds_v102():
    return (get_api_key() or ""), get_bookmakers()


def _is_k_market(name):
    key = " ".join(str(name or "").lower().replace("_", " ").replace("/", " ").split())
    return "strikeout" in key


def _payload_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        rows = data.get("data")
        if isinstance(rows, list):
            return rows
        if data.get("id") is not None:
            return [data]
    return []


def _fetch_market_lines_v102(games_df, pitcher_rows):
    key, books = _configured_odds_v102()
    if not key or games_df is None or games_df.empty:
        return {}, {"connected": False, "events": 0, "props": 0}
    try:
        start_iso, end_iso = _window_for_games(games_df)
        events = fetch_mlb_events(key, start_iso, end_iso)
    except Exception as exc:
        return {}, {"connected": False, "events": 0, "props": 0, "error": str(exc)}

    match_by_pk = {}
    ids = []
    for _, row in games_df.iterrows():
        try:
            pk = int(row.get("game_pk"))
        except Exception:
            continue
        event = _match_event(events, row)
        if event and event.get("id") is not None:
            match_by_pk[pk] = event
            ids.append(event.get("id"))
    if not ids:
        return {}, {"connected": True, "events": 0, "props": 0, "books": books}

    # First use the efficient multi endpoint already proven elsewhere in the app.
    by_id = {}
    try:
        for payload in fetch_multi_odds(key, tuple(ids), books):
            if isinstance(payload, dict) and payload.get("id") is not None:
                by_id[str(payload.get("id"))] = payload
    except Exception:
        pass

    def build_out(payload_map):
        out = {}
        count = 0
        for pk, event in match_by_pk.items():
            payload = payload_map.get(str(event.get("id")))
            if not payload:
                continue
            names = [x.get("player_name") for x in pitcher_rows if int(x.get("game_pk", -1)) == pk]
            parsed = base._parse_props(payload, names)
            for name, quotes in parsed.items():
                board = base._market_board(quotes)
                if board:
                    out[(pk, base._norm_name(name))] = board
                    count += 1
        return out, count

    out, prop_count = build_out(by_id)

    # Player props are officially exposed by the single-event /odds endpoint.
    # If multi returned main markets only, rescue with one date-scope request/event.
    if prop_count == 0:
        rescue = {}
        for event_id in ids:
            try:
                response = requests.get(
                    f"{ODDS_BASE}/odds",
                    params={"apiKey": str(key), "eventId": str(event_id), "bookmakers": str(books)},
                    timeout=15,
                )
                if response.status_code >= 400:
                    continue
                for payload in _payload_list(response.json()):
                    if payload.get("id") is not None:
                        rescue[str(payload.get("id"))] = payload
            except Exception:
                continue
        if rescue:
            out, prop_count = build_out(rescue)

    return out, {
        "connected": True,
        "events": len(match_by_pk),
        "props": prop_count,
        "books": books,
    }


# Patch only the sportsbook-facing helpers; projection math stays V1.0.
base._configured_odds = _configured_odds_v102
base._prop_market_name = _is_k_market
base._fetch_market_lines = _fetch_market_lines_v102


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    return base.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
