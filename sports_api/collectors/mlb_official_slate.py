"""MLB Step 19A — official daily slate ingestion.

This module owns only the official MLB schedule boundary. It does not call
sportsbook providers, start runtime workers, persist checkpoints, run models,
or emit actionable/wagering output.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import os
from typing import Any
from zoneinfo import ZoneInfo

import requests


SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
SOURCE_NAME = "MLB Stats API"
DEFAULT_TIMEOUT_SECONDS = 10.0
MLB_SPORT_ID = 1


class MLBOfficialSlateError(RuntimeError):
    """Fail-closed error raised at the Step 19A official-data boundary."""

    def __init__(self, category: str, message: str) -> None:
        self.category = str(category)
        self.message = str(message)
        super().__init__(f"{self.category}: {self.message}")


def _timeout_seconds(explicit: float | None) -> float:
    raw: Any = explicit
    if raw is None:
        raw = (
            os.getenv("MLB_OFFICIAL_SLATE_TIMEOUT_SECONDS")
            or os.getenv("MLB_LIVE_STATE_TIMEOUT_SECONDS")
            or DEFAULT_TIMEOUT_SECONDS
        )
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_TIMEOUT_SECONDS


def _nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _required_positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise MLBOfficialSlateError("malformed_payload", f"{field} must be a positive integer")
    return value


def _optional_positive_int(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    return _required_positive_int(value, field=field)


def _optional_bool(value: Any, *, field: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise MLBOfficialSlateError("malformed_payload", f"{field} must be boolean when present")
    return value


def _normalize_status(status: Mapping[str, Any]) -> str:
    abstract = (_nonempty_string(status.get("abstractGameState")) or "").casefold()
    detailed = (_nonempty_string(status.get("detailedState")) or "").casefold()
    text = f"{abstract} {detailed}"

    if "postpon" in text:
        return "postponed"
    if "cancel" in text:
        return "cancelled"
    if "suspend" in text:
        return "suspended"
    if "delay" in text:
        return "delayed"
    if "live" in text or "in progress" in text or "manager challenge" in text:
        return "in_progress"
    if "final" in text or "completed early" in text:
        return "final"
    if "preview" in text or "scheduled" in text or "pre-game" in text:
        return "scheduled"
    return "unknown"


def _normalize_team(side: Any, *, side_name: str) -> dict[str, Any]:
    if not isinstance(side, Mapping):
        raise MLBOfficialSlateError("malformed_payload", f"{side_name} team side is missing")
    team = side.get("team")
    if not isinstance(team, Mapping):
        raise MLBOfficialSlateError("malformed_payload", f"{side_name} team object is missing")

    team_id = _required_positive_int(team.get("id"), field=f"{side_name}.team.id")
    team_name = _nonempty_string(team.get("name"))
    if team_name is None:
        raise MLBOfficialSlateError("malformed_payload", f"{side_name}.team.name is missing")
    return {"id": team_id, "name": team_name}


def _normalize_probable_pitcher(side: Any, *, side_name: str) -> dict[str, Any] | None:
    if not isinstance(side, Mapping):
        return None
    pitcher = side.get("probablePitcher")
    if pitcher is None:
        return None
    if not isinstance(pitcher, Mapping):
        raise MLBOfficialSlateError(
            "malformed_payload", f"{side_name}.probablePitcher must be an object"
        )

    pitcher_id = _required_positive_int(
        pitcher.get("id"), field=f"{side_name}.probablePitcher.id"
    )
    pitcher_name = _nonempty_string(pitcher.get("fullName")) or _nonempty_string(
        pitcher.get("name")
    )
    if pitcher_name is None:
        raise MLBOfficialSlateError(
            "malformed_payload", f"{side_name}.probablePitcher name is missing"
        )
    return {"id": pitcher_id, "name": pitcher_name}


def _normalize_game(game: Any) -> dict[str, Any]:
    if not isinstance(game, Mapping):
        raise MLBOfficialSlateError("malformed_payload", "schedule game must be an object")

    game_pk = _required_positive_int(game.get("gamePk"), field="gamePk")
    game_date = _nonempty_string(game.get("gameDate"))
    if game_date is None:
        raise MLBOfficialSlateError("malformed_payload", "gameDate is missing")

    teams = game.get("teams")
    status = game.get("status")
    if not isinstance(teams, Mapping):
        raise MLBOfficialSlateError("malformed_payload", "teams must be an object")
    if not isinstance(status, Mapping):
        raise MLBOfficialSlateError("malformed_payload", "status must be an object")

    away_side = teams.get("away")
    home_side = teams.get("home")
    normalized_status = _normalize_status(status)
    doubleheader_code = _nonempty_string(game.get("doubleHeader"))
    game_number = _optional_positive_int(game.get("gameNumber"), field="gameNumber")

    return {
        "game_pk": game_pk,
        "game_date": game_date,
        "official_date": _nonempty_string(game.get("officialDate")),
        "game_type": _nonempty_string(game.get("gameType")),
        "status": normalized_status,
        "status_detail": _nonempty_string(status.get("detailedState")),
        "status_code": _nonempty_string(status.get("statusCode")),
        "start_time_tbd": _optional_bool(status.get("startTimeTBD"), field="startTimeTBD"),
        "away_team": _normalize_team(away_side, side_name="away"),
        "home_team": _normalize_team(home_side, side_name="home"),
        "away_probable_pitcher": _normalize_probable_pitcher(away_side, side_name="away"),
        "home_probable_pitcher": _normalize_probable_pitcher(home_side, side_name="home"),
        "doubleheader": bool(
            (doubleheader_code is not None and doubleheader_code.upper() != "N")
            or (game_number is not None and game_number > 1)
        ),
        "doubleheader_code": doubleheader_code,
        "game_number": game_number,
        "series_game_number": _optional_positive_int(
            game.get("seriesGameNumber"), field="seriesGameNumber"
        ),
        "scheduled_innings": _optional_positive_int(
            game.get("scheduledInnings"), field="scheduledInnings"
        ),
        "reschedule_date": _nonempty_string(game.get("rescheduleDate")),
        "is_postponed": normalized_status == "postponed",
        "is_cancelled": normalized_status == "cancelled",
    }


def _extract_games(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise MLBOfficialSlateError("malformed_payload", "schedule response must be an object")
    dates = payload.get("dates")
    if not isinstance(dates, list):
        raise MLBOfficialSlateError("malformed_payload", "schedule response dates must be a list")

    normalized: list[dict[str, Any]] = []
    seen_game_pks: set[int] = set()
    for date_entry in dates:
        if not isinstance(date_entry, Mapping):
            raise MLBOfficialSlateError("malformed_payload", "schedule date entry must be an object")
        games = date_entry.get("games", [])
        if not isinstance(games, list):
            raise MLBOfficialSlateError("malformed_payload", "schedule date games must be a list")
        for raw_game in games:
            game = _normalize_game(raw_game)
            if game["game_pk"] in seen_game_pks:
                raise MLBOfficialSlateError(
                    "malformed_payload", f"duplicate gamePk {game['game_pk']}"
                )
            seen_game_pks.add(game["game_pk"])
            normalized.append(game)

    declared_total = payload.get("totalGames")
    if declared_total is not None:
        if isinstance(declared_total, bool) or not isinstance(declared_total, int) or declared_total < 0:
            raise MLBOfficialSlateError("malformed_payload", "totalGames must be a non-negative integer")
        if declared_total != len(normalized):
            raise MLBOfficialSlateError(
                "malformed_payload",
                f"totalGames mismatch: provider={declared_total} normalized={len(normalized)}",
            )

    normalized.sort(key=lambda item: (item["game_date"], item["game_pk"]))
    return normalized


def _requested_date(value: str | date | None) -> str:
    if value is None:
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _nonempty_string(value)
    if text is None:
        raise MLBOfficialSlateError("invalid_request", "slate_date must be a non-empty ISO date")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise MLBOfficialSlateError("invalid_request", "slate_date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != text:
        raise MLBOfficialSlateError("invalid_request", "slate_date must use canonical YYYY-MM-DD")
    return text


def collect_official_mlb_slate(
    *,
    slate_date: str | date | None = None,
    session: Any | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Collect and normalize one official MLB daily slate, failing closed on bad data."""

    requested_date = _requested_date(slate_date)
    client = session or requests
    params = {
        "sportId": MLB_SPORT_ID,
        "date": requested_date,
        "hydrate": "team,probablePitcher",
    }

    try:
        response = client.get(
            SCHEDULE_URL,
            params=params,
            timeout=_timeout_seconds(timeout_seconds),
        )
    except Exception as exc:
        raise MLBOfficialSlateError("transport_error", str(exc)) from exc

    status_code = getattr(response, "status_code", None)
    if status_code != 200:
        raise MLBOfficialSlateError("http_error", f"MLB schedule returned HTTP {status_code}")

    try:
        payload = response.json()
    except Exception as exc:
        raise MLBOfficialSlateError(
            "parse_error", "MLB schedule response was not valid JSON"
        ) from exc

    games = _extract_games(payload)
    return {
        "sport": "MLB",
        "slate_date": requested_date,
        "game_count": len(games),
        "games": games,
        "collected_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        "source": SOURCE_NAME,
    }


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "MLBOfficialSlateError",
    "SCHEDULE_URL",
    "SOURCE_NAME",
    "collect_official_mlb_slate",
]
