"""Official WNBA schedule and daily-slate normalization.

Step 4C is limited to schedule identity, game status, venue, team mapping, and
slate integrity. It does not contain betting lines, injuries, projected
lineups, simulations, or model probabilities.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from sports_api.wnba_league import get_wnba_teams

WNBA_LEAGUE_ID = "10"
WNBA_PUBLIC_SCHEDULE_API_URL = "https://www.wnba.com/api/schedule"
WNBA_CDN_SCHEDULE_URL = (
    "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json"
)
# Historical compatibility constant only. The retired stats transport is
# intentionally excluded from the active production request sequence.
WNBA_STATS_SCHEDULE_URL = "https://stats.wnba.com/stats/scheduleleaguev2"
WNBA_SCHEDULE_SOURCE = "WNBA Official Schedule"

ARIZONA_TZ = ZoneInfo("America/Phoenix")
EASTERN_TZ = ZoneInfo("America/New_York")

CACHE_TTL_SECONDS = 60

HTTP_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.wnba.com",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
}

_CACHE: dict[int, dict[str, Any]] = {}
_CACHE_LOCK = Lock()


class WNBAScheduleUpstreamError(RuntimeError):
    """Raised when official WNBA schedule data cannot be consumed safely."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _date_block_iso(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None

    for fmt in ("%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def _iso_datetime(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return text

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _eastern_datetime(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(EASTERN_TZ).isoformat()


def _schedule_root(payload: dict[str, Any]) -> dict[str, Any]:
    root = payload.get("leagueSchedule")
    if not isinstance(root, dict):
        raise WNBAScheduleUpstreamError(
            "Official WNBA schedule payload is missing leagueSchedule."
        )

    if str(root.get("leagueId")) != WNBA_LEAGUE_ID:
        raise WNBAScheduleUpstreamError(
            f"Official WNBA schedule returned unexpected leagueId {root.get('leagueId')!r}."
        )

    game_dates = root.get("gameDates")
    if not isinstance(game_dates, list):
        raise WNBAScheduleUpstreamError(
            "Official WNBA schedule payload is missing gameDates."
        )

    return root


def _fetch_schedule_payload(
    season: int,
) -> tuple[dict[str, Any], str, str, str, bool]:
    """Fetch official schedule data from WNBA.com with current-CDN fallback.

    The legacy stats.wnba.com scheduleLeagueV2 transport is deliberately
    excluded so cloud deployments do not block on the retired endpoint.
    """

    now = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(season)
        if cached and cached["expires_at"] > now:
            return (
                deepcopy(cached["payload"]),
                cached["retrieved_at_utc"],
                cached["source_variant"],
                cached["source_url"],
                True,
            )
        if cached:
            _CACHE.pop(season, None)

    attempts: list[str] = []

    requests_to_try = (
        (
            "wnba_public_schedule_api",
            WNBA_PUBLIC_SCHEDULE_API_URL,
            [("season", str(season)), ("regionId", "1")],
        ),
        (
            "wnba_cdn_schedule",
            WNBA_CDN_SCHEDULE_URL,
            None,
        ),
    )

    payload = None
    source_variant = None
    source_url = None
    for variant, url, params in requests_to_try:
        try:
            response = httpx.get(
                url,
                params=params,
                headers=HTTP_HEADERS,
                timeout=20.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            candidate = response.json()
            if not isinstance(candidate, dict):
                raise ValueError("non-object JSON payload")
            root = _schedule_root(candidate)
            if str(root.get("seasonYear")) != str(season):
                raise ValueError(
                    f"schedule season {root.get('seasonYear')!r} does not match {season}"
                )
            payload = candidate
            source_variant = variant
            source_url = url
            break
        except (httpx.HTTPError, ValueError, WNBAScheduleUpstreamError) as exc:
            attempts.append(f"{variant}: {exc}")

    if payload is None or source_variant is None or source_url is None:
        joined = "; ".join(attempts)
        raise WNBAScheduleUpstreamError(
            f"All official WNBA schedule sources failed for {season}: {joined}"
        )

    retrieved_at_utc = _utc_now_iso()

    with _CACHE_LOCK:
        _CACHE[season] = {
            "payload": deepcopy(payload),
            "retrieved_at_utc": retrieved_at_utc,
            "source_variant": source_variant,
            "source_url": source_url,
            "expires_at": now + CACHE_TTL_SECONDS,
        }

    return payload, retrieved_at_utc, source_variant, source_url, False


def _registry_team_from_schedule(
    raw_team: dict[str, Any],
    season: int,
) -> dict[str, Any] | None:
    values = {
        (_clean_text(raw_team.get("teamTricode")) or "").casefold(),
        (_clean_text(raw_team.get("teamSlug")) or "").casefold(),
        (_clean_text(raw_team.get("teamName")) or "").casefold(),
    }

    city = _clean_text(raw_team.get("teamCity"))
    nickname = _clean_text(raw_team.get("teamName"))
    if city and nickname:
        values.add(f"{city} {nickname}".casefold())

    values.discard("")

    for team in get_wnba_teams(season):
        candidates = {
            team["team_key"].casefold(),
            team["slug"].casefold(),
            team["abbreviation"].casefold(),
            team["nickname"].casefold(),
            team["full_name"].casefold(),
        }
        if values & candidates:
            return team

    return None


def _normalize_team(raw_team: dict[str, Any], season: int) -> dict[str, Any]:
    registry = _registry_team_from_schedule(raw_team, season)
    return {
        "official_team_id": _to_int(raw_team.get("teamId")),
        "team_key": registry.get("team_key") if registry else None,
        "full_name": registry.get("full_name") if registry else None,
        "conference": registry.get("conference") if registry else None,
        "team_city": _clean_text(raw_team.get("teamCity")),
        "team_name": _clean_text(raw_team.get("teamName")),
        "team_tricode": _clean_text(raw_team.get("teamTricode")),
        "team_slug": _clean_text(raw_team.get("teamSlug")),
        "wins": _to_int(raw_team.get("wins")),
        "losses": _to_int(raw_team.get("losses")),
        "score": _to_int(raw_team.get("score")),
        "seed": _to_int(raw_team.get("seed")),
        "mapped_to_registry": registry is not None,
    }


def _status_category(status_code: int | None, status_text: str | None) -> str:
    text = (status_text or "").casefold()

    if "postpon" in text:
        return "postponed"
    if "cancel" in text:
        return "cancelled"
    if "suspend" in text:
        return "suspended"
    if "delay" in text:
        return "delayed"
    if status_code == 1:
        return "scheduled"
    if status_code == 2:
        return "live"
    if status_code == 3:
        return "final"
    return "unknown"


def _schedule_change_flags(game: dict[str, Any]) -> dict[str, Any]:
    status_text = _clean_text(game.get("gameStatusText"))
    searchable = " ".join(
        filter(
            None,
            [
                status_text,
                _clean_text(game.get("gameLabel")),
                _clean_text(game.get("gameSubLabel")),
                _clean_text(game.get("seriesText")),
            ],
        )
    ).casefold()

    postponed_raw = _clean_text(game.get("postponedStatus"))
    postponed = postponed_raw not in (None, "", "N", "0") or "postpon" in searchable
    cancelled = "cancel" in searchable
    delayed = "delay" in searchable
    suspended = "suspend" in searchable
    rescheduled_indicator = "resched" in searchable

    return {
        "postponed_status_raw": postponed_raw,
        "postponed": postponed,
        "cancelled": cancelled,
        "delayed": delayed,
        "suspended": suspended,
        "rescheduled_indicator": rescheduled_indicator,
        "schedule_changed": any(
            [postponed, cancelled, delayed, suspended, rescheduled_indicator]
        ),
        "note": (
            _clean_text(game.get("gameSubLabel"))
            or _clean_text(game.get("seriesText"))
            or _clean_text(game.get("gameLabel"))
        ),
    }


def _broadcast_displays(game: dict[str, Any]) -> list[str]:
    broadcasters = game.get("broadcasters")
    if not isinstance(broadcasters, dict):
        return []

    displays: list[str] = []
    for entries in broadcasters.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            display = _clean_text(entry.get("broadcasterDisplay"))
            if display and display not in displays:
                displays.append(display)

    return displays


def _normalize_game(
    game: dict[str, Any],
    official_date: str,
    season: int,
) -> dict[str, Any]:
    game_id = _clean_text(game.get("gameId"))
    status_code = _to_int(game.get("gameStatus"))
    status_text = _clean_text(game.get("gameStatusText"))
    away = _normalize_team(game.get("awayTeam") or {}, season)
    home = _normalize_team(game.get("homeTeam") or {}, season)
    schedule_change = _schedule_change_flags(game)

    game_id_valid = bool(game_id and game_id.isdigit())
    teams_mapped = away["mapped_to_registry"] and home["mapped_to_registry"]
    teams_distinct = (
        away["official_team_id"] is not None
        and home["official_team_id"] is not None
        and away["official_team_id"] != home["official_team_id"]
    )
    status_category = _status_category(status_code, status_text)
    playable_pregame = (
        status_category == "scheduled"
        and not schedule_change["schedule_changed"]
        and teams_mapped
        and teams_distinct
    )

    return {
        "game_id": game_id,
        "game_code": _clean_text(game.get("gameCode")),
        "season": season,
        "official_schedule_date": official_date,
        "game_sequence": _to_int(game.get("gameSequence")),
        "game_datetime_utc": _iso_datetime(game.get("gameDateTimeUTC")),
        "game_datetime_eastern": _eastern_datetime(game.get("gameDateTimeUTC")),
        "source_game_datetime_eastern": _clean_text(game.get("gameDateTimeEst")),
        "day": _clean_text(game.get("day")),
        "status": {
            "code": status_code,
            "text": status_text,
            "category": status_category,
        },
        "schedule_change": schedule_change,
        "competition": {
            "game_label": _clean_text(game.get("gameLabel")),
            "game_sub_label": _clean_text(game.get("gameSubLabel")),
            "game_subtype": _clean_text(game.get("gameSubtype")),
            "series_text": _clean_text(game.get("seriesText")),
            "series_game_number": _clean_text(game.get("seriesGameNumber")),
            "if_necessary": bool(game.get("ifNecessary")),
        },
        "venue": {
            "name": _clean_text(game.get("arenaName")),
            "city": _clean_text(game.get("arenaCity")),
            "state": _clean_text(game.get("arenaState")),
            "is_neutral": bool(game.get("isNeutral")),
        },
        "broadcasts": _broadcast_displays(game),
        "away": away,
        "home": home,
        "verification": {
            "game_id_valid": game_id_valid,
            "teams_mapped_to_registry": teams_mapped,
            "home_away_distinct": teams_distinct,
            "playable_pregame": playable_pregame,
        },
    }


def get_daily_schedule_dataset(target_date: str, season: int) -> dict[str, Any]:
    # Reuse Step 4A's fail-closed season validation.
    get_wnba_teams(season)

    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format.") from exc

    (
        payload,
        retrieved_at_utc,
        source_variant,
        source_url,
        cache_hit,
    ) = _fetch_schedule_payload(season)
    root = _schedule_root(payload)

    matching_blocks: list[dict[str, Any]] = []
    for block in root.get("gameDates", []):
        if not isinstance(block, dict):
            continue
        if _date_block_iso(block.get("gameDate")) == target_date:
            matching_blocks.append(block)

    raw_games: list[dict[str, Any]] = []
    for block in matching_blocks:
        games = block.get("games")
        if isinstance(games, list):
            raw_games.extend(game for game in games if isinstance(game, dict))

    games = [_normalize_game(game, target_date, season) for game in raw_games]
    games.sort(
        key=lambda game: (
            game.get("game_datetime_utc") or "",
            game.get("game_id") or "",
        )
    )

    return {
        "source": WNBA_SCHEDULE_SOURCE,
        "source_url": source_url,
        "source_variant": source_variant,
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "date": target_date,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "source_date_block_count": len(matching_blocks),
        "source_game_count": len(raw_games),
        "game_count": len(games),
        "games": games,
    }


def verify_daily_slate_dataset(target_date: str, season: int) -> dict[str, Any]:
    dataset = get_daily_schedule_dataset(target_date, season)
    games = dataset["games"]

    game_ids = [
        game["game_id"]
        for game in games
        if game.get("game_id") is not None
    ]
    duplicate_game_ids = sorted(
        {
            game_id
            for game_id in game_ids
            if game_ids.count(game_id) > 1
        }
    )

    all_game_ids_valid = all(
        game["verification"]["game_id_valid"] for game in games
    )
    all_game_ids_unique = len(game_ids) == len(set(game_ids))
    all_teams_mapped = all(
        game["verification"]["teams_mapped_to_registry"] for game in games
    )
    all_home_away_distinct = all(
        game["verification"]["home_away_distinct"] for game in games
    )
    game_count_matches_source = dataset["game_count"] == dataset["source_game_count"]
    date_block_count_valid = dataset["source_date_block_count"] <= 1

    if dataset["source_date_block_count"] == 0:
        completeness_status = "no_games_listed_for_date"
    elif dataset["source_date_block_count"] == 1:
        completeness_status = "official_date_block_verified"
    else:
        completeness_status = "duplicate_official_date_blocks"

    slate_integrity_pass = (
        date_block_count_valid
        and game_count_matches_source
        and all_game_ids_valid
        and all_game_ids_unique
        and all_teams_mapped
        and all_home_away_distinct
    )

    scheduled_games = sum(
        game["status"]["category"] == "scheduled" for game in games
    )
    live_games = sum(game["status"]["category"] == "live" for game in games)
    final_games = sum(game["status"]["category"] == "final" for game in games)
    changed_games = sum(
        game["schedule_change"]["schedule_changed"] for game in games
    )
    pregame_ready_games = sum(
        game["verification"]["playable_pregame"] for game in games
    )

    blocking_reasons: list[str] = []
    if not date_block_count_valid:
        blocking_reasons.append("duplicate_official_date_blocks")
    if not game_count_matches_source:
        blocking_reasons.append("normalized_game_count_mismatch")
    if not all_game_ids_valid:
        blocking_reasons.append("invalid_game_id")
    if not all_game_ids_unique:
        blocking_reasons.append("duplicate_game_id")
    if not all_teams_mapped:
        blocking_reasons.append("unmapped_team_identity")
    if not all_home_away_distinct:
        blocking_reasons.append("invalid_home_away_identity")

    return {
        "source": dataset["source"],
        "source_url": dataset["source_url"],
        "source_variant": dataset["source_variant"],
        "verified_by": "Kyre Sports API",
        "league_id": dataset["league_id"],
        "season": season,
        "date": target_date,
        "verified_at_utc": _utc_now_iso(),
        "source_retrieved_at_utc": dataset["retrieved_at_utc"],
        "slate": {
            "source_date_block_count": dataset["source_date_block_count"],
            "source_game_count": dataset["source_game_count"],
            "normalized_game_count": dataset["game_count"],
            "game_count_matches_source": game_count_matches_source,
            "all_game_ids_valid": all_game_ids_valid,
            "all_game_ids_unique": all_game_ids_unique,
            "duplicate_game_ids": duplicate_game_ids,
            "all_teams_mapped_to_registry": all_teams_mapped,
            "all_home_away_distinct": all_home_away_distinct,
            "completeness_status": completeness_status,
            "slate_integrity_pass": slate_integrity_pass,
            "blocking_reasons": blocking_reasons,
        },
        "status_summary": {
            "scheduled_games": scheduled_games,
            "live_games": live_games,
            "final_games": final_games,
            "schedule_changed_games": changed_games,
            "playable_pregame_games": pregame_ready_games,
        },
        "games": games,
    }


def get_today_schedule_dataset(season: int) -> dict[str, Any]:
    target_date = datetime.now(ARIZONA_TZ).date().isoformat()
    dataset = get_daily_schedule_dataset(target_date, season)
    dataset["date_basis"] = "America/Phoenix"
    return dataset
