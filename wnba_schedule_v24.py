"""WNBA PRA V2.4 schedule verification engine.

Step 1 only: make the selected WNBA slate trustworthy before any additional
player/model work. The engine probes multiple WNBA schedule paths, validates the
selected date and WNBA team IDs, and distinguishes a verified off-day from a
provider failure. It never silently converts a broken feed into "0 games".
"""
from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st

import wnba_data_v21 as transport
import wnba_data_v22 as guarded
import wnba_data_v232 as v232

ET = v232.ET
WNBA_CDN = v232.WNBA_CDN
ESPN_SCOREBOARD = v232.ESPN_SCOREBOARD

SCHEDULE_COLUMNS = [
    "game_id", "game_date", "first_tip_et", "status", "status_text",
    "away_team_id", "away_team", "away_tricode", "home_team_id",
    "home_team", "home_tricode", "venue", "source",
]


def _empty_schedule() -> pd.DataFrame:
    return pd.DataFrame(columns=SCHEDULE_COLUMNS)


def _safe_team_id(team: dict, direct=None) -> int:
    try:
        tid = int(direct or 0)
    except Exception:
        tid = 0
    if guarded._is_wnba_team_id(tid):
        return tid
    mapped = v232._team_id(team or {})
    return int(mapped or 0)


def _event_date_et(value) -> str:
    if not value:
        return ""
    try:
        ts = pd.to_datetime(value, utc=True)
        return ts.tz_convert(ET).strftime("%Y-%m-%d")
    except Exception:
        return transport.base._safe_date(value) or ""


def _request_json(provider: str, url: str, *, params=None, timeout=8, attempts=2):
    meta = {
        "provider": provider,
        "host": urlparse(url).netloc,
        "http": None,
        "content_type": "",
        "bytes": 0,
        "elapsed_ms": None,
        "json": False,
        "request_ok": False,
        "error": "",
    }
    last_error = None
    headers = {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    for n in range(max(1, int(attempts))):
        try:
            call_params = dict(params or {})
            if n and provider.startswith("WNBA"):
                call_params["_"] = pd.Timestamp.utcnow().strftime("%Y%m%d%H%M%S")
            response = requests.get(url, params=call_params or None, headers=headers, timeout=timeout)
            meta["http"] = int(response.status_code)
            meta["content_type"] = str(response.headers.get("content-type") or "")[:80]
            meta["bytes"] = len(response.content or b"")
            try:
                meta["elapsed_ms"] = int(response.elapsed.total_seconds() * 1000)
            except Exception:
                pass
            response.raise_for_status()
            text = (response.text or "").lstrip()
            if not text or not text.startswith(("{", "[")):
                raise ValueError("empty/non-JSON response")
            payload = response.json()
            meta["json"] = True
            meta["request_ok"] = True
            meta["error"] = ""
            return payload, meta
        except Exception as exc:
            last_error = exc
    meta["error"] = str(last_error or "request failed")[:240]
    return None, meta


def _parse_cdn(payload) -> tuple[pd.DataFrame, dict]:
    league = (payload or {}).get("leagueSchedule") or {}
    rows, raw_games, rejected = [], 0, 0
    for block in league.get("gameDates", []) or []:
        block_date = block.get("gameDate")
        for game in block.get("games", []) or []:
            raw_games += 1
            away, home = game.get("awayTeam") or {}, game.get("homeTeam") or {}
            away_team = {
                "abbreviation": away.get("teamTricode"),
                "displayName": transport.base._team_name(away),
                "name": transport.base._team_name(away),
            }
            home_team = {
                "abbreviation": home.get("teamTricode"),
                "displayName": transport.base._team_name(home),
                "name": transport.base._team_name(home),
            }
            away_id = _safe_team_id(away_team, away.get("teamId"))
            home_id = _safe_team_id(home_team, home.get("teamId"))
            if not guarded._is_wnba_team_id(away_id) or not guarded._is_wnba_team_id(home_id):
                rejected += 1
                continue
            raw_dt = game.get("gameDateTimeUTC") or game.get("gameDateTimeEst") or block_date
            rows.append({
                "game_id": str(game.get("gameId") or game.get("gameID") or ""),
                "game_date": transport.base._safe_date(raw_dt) or transport.base._safe_date(block_date),
                "first_tip_et": transport._tip_et(game),
                "status": transport.base._status_bucket(game.get("gameStatus"), game.get("gameStatusText")),
                "status_text": str(game.get("gameStatusText") or ""),
                "away_team_id": away_id,
                "away_team": transport.base._team_name(away),
                "away_tricode": str(away.get("teamTricode") or ""),
                "home_team_id": home_id,
                "home_team": transport.base._team_name(home),
                "home_tricode": str(home.get("teamTricode") or ""),
                "venue": str(game.get("arenaName") or game.get("arenaCity") or "Venue TBD"),
                "source": "WNBA official CDN",
            })
    frame = guarded._guard_schedule(pd.DataFrame(rows)) if rows else _empty_schedule()
    return frame, {"raw_games": raw_games, "valid_games": len(frame), "rejected_games": rejected}


def _parse_espn(payload, source: str) -> tuple[pd.DataFrame, dict]:
    rows, raw_games, rejected = [], 0, 0
    for event in (payload or {}).get("events", []) or []:
        raw_games += 1
        comps = event.get("competitions") or []
        if not comps:
            rejected += 1
            continue
        comp = comps[0]
        sides = {}
        for competitor in comp.get("competitors", []) or []:
            sides[str(competitor.get("homeAway") or "").lower()] = competitor
        away_c, home_c = sides.get("away") or {}, sides.get("home") or {}
        away_t, home_t = away_c.get("team") or {}, home_c.get("team") or {}
        away_id, home_id = _safe_team_id(away_t), _safe_team_id(home_t)
        if not guarded._is_wnba_team_id(away_id) or not guarded._is_wnba_team_id(home_id):
            rejected += 1
            continue
        status = (event.get("status") or {}).get("type") or {}
        raw_dt = event.get("date") or comp.get("date")
        game_date = _event_date_et(raw_dt)
        rows.append({
            "game_id": str(event.get("id") or ""),
            "game_date": game_date,
            "first_tip_et": v232._tip_et(raw_dt),
            "status": v232._status_bucket(status.get("state"), status.get("description") or status.get("detail")),
            "status_text": str(status.get("shortDetail") or status.get("detail") or status.get("description") or ""),
            "away_team_id": away_id,
            "away_team": str(away_t.get("displayName") or away_t.get("shortDisplayName") or "Away"),
            "away_tricode": str(away_t.get("abbreviation") or ""),
            "home_team_id": home_id,
            "home_team": str(home_t.get("displayName") or home_t.get("shortDisplayName") or "Home"),
            "home_tricode": str(home_t.get("abbreviation") or ""),
            "venue": str((comp.get("venue") or {}).get("fullName") or "Venue TBD"),
            "source": source,
        })
    frame = guarded._guard_schedule(pd.DataFrame(rows)) if rows else _empty_schedule()
    return frame, {"raw_games": raw_games, "valid_games": len(frame), "rejected_games": rejected}


def _selected(frame: pd.DataFrame, day_str: str) -> pd.DataFrame:
    if frame is None or frame.empty or "game_date" not in frame.columns:
        return _empty_schedule()
    out = frame.loc[frame["game_date"].astype(str).eq(day_str)].copy()
    if out.empty:
        return _empty_schedule()
    out = out.drop_duplicates(subset=["game_id", "away_team_id", "home_team_id"], keep="first")
    return out.reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def _verified_schedule(day_str: str):
    day_str = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    year = pd.to_datetime(day_str).year
    attempts = []
    selected_candidates = []
    season_sources_ok = 0

    # 1) Official WNBA full-season CDN.
    payload, meta = _request_json("WNBA official CDN", WNBA_CDN, timeout=8, attempts=2)
    if payload is not None:
        frame, counts = _parse_cdn(payload)
        meta.update(counts)
        meta["selected_games"] = len(_selected(frame, day_str))
        meta["parse_ok"] = True
        if len(frame):
            season_sources_ok += 1
        if meta["selected_games"]:
            selected_candidates.append((0, _selected(frame, day_str), "WNBA official CDN"))
    else:
        meta.update({"raw_games": 0, "valid_games": 0, "rejected_games": 0, "selected_games": 0, "parse_ok": False})
    attempts.append(meta)

    # 2) ESPN WNBA selected-date scoreboard.
    payload, meta = _request_json(
        "ESPN WNBA daily",
        ESPN_SCOREBOARD,
        params={"dates": pd.to_datetime(day_str).strftime("%Y%m%d"), "limit": 100},
        timeout=8,
        attempts=2,
    )
    if payload is not None:
        frame, counts = _parse_espn(payload, "ESPN WNBA daily fallback")
        meta.update(counts)
        selected = _selected(frame, day_str)
        meta["selected_games"] = len(selected)
        meta["parse_ok"] = True
        if len(selected):
            selected_candidates.append((1, selected, "ESPN WNBA daily"))
    else:
        meta.update({"raw_games": 0, "valid_games": 0, "rejected_games": 0, "selected_games": 0, "parse_ok": False})
    attempts.append(meta)

    # 3) ESPN WNBA season scoreboard. wehoop uses dates=<season> with limit=1000;
    # this gives us an independent whole-season check and lets us tell a real
    # off-day from a daily endpoint/provider failure.
    payload, meta = _request_json(
        "ESPN WNBA season",
        ESPN_SCOREBOARD,
        params={"dates": str(year), "limit": 1000},
        timeout=10,
        attempts=2,
    )
    if payload is not None:
        frame, counts = _parse_espn(payload, "ESPN WNBA season fallback")
        meta.update(counts)
        selected = _selected(frame, day_str)
        meta["selected_games"] = len(selected)
        meta["parse_ok"] = True
        if len(frame):
            season_sources_ok += 1
        if len(selected):
            selected_candidates.append((2, selected, "ESPN WNBA season"))
    else:
        meta.update({"raw_games": 0, "valid_games": 0, "rejected_games": 0, "selected_games": 0, "parse_ok": False})
    attempts.append(meta)

    if selected_candidates:
        selected_candidates.sort(key=lambda x: x[0])
        _, schedule, chosen = selected_candidates[0]
        confirming = [m["provider"] for m in attempts if int(m.get("selected_games") or 0) > 0]
        state = "VERIFIED"
    elif season_sources_ok:
        schedule, chosen, confirming = _empty_schedule(), "season schedule verification", []
        state = "VERIFIED_OFF_DAY"
    else:
        schedule, chosen, confirming = _empty_schedule(), "none", []
        state = "PROVIDER_FAILURE"

    valid_team_ids = set()
    if not schedule.empty:
        valid_team_ids.update(schedule["away_team_id"].astype(int).tolist())
        valid_team_ids.update(schedule["home_team_id"].astype(int).tolist())

    diagnostics = {
        "selected_date": day_str,
        "state": state,
        "games": len(schedule),
        "teams": len(valid_team_ids),
        "chosen_source": chosen,
        "confirming_sources": confirming,
        "season_sources_ok": season_sources_ok,
        "attempts": attempts,
    }
    return schedule, diagnostics


def schedule_for_date(day: str | date) -> pd.DataFrame:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    schedule, _ = _verified_schedule(day_str)
    return guarded._guard_schedule(schedule)


def schedule_diagnostics(day: str | date) -> dict:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    _, diagnostics = _verified_schedule(day_str)
    return diagnostics


def clear_schedule_cache():
    try:
        _verified_schedule.clear()
    except Exception:
        st.cache_data.clear()


def data_health(schedule, stats):
    health = v232.data_health(schedule, stats)
    if schedule is not None and not schedule.empty:
        health["WNBA schedule"] = "CONNECTED"
    return health


# Step 1 intentionally leaves player/stat/model transport unchanged.
current_season = v232.current_season
empirical_profile = v232.empirical_profile
game_for_team = v232.game_for_team
logo_url = v232.logo_url
official_roster = v232.official_roster
player_form_table = v232.player_form_table
player_game_log = v232.player_game_log
slate_player_pool = v232.slate_player_pool
team_player_pool = v232.team_player_pool
