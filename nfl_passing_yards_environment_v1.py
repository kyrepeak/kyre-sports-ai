"""NFL Passing Yards Step 6 — game environment context.

Descriptive evidence only. Uses the verified ESPN event ID and exact ESPN team
IDs already established by Steps 1–5, then adds transparent pace/play-volume,
pass-rate, venue/weather, rest/turnaround, site/travel and neutral-site context.

No sportsbook line, projection adjustment, probability, fair line, EV, Monte
Carlo result, ranking or recommendation is created here. Missing source fields
fail closed instead of being guessed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import math
import re
from typing import Any

import pandas as pd

import nfl_passing_yards_defense_v1 as defense

MODEL_VERSION = "NFL PASSING YARDS STEP 6 • GAME ENVIRONMENT V1"


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _first_number(value: Any):
    if isinstance(value, (int, float)):
        return _num(value)
    match = re.search(r"-?\d+(?:\.\d+)?", _safe(value))
    return _num(match.group(0)) if match else math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _safe(value).lower())


def _row_value(row: dict):
    for field in ("value", "displayValue", "perGameValue"):
        value = _num((row or {}).get(field))
        if _finite(value):
            return value
    return math.nan


def _row_per_game(row: dict, games: Any):
    per_game = _num((row or {}).get("perGameValue"))
    if _finite(per_game):
        return per_game
    total = _row_value(row)
    game_count = _num(games)
    if _finite(total) and _finite(game_count) and game_count > 0:
        return total / game_count
    return math.nan


def parse_team_pace(payload: dict) -> dict:
    """Parse explicit ESPN season play-volume and pass-attempt evidence."""
    stats = defense._flatten_stats(payload)
    games_row = defense._pick_row(stats, ("gamesPlayed", "games", "GP"))
    plays_row = defense._pick_row(stats, (
        "totalOffensivePlays", "offensivePlays", "plays", "totalPlays", "playsFromScrimmage",
    ))
    pass_row = defense._pick_row(stats, (
        "passingAttempts", "passAttempts", "teamPassingAttempts", "attempts", "ATT",
    ))
    rush_row = defense._pick_row(stats, (
        "rushingAttempts", "rushAttempts", "teamRushingAttempts", "carries",
    ))

    games = _row_value(games_row)
    plays = _row_value(plays_row)
    pass_attempts = _row_value(pass_row)
    rush_attempts = _row_value(rush_row)
    plays_pg = _row_per_game(plays_row, games)
    pass_attempts_pg = _row_per_game(pass_row, games)
    rush_attempts_pg = _row_per_game(rush_row, games)
    pass_rate = 100.0 * pass_attempts / plays if _finite(pass_attempts) and _finite(plays) and plays > 0 else math.nan

    if not _finite(plays) and _finite(pass_attempts) and _finite(rush_attempts):
        # Do not silently invent official play totals from components. Keep the
        # official play field unavailable, but expose the sourced components.
        plays_pg = math.nan

    return {
        "ready": bool(_finite(plays_pg) or _finite(pass_attempts_pg)),
        "games": games,
        "offensive_plays": plays,
        "offensive_plays_per_game": plays_pg,
        "pass_attempts": pass_attempts,
        "pass_attempts_per_game": pass_attempts_pg,
        "rush_attempts": rush_attempts,
        "rush_attempts_per_game": rush_attempts_pg,
        "pass_rate": pass_rate,
        "plays_state": "VERIFIED ESPN TEAM STAT" if _finite(plays_pg) else "UNAVAILABLE — explicit ESPN offensive plays not returned",
    }


def _competition(summary: dict) -> dict:
    header = (summary or {}).get("header") or {}
    competitions = header.get("competitions") or []
    return competitions[0] if competitions and isinstance(competitions[0], dict) else {}


def parse_game_environment(summary: dict, fallback_venue: str = "", fallback_location: str = "") -> dict:
    """Parse only fields ESPN actually exposes for the selected event."""
    game_info = (summary or {}).get("gameInfo") or {}
    competition = _competition(summary)
    venue = game_info.get("venue") or competition.get("venue") or {}
    weather = game_info.get("weather") or {}
    address = venue.get("address") or {}

    indoor_raw = venue.get("indoor")
    indoor = indoor_raw if isinstance(indoor_raw, bool) else None
    grass_raw = venue.get("grass")
    grass = grass_raw if isinstance(grass_raw, bool) else None

    location = ", ".join(
        x for x in (_safe(address.get("city")), _safe(address.get("state"))) if x
    ) or _safe(fallback_location)

    condition = _safe(
        weather.get("displayValue")
        or weather.get("weatherType")
        or weather.get("condition")
        or weather.get("description")
    )
    temperature = _first_number(weather.get("temperature"))
    if not _finite(temperature):
        temperature = _first_number(weather.get("highTemperature"))
    wind = _first_number(weather.get("windSpeed"))
    gust = _first_number(weather.get("windGust"))
    precipitation = _first_number(weather.get("precipitation"))

    roof = _safe(venue.get("roofType") or venue.get("roof"))
    if indoor is True:
        venue_type = "INDOOR"
    elif indoor is False:
        venue_type = "OUTDOOR"
    elif roof:
        venue_type = roof.upper()
    else:
        venue_type = "CHECK"

    surface = "GRASS" if grass is True else "TURF" if grass is False else "—"
    neutral_raw = competition.get("neutralSite")
    neutral_site = neutral_raw if isinstance(neutral_raw, bool) else None

    return {
        "venue": _safe(venue.get("fullName"), _safe(fallback_venue, "Venue unavailable")),
        "location": location,
        "venue_type": venue_type,
        "indoor": indoor,
        "roof": roof,
        "surface": surface,
        "neutral_site": neutral_site,
        "weather_condition": condition,
        "temperature_f": temperature,
        "wind_mph": wind,
        "wind_gust_mph": gust,
        "precipitation_pct": precipitation,
        "weather_available": bool(condition or _finite(temperature) or _finite(wind) or _finite(precipitation)),
    }


def weather_label(env: dict) -> tuple[str, str]:
    if env.get("indoor") is True:
        return "CONTROLLED", "verified indoor venue"
    wind = _num(env.get("wind_mph"))
    gust = _num(env.get("wind_gust_mph"))
    precip = _num(env.get("precipitation_pct"))
    temp = _num(env.get("temperature_f"))
    condition = _safe(env.get("weather_condition")).lower()

    severe_word = any(token in condition for token in ("snow", "thunder", "storm", "heavy rain", "sleet", "freezing"))
    if severe_word or (_finite(wind) and wind >= 20.0) or (_finite(gust) and gust >= 30.0) or (_finite(precip) and precip >= 60.0) or (_finite(temp) and (temp <= 30.0 or temp >= 95.0)):
        return "WATCH", "verified outdoor weather contains a notable condition"
    if env.get("weather_available"):
        return "NORMAL", "verified outdoor weather available; no Step 6 watch threshold triggered"
    return "CHECK", "pregame weather unavailable from the verified ESPN event summary"


def _schedule_events(payload: dict) -> list[dict]:
    rows = []
    for event in (payload or {}).get("events") or []:
        if not isinstance(event, dict):
            continue
        event_id = _safe(event.get("id"))
        event_date = pd.to_datetime(event.get("date"), errors="coerce", utc=True)
        comps = event.get("competitions") or []
        comp = comps[0] if comps and isinstance(comps[0], dict) else {}
        status_type = (comp.get("status") or {}).get("type") or {}
        completed = bool(status_type.get("completed")) or _safe(status_type.get("state")).lower() == "post"
        if event_id.isdigit() and pd.notna(event_date):
            rows.append({"event_id": event_id, "date": event_date, "completed": completed})
    return rows


def rest_context(schedule_payload: dict, cutoff_date: str) -> dict:
    """Return calendar-day turnaround from the most recent completed game."""
    cutoff = pd.to_datetime(cutoff_date, errors="coerce", utc=True)
    if pd.isna(cutoff):
        return {"ready": False, "turnaround_days": math.nan, "previous_game_date": ""}
    previous = [row for row in _schedule_events(schedule_payload) if row["completed"] and row["date"].normalize() < cutoff.normalize()]
    previous.sort(key=lambda row: row["date"], reverse=True)
    if not previous:
        return {"ready": False, "turnaround_days": math.nan, "previous_game_date": ""}
    prev = previous[0]
    turnaround = int((cutoff.normalize() - prev["date"].normalize()).days)
    return {
        "ready": True,
        "turnaround_days": turnaround,
        "previous_game_date": prev["date"].strftime("%Y-%m-%d"),
        "rest_label": "SHORT" if turnaround <= 5 else "STANDARD" if turnaround <= 8 else "EXTENDED",
    }


def pass_tendency_label(pace: dict) -> tuple[str, str]:
    rate = _num(pace.get("pass_rate"))
    if not _finite(rate):
        return "CHECK", "verified pass rate unavailable"
    if rate >= 60.0:
        return "PASS-LEAN", f"season pass attempts / offensive plays = {rate:.1f}%"
    if rate <= 52.0:
        return "RUN-LEAN", f"season pass attempts / offensive plays = {rate:.1f}%"
    return "BALANCED", f"season pass attempts / offensive plays = {rate:.1f}%"


def pace_label(away: dict, home: dict) -> tuple[str, str]:
    away_pg = _num(away.get("offensive_plays_per_game"))
    home_pg = _num(home.get("offensive_plays_per_game"))
    if not (_finite(away_pg) and _finite(home_pg)):
        return "CHECK", "explicit season offensive-play volume incomplete"
    combined = away_pg + home_pg
    if combined >= 132.0:
        return "HIGH VOLUME", f"combined season offensive-play rates {combined:.1f} plays/game"
    if combined <= 120.0:
        return "LOW VOLUME", f"combined season offensive-play rates {combined:.1f} plays/game"
    return "BALANCED", f"combined season offensive-play rates {combined:.1f} plays/game"


def environment_label(event_env: dict, away_rest: dict, home_rest: dict) -> tuple[str, str]:
    weather, weather_basis = weather_label(event_env)
    turnarounds = [_num(away_rest.get("turnaround_days")), _num(home_rest.get("turnaround_days"))]
    short = any(_finite(x) and x <= 5 for x in turnarounds)
    if weather == "WATCH" and short:
        return "WATCH", "weather watch plus short-turnaround context"
    if weather == "WATCH":
        return "WATCH", weather_basis
    if short:
        return "WATCH", "one or both teams are on a verified five-day-or-shorter turnaround"
    if event_env.get("indoor") is True:
        return "CONTROLLED", "indoor venue with no verified short-turnaround flag"
    if weather in {"NORMAL", "CHECK"}:
        return "NEUTRAL" if weather == "NORMAL" else "CHECK", weather_basis
    return "CHECK", "environment evidence incomplete"


def build_game_environment(game: dict, away_ctx: dict, home_ctx: dict, year: int, season_type: int, cutoff_date: str) -> dict:
    game_id = _safe(game.get("game_id"))
    away_id = _safe(away_ctx.get("team_id"))
    home_id = _safe(home_ctx.get("team_id"))
    if not game_id.isdigit():
        return {"ready": False, "reason": "official ESPN event ID is required", "projection_adjustment": 0.0}
    if not away_id.isdigit() or not home_id.isdigit():
        return {"ready": False, "reason": "verified ESPN away and home team IDs are required", "projection_adjustment": 0.0}

    with ThreadPoolExecutor(max_workers=5) as pool:
        summary_f = pool.submit(defense._summary_payload, game_id)
        away_stats_f = pool.submit(defense._team_stats_payload, year, season_type, away_id)
        home_stats_f = pool.submit(defense._team_stats_payload, year, season_type, home_id)
        away_schedule_f = pool.submit(defense._team_schedule_payload, year, season_type, away_id)
        home_schedule_f = pool.submit(defense._team_schedule_payload, year, season_type, home_id)
        summary, summary_diag = summary_f.result()
        away_stats, away_stats_diag = away_stats_f.result()
        home_stats, home_stats_diag = home_stats_f.result()
        away_schedule, away_schedule_diag = away_schedule_f.result()
        home_schedule, home_schedule_diag = home_schedule_f.result()

    event_env = parse_game_environment(summary, _safe(game.get("venue")), _safe(game.get("location"))) if summary_diag.get("ok") else parse_game_environment({}, _safe(game.get("venue")), _safe(game.get("location")))
    away_pace = parse_team_pace(away_stats) if away_stats_diag.get("ok") else {"ready": False}
    home_pace = parse_team_pace(home_stats) if home_stats_diag.get("ok") else {"ready": False}
    away_rest = rest_context(away_schedule, cutoff_date) if away_schedule_diag.get("ok") else {"ready": False}
    home_rest = rest_context(home_schedule, cutoff_date) if home_schedule_diag.get("ok") else {"ready": False}

    away_tendency, away_tendency_basis = pass_tendency_label(away_pace)
    home_tendency, home_tendency_basis = pass_tendency_label(home_pace)
    pace, pace_basis = pace_label(away_pace, home_pace)
    env_label, env_basis = environment_label(event_env, away_rest, home_rest)
    weather, weather_basis = weather_label(event_env)

    neutral = event_env.get("neutral_site")
    away_site = "NEUTRAL SITE" if neutral is True else "AWAY / TRAVEL"
    home_site = "NEUTRAL SITE" if neutral is True else "HOME"

    ready = bool(summary_diag.get("ok") and (away_pace.get("ready") or home_pace.get("ready")))
    return {
        "ready": ready,
        "reason": "" if ready else "verified event summary or team pace evidence is incomplete",
        "game_id": game_id,
        "away_team_id": away_id,
        "home_team_id": home_id,
        "away_team_name": _safe(away_ctx.get("team"), away_ctx.get("abbr")),
        "home_team_name": _safe(home_ctx.get("team"), home_ctx.get("abbr")),
        "event": event_env,
        "away_pace": away_pace,
        "home_pace": home_pace,
        "away_rest": away_rest,
        "home_rest": home_rest,
        "away_site": away_site,
        "home_site": home_site,
        "away_pass_tendency": away_tendency,
        "away_pass_tendency_basis": away_tendency_basis,
        "home_pass_tendency": home_tendency,
        "home_pass_tendency_basis": home_tendency_basis,
        "pace_label": pace,
        "pace_basis": pace_basis,
        "weather_label": weather,
        "weather_basis": weather_basis,
        "environment_label": env_label,
        "environment_basis": env_basis,
        "summary_http": summary_diag.get("http"),
        "away_stats_http": away_stats_diag.get("http"),
        "home_stats_http": home_stats_diag.get("http"),
        "away_schedule_http": away_schedule_diag.get("http"),
        "home_schedule_http": home_schedule_diag.get("http"),
        "projection_adjustment": 0.0,
        "sportsbook_influence": 0.0,
    }


__all__ = [
    "MODEL_VERSION",
    "build_game_environment",
    "environment_label",
    "pace_label",
    "parse_game_environment",
    "parse_team_pace",
    "pass_tendency_label",
    "rest_context",
    "weather_label",
]
