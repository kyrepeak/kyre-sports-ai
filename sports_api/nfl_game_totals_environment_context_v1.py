"""Descriptive NFL game-environment context for Game Totals page Step 7.

Uses exact ESPN event identity. Venue name + indoor status come from the ESPN
scoreboard event; weather comes from the exact ESPN event summary. Indoor games
always neutralize weather even when ESPN returns an outside-weather object.
Sportsbook data is never consumed here and has 0.0 projection influence.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import math
from typing import Any

import requests

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
VENUE_INDOOR_FIELD = "indoor"
WEATHER_FIELDS = ("temperature", "precipitation", "gust")
REQUEST_TIMEOUT_SECONDS = 8
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "Mozilla/5.0 kyre-sports-ai/nfl-game-totals-step7",
}


def _safe(value: Any, default: str = "") -> str:
    try:
        text = str(value if value is not None else "").strip()
    except Exception:
        text = ""
    return text or default


def _num(value: Any) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else math.nan
    except (TypeError, ValueError):
        return math.nan


def classify_weather_pressure(temperature: Any, precipitation: Any, gust: Any, *, indoor: bool) -> str:
    """Classify descriptive outdoor weather pressure; indoor weather is neutralized."""
    if bool(indoor):
        return "INDOOR"

    temp = _num(temperature)
    precip = _num(precipitation)
    wind_gust = _num(gust)
    if not all(math.isfinite(value) for value in (temp, precip, wind_gust)):
        return "UNAVAILABLE"

    if wind_gust >= 25.0 or precip >= 60.0 or temp <= 32.0 or temp >= 95.0:
        return "HIGH"
    if wind_gust >= 15.0 or precip >= 30.0 or temp <= 40.0 or temp >= 90.0:
        return "WATCH"
    return "LOW"


def extract_environment_metrics(scoreboard_event: dict[str, Any], summary_payload: dict[str, Any]) -> dict[str, Any]:
    """Extract venue/indoor truth and exact-summary weather for one ESPN event."""
    event = scoreboard_event if isinstance(scoreboard_event, dict) else {}
    summary = summary_payload if isinstance(summary_payload, dict) else {}
    event_id = _safe(event.get("id"))

    competitions = event.get("competitions") or []
    competition = competitions[0] if isinstance(competitions, list) and len(competitions) == 1 and isinstance(competitions[0], dict) else {}
    venue = competition.get("venue") if isinstance(competition, dict) else None
    venue = venue if isinstance(venue, dict) else {}
    venue_name = _safe(venue.get("fullName"))
    indoor_raw = venue.get(VENUE_INDOOR_FIELD)
    indoor_known = isinstance(indoor_raw, bool)
    indoor = bool(indoor_raw) if indoor_known else False

    game_info = summary.get("gameInfo") or {}
    weather = game_info.get("weather") if isinstance(game_info, dict) else None
    weather = weather if isinstance(weather, dict) else {}

    temperature = _num(weather.get("temperature"))
    precipitation = _num(weather.get("precipitation"))
    gust = _num(weather.get("gust"))
    condition_id = _safe(weather.get("conditionId"))

    venue_ready = bool(venue_name and indoor_known)
    if indoor:
        return {
            "event_id": event_id,
            "ready": venue_ready,
            "venue_name": venue_name,
            "indoor": True,
            "weather_applies": False,
            "temperature": float(temperature) if math.isfinite(temperature) else math.nan,
            "precipitation": float(precipitation) if math.isfinite(precipitation) else math.nan,
            "gust": float(gust) if math.isfinite(gust) else math.nan,
            "condition_id": condition_id,
            "weather_pressure": "INDOOR" if venue_ready else "UNAVAILABLE",
            "provider": "ESPN NFL scoreboard + exact event summary",
            "diagnostics": [] if venue_ready else ["venue indoor metadata unavailable"],
            "descriptive_only": True,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        }

    weather_ready = bool(
        venue_ready
        and math.isfinite(temperature)
        and math.isfinite(precipitation)
        and 0.0 <= precipitation <= 100.0
        and math.isfinite(gust)
        and gust >= 0.0
    )
    pressure = classify_weather_pressure(temperature, precipitation, gust, indoor=False) if weather_ready else "UNAVAILABLE"
    return {
        "event_id": event_id,
        "ready": weather_ready,
        "venue_name": venue_name,
        "indoor": False,
        "weather_applies": weather_ready,
        "temperature": float(temperature) if math.isfinite(temperature) else math.nan,
        "precipitation": float(precipitation) if math.isfinite(precipitation) else math.nan,
        "gust": float(gust) if math.isfinite(gust) else math.nan,
        "condition_id": condition_id,
        "weather_pressure": pressure,
        "provider": "ESPN NFL scoreboard + exact event summary",
        "diagnostics": [] if weather_ready else ["exact ESPN venue/weather fields unavailable"],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


def _fetch_scoreboard(day_str: str) -> tuple[list[dict[str, Any]], str]:
    day_key = _safe(day_str).replace("-", "")[:8]
    if len(day_key) != 8 or not day_key.isdigit():
        return [], "invalid scoreboard day"
    try:
        response = requests.get(
            ESPN_SCOREBOARD,
            params={"dates": day_key},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return [], str(exc)[:220]
    events = payload.get("events") or []
    return ([event for event in events if isinstance(event, dict)] if isinstance(events, list) else []), ""


def _fetch_summary(event_id: str) -> tuple[dict[str, Any], str]:
    try:
        response = requests.get(
            ESPN_SUMMARY,
            params={"event": str(event_id)},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return (payload if isinstance(payload, dict) else {}), ""
    except Exception as exc:
        return {}, str(exc)[:220]


def build_slate_environment_context(day_str: str, event_ids: list[str] | tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """Build environment context for exact requested ESPN event IDs only."""
    requested = list(dict.fromkeys(_safe(event_id) for event_id in event_ids if _safe(event_id)))
    if not requested:
        return {}

    events, board_error = _fetch_scoreboard(day_str)
    if board_error:
        return {
            event_id: {
                "event_id": event_id,
                "ready": False,
                "weather_applies": False,
                "weather_pressure": "UNAVAILABLE",
                "provider": "ESPN NFL scoreboard + exact event summary",
                "diagnostics": [board_error],
                "descriptive_only": True,
                "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
            }
            for event_id in requested
        }

    by_id: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for event in events:
        event_id = _safe(event.get("id"))
        if event_id not in requested:
            continue
        if event_id in by_id:
            duplicate_ids.add(event_id)
        else:
            by_id[event_id] = event

    output: dict[str, dict[str, Any]] = {}
    fetchable: list[str] = []
    for event_id in requested:
        if event_id in duplicate_ids:
            output[event_id] = {
                "event_id": event_id,
                "ready": False,
                "weather_applies": False,
                "weather_pressure": "UNAVAILABLE",
                "provider": "ESPN NFL scoreboard + exact event summary",
                "diagnostics": ["ambiguous exact ESPN event identity"],
                "descriptive_only": True,
                "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
            }
        elif event_id not in by_id:
            output[event_id] = {
                "event_id": event_id,
                "ready": False,
                "weather_applies": False,
                "weather_pressure": "UNAVAILABLE",
                "provider": "ESPN NFL scoreboard + exact event summary",
                "diagnostics": ["exact ESPN event not present on requested scoreboard day"],
                "descriptive_only": True,
                "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
            }
        else:
            fetchable.append(event_id)

    if fetchable:
        with ThreadPoolExecutor(max_workers=min(8, len(fetchable))) as pool:
            futures = {pool.submit(_fetch_summary, event_id): event_id for event_id in fetchable}
            for future in as_completed(futures):
                event_id = futures[future]
                try:
                    summary, summary_error = future.result()
                except Exception as exc:
                    summary, summary_error = {}, str(exc)[:220]
                if summary_error:
                    output[event_id] = {
                        "event_id": event_id,
                        "ready": False,
                        "weather_applies": False,
                        "weather_pressure": "UNAVAILABLE",
                        "provider": "ESPN NFL scoreboard + exact event summary",
                        "diagnostics": [summary_error],
                        "descriptive_only": True,
                        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
                    }
                else:
                    output[event_id] = extract_environment_metrics(by_id[event_id], summary)

    return {event_id: output[event_id] for event_id in requested}


__all__ = [
    "ESPN_SCOREBOARD",
    "ESPN_SUMMARY",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "VENUE_INDOOR_FIELD",
    "WEATHER_FIELDS",
    "build_slate_environment_context",
    "classify_weather_pressure",
    "extract_environment_metrics",
]
