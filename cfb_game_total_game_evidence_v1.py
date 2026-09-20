"""Game Evidence display-only adapter for page cleanup Step 5.

Reuses the already-certified exact-event environment source. It enriches only
missing display fields and never feeds model/projection math.
"""
from __future__ import annotations

from typing import Any, Mapping

import cfb_over_under_environment_engine_v1 as environment_owner

MODEL_VERSION = "CFB GAME TOTAL GAME EVIDENCE V1 • PAGE CLEANUP STEP 5"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


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


def _environment_payload(
    game: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    day = _clean(game.get("game_date") or game.get("date"))[:10]
    scoreboard, scoreboard_attempts = environment_owner._fetch_scoreboard(day)
    event = environment_owner._resolve_event(scoreboard, game)
    if not event:
        return {}, {
            "source": "certified_environment_engine",
            "event_found": False,
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
        gust = weather.get("gust_mph")
        if gust is not None:
            try:
                out["wind_mph"] = float(gust)
                out["wind"] = f"{float(gust):.0f} mph gusts"
            except (TypeError, ValueError):
                pass

    if not _usable(out.get("weather") or out.get("forecast")):
        weather_text = _weather_text(weather, venue)
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
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "enrich_game_evidence",
]
