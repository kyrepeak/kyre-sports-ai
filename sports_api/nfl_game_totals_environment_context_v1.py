"""Descriptive NFL game-environment context for Game Totals page Step 7.

Exact verified slate metadata supplies game identity, home team, venue, and
kickoff. Weather acquisition is routed through the shared multi-source layer:
NWS is primary and the isolated ESPN adapter is fallback only. Indoor games
neutralize outside weather. Sportsbook data is never consumed here and has
0.0 projection influence.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import math
import re
from typing import Any
from zoneinfo import ZoneInfo

from nfl_hub_v1 import load_nfl_slate
from sports_api import nfl_data_espn_fallback_v1 as espn
from sports_api import nfl_data_nws_v1 as nws
from sports_api.nfl_data_router_v1 import route_metric

# Preserved Step-7 public constants/backward-compatible source evidence. Direct
# transport is intentionally owned by provider adapters, not this context module.
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

_ET = ZoneInfo("America/New_York")
PROVIDER = "MULTI-SOURCE NFL environment router"


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
    """Preserve the original exact-ESPN extraction contract for compatibility."""
    event = scoreboard_event if isinstance(scoreboard_event, dict) else {}
    summary = summary_payload if isinstance(summary_payload, dict) else {}
    event_id = _safe(event.get("id"))

    competitions = event.get("competitions") or []
    competition = (
        competitions[0]
        if isinstance(competitions, list)
        and len(competitions) == 1
        and isinstance(competitions[0], dict)
        else {}
    )
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
    pressure = (
        classify_weather_pressure(temperature, precipitation, gust, indoor=False)
        if weather_ready
        else "UNAVAILABLE"
    )
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


def _kickoff_utc(row: Any) -> str:
    """Convert the verified slate's ET game date/clock into an exact UTC instant."""
    try:
        game_date = _safe(row.get("game_date"))
        tip_et = _safe(row.get("tip_et"))
    except Exception:
        return ""
    if not game_date or not tip_et or tip_et.upper().startswith("TBD"):
        return ""

    clock = re.sub(r"\s+(?:ET|EST|EDT)\s*$", "", tip_et, flags=re.IGNORECASE).strip()
    try:
        eastern = datetime.strptime(f"{game_date} {clock}", "%Y-%m-%d %I:%M %p").replace(tzinfo=_ET)
    except (TypeError, ValueError):
        return ""
    return eastern.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def route_environment(request: dict[str, Any]) -> dict[str, Any]:
    """Route canonical environment data through NWS first, ESPN second."""
    return route_metric(
        "environment",
        request,
        (
            nws.fetch_environment,
            espn.fetch_environment,
        ),
    )


def _provenance(routed: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_used": _safe(routed.get("provider_used")),
        "fallback_rank": int(routed.get("fallback_rank") or 0),
        "data_freshness": _safe(routed.get("data_freshness")),
        "fields_verified": list(routed.get("fields_verified") or []),
        "quality": _safe(routed.get("quality"), "UNAVAILABLE"),
        "provider_attempts": list(routed.get("provider_attempts") or []),
    }


def _display_provider(provider_used: Any) -> str:
    provider = _safe(provider_used)
    if provider.upper().startswith("NWS"):
        return "NWS"
    return provider or PROVIDER


def _unavailable(
    event_id: str,
    diagnostics: list[str] | tuple[str, ...] | None = None,
    *,
    routed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    route = routed if isinstance(routed, dict) else {}
    return {
        "event_id": event_id,
        "ready": False,
        "venue_name": "",
        "indoor": False,
        "weather_applies": False,
        "temperature": math.nan,
        "precipitation": math.nan,
        "gust": math.nan,
        "condition_id": "",
        "weather_pressure": "UNAVAILABLE",
        "provider": _display_provider(route.get("provider_used")),
        "diagnostics": [str(item) for item in (diagnostics or route.get("diagnostics") or []) if str(item).strip()]
        or ["certified environment context unavailable"],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "provenance": _provenance(route),
    }


def _context_from_route(event_id: str, routed: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(routed, dict) or routed.get("ready") is not True:
        return _unavailable(event_id, routed=routed if isinstance(routed, dict) else {})

    data = routed.get("data") if isinstance(routed.get("data"), dict) else {}
    venue_name = _safe(data.get("venue_name"))
    indoor = data.get("indoor") is True
    temperature = _num(data.get("temperature"))
    precipitation = _num(data.get("precipitation"))
    gust = _num(data.get("gust"))

    if indoor:
        weather_applies = False
        pressure = "INDOOR"
    else:
        weather_applies = True
        pressure = classify_weather_pressure(temperature, precipitation, gust, indoor=False)
        if pressure == "UNAVAILABLE":
            return _unavailable(
                event_id,
                ["routed outdoor environment fields were non-numeric"],
                routed=routed,
            )

    return {
        "event_id": event_id,
        "ready": True,
        "venue_name": venue_name,
        "indoor": indoor,
        "weather_applies": weather_applies,
        "temperature": math.nan if indoor else float(temperature),
        "precipitation": math.nan if indoor else float(precipitation),
        "gust": math.nan if indoor else float(gust),
        "condition_id": _safe(data.get("condition_id")),
        "weather_pressure": pressure,
        "provider": _display_provider(routed.get("provider_used")),
        "diagnostics": [str(item) for item in (routed.get("diagnostics") or []) if str(item).strip()],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "provenance": _provenance(routed),
    }


def _verified_rows(day_str: str, requested: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Resolve requested event IDs from the already-certified exact slate path."""
    try:
        games, diag = load_nfl_slate(day_str)
    except Exception as exc:
        return {}, [f"verified slate transport error: {type(exc).__name__}: {str(exc)[:180]}"]

    diagnostics: list[str] = []
    if not isinstance(diag, dict) or diag.get("request_ok") is not True:
        detail = _safe(diag.get("error") if isinstance(diag, dict) else "")
        diagnostics.append(detail or "verified exact slate metadata unavailable")
        return {}, diagnostics

    by_id: dict[str, Any] = {}
    duplicate_ids: set[str] = set()
    try:
        rows = games.iterrows() if games is not None else ()
    except Exception:
        return {}, ["verified slate rows unavailable"]

    for _, row in rows:
        event_id = _safe(row.get("game_id"))
        if event_id not in requested:
            continue
        if event_id in by_id:
            duplicate_ids.add(event_id)
        else:
            by_id[event_id] = row

    for event_id in duplicate_ids:
        by_id.pop(event_id, None)
    if duplicate_ids:
        diagnostics.extend(f"ambiguous verified event identity: {event_id}" for event_id in sorted(duplicate_ids))
    return by_id, diagnostics


def build_slate_environment_context(
    day_str: str,
    event_ids: list[str] | tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    """Build routed environment context for exact requested NFL event IDs only."""
    requested = list(dict.fromkeys(_safe(event_id) for event_id in event_ids if _safe(event_id)))
    if not requested:
        return {}

    by_id, slate_diagnostics = _verified_rows(day_str, requested)
    output: dict[str, dict[str, Any]] = {}
    requests_by_id: dict[str, dict[str, Any]] = {}

    for event_id in requested:
        row = by_id.get(event_id)
        if row is None:
            detail = next(
                (item for item in slate_diagnostics if event_id in item),
                slate_diagnostics[0] if slate_diagnostics else "exact verified event not present on requested slate day",
            )
            output[event_id] = _unavailable(event_id, [detail])
            continue

        home_abbr = _safe(row.get("home_abbr")).upper()
        venue_name = _safe(row.get("venue"))
        kickoff_utc = _kickoff_utc(row)
        if not home_abbr or not venue_name or venue_name.lower() == "venue tbd" or not kickoff_utc:
            output[event_id] = _unavailable(
                event_id,
                ["verified slate missing exact home team, venue, or kickoff metadata"],
            )
            continue

        requests_by_id[event_id] = {
            "event_id": event_id,
            "day_str": _safe(day_str)[:10],
            "home_abbr": home_abbr,
            "venue_name": venue_name,
            "kickoff_utc": kickoff_utc,
        }

    if requests_by_id:
        with ThreadPoolExecutor(max_workers=min(8, len(requests_by_id))) as pool:
            futures = {
                pool.submit(route_environment, dict(request)): event_id
                for event_id, request in requests_by_id.items()
            }
            for future in as_completed(futures):
                event_id = futures[future]
                try:
                    routed = future.result()
                except Exception as exc:
                    routed = {
                        "ready": False,
                        "diagnostics": [f"environment router error: {type(exc).__name__}: {str(exc)[:180]}"],
                    }
                output[event_id] = _context_from_route(event_id, routed)

    return {event_id: output.get(event_id, _unavailable(event_id)) for event_id in requested}


__all__ = [
    "ESPN_SCOREBOARD",
    "ESPN_SUMMARY",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "VENUE_INDOOR_FIELD",
    "WEATHER_FIELDS",
    "build_slate_environment_context",
    "classify_weather_pressure",
    "extract_environment_metrics",
    "route_environment",
]
