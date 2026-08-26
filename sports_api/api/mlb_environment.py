from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-environment"])

MLB_LIVE_FEED_URL = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
MLB_VENUE_URL = "https://statsapi.mlb.com/api/v1/venues/{venue_id}"
NWS_POINTS_URL = "https://api.weather.gov/points/{latitude},{longitude}"

NWS_HEADERS = {
    "Accept": "application/geo+json",
    "User-Agent": "KyreSportsAPI/0.1 (sports analytics application)",
}


def _get_json(url: str, *, params=None, headers=None, timeout=20.0):
    try:
        response = httpx.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream request failed: {exc}",
        ) from exc

    return response.json()


def _parse_iso_datetime(value):
    if not value:
        return None

    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _extract_coordinates(venue):
    location = venue.get("location", {})
    coordinates = location.get("defaultCoordinates", {})

    latitude = coordinates.get("latitude")
    longitude = coordinates.get("longitude")

    if latitude is None or longitude is None:
        return None

    try:
        return float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None


def _venue_details(venue_id: int | None, live_venue):
    venue = live_venue or {}

    if _extract_coordinates(venue) is not None:
        return venue

    if not isinstance(venue_id, int):
        return venue

    payload = _get_json(
        MLB_VENUE_URL.format(venue_id=venue_id),
        params={"hydrate": "location"},
        timeout=15.0,
    )

    venues = (payload or {}).get("venues", [])
    return venues[0] if venues else venue


def _weather_relevance(roof_type):
    if not roof_type:
        return "unknown"

    normalized = str(roof_type).strip().lower()

    if "fixed" in normalized or "dome" in normalized:
        return "low"
    if "retract" in normalized:
        return "conditional"
    if "open" in normalized or "outdoor" in normalized:
        return "high"

    return "unknown"


def _nearest_hourly_period(periods, game_datetime):
    if not periods:
        return None

    if game_datetime is None:
        return periods[0]

    best_period = None
    best_delta = None

    for period in periods:
        start = _parse_iso_datetime(period.get("startTime"))
        if start is None:
            continue

        try:
            delta = abs((start - game_datetime).total_seconds())
        except TypeError:
            continue

        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_period = period

    return best_period or periods[0]


def _value_from_quantitative_object(value):
    if isinstance(value, dict):
        return value.get("value")
    return value


def _fetch_nws_weather(latitude: float, longitude: float, game_datetime):
    points_url = NWS_POINTS_URL.format(
        latitude=round(latitude, 4),
        longitude=round(longitude, 4),
    )

    points_payload = _get_json(
        points_url,
        headers=NWS_HEADERS,
        timeout=15.0,
    )

    if not points_payload:
        return {
            "available": False,
            "reason": "nws_point_lookup_unavailable",
        }

    properties = points_payload.get("properties", {})
    hourly_url = properties.get("forecastHourly")

    if not hourly_url:
        return {
            "available": False,
            "reason": "nws_hourly_forecast_url_missing",
            "grid_id": properties.get("gridId"),
            "grid_x": properties.get("gridX"),
            "grid_y": properties.get("gridY"),
        }

    hourly_payload = _get_json(
        hourly_url,
        headers=NWS_HEADERS,
        timeout=15.0,
    )

    periods = (hourly_payload or {}).get("properties", {}).get("periods", [])
    period = _nearest_hourly_period(periods, game_datetime)

    if period is None:
        return {
            "available": False,
            "reason": "nws_hourly_period_missing",
            "grid_id": properties.get("gridId"),
            "grid_x": properties.get("gridX"),
            "grid_y": properties.get("gridY"),
        }

    return {
        "available": True,
        "source": "National Weather Service",
        "forecast_hour_start": period.get("startTime"),
        "forecast_hour_end": period.get("endTime"),
        "temperature": period.get("temperature"),
        "temperature_unit": period.get("temperatureUnit"),
        "wind_speed": period.get("windSpeed"),
        "wind_direction": period.get("windDirection"),
        "short_forecast": period.get("shortForecast"),
        "precipitation_probability_pct": _value_from_quantitative_object(
            period.get("probabilityOfPrecipitation")
        ),
        "relative_humidity_pct": _value_from_quantitative_object(
            period.get("relativeHumidity")
        ),
        "dewpoint": _value_from_quantitative_object(period.get("dewpoint")),
        "grid_id": properties.get("gridId"),
        "grid_x": properties.get("gridX"),
        "grid_y": properties.get("gridY"),
        "forecast_office": properties.get("forecastOffice"),
        "hourly_forecast_url": hourly_url,
    }


def _normalize_park(venue):
    location = venue.get("location", {})
    coordinates = location.get("defaultCoordinates", {})
    field_info = venue.get("fieldInfo", {})

    roof_type = field_info.get("roofType")

    return {
        "venue_id": venue.get("id"),
        "name": venue.get("name"),
        "active": venue.get("active"),
        "location": {
            "city": location.get("city"),
            "state": location.get("state"),
            "state_abbreviation": location.get("stateAbbrev"),
            "country": location.get("country"),
            "latitude": coordinates.get("latitude"),
            "longitude": coordinates.get("longitude"),
        },
        "field": {
            "turf_type": field_info.get("turfType"),
            "roof_type": roof_type,
            "left_line_ft": field_info.get("leftLine"),
            "left_center_ft": field_info.get("leftCenter"),
            "center_ft": field_info.get("center"),
            "right_center_ft": field_info.get("rightCenter"),
            "right_line_ft": field_info.get("rightLine"),
        },
        "weather_relevance": _weather_relevance(roof_type),
    }


@router.get("/games/{game_pk}/environment")
def get_mlb_game_environment(game_pk: int):
    game_url = MLB_LIVE_FEED_URL.format(game_pk=game_pk)
    payload = _get_json(game_url, timeout=20.0)

    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"MLB game {game_pk} was not found.",
        )

    game_data = payload.get("gameData", {})
    datetime_data = game_data.get("datetime", {})
    status = game_data.get("status", {})
    teams = game_data.get("teams", {})
    live_venue = game_data.get("venue", {})

    venue_id = live_venue.get("id")
    venue = _venue_details(venue_id, live_venue)
    coordinates = _extract_coordinates(venue)

    game_datetime = _parse_iso_datetime(datetime_data.get("dateTime"))

    if coordinates is None:
        weather = {
            "available": False,
            "reason": "venue_coordinates_missing",
        }
    else:
        latitude, longitude = coordinates
        weather = _fetch_nws_weather(latitude, longitude, game_datetime)

    park = _normalize_park(venue)

    return {
        "sources": ["MLB Stats API", "National Weather Service"],
        "game_pk": game_pk,
        "official_date": datetime_data.get("officialDate"),
        "game_datetime_utc": datetime_data.get("dateTime"),
        "status": {
            "abstract_game_state": status.get("abstractGameState"),
            "detailed_state": status.get("detailedState"),
        },
        "matchup": {
            "away_team_id": teams.get("away", {}).get("id"),
            "away_team_name": teams.get("away", {}).get("name"),
            "home_team_id": teams.get("home", {}).get("id"),
            "home_team_name": teams.get("home", {}).get("name"),
        },
        "park": park,
        "weather": weather,
        "environment_readiness": {
            "venue_identified": park.get("venue_id") is not None,
            "coordinates_available": coordinates is not None,
            "weather_available": weather.get("available") is True,
            "weather_relevance": park.get("weather_relevance"),
        },
        "modeling_note": (
            "Weather is an external environment input. Retractable-roof stadiums require "
            "separate roof-state confirmation before treating outdoor conditions as fully active."
        ),
    }
