"""MLB Daily Game Picks V2.1.0 — bounded sportsbook resume hotfix.

UI/orchestration hotfix only. Preserves V2.0.9 polished mobile UI, V2.0.8
one-tap controller, V2.0.7 market-neutral normalization, all seven production
models, simulation depths, Step 5/6 ranking rules, sportsbook verification gates,
and identity firewalls.

Fixes the Run Line/Total resume path so a sportsbook retry cannot appear frozen:
- provider event discovery uses an 8-second request timeout
- HTTP 429 is never followed by the old league-filter fallback request
- multi-event odds chunks use an 8-second request timeout
- existing V2.0.5 shared snapshot + cooldown logic remains authoritative
"""
from __future__ import annotations

import requests
import streamlit as st

import mlb_daily_game_picks_v209 as previous
import slate_odds_feed_v203 as odds203
import slate_odds_feed_v201 as odds201
import live_odds_feed as live_odds

VERSION = "MLB Daily Game Picks V2.1.0 • BOUNDED SPORTSBOOK RESUME"
SPORTSBOOK_TIMEOUT = 8


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_mlb_events_bounded(api_key, start_iso, end_iso):
    params = {
        "apiKey": str(api_key),
        "sport": "baseball",
        "league": "usa-mlb",
        "status": "pending,live",
        "from": str(start_iso),
        "to": str(end_iso),
    }
    response = requests.get(
        f"{live_odds.ODDS_BASE}/events",
        params=params,
        timeout=SPORTSBOOK_TIMEOUT,
    )

    # A 429 is a provider quota signal, not evidence that the league filter is
    # unsupported. Do not spend a second request when the account is throttled.
    if response.status_code == 429:
        response.raise_for_status()

    # Preserve the prior compatibility fallback for non-rate-limit HTTP errors.
    if response.status_code >= 400:
        params.pop("league", None)
        response = requests.get(
            f"{live_odds.ODDS_BASE}/events",
            params=params,
            timeout=SPORTSBOOK_TIMEOUT,
        )

    response.raise_for_status()
    return odds201._event_list(response.json())


@st.cache_data(ttl=55, show_spinner=False)
def _fetch_multi_odds_bounded(api_key, event_ids, bookmakers):
    ids = [str(x) for x in event_ids if x is not None]
    if not ids:
        return []

    all_rows = []
    for start in range(0, len(ids), 10):
        chunk = ids[start:start + 10]
        response = requests.get(
            f"{live_odds.ODDS_BASE}/odds/multi",
            params={
                "apiKey": str(api_key),
                "eventIds": ",".join(chunk),
                "bookmakers": str(bookmakers),
            },
            timeout=SPORTSBOOK_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            all_rows.extend(payload)
        elif isinstance(payload, dict):
            rows = payload.get("data")
            if isinstance(rows, list):
                all_rows.extend(rows)
            elif payload.get("id") is not None:
                all_rows.append(payload)
    return all_rows


def _install_bounded_sportsbook_io():
    # slate_odds_feed_v205 calls the V20.3 function, whose globals resolve these
    # two names at execution time. Patching here scopes the latency hotfix to the
    # Daily Game Picks route without changing sportsbook parsing/model math.
    odds203.fetch_mlb_events = _fetch_mlb_events_bounded
    odds203.fetch_multi_odds = _fetch_multi_odds_bounded


_install_bounded_sportsbook_io()


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    _install_bounded_sportsbook_io()
    st.caption(
        "⚡ V2.1.0 sportsbook-resume hotfix: bounded provider requests • no duplicate fallback call on HTTP 429 • Run Line/Total still share the same verified snapshot."
    )
    return previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
