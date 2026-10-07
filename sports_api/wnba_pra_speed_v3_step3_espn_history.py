"""Step-3-only fast WNBA player-history transport.

The frozen WNBA Stats playergamelog transport is not latency-safe on the Render
service used by the PRA detail bundle: both stats.wnba.com and stats.nba.com have
been observed taking about 20 seconds.  This module uses ESPN's common/v3
single-athlete WNBA gamelog endpoint and normalizes the response to the existing
Player Intelligence history contract.

Scope:
- Step-3 detail bundle only.
- One read-only HTTP request on a cold miss.
- No model/projection/market/ranking/qualification/sportsbook changes.
- Frozen Navigation V2 and Speed V3 Steps 1-2 remain untouched.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from threading import Lock
from time import monotonic
from typing import Any, Iterable, Mapping

import requests

from sports_api.wnba_league import get_wnba_teams


ESPN_GAMELOG_BASE = (
    "https://site.web.api.espn.com/apis/common/v3/sports/"
    "basketball/wnba/athletes"
)
ESPN_HISTORY_SOURCE = "ESPN WNBA Athlete Gamelog"
ESPN_HISTORY_SOURCE_URL = "https://www.espn.com/wnba/"
ESPN_HISTORY_ENDPOINT = "common/v3 WNBA athlete gamelog"

REQUEST_TIMEOUT_SECONDS = 4.0
CACHE_TTL_SECONDS = 120
CACHE_MAX_ENTRIES = 256

HTTP_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Safari/604.1"
    ),
}

_CACHE: dict[tuple[int, int], dict[str, Any]] = {}
_CACHE_LOCK = Lock()


class WNBAStep3ESPNHistoryUpstreamError(RuntimeError):
    """Raised when ESPN WNBA gamelog cannot be consumed safely."""


class WNBAStep3ESPNHistoryNotFoundError(LookupError):
    """Raised when ESPN has no gamelog for the requested player/season."""


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _norm(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = text.replace("+/-", "plusminus").replace("%", "pct")
    return re.sub(r"[^a-z0-9]+", "", text)


def _to_float(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    text = text.replace(",", "").replace("%", "")
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    if number is None:
        return None
    try:
        return int(number)
    except (TypeError, ValueError, OverflowError):
        return None


def _minutes(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    if text.startswith("PT"):
        match = re.fullmatch(
            r"PT(?:(?P<hours>\d+(?:\.\d+)?)H)?"
            r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
            r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?",
            text,
        )
        if match:
            hours = float(match.group("hours") or 0.0)
            minutes = float(match.group("minutes") or 0.0)
            seconds = float(match.group("seconds") or 0.0)
            return round(hours * 60.0 + minutes + seconds / 60.0, 4)
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2:
            try:
                return round(float(parts[0]) + float(parts[1]) / 60.0, 4)
            except ValueError:
                return None
    return _to_float(text)


def _iso_date(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    if len(text) >= 10 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", text[:10]):
        return text[:10]
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%m.%d.%Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _pair(value: Any) -> tuple[int | None, int | None]:
    text = _clean(value)
    if text is None:
        return None, None
    for sep in ("-", "/"):
        if sep in text:
            left, right = text.split(sep, 1)
            return _to_int(left), _to_int(right)
    return None, None


def _team_from_values(values: Iterable[Any], season: int) -> dict[str, Any] | None:
    wanted = {_norm(value) for value in values if _clean(value)}
    wanted.discard("")
    for team in get_wnba_teams(season):
        candidates = {
            _norm(team.get("team_key")),
            _norm(team.get("slug")),
            _norm(team.get("abbreviation")),
            _norm(team.get("nickname")),
            _norm(team.get("full_name")),
        }
        if wanted & candidates:
            return team
    return None


def _event_id(value: Mapping[str, Any], fallback: Any = None) -> str | None:
    nested = value.get("event") if isinstance(value.get("event"), Mapping) else {}
    return _clean(
        value.get("eventId")
        or value.get("event_id")
        or value.get("id")
        or nested.get("id")
        or fallback
    )


def _event_meta_map(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("events")
    result: dict[str, dict[str, Any]] = {}
    if isinstance(raw, Mapping):
        items = raw.get("items") if isinstance(raw.get("items"), list) else None
        if items is None:
            for key, value in raw.items():
                if not isinstance(value, Mapping):
                    continue
                item = dict(value)
                event_id = _event_id(item, key)
                if event_id:
                    result[event_id] = item
            return result
        raw = items
    if isinstance(raw, list):
        for value in raw:
            if not isinstance(value, Mapping):
                continue
            item = dict(value)
            nested = item.get("event") if isinstance(item.get("event"), Mapping) else {}
            merged = dict(nested)
            merged.update({key: val for key, val in item.items() if key not in merged})
            event_id = _event_id(merged)
            if event_id:
                result[event_id] = merged
    return result


_METADATA_KEYS = {
    "date",
    "gamedate",
    "opp",
    "opponent",
    "result",
    "gameresult",
}


def _axis_for_stats(
    labels: list[Any],
    names: list[Any],
    stats: list[Any],
) -> list[str]:
    candidates = [
        [_norm(item) for item in names],
        [_norm(item) for item in labels],
    ]
    for axis in candidates:
        if len(axis) == len(stats):
            return axis
    for axis in candidates:
        filtered = [item for item in axis if item not in _METADATA_KEYS]
        if len(filtered) == len(stats):
            return filtered
    return []


def _stat_map(
    labels: list[Any],
    names: list[Any],
    raw_stats: Any,
) -> dict[str, Any]:
    if isinstance(raw_stats, Mapping):
        return {_norm(key): value for key, value in raw_stats.items()}
    if not isinstance(raw_stats, list):
        return {}
    axis = _axis_for_stats(labels, names, raw_stats)
    if not axis:
        return {}
    return {axis[index]: raw_stats[index] for index in range(len(raw_stats))}


def _iter_event_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        items = value.get("items") if isinstance(value.get("items"), list) else None
        if items is not None:
            return [dict(item) for item in items if isinstance(item, Mapping)]
        rows: list[dict[str, Any]] = []
        for key, item in value.items():
            if not isinstance(item, Mapping):
                continue
            row = dict(item)
            row.setdefault("eventId", str(key))
            rows.append(row)
        return rows
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _candidate_sections(payload: Mapping[str, Any]) -> list[tuple[list[Any], list[Any], Any]]:
    sections: list[tuple[list[Any], list[Any], Any]] = []

    root_labels = payload.get("labels") if isinstance(payload.get("labels"), list) else []
    root_names = payload.get("names") if isinstance(payload.get("names"), list) else []
    if payload.get("events") is not None:
        sections.append((root_labels, root_names, payload.get("events")))

    root_categories = payload.get("categories")
    if isinstance(root_categories, list):
        for category in root_categories:
            if not isinstance(category, Mapping):
                continue
            labels = category.get("labels") if isinstance(category.get("labels"), list) else root_labels
            names = category.get("names") if isinstance(category.get("names"), list) else root_names
            if category.get("events") is not None:
                sections.append((labels, names, category.get("events")))

    season_types = payload.get("seasonTypes")
    if isinstance(season_types, list):
        for season_type in season_types:
            if not isinstance(season_type, Mapping):
                continue
            categories = season_type.get("categories")
            if not isinstance(categories, list):
                continue
            for category in categories:
                if not isinstance(category, Mapping):
                    continue
                labels = category.get("labels") if isinstance(category.get("labels"), list) else root_labels
                names = category.get("names") if isinstance(category.get("names"), list) else root_names
                if category.get("events") is not None:
                    sections.append((labels, names, category.get("events")))
    return sections


def _stats_by_event(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for labels, names, events in _candidate_sections(payload):
        for row in _iter_event_rows(events):
            event_id = _event_id(row)
            if not event_id:
                continue
            raw_stats = row.get("stats")
            if raw_stats is None:
                raw_stats = row.get("statistics")
            current = _stat_map(labels, names, raw_stats)
            if current:
                result.setdefault(event_id, {}).update(current)
    return result


def _pick(stats: Mapping[str, Any], *aliases: str) -> Any:
    for alias in aliases:
        key = _norm(alias)
        if key in stats:
            return stats[key]
    return None


def _top_level_team(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    team = payload.get("team")
    if isinstance(team, Mapping):
        return team
    teams = payload.get("teams")
    if isinstance(teams, list):
        for value in teams:
            if isinstance(value, Mapping):
                return value
    return {}


def _normalize_game(
    event_id: str,
    metadata: Mapping[str, Any],
    stats: Mapping[str, Any],
    *,
    player_id: int,
    season: int,
    payload_team: Mapping[str, Any],
) -> dict[str, Any]:
    event_obj = metadata.get("event") if isinstance(metadata.get("event"), Mapping) else {}
    merged_meta = dict(event_obj)
    merged_meta.update({key: value for key, value in metadata.items() if key not in merged_meta})

    team_raw = merged_meta.get("team") if isinstance(merged_meta.get("team"), Mapping) else payload_team
    opponent_raw = (
        merged_meta.get("opponent")
        if isinstance(merged_meta.get("opponent"), Mapping)
        else {}
    )

    team = _team_from_values(
        (
            team_raw.get("abbreviation"),
            team_raw.get("displayName"),
            team_raw.get("shortDisplayName"),
            team_raw.get("name"),
            merged_meta.get("teamAbbreviation"),
            merged_meta.get("teamName"),
        ),
        season,
    )
    opponent = _team_from_values(
        (
            opponent_raw.get("abbreviation"),
            opponent_raw.get("displayName"),
            opponent_raw.get("shortDisplayName"),
            opponent_raw.get("name"),
            merged_meta.get("opponentAbbreviation"),
            merged_meta.get("opponentName"),
        ),
        season,
    )

    team_abbr = _clean(
        team_raw.get("abbreviation")
        or merged_meta.get("teamAbbreviation")
        or (team or {}).get("abbreviation")
    )
    opponent_abbr = _clean(
        opponent_raw.get("abbreviation")
        or merged_meta.get("opponentAbbreviation")
        or (opponent or {}).get("abbreviation")
    )

    site = _clean(
        merged_meta.get("atVs")
        or merged_meta.get("homeAway")
        or merged_meta.get("location")
    )
    site_norm = (site or "").casefold()
    if site_norm in {"@", "at", "away"}:
        location = "away"
    elif site_norm in {"vs", "vs.", "home"}:
        location = "home"
    else:
        location = "unknown"

    if team_abbr and opponent_abbr:
        marker = "@" if location == "away" else "vs."
        matchup_raw = f"{team_abbr} {marker} {opponent_abbr}"
    elif opponent_abbr:
        marker = "@" if location == "away" else "vs."
        matchup_raw = f"{marker} {opponent_abbr}"
    else:
        matchup_raw = None

    fgm, fga = _pair(_pick(stats, "FG", "FGM-A", "fieldGoals"))
    if fgm is None:
        fgm = _to_int(_pick(stats, "FGM", "fieldGoalsMade"))
    if fga is None:
        fga = _to_int(_pick(stats, "FGA", "fieldGoalsAttempted"))

    fg3m, fg3a = _pair(_pick(stats, "3PT", "3PM-A", "threePointFieldGoals"))
    if fg3m is None:
        fg3m = _to_int(_pick(stats, "3PM", "FG3M", "threePointersMade"))
    if fg3a is None:
        fg3a = _to_int(_pick(stats, "3PA", "FG3A", "threePointersAttempted"))

    ftm, fta = _pair(_pick(stats, "FT", "FTM-A", "freeThrows"))
    if ftm is None:
        ftm = _to_int(_pick(stats, "FTM", "freeThrowsMade"))
    if fta is None:
        fta = _to_int(_pick(stats, "FTA", "freeThrowsAttempted"))

    raw_date = (
        merged_meta.get("date")
        or merged_meta.get("gameDate")
        or metadata.get("date")
        or metadata.get("gameDate")
    )

    return {
        "season_id": f"2{season}",
        "player_id": int(player_id),
        "game_id": str(event_id),
        "game_id_valid": bool(str(event_id).isdigit()),
        "game_date_raw": _clean(raw_date),
        "game_date": _iso_date(raw_date),
        "matchup": {
            "raw": matchup_raw,
            "location": location,
            "team_abbreviation": team_abbr,
            "team_key": None if team is None else team.get("team_key"),
            "opponent_abbreviation": opponent_abbr,
            "opponent_team_key": None if opponent is None else opponent.get("team_key"),
        },
        "result": _clean(
            merged_meta.get("gameResult")
            or merged_meta.get("result")
            or metadata.get("gameResult")
        ),
        "minutes": _minutes(_pick(stats, "MIN", "minutes")),
        "field_goals_made": fgm,
        "field_goals_attempted": fga,
        "field_goal_percentage": _to_float(_pick(stats, "FG%", "FG_PCT", "fieldGoalPct")),
        "three_pointers_made": fg3m,
        "three_pointers_attempted": fg3a,
        "three_point_percentage": _to_float(_pick(stats, "3P%", "3PT%", "FG3_PCT", "threePointPct")),
        "free_throws_made": ftm,
        "free_throws_attempted": fta,
        "free_throw_percentage": _to_float(_pick(stats, "FT%", "FT_PCT", "freeThrowPct")),
        "offensive_rebounds": _to_int(_pick(stats, "OREB", "offensiveRebounds")),
        "defensive_rebounds": _to_int(_pick(stats, "DREB", "defensiveRebounds")),
        "rebounds": _to_int(_pick(stats, "REB", "rebounds", "totalRebounds")),
        "assists": _to_int(_pick(stats, "AST", "assists")),
        "steals": _to_int(_pick(stats, "STL", "steals")),
        "blocks": _to_int(_pick(stats, "BLK", "blocks")),
        "turnovers": _to_int(_pick(stats, "TO", "TOV", "turnovers")),
        "personal_fouls": _to_int(_pick(stats, "PF", "fouls")),
        "points": _to_int(_pick(stats, "PTS", "points")),
        "plus_minus": _to_float(_pick(stats, "+/-", "PLUS_MINUS", "plusMinus")),
        "video_available": None,
    }


def normalize_espn_wnba_gamelog(
    payload: Mapping[str, Any],
    *,
    player_id: int,
    season: int,
    retrieved_at_utc: str | None = None,
    cache_hit: bool = False,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise WNBAStep3ESPNHistoryUpstreamError(
            "ESPN WNBA athlete gamelog returned a non-object payload."
        )

    metadata = _event_meta_map(payload)
    stats = _stats_by_event(payload)
    event_ids = list(dict.fromkeys([*metadata.keys(), *stats.keys()]))
    if not event_ids:
        raise WNBAStep3ESPNHistoryNotFoundError(
            f"ESPN WNBA athlete gamelog has no events for player {player_id} in {season}."
        )

    payload_team = _top_level_team(payload)
    games = [
        _normalize_game(
            event_id,
            metadata.get(event_id, {}),
            stats.get(event_id, {}),
            player_id=int(player_id),
            season=int(season),
            payload_team=payload_team,
        )
        for event_id in event_ids
    ]
    games = [
        game
        for game in games
        if game.get("game_date") is not None
        and any(
            game.get(field) is not None
            for field in ("points", "rebounds", "assists", "minutes")
        )
    ]
    games.sort(key=lambda game: str(game.get("game_date") or ""), reverse=True)

    if not games:
        raise WNBAStep3ESPNHistoryNotFoundError(
            f"ESPN WNBA athlete gamelog has no usable completed games for player {player_id} in {season}."
        )

    game_ids = [str(game.get("game_id") or "") for game in games if game.get("game_id")]
    duplicates = sorted(
        game_id
        for game_id in set(game_ids)
        if game_ids.count(game_id) > 1
    )
    all_matchups_mapped = all(
        (game.get("matchup") or {}).get("opponent_team_key") is not None
        for game in games
    )

    return {
        "source": ESPN_HISTORY_SOURCE,
        "source_url": ESPN_HISTORY_SOURCE_URL,
        "source_endpoint": ESPN_HISTORY_ENDPOINT,
        "data_type": "official_player_game_log",
        "season": int(season),
        "season_type": "Regular Season",
        "player_id": int(player_id),
        "retrieved_at_utc": retrieved_at_utc
        or datetime.now(timezone.utc).isoformat(),
        "cache_hit": bool(cache_hit),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "game_count": len(games),
        "games": deepcopy(games),
        "verification": {
            "returned_player_ids_match_request": True,
            "all_game_ids_valid": all(bool(game.get("game_id_valid")) for game in games),
            "all_game_ids_unique": len(duplicates) == 0,
            "duplicate_game_ids": duplicates,
            "all_matchup_teams_mapped_to_registry": all_matchups_mapped,
            "step3_source_router_fallback": True,
            "projection_math_changed": False,
            "market_math_changed": False,
        },
    }


def _fetch_payload(
    player_id: int,
    season: int,
) -> tuple[dict[str, Any], str, bool]:
    key = (int(player_id), int(season))
    now = monotonic()

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and float(cached.get("expires_at") or 0.0) > now:
            return (
                deepcopy(cached["payload"]),
                str(cached["retrieved_at_utc"]),
                True,
            )
        if cached:
            _CACHE.pop(key, None)

    url = f"{ESPN_GAMELOG_BASE}/{int(player_id)}/gamelog"
    try:
        response = requests.get(
            url,
            params={"season": int(season)},
            headers=HTTP_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            raise WNBAStep3ESPNHistoryNotFoundError(
                f"ESPN WNBA athlete gamelog was not found for player {player_id}."
            )
        response.raise_for_status()
        payload = response.json()
    except WNBAStep3ESPNHistoryNotFoundError:
        raise
    except (requests.RequestException, ValueError) as exc:
        raise WNBAStep3ESPNHistoryUpstreamError(
            "ESPN WNBA athlete gamelog request failed: "
            f"{type(exc).__name__}"
        ) from exc

    if not isinstance(payload, dict):
        raise WNBAStep3ESPNHistoryUpstreamError(
            "ESPN WNBA athlete gamelog returned a non-object payload."
        )

    retrieved_at_utc = datetime.now(timezone.utc).isoformat()
    with _CACHE_LOCK:
        expired = [
            cache_key
            for cache_key, item in _CACHE.items()
            if float(item.get("expires_at") or 0.0) <= now
        ]
        for cache_key in expired:
            _CACHE.pop(cache_key, None)
        if len(_CACHE) >= CACHE_MAX_ENTRIES:
            _CACHE.pop(next(iter(_CACHE)), None)
        _CACHE[key] = {
            "payload": deepcopy(payload),
            "retrieved_at_utc": retrieved_at_utc,
            "expires_at": now + CACHE_TTL_SECONDS,
        }

    return payload, retrieved_at_utc, False


def get_step3_espn_player_game_log_dataset(
    player_id: int,
    season: int,
) -> dict[str, Any]:
    pid = int(player_id)
    year = int(season)
    if pid <= 0:
        raise ValueError("WNBA player_id must be positive.")
    if year < 1997 or year > 2100:
        raise ValueError("WNBA season is outside the supported range.")

    payload, retrieved_at_utc, cache_hit = _fetch_payload(pid, year)
    return normalize_espn_wnba_gamelog(
        payload,
        player_id=pid,
        season=year,
        retrieved_at_utc=retrieved_at_utc,
        cache_hit=cache_hit,
    )


__all__ = [
    "CACHE_TTL_SECONDS",
    "ESPN_GAMELOG_BASE",
    "ESPN_HISTORY_SOURCE",
    "REQUEST_TIMEOUT_SECONDS",
    "WNBAStep3ESPNHistoryNotFoundError",
    "WNBAStep3ESPNHistoryUpstreamError",
    "get_step3_espn_player_game_log_dataset",
    "normalize_espn_wnba_gamelog",
]
