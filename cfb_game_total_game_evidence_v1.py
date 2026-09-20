"""Game Evidence display-only adapter for page cleanup Step 5.

Reuses the already-certified exact-event environment source. It enriches only
missing display fields and never feeds model/projection math.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import cfb_over_under_environment_engine_v1 as environment_owner

MODEL_VERSION = "CFB GAME TOTAL GAME EVIDENCE V1 • PAGE CLEANUP STEP 5"
ENVIRONMENT_CACHE_PATH = Path(__file__).resolve().parent / "data" / "cfb_game_total_environment_cache_v1.json"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PRODUCTION_EVIDENCE_CACHE_PATH = Path(__file__).resolve().parent / "data" / "cfb_game_total_production_evidence_v1.json"
LOCAL_ENV_CACHE_PATH = Path(__file__).resolve().parent / "data" / "cfb_game_total_environment_cache_v1.json"
VERIFIED_CACHE_PATH = Path(__file__).resolve().parent / "data" / "cfb_game_total_environment_cache_v1.json"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _usable(value: Any) -> bool:
    text = _clean(value)
    return bool(
        text
        and text != "—"
        and "unavailable" not in text.lower()
        and "pending" not in text.lower()
    )


def _kickoff(game: Mapping[str, Any]) -> str:
    for key in (
        "kickoff",
        "kickoff_iso",
        "date",
        "start_date",
        "start_time",
        "commence_time",
        "game_time",
    ):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _status_text(event: Mapping[str, Any]) -> str:
    status = event.get("status") or {}
    if not isinstance(status, Mapping):
        return ""
    kind = status.get("type") or {}
    if not isinstance(kind, Mapping):
        kind = {}
    return _clean(
        kind.get("shortDetail")
        or kind.get("detail")
        or kind.get("description")
        or kind.get("name")
        or status.get("displayClock")
    )


def _event_kickoff(event: Mapping[str, Any]) -> str:
    return _clean(event.get("date"))


def _competition_venue(event: Mapping[str, Any]) -> dict[str, Any]:
    competitions = event.get("competitions") or []
    if not competitions or not isinstance(competitions[0], Mapping):
        return {}
    venue = competitions[0].get("venue") or {}
    return dict(venue) if isinstance(venue, Mapping) else {}


def _cached_environment_payload(
    game: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return only an exact, identity-matched checked-in environment row."""
    event_id = _clean(game.get("espn_event_id") or game.get("event_id"))
    if not event_id:
        return None
    try:
        payload = json.loads(ENVIRONMENT_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if int(payload.get("version") or 0) != 1:
        return None
    events = payload.get("events")
    if not isinstance(events, Mapping):
        return None
    row = events.get(event_id)
    if not isinstance(row, Mapping):
        return None

    row_day = _clean(row.get("game_date"))[:10]
    game_day = _clean(game.get("game_date") or game.get("date"))[:10]
    if game_day and row_day and game_day != row_day:
        return None

    for key in ("away_team", "home_team"):
        expected = _clean(game.get(key)).casefold()
        actual = _clean(row.get(key)).casefold()
        if expected and actual and expected != actual:
            return None

    venue = row.get("venue") if isinstance(row.get("venue"), Mapping) else {}
    weather = row.get("weather") if isinstance(row.get("weather"), Mapping) else {}
    if not (
        venue.get("ready") is True
        and weather.get("ready") is True
        and weather.get("temperature_f") is not None
        and weather.get("gust_mph") is not None
    ):
        return None

    return {
        "event_id": event_id,
        "kickoff": _clean(row.get("kickoff")),
        "status": _clean(row.get("status")),
        "weather": dict(weather),
        "venue": dict(venue),
    }, {
        "source": "checked-in-verified-environment-cache-v1",
        "event_found": True,
        "event_id": event_id,
        "exact_event_id_used": True,
        "cache_used": True,
        "summary_identity_verified": True,
        "cache_generated_at": payload.get("generated_at"),
    }


def _verified_environment_cache(
    game: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        payload = json.loads(VERIFIED_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}, {}

    raw_events = payload.get("events") if isinstance(payload, Mapping) else []
    if isinstance(raw_events, Mapping):
        rows = [
            row for row in raw_events.values()
            if isinstance(row, Mapping)
        ]
    elif isinstance(raw_events, list):
        rows = [
            row for row in raw_events
            if isinstance(row, Mapping)
        ]
    else:
        return {}, {}

    event_id = _clean(game.get("espn_event_id") or game.get("event_id"))
    target_day = _clean(game.get("game_date") or game.get("date"))[:10]
    away_name = _clean(game.get("away_team")).casefold()
    home_name = _clean(game.get("home_team")).casefold()

    matches: list[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if event_id and _clean(row.get("event_id")) == event_id:
            matches.append(row)
            continue
        if (
            target_day
            and away_name
            and home_name
            and _clean(row.get("game_date")) == target_day
            and _clean(row.get("away_team")).casefold() == away_name
            and _clean(row.get("home_team")).casefold() == home_name
        ):
            matches.append(row)

    # Deduplicate an event that matched both exact ID and exact names.
    unique: dict[str, Mapping[str, Any]] = {}
    for row in matches:
        key = _clean(row.get("event_id")) or json.dumps(dict(row), sort_keys=True)
        unique[key] = row
    if len(unique) != 1:
        return {}, {}

    row = dict(next(iter(unique.values())))
    return {
        "event_id": _clean(row.get("event_id")),
        "kickoff": _clean(row.get("kickoff")),
        "status": _clean(row.get("status")),
        "venue": dict(row.get("venue") or {}),
        "weather": dict(row.get("weather") or {}),
    }, {
        "source": "checked-in verified Step 5 exact-event cache",
        "event_found": True,
        "event_id": _clean(row.get("event_id")),
        "cache_used": True,
        "verified_cache_used": True,
        "verified_at": payload.get("verified_at"),
        "proof_run_id": payload.get("proof_run_id"),
    }


def _local_environment_payload(
    game: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    event_id = _clean(game.get("espn_event_id") or game.get("event_id"))
    if not event_id:
        return {}, {"source": "checked-in-environment-cache", "event_found": False}
    try:
        payload = json.loads(LOCAL_ENV_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}, {"source": "checked-in-environment-cache", "event_found": False}
    events = payload.get("events") if isinstance(payload, Mapping) else {}
    row = events.get(event_id) if isinstance(events, Mapping) else None
    if not isinstance(row, Mapping):
        return {}, {"source": "checked-in-environment-cache", "event_found": False}

    weather_text = _clean(row.get("weather"))
    wind_text = _clean(row.get("wind"))
    temperature = row.get("temperature_f")
    venue_name = _clean(row.get("venue"))
    location = _clean(row.get("venue_location"))
    city, state = "", ""
    if location:
        parts = [part.strip() for part in location.split(",", 1)]
        city = parts[0] if parts else ""
        state = parts[1] if len(parts) > 1 else ""

    return {
        "event_id": event_id,
        "kickoff": _clean(row.get("kickoff")),
        "status": _clean(row.get("status")),
        "weather": {
            "ready": bool(weather_text or temperature is not None or wind_text),
            "temperature_f": temperature,
            "source": "checked-in certified environment cache",
            "display_text": weather_text,
            "wind_text": wind_text,
        },
        "venue": {
            "ready": bool(venue_name),
            "name": venue_name,
            "city": city,
            "state": state,
            "indoor": False,
        },
        "cached_weather_text": weather_text,
        "cached_wind_text": wind_text,
    }, {
        "source": "checked-in-environment-cache",
        "event_found": True,
        "event_id": event_id,
        "exact_event_id_used": True,
        "summary_identity_verified": True,
        "network_used": False,
    }


def _environment_payload(
    game: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    cached, cached_diag = _verified_environment_cache(game)
    if cached:
        return cached, cached_diag

    cached = _cached_environment_payload(game)
    if cached is not None:
        return cached

    # Fast path: the selected schedule/deep-reconciliation row already carries
    # an exact verified ESPN event ID. Do not rediscover it through scoreboard
    # matching when direct exact-event summary access is available.
    exact_event_id = _clean(
        game.get("espn_event_id")
        or game.get("event_id")
    )
    if exact_event_id:
        summary, summary_attempts = environment_owner._fetch_summary(
            exact_event_id
        )
        identity_ok = environment_owner._summary_identity_matches(
            summary,
            exact_event_id,
        )
        if identity_ok:
            weather = environment_owner._weather(summary)
            venue = environment_owner._venue(summary)
            return {
                "event_id": exact_event_id,
                "kickoff": _kickoff(game),
                "status": _clean(
                    game.get("status")
                    or game.get("game_status")
                    or game.get("status_detail")
                ),
                "weather": dict(weather or {}),
                "venue": dict(venue or {}),
            }, {
                "source": "certified_environment_engine_exact_event_summary",
                "event_found": True,
                "event_id": exact_event_id,
                "exact_event_id_used": True,
                "summary_identity_verified": True,
                "summary_attempts": summary_attempts,
            }

    # Fallback only when no usable exact event ID/summary is available.
    day = _clean(game.get("game_date") or game.get("date"))[:10]
    scoreboard, scoreboard_attempts = environment_owner._fetch_scoreboard(day)
    event = environment_owner._resolve_event(scoreboard, game)
    if not event:
        return {}, {
            "source": "certified_environment_engine",
            "event_found": False,
            "exact_event_id_used": bool(exact_event_id),
            "scoreboard_attempts": scoreboard_attempts,
        }

    event_id = _clean(event.get("id"))
    summary, summary_attempts = environment_owner._fetch_summary(event_id)
    identity_ok = environment_owner._summary_identity_matches(summary, event_id)
    weather = environment_owner._weather(summary) if identity_ok else {}
    venue = environment_owner._venue(summary) if identity_ok else {}

    if not venue.get("ready"):
        fallback_venue = _competition_venue(event)
        address = fallback_venue.get("address") or {}
        if not isinstance(address, Mapping):
            address = {}
        name = _clean(
            fallback_venue.get("fullName")
            or fallback_venue.get("name")
        )
        if name:
            venue = {
                "ready": True,
                "name": name,
                "city": _clean(address.get("city")),
                "state": _clean(address.get("state")),
                "indoor": fallback_venue.get("indoor") is True,
            }

    return {
        "event_id": event_id,
        "kickoff": _event_kickoff(event),
        "status": _status_text(event),
        "weather": dict(weather or {}),
        "venue": dict(venue or {}),
    }, {
        "source": "certified_environment_engine",
        "event_found": True,
        "event_id": event_id,
        "exact_event_id_used": False,
        "summary_identity_verified": bool(identity_ok),
        "scoreboard_attempts": scoreboard_attempts,
        "summary_attempts": summary_attempts,
    }

def _weather_text(weather: Mapping[str, Any], venue: Mapping[str, Any]) -> str:
    if venue.get("indoor") is True:
        return "Indoor"
    precip = weather.get("precipitation_pct")
    try:
        if precip is not None:
            return f"{float(precip):.0f}% precipitation"
    except (TypeError, ValueError):
        pass
    condition_id = _clean(weather.get("condition_id"))
    if condition_id:
        return f"Forecast condition {condition_id}"
    return ""


def enrich_game_evidence(
    display_game: Mapping[str, Any],
    source_game: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    out = dict(display_game or {})
    source = dict(source_game or display_game or {})

    # Keep every already-good field. Only activate the exact-event fallback when
    # at least one required Game Evidence field is missing.
    kickoff_before = _kickoff(out)
    venue_before = _clean(out.get("venue"))
    temp_before = out.get("temperature")
    wind_before = out.get("wind") or out.get("wind_mph")
    status_before = _clean(out.get("status") or out.get("game_status"))

    needs_fallback = not all((
        _usable(venue_before),
        bool(kickoff_before),
        temp_before not in (None, "", "—"),
        _usable(wind_before),
        _usable(status_before),
    ))

    env: dict[str, Any] = {}
    diag: dict[str, Any] = {
        "version": MODEL_VERSION,
        "fallback_used": False,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }
    if needs_fallback:
        env, env_diag = _local_environment_payload(source)
        if not env:
            env, env_diag = _environment_payload(source)
        diag.update(env_diag)
        diag["fallback_used"] = bool(env)

    venue = env.get("venue") if isinstance(env.get("venue"), Mapping) else {}
    weather = env.get("weather") if isinstance(env.get("weather"), Mapping) else {}

    if not _usable(out.get("venue")) and _usable(venue.get("name")):
        out["venue"] = _clean(venue.get("name"))

    if not _usable(
        out.get("venue_location")
        or out.get("location")
        or out.get("city")
    ):
        city = _clean(venue.get("city"))
        state = _clean(venue.get("state"))
        location = ", ".join(x for x in (city, state) if x)
        if location:
            out["venue_location"] = location

    if out.get("temperature") in (None, "", "—"):
        temp = weather.get("temperature_f")
        if temp is not None:
            out["temperature"] = temp

    if not _usable(out.get("wind") or out.get("wind_mph")):
        cached_wind = _clean(env.get("cached_wind_text"))
        if cached_wind:
            out["wind"] = cached_wind
        else:
            gust = weather.get("gust_mph")
            if gust is not None:
                try:
                    out["wind_mph"] = float(gust)
                    out["wind"] = f"{float(gust):.0f} mph gusts"
                except (TypeError, ValueError):
                    pass

    if not _usable(out.get("weather") or out.get("forecast")):
        cached_weather = _clean(env.get("cached_weather_text"))
        weather_text = cached_weather or _weather_text(weather, venue)
        if weather_text:
            out["weather"] = weather_text

    if not _kickoff(out) and _usable(env.get("kickoff")):
        out["kickoff_iso"] = _clean(env.get("kickoff"))
        out["date"] = _clean(env.get("kickoff"))

    if not _usable(out.get("status") or out.get("game_status")) and _usable(env.get("status")):
        out["status"] = _clean(env.get("status"))

    weather_source = _clean(weather.get("source"))
    if weather_source:
        out["weather_source"] = weather_source
    if env.get("event_id"):
        out["game_evidence_event_id"] = _clean(env.get("event_id"))

    required = {
        "venue": _usable(out.get("venue")),
        "kickoff": bool(_kickoff(out)),
        "temperature": out.get("temperature") not in (None, "", "—"),
        "wind": _usable(out.get("wind") or out.get("wind_mph")),
        "status": _usable(out.get("status") or out.get("game_status")),
    }
    weather_context = _usable(out.get("weather") or out.get("forecast"))
    data_green = all(required.values()) and weather_context

    diag.update({
        "required": required,
        "weather_context": bool(weather_context),
        "verified_count": sum(required.values()) + int(bool(weather_context)),
        "required_count": 6,
        "data_green": bool(data_green),
    })
    out["game_evidence_data_green"] = bool(data_green)
    out["game_evidence_source"] = (
        "existing verified display fields + certified exact-event environment fallback"
        if diag.get("fallback_used")
        else "existing verified display fields"
    )
    return out, diag


__all__ = [
    "PRODUCTION_EVIDENCE_CACHE_PATH",
    "ENVIRONMENT_CACHE_PATH",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VERIFIED_CACHE_PATH",
    "enrich_game_evidence",
]
