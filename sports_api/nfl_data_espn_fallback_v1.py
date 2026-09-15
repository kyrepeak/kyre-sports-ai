"""ESPN fallback adapter for NFL Game Totals canonical data contracts.

This module isolates the existing ESPN transport/extraction semantics behind the
shared multi-source router. ESPN is intentionally a fallback provider; this
adapter contains no sportsbook input and no total-projection logic.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import math
from typing import Any, Callable

import requests

ESPN_TEAM_SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/schedule"
ESPN_TEAM_STATS = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/statistics"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
REQUEST_TIMEOUT_SECONDS = 8
HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "Mozilla/5.0 kyre-sports-ai/nfl-game-totals-espn-fallback",
}

JsonGetter = Callable[..., dict[str, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _request_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(
        url,
        params=params or {},
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("ESPN response was not a JSON object")
    return payload


def _get_json(
    url: str,
    params: dict[str, Any] | None,
    injected: JsonGetter | None,
) -> dict[str, Any]:
    if injected is None:
        return _request_json(url, params)
    payload = injected(url, params=params)
    if not isinstance(payload, dict):
        raise ValueError("injected ESPN response was not a JSON object")
    return payload


def _result(
    *,
    provider: str,
    ready: bool,
    data: dict[str, Any] | None = None,
    fields_verified: list[str] | None = None,
    diagnostics: list[str] | None = None,
    freshness: str = "",
) -> dict[str, Any]:
    fetched_at = _utc_now()
    return {
        "ready": bool(ready),
        "provider": provider,
        "data": dict(data or {}) if ready else {},
        "fields_verified": list(fields_verified or []) if ready else [],
        "quality": "HIGH" if ready else "UNAVAILABLE",
        "data_freshness": freshness or fetched_at,
        "fetched_at": fetched_at,
        "diagnostics": list(diagnostics or []),
    }


def _transport_failure(provider: str, exc: Exception) -> dict[str, Any]:
    return _result(
        provider=provider,
        ready=False,
        diagnostics=[f"{type(exc).__name__}: {str(exc)[:200]}"],
    )


def _completed_regular_games(
    payload: dict[str, Any],
    team_abbr: str,
    cutoff_day: str,
) -> list[dict[str, Any]]:
    abbr = _safe(team_abbr).upper()
    try:
        cutoff = date.fromisoformat(str(cutoff_day)[:10])
    except ValueError:
        return []

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    events = payload.get("events") or []
    if not isinstance(events, list):
        return rows

    for event in events:
        if not isinstance(event, dict):
            continue
        status_type = ((event.get("status") or {}).get("type") or {})
        if not bool(status_type.get("completed")) and _safe(status_type.get("state")).lower() != "post":
            continue
        event_date = _safe(event.get("date"))[:10]
        try:
            event_day = date.fromisoformat(event_date)
        except ValueError:
            continue
        if event_day > cutoff:
            continue

        competitions = event.get("competitions") or []
        if not isinstance(competitions, list) or not competitions:
            continue
        competitors = (competitions[0] or {}).get("competitors") or []
        if not isinstance(competitors, list):
            continue

        ours = None
        opponent = None
        for competitor in competitors:
            if not isinstance(competitor, dict):
                continue
            team = competitor.get("team") or {}
            if _safe(team.get("abbreviation")).upper() == abbr:
                ours = competitor
            else:
                opponent = competitor
        if not ours or not opponent:
            continue

        points_for = _num(ours.get("score"))
        points_against = _num(opponent.get("score"))
        if not math.isfinite(points_for) or not math.isfinite(points_against):
            continue
        opponent_abbr = _safe((opponent.get("team") or {}).get("abbreviation")).upper()
        key = (event_day.isoformat(), opponent_abbr)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "date": event_day.isoformat(),
                "pf": float(points_for),
                "pa": float(points_against),
                "opponent_abbr": opponent_abbr,
            }
        )

    rows.sort(key=lambda row: row["date"])
    return rows


def fetch_scoring_games(
    request: dict[str, Any],
    *,
    get_json: JsonGetter | None = None,
) -> dict[str, Any]:
    provider = "ESPN NFL team schedule"
    team = _safe(request.get("team_abbr") if isinstance(request, dict) else "").upper()
    cutoff_day = _safe(request.get("cutoff_day") if isinstance(request, dict) else "")[:10]
    try:
        season = int(request.get("season"))
    except (AttributeError, TypeError, ValueError):
        return _result(provider=provider, ready=False, diagnostics=["invalid season"])
    if not team or not cutoff_day:
        return _result(provider=provider, ready=False, diagnostics=["missing team or cutoff day"])

    try:
        payload = _get_json(
            ESPN_TEAM_SCHEDULE.format(team=team.lower()),
            {"season": season, "seasontype": 2},
            get_json,
        )
    except Exception as exc:
        return _transport_failure(provider, exc)

    games = _completed_regular_games(payload, team, cutoff_day)
    freshness = max((row["date"] for row in games), default=cutoff_day)
    return _result(
        provider=provider,
        ready=True,
        data={"games": games},
        fields_verified=["date", "pf", "pa", "opponent_abbr"],
        freshness=freshness,
    )


def _stat_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("results") or {}
    stats_root = results.get("stats") if isinstance(results, dict) else {}
    categories = stats_root.get("categories") if isinstance(stats_root, dict) else []
    if not isinstance(categories, list):
        return []
    rows: list[dict[str, Any]] = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        category_name = _safe(category.get("name")).lower()
        stats = category.get("stats") or []
        if not isinstance(stats, list):
            continue
        for stat in stats:
            if isinstance(stat, dict):
                row = dict(stat)
                row["_category_name"] = category_name
                rows.append(row)
    return rows


def _matches(rows: list[dict[str, Any]], name: str, category: str | None = None) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if _safe(row.get("name")) == name
        and (category is None or _safe(row.get("_category_name")).lower() == category.lower())
    ]


def _single_value(
    rows: list[dict[str, Any]],
    name: str,
    *,
    field: str,
    category: str | None = None,
) -> float:
    matched = _matches(rows, name, category)
    if len(matched) != 1:
        return math.nan
    return _num(matched[0].get(field))


def _team_stats_payload(
    request: dict[str, Any],
    get_json: JsonGetter | None,
    provider: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    team = _safe(request.get("team_abbr") if isinstance(request, dict) else "").upper()
    try:
        season = int(request.get("season"))
    except (AttributeError, TypeError, ValueError):
        return None, _result(provider=provider, ready=False, diagnostics=["invalid season"])
    if not team:
        return None, _result(provider=provider, ready=False, diagnostics=["missing team abbreviation"])
    try:
        payload = _get_json(
            ESPN_TEAM_STATS.format(team=team.lower()),
            {"season": season},
            get_json,
        )
    except Exception as exc:
        return None, _transport_failure(provider, exc)
    return payload, None


def fetch_pace(
    request: dict[str, Any],
    *,
    get_json: JsonGetter | None = None,
) -> dict[str, Any]:
    provider = "ESPN NFL team statistics"
    payload, failure = _team_stats_payload(request, get_json, provider)
    if failure is not None:
        return failure
    rows = _stat_rows(payload or {})
    plays = _single_value(rows, "totalOffensivePlays", field="perGameValue")
    possession = _single_value(rows, "possessionTimeSeconds", field="perGameValue")
    ready = bool(math.isfinite(plays) and plays > 0 and math.isfinite(possession) and possession > 0)
    if not ready:
        return _result(
            provider=provider,
            ready=False,
            diagnostics=["exact ESPN pace/possession fields unavailable"],
        )
    return _result(
        provider=provider,
        ready=True,
        data={
            "plays_per_game": float(plays),
            "possession_seconds_per_game": float(possession),
        },
        fields_verified=["plays_per_game", "possession_seconds_per_game"],
    )


def fetch_explosive(
    request: dict[str, Any],
    *,
    get_json: JsonGetter | None = None,
) -> dict[str, Any]:
    provider = "ESPN NFL team statistics"
    payload, failure = _team_stats_payload(request, get_json, provider)
    if failure is not None:
        return failure
    rows = _stat_rows(payload or {})
    rushing_big = _single_value(rows, "rushingBigPlays", field="value", category="rushing")
    receiving_big = _single_value(rows, "receivingBigPlays", field="value", category="receiving")
    games = _single_value(rows, "gamesPlayed", field="value", category="general")
    ready = bool(
        math.isfinite(games)
        and games > 0
        and math.isfinite(rushing_big)
        and rushing_big >= 0
        and math.isfinite(receiving_big)
        and receiving_big >= 0
    )
    if not ready:
        return _result(
            provider=provider,
            ready=False,
            diagnostics=["exact ESPN explosive-play or games-played fields unavailable"],
        )
    total_big = rushing_big + receiving_big
    return _result(
        provider=provider,
        ready=True,
        data={
            "games_played": float(games),
            "rushing_big_plays": float(rushing_big),
            "receiving_big_plays": float(receiving_big),
            "total_big_plays": float(total_big),
            "rushing_big_plays_per_game": float(rushing_big / games),
            "receiving_big_plays_per_game": float(receiving_big / games),
            "explosive_plays_per_game": float(total_big / games),
        },
        fields_verified=[
            "games_played",
            "rushing_big_plays",
            "receiving_big_plays",
            "total_big_plays",
            "explosive_plays_per_game",
        ],
    )


def fetch_red_zone_drive(
    request: dict[str, Any],
    *,
    get_json: JsonGetter | None = None,
) -> dict[str, Any]:
    provider = "ESPN NFL team statistics"
    payload, failure = _team_stats_payload(request, get_json, provider)
    if failure is not None:
        return failure
    rows = _stat_rows(payload or {})
    rz = _single_value(rows, "redzoneTouchdownPct", field="value", category="miscellaneous")
    third = _single_value(rows, "thirdDownConvPct", field="value", category="miscellaneous")
    first = _single_value(rows, "firstDowns", field="perGameValue", category="miscellaneous")
    ready = bool(
        math.isfinite(rz)
        and 0.0 <= rz <= 100.0
        and math.isfinite(third)
        and 0.0 <= third <= 100.0
        and math.isfinite(first)
        and first >= 0.0
    )
    if not ready:
        return _result(
            provider=provider,
            ready=False,
            diagnostics=["exact ESPN red-zone or sustainability fields unavailable"],
        )
    return _result(
        provider=provider,
        ready=True,
        data={
            "red_zone_td_pct": float(rz),
            "third_down_conv_pct": float(third),
            "first_downs_per_game": float(first),
        },
        fields_verified=["red_zone_td_pct", "third_down_conv_pct", "first_downs_per_game"],
    )


def _weather_pressure(temperature: float, precipitation: float, gust: float, *, indoor: bool) -> str:
    if indoor:
        return "INDOOR"
    if gust >= 25.0 or precipitation >= 60.0 or temperature <= 32.0 or temperature >= 95.0:
        return "HIGH"
    if gust >= 15.0 or precipitation >= 30.0 or temperature <= 40.0 or temperature >= 90.0:
        return "WATCH"
    return "LOW"


def _scoreboard_event(payload: dict[str, Any], event_id: str) -> tuple[dict[str, Any] | None, str]:
    events = payload.get("events") or []
    if not isinstance(events, list):
        return None, "ESPN scoreboard events unavailable"
    matched = [event for event in events if isinstance(event, dict) and _safe(event.get("id")) == event_id]
    if len(matched) != 1:
        return None, "exact ESPN event identity missing or ambiguous"
    return matched[0], ""


def fetch_environment(
    request: dict[str, Any],
    *,
    get_json: JsonGetter | None = None,
) -> dict[str, Any]:
    provider = "ESPN NFL scoreboard + exact event summary"
    if not isinstance(request, dict):
        return _result(provider=provider, ready=False, diagnostics=["environment request must be an object"])
    event_id = _safe(request.get("event_id"))
    day_str = _safe(request.get("day_str"))[:10]
    scoreboard_event = request.get("scoreboard_event")
    scoreboard_event = scoreboard_event if isinstance(scoreboard_event, dict) else None
    if not event_id:
        return _result(provider=provider, ready=False, diagnostics=["missing event_id"])

    if scoreboard_event is None:
        day_key = day_str.replace("-", "")[:8]
        if len(day_key) != 8 or not day_key.isdigit():
            return _result(provider=provider, ready=False, diagnostics=["invalid scoreboard day"])
        try:
            board = _get_json(ESPN_SCOREBOARD, {"dates": day_key}, get_json)
        except Exception as exc:
            return _transport_failure(provider, exc)
        scoreboard_event, identity_error = _scoreboard_event(board, event_id)
        if scoreboard_event is None:
            return _result(provider=provider, ready=False, diagnostics=[identity_error])

    competitions = scoreboard_event.get("competitions") or []
    competition = competitions[0] if isinstance(competitions, list) and len(competitions) == 1 and isinstance(competitions[0], dict) else {}
    venue = competition.get("venue") if isinstance(competition, dict) else None
    venue = venue if isinstance(venue, dict) else {}
    venue_name = _safe(venue.get("fullName"))
    indoor_raw = venue.get("indoor")
    if not venue_name or not isinstance(indoor_raw, bool):
        return _result(provider=provider, ready=False, diagnostics=["venue indoor metadata unavailable"])
    indoor = bool(indoor_raw)

    if indoor:
        return _result(
            provider=provider,
            ready=True,
            data={
                "venue_name": venue_name,
                "indoor": True,
                "weather_applies": False,
                "temperature": math.nan,
                "precipitation": math.nan,
                "gust": math.nan,
                "condition_id": "",
                "weather_pressure": "INDOOR",
            },
            fields_verified=["venue_name", "indoor"],
        )

    try:
        summary = _get_json(ESPN_SUMMARY, {"event": event_id}, get_json)
    except Exception as exc:
        return _transport_failure(provider, exc)
    game_info = summary.get("gameInfo") or {}
    weather = game_info.get("weather") if isinstance(game_info, dict) else None
    weather = weather if isinstance(weather, dict) else {}
    temperature = _num(weather.get("temperature"))
    precipitation = _num(weather.get("precipitation"))
    gust = _num(weather.get("gust"))
    condition_id = _safe(weather.get("conditionId"))
    ready = bool(
        math.isfinite(temperature)
        and math.isfinite(precipitation)
        and 0.0 <= precipitation <= 100.0
        and math.isfinite(gust)
        and gust >= 0.0
    )
    if not ready:
        return _result(provider=provider, ready=False, diagnostics=["exact ESPN venue/weather fields unavailable"])
    return _result(
        provider=provider,
        ready=True,
        data={
            "venue_name": venue_name,
            "indoor": False,
            "weather_applies": True,
            "temperature": float(temperature),
            "precipitation": float(precipitation),
            "gust": float(gust),
            "condition_id": condition_id,
            "weather_pressure": _weather_pressure(
                float(temperature),
                float(precipitation),
                float(gust),
                indoor=False,
            ),
        },
        fields_verified=["venue_name", "indoor", "temperature", "precipitation", "gust"],
    )


__all__ = [
    "ESPN_SCOREBOARD",
    "ESPN_SUMMARY",
    "ESPN_TEAM_SCHEDULE",
    "ESPN_TEAM_STATS",
    "HEADERS",
    "REQUEST_TIMEOUT_SECONDS",
    "fetch_environment",
    "fetch_explosive",
    "fetch_pace",
    "fetch_red_zone_drive",
    "fetch_scoring_games",
]
