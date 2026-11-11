"""Display-only CFB Moneyline team identity + logo resolver.

Uses the ESPN scoreboard payload already fetched by the verified schedule layer.
No projection, probability, calibration, ranking, sportsbook, or team-data values
are calculated or changed here.
"""
from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import urlparse

SOURCE = "ESPN College Football scoreboard"


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def initials(name: Any) -> str:
    text = _text(name)
    if not text:
        return "CF"
    words = re.findall(r"[A-Za-z0-9]+", text)
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    token = words[0] if words else text
    return token[:2].upper()


def _safe_logo_url(value: Any) -> str:
    url = _text(value)
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    if parsed.scheme != "https" or not parsed.netloc:
        return ""
    return url


def _logo_from_team(team: Mapping[str, Any]) -> str:
    direct = _safe_logo_url(team.get("logo"))
    if direct:
        return direct
    for logo in team.get("logos") or []:
        if not isinstance(logo, Mapping):
            continue
        href = _safe_logo_url(logo.get("href"))
        if href:
            return href
    return ""


def _fallback_side(name: Any) -> dict[str, str]:
    clean = _text(name)
    return {
        "team_id": "",
        "display_name": clean,
        "short_name": clean,
        "logo_url": "",
        "fallback": initials(clean),
    }


def _side_identity(competitor: Mapping[str, Any], fallback_name: Any) -> dict[str, str]:
    team = competitor.get("team") or {}
    if not isinstance(team, Mapping):
        return _fallback_side(fallback_name)
    display = _text(team.get("displayName") or fallback_name)
    short = _text(team.get("shortDisplayName") or team.get("location") or display)
    return {
        "team_id": _text(team.get("id")),
        "display_name": display,
        "short_name": short,
        "logo_url": _logo_from_team(team),
        "fallback": initials(short or display or fallback_name),
    }


def resolve_game_identities(
    game: Mapping[str, Any],
    espn_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Resolve away/home identity by exact verified ESPN event id only."""
    away_fallback = _fallback_side(game.get("away_team"))
    home_fallback = _fallback_side(game.get("home_team"))
    event_id = _text(game.get("espn_event_id"))
    payload = espn_payload if isinstance(espn_payload, Mapping) else {}

    if not event_id:
        return {"away": away_fallback, "home": home_fallback, "source": "fallback initials"}

    for event in payload.get("events") or []:
        if not isinstance(event, Mapping) or _text(event.get("id")) != event_id:
            continue
        competitions = event.get("competitions") or []
        if not competitions or not isinstance(competitions[0], Mapping):
            break
        sides: dict[str, Mapping[str, Any]] = {}
        for competitor in competitions[0].get("competitors") or []:
            if not isinstance(competitor, Mapping):
                continue
            side = _text(competitor.get("homeAway")).lower()
            if side in {"away", "home"}:
                sides[side] = competitor
        away = _side_identity(sides.get("away") or {}, game.get("away_team"))
        home = _side_identity(sides.get("home") or {}, game.get("home_team"))
        return {"away": away, "home": home, "source": SOURCE}

    return {"away": away_fallback, "home": home_fallback, "source": "fallback initials"}


__all__ = ["SOURCE", "initials", "resolve_game_identities"]
