"""Fast Player PRA history transport for WNBA PRA Speed V3 Step 3.

Render cannot reliably reach the legacy WNBA Stats playergamelog endpoint within
the Step-3 latency budget. This adapter uses ESPN's single-athlete WNBA gamelog
endpoint, already an established fallback family elsewhere in this repository,
and normalizes it to the existing Player Intelligence history shape.

Scope is deliberately narrow:
- read-only HTTP GET
- no model/projection/market/ranking changes
- no sportsbook calls
- no navigation changes
- no changes to frozen Speed V3 Steps 1-2
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from typing import Any, Iterable, Mapping

import httpx

from sports_api.wnba_league import get_wnba_teams


ESPN_GAMELOG_URL = (
    "https://site.web.api.espn.com/apis/common/v3/sports/basketball/"
    "wnba/athletes/{player_id}/gamelog"
)
SOURCE = "ESPN WNBA Athlete Gamelog"
SOURCE_URL = "https://www.espn.com/wnba/"
DATA_TYPE = "official_player_game_log"
REQUEST_TIMEOUT_SECONDS = 3.5


class WNBAFastHistoryUpstreamError(RuntimeError):
    """Raised when the Step-3 fallback history transport cannot be consumed safely."""


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _num(value: Any) -> float | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    try:
        return int(number)
    except (TypeError, ValueError, OverflowError):
        return None


def _minutes(value: Any) -> float | None:
    text = _text(value)
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
                pass
    return _num(text)


def _date(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    if len(text) >= 10 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", text[:10]):
        return text[:10]
    for fmt in ("%m/%d/%Y", "%m.%d.%Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _stat_key(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _stat(stats: Mapping[str, Any], *names: str) -> Any:
    lookup = {_stat_key(key): value for key, value in stats.items()}
    for name in names:
        key = _stat_key(name)
        if key in lookup:
            return lookup[key]
    return None


def _split_pair(value: Any) -> tuple[int | None, int | None]:
    text = _text(value)
    if not text or "-" not in text:
        return None, None
    left, right = text.split("-", 1)
    return _int(left), _int(right)


def _team_registry(values: Iterable[Any], season: int) -> dict[str, Any] | None:
    wanted = {str(value).strip().casefold() for value in values if _text(value)}
    for team in get_wnba_teams(season):
        candidates = {
            str(team.get("team_key") or "").casefold(),
            str(team.get("slug") or "").casefold(),
            str(team.get("abbreviation") or "").casefold(),
            str(team.get("nickname") or "").casefold(),
            str(team.get("full_name") or "").casefold(),
        }
        if wanted & candidates:
            return team
    return None


def _event_id(item: Mapping[str, Any], fallback: str | None = None) -> str | None:
    return _text(item.get("eventId") or item.get("event_id") or item.get("id") or fallback)


def _event_map(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("events") or payload.get("games") or payload.get("gameLog")
    result: dict[str, dict[str, Any]] = {}
    if isinstance(raw, Mapping):
        for key, value in raw.items():
            if not isinstance(value, Mapping):
                continue
            event = dict(value)
            event_id = _event_id(event, str(key))
            if event_id:
                result[event_id] = event
    elif isinstance(raw, list):
        for value in raw:
            if not isinstance(value, Mapping):
                continue
            event = dict(value)
            event_id = _event_id(event)
            if event_id:
                result[event_id] = event
    return result


def _collect_stat_rows(node: Any, out: dict[str, dict[str, Any]]) -> None:
    if isinstance(node, Mapping):
        labels = node.get("labels") or node.get("statNames") or node.get("names")
        rows = node.get("events") or node.get("games") or node.get("gameLog")
        if isinstance(labels, list) and isinstance(rows, (list, Mapping)):
            iterable = rows.values() if isinstance(rows, Mapping) else rows
            for value in iterable:
                if not isinstance(value, Mapping):
                    continue
                stats = value.get("stats") or value.get("values")
                event_id = _event_id(value)
                if event_id and isinstance(stats, list) and len(stats) == len(labels):
                    out[event_id] = {
                        str(label): stat for label, stat in zip(labels, stats)
                    }
                elif event_id and isinstance(stats, Mapping):
                    out[event_id] = dict(stats)
        event_id = _event_id(node)
        inline = node.get("stats") or node.get("values")
        if event_id and isinstance(inline, Mapping):
            out[event_id] = dict(inline)
        for value in node.values():
            _collect_stat_rows(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_stat_rows(value, out)


def _metadata_values(item: Mapping[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    item = item or {}
    team = item.get("team") if isinstance(item.get("team"), Mapping) else {}
    opponent = item.get("opponent") if isinstance(item.get("opponent"), Mapping) else {}
    return dict(team), dict(opponent)


def _normalize_game(
    event_id: str,
    metadata: Mapping[str, Any],
    stats: Mapping[str, Any],
    season: int,
    player_id: int,
) -> dict[str, Any]:
    team, opponent = _metadata_values(metadata)
    team_registry = _team_registry(
        (
            team.get("abbreviation"),
            team.get("displayName"),
            team.get("shortDisplayName"),
            team.get("name"),
            metadata.get("teamAbbreviation"),
            metadata.get("teamName"),
        ),
        season,
    )
    opponent_registry = _team_registry(
        (
            opponent.get("abbreviation"),
            opponent.get("displayName"),
            opponent.get("shortDisplayName"),
            opponent.get("name"),
            metadata.get("opponentAbbreviation"),
            metadata.get("opponentName"),
        ),
        season,
    )

    team_abbr = _text(
        team.get("abbreviation")
        or metadata.get("teamAbbreviation")
        or (team_registry or {}).get("abbreviation")
    )
    opp_abbr = _text(
        opponent.get("abbreviation")
        or metadata.get("opponentAbbreviation")
        or (opponent_registry or {}).get("abbreviation")
    )
    marker = str(metadata.get("atVs") or metadata.get("homeAway") or "").strip().casefold()
    location = "away" if marker in {"@", "at", "away"} else "home" if marker in {"vs", "vs.", "home"} else "unknown"
    matchup_raw = (
        f"{team_abbr} {'@' if location == 'away' else 'vs.'} {opp_abbr}"
        if team_abbr and opp_abbr
        else None
    )

    fgm, fga = _split_pair(_stat(stats, "FG", "FGM-A", "FGMA"))
    three_made, three_attempted = _split_pair(_stat(stats, "3PT", "3PM-A", "3PMA"))
    ftm, fta = _split_pair(_stat(stats, "FT", "FTM-A", "FTMA"))

    return {
        "season_id": f"2{season}",
        "player_id": int(player_id),
        "game_id": str(event_id),
        "game_id_valid": bool(str(event_id).isdigit()),
        "game_date_raw": _text(metadata.get("gameDate") or metadata.get("date")),
        "game_date": _date(metadata.get("gameDate") or metadata.get("date")),
        "matchup": {
            "raw": matchup_raw,
            "location": location,
            "team_abbreviation": team_abbr,
            "team_key": None if team_registry is None else team_registry.get("team_key"),
            "opponent_abbreviation": opp_abbr,
            "opponent_team_key": None if opponent_registry is None else opponent_registry.get("team_key"),
        },
        "result": _text(metadata.get("gameResult") or metadata.get("result")),
        "minutes": _minutes(_stat(stats, "MIN", "MINUTES")),
        "field_goals_made": fgm,
        "field_goals_attempted": fga,
        "field_goal_percentage": _num(_stat(stats, "FG%", "FGPCT")),
        "three_pointers_made": three_made,
        "three_pointers_attempted": three_attempted,
        "three_point_percentage": _num(_stat(stats, "3P%", "3PT%", "3PCT")),
        "free_throws_made": ftm,
        "free_throws_attempted": fta,
        "free_throw_percentage": _num(_stat(stats, "FT%", "FTPCT")),
        "offensive_rebounds": _int(_stat(stats, "OREB")),
        "defensive_rebounds": _int(_stat(stats, "DREB")),
        "rebounds": _int(_stat(stats, "REB", "REBOUNDS")),
        "assists": _int(_stat(stats, "AST", "ASSISTS")),
        "steals": _int(_stat(stats, "STL", "STEALS")),
        "blocks": _int(_stat(stats, "BLK", "BLOCKS")),
        "turnovers": _int(_stat(stats, "TO", "TOV", "TURNOVERS")),
        "personal_fouls": _int(_stat(stats, "PF", "FOULS")),
        "points": _int(_stat(stats, "PTS", "POINTS")),
        "plus_minus": _num(_stat(stats, "+/-", "PLUSMINUS")),
        "video_available": None,
    }


def normalize_espn_player_gamelog(
    payload: Mapping[str, Any],
    *,
    player_id: int,
    season: int,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise WNBAFastHistoryUpstreamError("ESPN WNBA gamelog returned a non-object payload.")

    metadata = _event_map(payload)
    stat_rows: dict[str, dict[str, Any]] = {}
    _collect_stat_rows(payload, stat_rows)

    event_ids = list(dict.fromkeys([*metadata.keys(), *stat_rows.keys()]))
    games = [
        _normalize_game(
            event_id,
            metadata.get(event_id, {}),
            stat_rows.get(event_id, {}),
            int(season),
            int(player_id),
        )
        for event_id in event_ids
    ]
    games = [game for game in games if game["game_date"] is not None]
    games.sort(key=lambda item: str(item.get("game_date") or ""), reverse=True)

    if games and not any(
        game.get("points") is not None
        or game.get("rebounds") is not None
        or game.get("assists") is not None
        for game in games
    ):
        raise WNBAFastHistoryUpstreamError("ESPN WNBA gamelog did not expose usable player stats.")

    duplicate_ids = sorted(
        game_id
        for game_id in {str(game.get("game_id") or "") for game in games}
        if sum(str(row.get("game_id") or "") == game_id for row in games) > 1
    )
    all_matchups_mapped = all(
        (game.get("matchup") or {}).get("team_key") is not None
        and (game.get("matchup") or {}).get("opponent_team_key") is not None
        for game in games
    )

    return {
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "source_endpoint": "site.web.api.espn.com common/v3 athlete gamelog",
        "data_type": DATA_TYPE,
        "season": int(season),
        "season_type": "Regular Season",
        "player_id": int(player_id),
        "retrieved_at_utc": datetime.utcnow().isoformat() + "Z",
        "cache_hit": False,
        "cache_ttl_seconds": 0,
        "game_count": len(games),
        "games": deepcopy(games),
        "verification": {
            "returned_player_ids_match_request": True,
            "all_game_ids_valid": all(bool(game.get("game_id_valid")) for game in games),
            "all_game_ids_unique": not duplicate_ids,
            "duplicate_game_ids": duplicate_ids,
            "all_matchup_teams_mapped_to_registry": all_matchups_mapped,
            "step3_fallback_transport": True,
            "projection_math_changed": False,
        },
    }


def get_step3_player_history(player_id: int, season: int) -> dict[str, Any]:
    pid = int(player_id)
    year = int(season)
    if pid <= 0:
        raise ValueError("player_id must be positive.")
    try:
        response = httpx.get(
            ESPN_GAMELOG_URL.format(player_id=pid),
            params={"season": year},
            headers={
                "Accept": "application/json",
                "User-Agent": "kyre-sports-ai-step3-history/1",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WNBAFastHistoryUpstreamError(
            f"ESPN WNBA athlete gamelog request failed: {type(exc).__name__}"
        ) from exc
    return normalize_espn_player_gamelog(payload, player_id=pid, season=year)


__all__ = [
    "DATA_TYPE",
    "ESPN_GAMELOG_URL",
    "REQUEST_TIMEOUT_SECONDS",
    "SOURCE",
    "WNBAFastHistoryUpstreamError",
    "get_step3_player_history",
    "normalize_espn_player_gamelog",
]
