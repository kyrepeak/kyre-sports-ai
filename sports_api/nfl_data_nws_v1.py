"""National Weather Service adapter for NFL Game Totals environment context.

Outdoor U.S. games use the NWS points -> forecastGridData path and select the
weather interval containing the exact kickoff timestamp. Indoor games are
neutralized before any network request. No API key, sportsbook data, or model
math is used here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import math
import re
from typing import Any, Callable

import requests

from sports_api.nfl_stadium_coordinates_v1 import lookup_stadium

NWS_POINTS_URL = "https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
REQUEST_TIMEOUT_SECONDS = 10
PROVIDER = "NWS + canonical NFL stadium registry"
HEADERS = {
    "Accept": "application/geo+json,application/json",
    "User-Agent": "kyre-sports-ai/1.0 (https://github.com/kyrepeak/kyre-sports-ai)",
}

JsonGetter = Callable[..., dict[str, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_duration(value: str) -> timedelta | None:
    """Parse the subset of ISO-8601 durations emitted by NWS grid validTime."""
    match = re.fullmatch(
        r"P(?:(?P<days>\d+(?:\.\d+)?)D)?(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?(?:(?P<minutes>\d+(?:\.\d+)?)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?",
        str(value or "").strip(),
    )
    if not match:
        return None
    values = {name: float(raw or 0.0) for name, raw in match.groupdict().items()}
    duration = timedelta(
        days=values["days"],
        hours=values["hours"],
        minutes=values["minutes"],
        seconds=values["seconds"],
    )
    return duration if duration.total_seconds() > 0 else None


def _interval_contains(valid_time: Any, kickoff_utc: datetime) -> bool:
    text = str(valid_time if valid_time is not None else "").strip()
    if "/" not in text:
        return False
    start_text, duration_text = text.split("/", 1)
    start = _parse_datetime(start_text)
    duration = _parse_duration(duration_text)
    if start is None or duration is None:
        return False
    kickoff = kickoff_utc.astimezone(timezone.utc)
    return start <= kickoff < start + duration


def _grid_value(properties: dict[str, Any], field: str, kickoff_utc: datetime) -> tuple[Any, str]:
    block = properties.get(field)
    if not isinstance(block, dict):
        return None, ""
    unit = str(block.get("uom") or "").strip()
    values = block.get("values")
    if not isinstance(values, list):
        return None, unit
    for row in values:
        if not isinstance(row, dict):
            continue
        if _interval_contains(row.get("validTime"), kickoff_utc):
            return row.get("value"), unit
    return None, unit


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _temperature_f(value: Any, unit: str) -> float | None:
    number = _finite(value)
    if number is None:
        return None
    token = unit.lower()
    if "degc" in token:
        return number * 9.0 / 5.0 + 32.0
    if "degf" in token:
        return number
    return None


def _gust_mph(value: Any, unit: str) -> float | None:
    number = _finite(value)
    if number is None:
        return None
    token = unit.lower().replace(" ", "")
    if "km_h-1" in token or "km/h" in token:
        return number * 0.6213711922
    if "m_s-1" in token or "m/s" in token:
        return number * 2.2369362921
    if "mi_h-1" in token or "mph" in token:
        return number
    return None


def _precip_percent(value: Any, unit: str) -> float | None:
    number = _finite(value)
    if number is None:
        return None
    if "percent" not in unit.lower():
        return None
    return number if 0.0 <= number <= 100.0 else None


def classify_weather_pressure(temperature: Any, precipitation: Any, gust: Any) -> str:
    temp = _finite(temperature)
    precip = _finite(precipitation)
    wind_gust = _finite(gust)
    if temp is None or precip is None or wind_gust is None:
        return "UNAVAILABLE"
    if wind_gust >= 25.0 or precip >= 60.0 or temp <= 32.0 or temp >= 95.0:
        return "HIGH"
    if wind_gust >= 15.0 or precip >= 30.0 or temp <= 40.0 or temp >= 90.0:
        return "WATCH"
    return "LOW"


def extract_grid_weather(grid_payload: dict[str, Any], kickoff_utc: datetime) -> dict[str, Any]:
    """Extract exact-kickoff temperature, precipitation probability, and gust."""
    payload = grid_payload if isinstance(grid_payload, dict) else {}
    properties = payload.get("properties")
    properties = properties if isinstance(properties, dict) else {}

    temperature_raw, temperature_unit = _grid_value(properties, "temperature", kickoff_utc)
    precipitation_raw, precipitation_unit = _grid_value(
        properties, "probabilityOfPrecipitation", kickoff_utc
    )
    gust_raw, gust_unit = _grid_value(properties, "windGust", kickoff_utc)

    temperature = _temperature_f(temperature_raw, temperature_unit)
    precipitation = _precip_percent(precipitation_raw, precipitation_unit)
    gust = _gust_mph(gust_raw, gust_unit)

    diagnostics: list[str] = []
    if temperature is None:
        diagnostics.append("temperature unavailable for exact kickoff interval or unsupported unit")
    if precipitation is None:
        diagnostics.append("precipitation unavailable for exact kickoff interval or unsupported unit")
    if gust is None:
        diagnostics.append("gust unavailable for exact kickoff interval or unsupported unit")

    ready = not diagnostics
    return {
        "ready": ready,
        "temperature": float(temperature) if temperature is not None else None,
        "precipitation": float(precipitation) if precipitation is not None else None,
        "gust": float(gust) if gust is not None else None,
        "diagnostics": diagnostics,
    }


def _request_json(url: str) -> dict[str, Any]:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("NWS response was not a JSON object")
    return payload


@lru_cache(maxsize=64)
def _points(lat: float, lon: float) -> dict[str, Any]:
    return _request_json(NWS_POINTS_URL.format(lat=float(lat), lon=float(lon)))


@lru_cache(maxsize=128)
def _grid_data(url: str) -> dict[str, Any]:
    return _request_json(str(url))


_points.clear = _points.cache_clear  # type: ignore[attr-defined]
_grid_data.clear = _grid_data.cache_clear  # type: ignore[attr-defined]


def _result(
    *,
    ready: bool,
    data: dict[str, Any] | None = None,
    fields_verified: list[str] | None = None,
    diagnostics: list[str] | None = None,
) -> dict[str, Any]:
    fetched_at = _utc_now()
    return {
        "ready": bool(ready),
        "provider": PROVIDER,
        "data": dict(data or {}) if ready else {},
        "fields_verified": list(fields_verified or []) if ready else [],
        "quality": "HIGH" if ready else "UNAVAILABLE",
        "data_freshness": fetched_at,
        "fetched_at": fetched_at,
        "diagnostics": list(diagnostics or []),
    }


def fetch_environment(
    request: dict[str, Any],
    *,
    get_json: JsonGetter | None = None,
) -> dict[str, Any]:
    """Resolve canonical venue truth and NWS weather for an exact game kickoff."""
    if not isinstance(request, dict):
        return _result(ready=False, diagnostics=["environment request must be an object"])

    venue_name = str(request.get("venue_name") or "").strip()
    home_abbr = str(request.get("home_abbr") or "").strip().upper()
    stadium = lookup_stadium(venue_name, home_abbr)
    if stadium is None:
        return _result(
            ready=False,
            diagnostics=["unknown or ambiguous NFL stadium identity"],
        )

    canonical_venue = str(stadium["venue"])
    indoor = bool(stadium["indoor"])
    if indoor:
        return _result(
            ready=True,
            data={
                "venue_name": canonical_venue,
                "indoor": True,
                "weather_applies": False,
                "temperature": None,
                "precipitation": None,
                "gust": None,
                "weather_pressure": "INDOOR",
            },
            fields_verified=["venue_name", "indoor"],
        )

    kickoff = _parse_datetime(request.get("kickoff_utc"))
    if kickoff is None:
        return _result(ready=False, diagnostics=["invalid or missing kickoff_utc"])

    try:
        if get_json is None:
            points_payload = _points(float(stadium["latitude"]), float(stadium["longitude"]))
        else:
            points_url = NWS_POINTS_URL.format(
                lat=float(stadium["latitude"]),
                lon=float(stadium["longitude"]),
            )
            points_payload = get_json(points_url)
        properties = points_payload.get("properties") if isinstance(points_payload, dict) else None
        properties = properties if isinstance(properties, dict) else {}
        grid_url = str(properties.get("forecastGridData") or "").strip()
        if not grid_url.startswith("https://api.weather.gov/"):
            return _result(
                ready=False,
                diagnostics=["NWS points response missing valid forecastGridData URL"],
            )

        grid_payload = _grid_data(grid_url) if get_json is None else get_json(grid_url)
    except Exception as exc:
        return _result(
            ready=False,
            diagnostics=[f"NWS transport error: {type(exc).__name__}: {str(exc)[:180]}"],
        )

    weather = extract_grid_weather(grid_payload, kickoff)
    if weather.get("ready") is not True:
        return _result(
            ready=False,
            diagnostics=list(weather.get("diagnostics") or ["NWS exact-kickoff weather unavailable"]),
        )

    temperature = float(weather["temperature"])
    precipitation = float(weather["precipitation"])
    gust = float(weather["gust"])
    return _result(
        ready=True,
        data={
            "venue_name": canonical_venue,
            "indoor": False,
            "weather_applies": True,
            "temperature": temperature,
            "precipitation": precipitation,
            "gust": gust,
            "weather_pressure": classify_weather_pressure(
                temperature,
                precipitation,
                gust,
            ),
        },
        fields_verified=[
            "venue_name",
            "indoor",
            "temperature",
            "precipitation",
            "gust",
        ],
    )


def clear_caches() -> None:
    _points.cache_clear()
    _grid_data.cache_clear()


__all__ = [
    "HEADERS",
    "NWS_POINTS_URL",
    "PROVIDER",
    "REQUEST_TIMEOUT_SECONDS",
    "classify_weather_pressure",
    "clear_caches",
    "extract_grid_weather",
    "fetch_environment",
    "_grid_data",
    "_points",
]
