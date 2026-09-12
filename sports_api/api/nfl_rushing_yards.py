"""Exact-ID NFL Rushing Yards data bridge for the Kyre Sports API.

This endpoint is intentionally data-only. It verifies the requested ESPN event
ID against ESPN's event payload and exposes exact-ID rushing boxscore rows when
they exist. It does not project, grade, price, rank, or size wagers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/nfl", tags=["nfl-rushing-yards"])

ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
SCHEMA_VERSION = "nfl_rushing_yards_data_v1"
UPSTREAM_TIMEOUT_SECONDS = 10.0


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _as_number(value: Any):
    text = _safe(value).replace(",", "")
    if not text or text in {"--", "-"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _event_identity(payload: dict) -> str:
    header = payload.get("header") or {}
    direct = _safe(header.get("id"))
    if direct:
        return direct
    competitions = header.get("competitions") or []
    if competitions and isinstance(competitions[0], dict):
        return _safe(competitions[0].get("id"))
    return ""


def _matchup(payload: dict) -> dict:
    header = payload.get("header") or {}
    competitions = header.get("competitions") or []
    competition = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    competitors = competition.get("competitors") or []

    sides: dict[str, dict] = {}
    for competitor in competitors:
        if not isinstance(competitor, dict):
            continue
        home_away = _safe(competitor.get("homeAway")).lower()
        team = competitor.get("team") or {}
        team_id = _safe(team.get("id"))
        if home_away not in {"home", "away"} or not team_id.isdigit():
            continue
        sides[home_away] = {
            "official_team_id": team_id,
            "name": _safe(team.get("displayName") or team.get("name")),
            "abbreviation": _safe(team.get("abbreviation")),
        }

    return {
        "away": sides.get("away", {}),
        "home": sides.get("home", {}),
        "status": _safe((competition.get("status") or {}).get("type", {}).get("name")),
        "date": _safe(competition.get("date")),
        "venue": _safe((competition.get("venue") or {}).get("fullName")),
    }


def _rushing_players(payload: dict, event_id: str) -> list[dict]:
    boxscore = payload.get("boxscore") or {}
    team_groups = boxscore.get("players") or []
    rows: list[dict] = []
    seen: set[str] = set()

    for group in team_groups:
        if not isinstance(group, dict):
            continue
        team = group.get("team") or {}
        team_id = _safe(team.get("id"))
        if not team_id.isdigit():
            continue

        statistics = group.get("statistics") or []
        for category in statistics:
            if not isinstance(category, dict):
                continue
            category_name = _safe(category.get("name") or category.get("displayName")).lower()
            if "rush" not in category_name:
                continue

            labels = [str(label).strip().upper() for label in (category.get("labels") or [])]
            keys = [str(key).strip().lower() for key in (category.get("keys") or [])]
            athletes = category.get("athletes") or []
            for item in athletes:
                if not isinstance(item, dict):
                    continue
                athlete = item.get("athlete") or {}
                athlete_id = _safe(athlete.get("id"))
                if not athlete_id.isdigit() or athlete_id in seen:
                    continue

                raw_stats = item.get("stats") or []
                by_label = {
                    labels[index]: raw_stats[index]
                    for index in range(min(len(labels), len(raw_stats)))
                }
                by_key = {
                    keys[index]: raw_stats[index]
                    for index in range(min(len(keys), len(raw_stats)))
                }

                def pick(*names: str):
                    for name in names:
                        upper = name.upper()
                        lower = name.lower()
                        if upper in by_label:
                            return by_label[upper]
                        if lower in by_key:
                            return by_key[lower]
                    return None

                carries = _as_number(pick("CAR", "rushingAttempts", "attempts"))
                rushing_yards = _as_number(pick("YDS", "rushingYards", "yards"))
                yards_per_carry = _as_number(pick("AVG", "yardsPerRushAttempt", "yardsPerCarry"))
                rushing_tds = _as_number(pick("TD", "rushingTouchdowns", "touchdowns"))
                long_rush = _as_number(pick("LONG", "longRushing", "long"))

                seen.add(athlete_id)
                rows.append(
                    {
                        "official_event_id": event_id,
                        "official_athlete_id": athlete_id,
                        "official_team_id": team_id,
                        "player_name": _safe(athlete.get("displayName") or athlete.get("fullName")),
                        "position": _safe((athlete.get("position") or {}).get("abbreviation")),
                        "carries": carries,
                        "rushing_yards": rushing_yards,
                        "yards_per_carry": yards_per_carry,
                        "rushing_touchdowns": rushing_tds,
                        "long_rush": long_rush,
                        "source": "ESPN exact-event boxscore",
                    }
                )

    return rows


@router.get("/rushing-yards")
def get_nfl_rushing_yards(
    event_id: str = Query(..., min_length=1, pattern=r"^\d+$"),
):
    """Return exact-event NFL rushing data without fuzzy or synthetic identity."""
    requested_event_id = _safe(event_id)
    try:
        response = httpx.get(
            ESPN_SUMMARY_URL,
            params={"event": requested_event_id},
            timeout=UPSTREAM_TIMEOUT_SECONDS,
            headers={"Accept": "application/json", "User-Agent": "KyreSportsAPI/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"NFL upstream request failed for exact event {requested_event_id}: {type(exc).__name__}",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="NFL upstream returned an invalid payload")

    official_event_id = _event_identity(payload)
    if official_event_id != requested_event_id:
        raise HTTPException(
            status_code=409,
            detail="NFL upstream official event identity mismatch",
        )

    players = _rushing_players(payload, requested_event_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "ready": True,
        "data_available": bool(players),
        "official_event_id": requested_event_id,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "players": players,
        "matchup": _matchup(payload),
        "identity": {
            "fuzzy_matching": False,
            "player_name_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "data_semantics": {
            "model_enabled": False,
            "projection_enabled": False,
            "market_enabled": False,
            "projection_weight": 0.0,
            "stake_sizing_enabled": False,
        },
        "source": {
            "provider": "ESPN",
            "endpoint": "event summary",
            "identity_authority": "official ESPN event/athlete/team IDs",
        },
    }


__all__ = ["SCHEMA_VERSION", "get_nfl_rushing_yards", "router"]
