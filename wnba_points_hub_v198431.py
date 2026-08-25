"""WNBA Points V1.9.8.4.31 — restore exact Points market handoff.

Points-only transport repair over V1.9.8.4.30.

Root cause fixed here:
The isolated Points engine still used the original WNBA SportsGameOdds fetcher,
which sends the configured bookmakerID list in the provider request. Other WNBA
modules already discovered that subscription-limited SportsGameOdds accounts can
reject the whole request when even one requested bookmaker is outside the plan.
That leaves the Points exact-market frame empty, which in turn makes the Top-5
Player-vs-Team History cards empty and keeps the real 5M button disabled.

This wrapper changes ONLY the Points engine's private sportsbook transport:
- use the current ET-reconciled WNBA schedule V2.5;
- request the exact full-game player Points O/U markets without forcing a
  bookmakerID at the provider boundary;
- locally retain only the same configured target sportsbooks;
- keep exact same-player + same-book + same-line O/U pairing downstream;
- fail closed if no real exact pair exists.

No line is invented and no readiness gate is bypassed. Projection, minutes,
matchup factors, Monte Carlo, calibration, ranking, qualification, H2H evidence,
Steps 2-12, PRA, Rebounds, Assists, Spread, MLB and NFL logic are untouched.
"""
from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

import wnba_points_hub_v198430 as prior
import wnba_schedule_v25 as schedule25
import wnba_sportsgameodds_v1 as sgo1

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.31 • EXACT MARKET HANDOFF REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

POINTS_ODD_IDS = (
    "points-PLAYER_ID-game-ou-over,"
    "points-PLAYER_ID-game-ou-under"
)


def _day(value) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _configured_book_ids() -> list[str]:
    out = []
    for raw in str(sgo1.get_bookmakers() or "").split(","):
        key = sgo1._book_id(raw)
        if key and key not in out:
            out.append(key)
    return out


def _allowed_book_labels() -> set[str]:
    labels = set()
    for book_id in _configured_book_ids():
        labels.add(str(sgo1._BOOK_ALIASES.get(book_id, book_id)).strip().lower())
    return labels


@st.cache_data(ttl=120, show_spinner=False, max_entries=16)
def _fetch_points_events_tier_safe(api_key: str, starts_after: str, starts_before: str):
    """Fetch exact WNBA Points props without forcing plan-restricted books."""
    headers = {"x-api-key": str(api_key)}
    base_params = {
        "leagueID": "WNBA",
        "oddsAvailable": "true",
        "startsAfter": str(starts_after),
        "startsBefore": str(starts_before),
        "includeAltLines": "false",
        "limit": 100,
        # bookmakerID is intentionally omitted. Returned books are filtered
        # locally to the exact same configured target list.
    }

    attempts = (
        {**base_params, "oddID": POINTS_ODD_IDS},
        {**base_params, "oddIDs": POINTS_ODD_IDS},
        base_params,
    )
    last = None
    for idx, params in enumerate(attempts):
        response = requests.get(
            f"{sgo1.SGO_BASE}/events",
            params=params,
            headers=headers,
            timeout=20,
        )
        last = response
        if response.status_code == 200:
            payload = response.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list):
                return data
            return []
        # Retry only request-shape / access / gateway failures. Other provider
        # errors remain fail-closed and are surfaced by raise_for_status below.
        if response.status_code not in {400, 403, 504}:
            break
        if idx == len(attempts) - 1:
            break

    if last is not None:
        last.raise_for_status()
    return []


def _local_book_filter(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame() if frame is None else frame
    allowed = _allowed_book_labels()
    if not allowed or "book" not in frame.columns:
        return frame
    mask = frame["book"].astype(str).str.strip().str.lower().isin(allowed)
    return frame.loc[mask].copy()


def _market_snapshot_points_only(day):
    key = sgo1.get_api_key()
    if not key:
        return sgo1._empty_result(day, "NO_API_KEY")

    try:
        schedule = schedule25.schedule_for_date(day)
    except Exception as exc:
        return sgo1._empty_result(day, "SCHEDULE_ERROR", f"{type(exc).__name__}: {exc}")

    if schedule is None or schedule.empty:
        out = sgo1._empty_result(day, "NO_WNBA_GAMES")
        out["schedule_games"] = 0
        return out

    starts_after, starts_before = sgo1._slate_window(day)
    try:
        events = _fetch_points_events_tier_safe(key, starts_after, starts_before)
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        code = getattr(response, "status_code", None)
        out = sgo1._empty_result(
            day,
            "PROVIDER_ERROR",
            f"HTTP {code}" if code else type(exc).__name__,
        )
        out["schedule_games"] = int(len(schedule))
        return out
    except Exception as exc:
        out = sgo1._empty_result(day, "PROVIDER_ERROR", f"{type(exc).__name__}: {exc}")
        out["schedule_games"] = int(len(schedule))
        return out

    game_rows = []
    prop_rows = []
    unmatched = []
    matched = 0

    for _, row in schedule.iterrows():
        event = sgo1._match_event(events, row)
        if event is None:
            unmatched.append(f"{row.get('away_team','Away')} @ {row.get('home_team','Home')}")
            continue
        matched += 1
        game_id = row.get("game_id")
        game_rows.extend(sgo1._parse_game_lines(event, game_id))
        prop_rows.extend(sgo1._parse_props(event, game_id))

    game_df = _local_book_filter(pd.DataFrame(game_rows))
    prop_df = _local_book_filter(pd.DataFrame(prop_rows))
    if not prop_df.empty and "market" in prop_df.columns:
        prop_df = prop_df.loc[
            prop_df["market"].astype(str).str.upper().eq("POINTS")
        ].copy()

    if matched and not prop_df.empty:
        state = "CONNECTED"
    elif matched:
        state = "NO_OPEN_POINTS_MARKETS"
    elif not events:
        state = "NO_OPEN_WNBA_MARKETS"
    else:
        state = "MATCH_FAILURE"

    return {
        "selected_date": _day(day),
        "provider": "SportsGameOdds",
        "league": "WNBA",
        "state": state,
        "events_received": int(len(events)),
        "schedule_games": int(len(schedule)),
        "matched_games": int(matched),
        "unmatched_games": unmatched,
        "game_lines": game_df,
        "player_props": prop_df,
        "error": None,
        "bookmakers": sgo1.get_bookmakers(),
        "schedule_version": "V2.5 ET-reconciled",
        "request_mode": "POINTS ONLY • subscription-safe • provider bookmaker filter omitted",
    }


class _PointsSGOFacade:
    market_snapshot = staticmethod(_market_snapshot_points_only)
    _norm = staticmethod(sgo1._norm)


_POINTS_SGO = _PointsSGOFacade()


def _install() -> None:
    # The protected _paired_points_markets function is defined in the original
    # Points V1.0 module and resolves its module-global `sgo` at call time.
    # Current Points V1.9 exposes that exact module as points.base. Replacing this
    # one Points-private dependency repairs the handoff without changing shared
    # WNBA/PRA transports.
    points.base.sgo = _POINTS_SGO
    points.sgo = _POINTS_SGO


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🔌 Points V1.9.8.4.31 • exact Points market handoff repaired • "
        "subscription-safe SportsGameOdds request • same configured books filtered locally • "
        "exact O/U pairing and every 5M gate remain fail-closed"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
