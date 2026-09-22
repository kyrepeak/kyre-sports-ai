"""WNBA rest, schedule-density, workload, and travel context.

Step 4N is descriptive context only. It does not turn rest or travel into
betting edges, player projections, injury probabilities, or fatigue scores.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any
from zoneinfo import ZoneInfo

from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_schedule import (
    WNBA_LEAGUE_ID,
    WNBA_SCHEDULE_SOURCE,
    _date_block_iso,
    _fetch_schedule_payload,
    _normalize_game,
    _schedule_root,
)
from sports_api.wnba_team_history import (
    WNBATeamHistoryUpstreamError,
    get_team_game_log_dataset,
)

WINDOW_DAYS = (3, 5, 7, 8)
REGULATION_TEAM_MINUTES = 200.0

# Approximate city centroids used only for descriptive great-circle travel
# context. These are not arena coordinates and are never labeled as route miles.
VENUE_CITY_POINTS: dict[str, dict[str, Any]] = {
    "atlanta": {"lat": 33.7490, "lon": -84.3880, "timezone": "America/New_York"},
    "chicago": {"lat": 41.8781, "lon": -87.6298, "timezone": "America/Chicago"},
    "uncasville": {"lat": 41.4345, "lon": -72.1098, "timezone": "America/New_York"},
    "hartford": {"lat": 41.7658, "lon": -72.6734, "timezone": "America/New_York"},
    "boston": {"lat": 42.3601, "lon": -71.0589, "timezone": "America/New_York"},
    "arlington": {"lat": 32.7357, "lon": -97.1081, "timezone": "America/Chicago"},
    "dallas": {"lat": 32.7767, "lon": -96.7970, "timezone": "America/Chicago"},
    "san francisco": {"lat": 37.7749, "lon": -122.4194, "timezone": "America/Los_Angeles"},
    "oakland": {"lat": 37.8044, "lon": -122.2712, "timezone": "America/Los_Angeles"},
    "indianapolis": {"lat": 39.7684, "lon": -86.1581, "timezone": "America/Indiana/Indianapolis"},
    "las vegas": {"lat": 36.1699, "lon": -115.1398, "timezone": "America/Los_Angeles"},
    "los angeles": {"lat": 34.0522, "lon": -118.2437, "timezone": "America/Los_Angeles"},
    "minneapolis": {"lat": 44.9778, "lon": -93.2650, "timezone": "America/Chicago"},
    "brooklyn": {"lat": 40.6782, "lon": -73.9442, "timezone": "America/New_York"},
    "new york": {"lat": 40.7128, "lon": -74.0060, "timezone": "America/New_York"},
    "phoenix": {"lat": 33.4484, "lon": -112.0740, "timezone": "America/Phoenix"},
    "portland": {"lat": 45.5152, "lon": -122.6784, "timezone": "America/Los_Angeles"},
    "seattle": {"lat": 47.6062, "lon": -122.3321, "timezone": "America/Los_Angeles"},
    "toronto": {"lat": 43.6532, "lon": -79.3832, "timezone": "America/Toronto"},
    "montreal": {"lat": 45.5017, "lon": -73.5673, "timezone": "America/Toronto"},
    "vancouver": {"lat": 49.2827, "lon": -123.1207, "timezone": "America/Vancouver"},
    "washington": {"lat": 38.9072, "lon": -77.0369, "timezone": "America/New_York"},
    "washington, d.c.": {"lat": 38.9072, "lon": -77.0369, "timezone": "America/New_York"},
}

TEAM_HOME_MARKETS: dict[str, tuple[str, str | None]] = {
    "atlanta-dream": ("Atlanta", "GA"),
    "chicago-sky": ("Chicago", "IL"),
    "connecticut-sun": ("Uncasville", "CT"),
    "dallas-wings": ("Arlington", "TX"),
    "golden-state-valkyries": ("San Francisco", "CA"),
    "indiana-fever": ("Indianapolis", "IN"),
    "las-vegas-aces": ("Las Vegas", "NV"),
    "los-angeles-sparks": ("Los Angeles", "CA"),
    "minnesota-lynx": ("Minneapolis", "MN"),
    "new-york-liberty": ("Brooklyn", "NY"),
    "phoenix-mercury": ("Phoenix", "AZ"),
    "portland-fire": ("Portland", "OR"),
    "seattle-storm": ("Seattle", "WA"),
    "toronto-tempo": ("Toronto", "ON"),
    "washington-mystics": ("Washington", "DC"),
}


class WNBARestTravelUpstreamError(RuntimeError):
    """Raised when source schedule/history cannot be consumed safely."""


class WNBARestTravelNotFoundError(LookupError):
    """Raised when a team or game cannot be found in the supported season."""


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format.") from exc


def _team(team_key: str, season: int) -> dict[str, Any]:
    key = str(team_key).strip().casefold()
    for item in get_wnba_teams(season):
        if item["team_key"].casefold() == key:
            return item
    raise WNBARestTravelNotFoundError(
        f"WNBA team key {team_key!r} was not found for the {season} season."
    )


def _valid_game_id(game_id: str) -> str:
    text = str(game_id).strip()
    if len(text) != 10 or not text.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return text


def _season_schedule_dataset(season: int) -> dict[str, Any]:
    get_wnba_teams(season)
    payload, retrieved, variant, source_url, cache_hit = _fetch_schedule_payload(season)
    root = _schedule_root(payload)

    games: list[dict[str, Any]] = []
    for block in root.get("gameDates", []):
        if not isinstance(block, dict):
            continue
        official_date = _date_block_iso(block.get("gameDate"))
        if official_date is None:
            continue
        raw_games = block.get("games")
        if not isinstance(raw_games, list):
            continue
        for raw in raw_games:
            if isinstance(raw, dict):
                normalized = _normalize_game(raw, official_date, season)
                away_mapped = bool((normalized.get("away") or {}).get("mapped_to_registry"))
                home_mapped = bool((normalized.get("home") or {}).get("mapped_to_registry"))
                if away_mapped and home_mapped:
                    games.append(normalized)
                elif away_mapped != home_mapped:
                    raise WNBARestTravelUpstreamError(
                        "Official WNBA schedule returned a one-sided unmapped team identity."
                    )
                # Two unmapped teams can represent a non-franchise event such as All-Star;
                # those are intentionally excluded from franchise schedule-load context.

    ids = [game.get("game_id") for game in games if game.get("game_id")]
    duplicates = sorted({game_id for game_id in ids if ids.count(game_id) > 1})
    invalid = sorted(
        {
            game.get("game_id")
            for game in games
            if not game.get("verification", {}).get("game_id_valid")
        },
        key=lambda item: item or "",
    )
    unmapped = [
        game.get("game_id")
        for game in games
        if not game.get("verification", {}).get("teams_mapped_to_registry")
    ]
    if duplicates or invalid or unmapped:
        raise WNBARestTravelUpstreamError(
            "Official WNBA season schedule failed Step 4N integrity checks."
        )

    games.sort(
        key=lambda g: (
            g.get("official_schedule_date") or "",
            g.get("game_datetime_utc") or "",
            g.get("game_id") or "",
        )
    )
    return {
        "source": WNBA_SCHEDULE_SOURCE,
        "source_url": source_url,
        "source_variant": variant,
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "retrieved_at_utc": retrieved,
        "cache_hit": cache_hit,
        "game_count": len(games),
        "games": games,
        "verification": {
            "all_game_ids_valid": True,
            "all_game_ids_unique": True,
            "all_teams_mapped_to_registry": True,
        },
    }


def _active_for_load(game: dict[str, Any]) -> bool:
    category = (game.get("status") or {}).get("category")
    change = game.get("schedule_change") or {}
    if change.get("cancelled") or change.get("postponed"):
        return False
    return category in {"scheduled", "live", "final", "delayed", "suspended", "unknown"}


def _team_side(game: dict[str, Any], team_key: str) -> str | None:
    if (game.get("home") or {}).get("team_key") == team_key:
        return "home"
    if (game.get("away") or {}).get("team_key") == team_key:
        return "away"
    return None


def _team_games(games: list[dict[str, Any]], team_key: str) -> list[dict[str, Any]]:
    selected = [g for g in games if _active_for_load(g) and _team_side(g, team_key)]
    selected.sort(
        key=lambda g: (
            g.get("official_schedule_date") or "",
            g.get("game_datetime_utc") or "",
            g.get("game_id") or "",
        )
    )
    return selected


def _game_stub(game: dict[str, Any] | None, team_key: str | None = None) -> dict[str, Any] | None:
    if game is None:
        return None
    side = _team_side(game, team_key) if team_key else None
    opponent = None
    if team_key:
        if side == "home":
            opponent = (game.get("away") or {}).get("team_key")
        elif side == "away":
            opponent = (game.get("home") or {}).get("team_key")
    return {
        "game_id": game.get("game_id"),
        "date": game.get("official_schedule_date"),
        "game_datetime_utc": game.get("game_datetime_utc"),
        "game_datetime_eastern": game.get("game_datetime_eastern"),
        "team_location": "neutral" if (game.get("venue") or {}).get("is_neutral") else side,
        "opponent_team_key": opponent,
        "venue": deepcopy(game.get("venue") or {}),
        "status": deepcopy(game.get("status") or {}),
        "schedule_change": deepcopy(game.get("schedule_change") or {}),
    }


def _date_of(game: dict[str, Any]) -> date:
    return _parse_date(game["official_schedule_date"])


def _previous_next(
    team_games: list[dict[str, Any]],
    target_date: date,
    target_game_id: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    previous = None
    next_game = None
    for game in team_games:
        gd = _date_of(game)
        gid = game.get("game_id")
        if gd < target_date or (
            gd == target_date and target_game_id is not None and gid < target_game_id
        ):
            previous = game
            continue
        if gd > target_date or (
            gd == target_date and target_game_id is not None and gid > target_game_id
        ):
            next_game = game
            break
    return previous, next_game


def _window_count(team_games: list[dict[str, Any]], target_date: date, days: int) -> int:
    start = target_date - timedelta(days=days - 1)
    return sum(start <= _date_of(game) <= target_date for game in team_games)


def _forward_count(team_games: list[dict[str, Any]], target_date: date, days: int) -> int:
    end = target_date + timedelta(days=days - 1)
    return sum(target_date <= _date_of(game) <= end for game in team_games)


def _venue_location(game: dict[str, Any]) -> dict[str, Any]:
    venue = game.get("venue") or {}
    city = _clean(venue.get("city"))
    state = _clean(venue.get("state"))
    source = "official_schedule_arena_city"
    if city is None:
        home_key = (game.get("home") or {}).get("team_key")
        fallback = TEAM_HOME_MARKETS.get(home_key)
        if fallback:
            city, state = fallback
            source = "home_market_fallback"
    point = VENUE_CITY_POINTS.get((city or "").casefold())
    return {
        "venue_name": _clean(venue.get("name")),
        "city": city,
        "state": state,
        "is_neutral": bool(venue.get("is_neutral")),
        "location_source": source if city else None,
        "centroid_available": point is not None,
        "centroid": deepcopy(point) if point else None,
    }


def _haversine_miles(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lon1, lat2, lon2 = map(
        radians, [a["lat"], a["lon"], b["lat"], b["lon"]]
    )
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 3958.7613 * 2 * asin(sqrt(h))


def _timezone_shift_hours(
    previous: dict[str, Any],
    current: dict[str, Any],
    when_utc: str | None,
) -> float | None:
    if not when_utc:
        return None
    p_tz = (previous.get("centroid") or {}).get("timezone")
    c_tz = (current.get("centroid") or {}).get("timezone")
    if not p_tz or not c_tz:
        return None
    try:
        instant = datetime.fromisoformat(when_utc.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        p_off = instant.astimezone(ZoneInfo(p_tz)).utcoffset()
        c_off = instant.astimezone(ZoneInfo(c_tz)).utcoffset()
        if p_off is None or c_off is None:
            return None
        return round((c_off - p_off).total_seconds() / 3600.0, 2)
    except (ValueError, KeyError):
        return None


def _travel_transition(
    previous_game: dict[str, Any] | None,
    current_game: dict[str, Any] | None,
) -> dict[str, Any]:
    if previous_game is None or current_game is None:
        return {
            "available": False,
            "reason": "previous_or_current_game_missing",
            "great_circle_miles": None,
            "timezone_offset_change_hours": None,
        }
    previous = _venue_location(previous_game)
    current = _venue_location(current_game)
    a, b = previous.get("centroid"), current.get("centroid")
    miles = round(_haversine_miles(a, b), 1) if a and b else None
    return {
        "available": miles is not None,
        "method": "venue_city_centroid_haversine",
        "distance_is_route_miles": False,
        "great_circle_miles": miles,
        "previous_location": previous,
        "current_location": current,
        "timezone_offset_change_hours": _timezone_shift_hours(
            previous, current, current_game.get("game_datetime_utc")
        ),
        "same_city": bool(
            previous.get("city")
            and current.get("city")
            and previous["city"].casefold() == current["city"].casefold()
        ),
    }


def _road_trip_context(
    team_games: list[dict[str, Any]],
    target_game: dict[str, Any] | None,
    team_key: str,
) -> dict[str, Any]:
    if target_game is None:
        return {
            "applicable": False,
            "road_trip_game_number": None,
            "consecutive_away_games_through_target": 0,
        }
    side = _team_side(target_game, team_key)
    if (target_game.get("venue") or {}).get("is_neutral") or side != "away":
        return {
            "applicable": False,
            "road_trip_game_number": None,
            "consecutive_away_games_through_target": 0,
        }
    index = next(
        (
            i
            for i, game in enumerate(team_games)
            if game.get("game_id") == target_game.get("game_id")
        ),
        None,
    )
    if index is None:
        return {
            "applicable": False,
            "road_trip_game_number": None,
            "consecutive_away_games_through_target": 0,
        }
    count = 0
    for i in range(index, -1, -1):
        game = team_games[i]
        if (
            (game.get("venue") or {}).get("is_neutral")
            or _team_side(game, team_key) != "away"
        ):
            break
        count += 1
    return {
        "applicable": True,
        "road_trip_game_number": count,
        "consecutive_away_games_through_target": count,
    }


def _observed_workload(
    team_key: str,
    season: int,
    target_date: date,
) -> dict[str, Any]:
    try:
        dataset = get_team_game_log_dataset(
            team_key, season, season_type="Regular Season"
        )
    except WNBATeamHistoryUpstreamError as exc:
        raise WNBARestTravelUpstreamError(str(exc)) from exc
    games = [
        game
        for game in dataset.get("games", [])
        if game.get("game_date") and _parse_date(game["game_date"]) < target_date
    ]
    games.sort(
        key=lambda game: (game.get("game_date") or "", game.get("game_id") or ""),
        reverse=True,
    )

    def recent(days: int) -> list[dict[str, Any]]:
        start = target_date - timedelta(days=days)
        return [
            game
            for game in games
            if start <= _parse_date(game["game_date"]) < target_date
        ]

    recent7 = recent(7)
    minutes = [
        float(game["minutes"])
        for game in recent7
        if isinstance(game.get("minutes"), (int, float))
        and not isinstance(game.get("minutes"), bool)
    ]
    above = [max(value - REGULATION_TEAM_MINUTES, 0.0) for value in minutes]
    return {
        "source": dataset.get("source"),
        "source_endpoint": dataset.get("source_endpoint"),
        "completed_games_before_target_date": len(games),
        "completed_games_previous_3_days": len(recent(3)),
        "completed_games_previous_5_days": len(recent(5)),
        "completed_games_previous_7_days": len(recent7),
        "team_minutes_previous_7_days": round(sum(minutes), 1) if minutes else 0.0,
        "team_minutes_above_regulation_previous_7_days": (
            round(sum(above), 1) if minutes else 0.0
        ),
        "games_above_regulation_team_minutes_previous_7_days": sum(
            value > 0 for value in above
        ),
        "most_recent_completed_game": deepcopy(games[0]) if games else None,
        "team_minutes_note": (
            "WNBA team game-log MIN is used descriptively. Values above 200 team-minutes "
            "indicate additional played team-minutes; no fatigue score is inferred."
        ),
        "verification": deepcopy(dataset.get("verification") or {}),
    }


def get_team_rest_travel_context(
    team_key: str,
    season: int,
    target_date: str,
    *,
    include_observed_workload: bool = True,
) -> dict[str, Any]:
    stable = _team(team_key, season)
    td = _parse_date(target_date)
    schedule = _season_schedule_dataset(season)
    team_games = _team_games(schedule["games"], stable["team_key"])

    target_games = [game for game in team_games if _date_of(game) == td]
    if len(target_games) > 1:
        raise WNBARestTravelUpstreamError(
            f"WNBA schedule returned multiple active games for {stable['team_key']} "
            f"on {target_date}."
        )
    target_game = target_games[0] if target_games else None
    previous, next_game = _previous_next(
        team_games,
        td,
        target_game.get("game_id") if target_game else None,
    )

    days_since_previous = (td - _date_of(previous)).days if previous else None
    days_until_next = (_date_of(next_game) - td).days if next_game else None
    full_rest_days_before = (
        max(days_since_previous - 1, 0) if days_since_previous is not None else None
    )
    full_rest_days_after = (
        max(days_until_next - 1, 0) if days_until_next is not None else None
    )

    second_b2b = bool(target_game and days_since_previous == 1)
    first_b2b = bool(target_game and days_until_next == 1)
    if second_b2b and first_b2b:
        b2b_position = "middle_of_three_consecutive_calendar_days"
    elif second_b2b:
        b2b_position = "second_night"
    elif first_b2b:
        b2b_position = "first_night"
    else:
        b2b_position = "none"

    density = {
        f"games_in_last_{days}_calendar_days_including_date": _window_count(
            team_games, td, days
        )
        for days in WINDOW_DAYS
    }
    density.update(
        {
            "three_in_five_through_date": _window_count(team_games, td, 5) >= 3,
            "four_in_seven_through_date": _window_count(team_games, td, 7) >= 4,
            "five_in_eight_through_date": _window_count(team_games, td, 8) >= 5,
            "games_next_3_calendar_days_including_date": _forward_count(
                team_games, td, 3
            ),
            "games_next_5_calendar_days_including_date": _forward_count(
                team_games, td, 5
            ),
            "games_next_7_calendar_days_including_date": _forward_count(
                team_games, td, 7
            ),
        }
    )

    travel_target = target_game or next_game
    travel_previous = previous
    if target_game is None and next_game is not None:
        prior_candidates = [
            game for game in team_games if _date_of(game) < _date_of(next_game)
        ]
        travel_previous = prior_candidates[-1] if prior_candidates else None

    return {
        "source": schedule["source"],
        "source_url": schedule["source_url"],
        "source_variant": schedule["source_variant"],
        "data_type": "wnba_rest_schedule_density_travel_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "team": stable,
        "date": target_date,
        "has_game_on_date": target_game is not None,
        "target_game": _game_stub(target_game, stable["team_key"]),
        "previous_game": _game_stub(previous, stable["team_key"]),
        "next_game": _game_stub(next_game, stable["team_key"]),
        "rest": {
            "calendar_days_since_previous_game": days_since_previous,
            "full_rest_days_before_date": full_rest_days_before,
            "calendar_days_until_next_game": days_until_next,
            "full_rest_days_after_date": full_rest_days_after,
            "is_second_night_of_back_to_back": second_b2b,
            "is_first_night_of_back_to_back": first_b2b,
            "back_to_back_position": b2b_position,
            "rest_day_definition": "full calendar days between game dates",
        },
        "schedule_density": density,
        "road_trip": _road_trip_context(
            team_games, target_game, stable["team_key"]
        ),
        "travel_to_target_or_next_game": _travel_transition(
            travel_previous, travel_target
        ),
        "observed_workload": (
            _observed_workload(stable["team_key"], season, td)
            if include_observed_workload
            else {"included": False}
        ),
        "retrieved_at_utc": schedule["retrieved_at_utc"],
        "cache_hit": schedule["cache_hit"],
        "verification": {
            **schedule["verification"],
            "team_game_count": len(team_games),
            "target_date_has_at_most_one_active_game": len(target_games) <= 1,
            "travel_distance_is_descriptive_great_circle_only": True,
            "rest_context_is_descriptive_not_predictive": True,
            "no_fatigue_score_created": True,
        },
    }


def get_game_rest_travel_context(
    game_id: str,
    season: int,
    *,
    include_observed_workload: bool = True,
) -> dict[str, Any]:
    gid = _valid_game_id(game_id)
    schedule = _season_schedule_dataset(season)
    matches = [game for game in schedule["games"] if game.get("game_id") == gid]
    if not matches:
        raise WNBARestTravelNotFoundError(
            f"WNBA game {gid} was not found in the {season} official schedule."
        )
    if len(matches) != 1:
        raise WNBARestTravelUpstreamError(f"WNBA schedule returned duplicate game {gid}.")
    game = matches[0]
    target_date = game["official_schedule_date"]
    away_key = game["away"]["team_key"]
    home_key = game["home"]["team_key"]
    away = get_team_rest_travel_context(
        away_key,
        season,
        target_date,
        include_observed_workload=include_observed_workload,
    )
    home = get_team_rest_travel_context(
        home_key,
        season,
        target_date,
        include_observed_workload=include_observed_workload,
    )
    if (
        (away.get("target_game") or {}).get("game_id") != gid
        or (home.get("target_game") or {}).get("game_id") != gid
    ):
        raise WNBARestTravelUpstreamError(
            "Game-level rest/travel context did not resolve the requested game for both teams."
        )
    return {
        "source": schedule["source"],
        "source_url": schedule["source_url"],
        "data_type": "wnba_game_rest_travel_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "game": _game_stub(game),
        "away_team_key": away_key,
        "home_team_key": home_key,
        "away_context": away,
        "home_context": home,
        "verification": {
            "requested_game_id_matches_both_team_contexts": True,
            "rest_travel_context_is_descriptive_not_predictive": True,
        },
    }


def get_rest_travel_board(
    season: int,
    target_date: str,
    *,
    games_only: bool = True,
    include_observed_workload: bool = False,
) -> dict[str, Any]:
    _parse_date(target_date)
    rows = [
        get_team_rest_travel_context(
            team["team_key"],
            season,
            target_date,
            include_observed_workload=include_observed_workload,
        )
        for team in get_wnba_teams(season)
    ]
    if games_only:
        rows = [row for row in rows if row["has_game_on_date"]]
    rows.sort(
        key=lambda row: (
            (row.get("target_game") or {}).get("game_datetime_utc") or "",
            row["team"]["team_key"],
        )
    )
    return {
        "source": WNBA_SCHEDULE_SOURCE,
        "data_type": "wnba_rest_travel_board",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "date": target_date,
        "games_only": games_only,
        "include_observed_workload": include_observed_workload,
        "team_count": len(rows),
        "teams": rows,
        "verification": {
            "board_uses_official_schedule": True,
            "rest_and_travel_are_descriptive_not_predictive": True,
        },
    }
