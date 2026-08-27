"""Official WNBA live scoreboard, play-by-play, and in-game state.

Step 4K is an observed live-data layer only. It does not create betting lines,
win probabilities, player projections, or model-derived live adjustments.

Primary official/keyless sources:
- https://cdn.wnba.com/static/json/liveData/scoreboard/todaysScoreboard_10.json
- https://cdn.wnba.com/static/json/liveData/boxscore/boxscore_{gameId}.json
- https://cdn.wnba.com/static/json/liveData/playbyplay/playbyplay_{gameId}.json

WNBA liveData uses NBA-family 10-digit GAME_ID values. Those IDs are kept
separate from any third-party event identifiers.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from threading import Lock
from time import monotonic
from typing import Any, Iterable

import httpx

from sports_api.wnba_league import get_wnba_teams

WNBA_LEAGUE_ID = "10"
WNBA_LIVE_SOURCE = "WNBA Official Live Data"
WNBA_LIVE_BASE_URL = "https://cdn.wnba.com/static/json/liveData"
WNBA_SCOREBOARD_URL = f"{WNBA_LIVE_BASE_URL}/scoreboard/todaysScoreboard_10.json"
WNBA_BOX_SCORE_URL = f"{WNBA_LIVE_BASE_URL}/boxscore/boxscore_{{game_id}}.json"
WNBA_PLAY_BY_PLAY_URL = (
    f"{WNBA_LIVE_BASE_URL}/playbyplay/playbyplay_{{game_id}}.json"
)

CACHE_TTL_SECONDS = 4
CACHE_MAX_ENTRIES = 512
ALLOWED_EVENT_CATEGORIES = (
    "All",
    "shot",
    "free_throw",
    "rebound",
    "turnover",
    "foul",
    "substitution",
    "timeout",
    "jump_ball",
    "period",
    "violation",
    "other",
)

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

_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_LOCK = Lock()
_CLOCK_RE = re.compile(r"^PT(?:(\d+)M)?(?:([\d.]+)S)?$", re.I)


class WNBALiveUpstreamError(RuntimeError):
    """Raised when official WNBA live data cannot be consumed safely."""


class WNBALiveNotFoundError(LookupError):
    """Raised when an official WNBA live-data resource does not exist."""


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


def _to_float(value: Any) -> float | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _validate_game_id(game_id: str) -> str:
    normalized = str(game_id).strip()
    if len(normalized) != 10 or not normalized.isdigit():
        raise ValueError("WNBA game_id must be a 10-digit official game ID.")
    return normalized


def _normalize_choice(value: str, allowed: Iterable[str], label: str) -> str:
    text = str(value).strip()
    lookup = {item.casefold(): item for item in allowed}
    resolved = lookup.get(text.casefold())
    if resolved is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return resolved


def clock_to_seconds_remaining(clock: Any) -> float | None:
    """Convert liveData ISO-8601 game clock text to seconds remaining."""
    text = _clean_text(clock)
    if text is None:
        return None
    match = _CLOCK_RE.match(text)
    if not match:
        return None
    minutes = float(match.group(1) or 0)
    seconds = float(match.group(2) or 0)
    return round(minutes * 60.0 + seconds, 3)


def _period_length_seconds(period: int) -> float:
    return 600.0 if period <= 4 else 300.0


def _elapsed_game_seconds(period: int | None, clock_seconds: float | None) -> float | None:
    if period is None or period <= 0 or clock_seconds is None:
        return None
    prior = sum(_period_length_seconds(value) for value in range(1, period))
    return round(prior + (_period_length_seconds(period) - clock_seconds), 3)


def _status_category(code: int | None, text: str | None) -> str:
    value = (text or "").casefold()
    if "postpon" in value:
        return "postponed"
    if "cancel" in value:
        return "cancelled"
    if "suspend" in value:
        return "suspended"
    if "delay" in value:
        return "delayed"
    if code == 1:
        return "scheduled"
    if code == 2:
        return "live"
    if code == 3:
        return "final"
    return "unknown"


def _registry_team_from_live(raw: dict[str, Any], season: int) -> dict[str, Any] | None:
    values = {
        (_clean_text(raw.get("teamTricode")) or "").casefold(),
        (_clean_text(raw.get("teamName")) or "").casefold(),
        (_clean_text(raw.get("teamCity")) or "").casefold(),
    }
    city = _clean_text(raw.get("teamCity"))
    name = _clean_text(raw.get("teamName"))
    if city and name:
        values.add(f"{city} {name}".casefold())
    values.discard("")
    if "pdx" in values:
        values.add("portland-fire")
    if "gs" in values:
        values.add("golden-state-valkyries")

    for team in get_wnba_teams(season):
        candidates = {
            team["team_key"].casefold(),
            team["slug"].casefold(),
            team["abbreviation"].casefold(),
            team["nickname"].casefold(),
            team["full_name"].casefold(),
            team["city"].casefold(),
        }
        if values & candidates:
            return team
    return None


def _registry_team_from_tricode(tricode: Any, season: int) -> dict[str, Any] | None:
    text = (_clean_text(tricode) or "").casefold()
    if text == "pdx":
        text = "por"
    if text == "gs":
        text = "gsv"
    for team in get_wnba_teams(season):
        if team["abbreviation"].casefold() == text:
            return team
    return None


def _request_json(url: str) -> tuple[dict[str, Any], str, bool]:
    now = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(url)
        if cached and cached["expires_at"] > now:
            return deepcopy(cached["payload"]), cached["retrieved_at_utc"], True
        if cached:
            _CACHE.pop(url, None)

    try:
        response = httpx.get(
            url,
            headers=HTTP_HEADERS,
            timeout=15.0,
            follow_redirects=True,
        )
        if response.status_code == 404:
            raise WNBALiveNotFoundError(
                f"Official WNBA live-data resource was not found: {url}"
            )
        response.raise_for_status()
        payload = response.json()
    except WNBALiveNotFoundError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise WNBALiveUpstreamError(
            f"Official WNBA live-data request failed: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WNBALiveUpstreamError(
            "Official WNBA live-data endpoint returned a non-object payload."
        )

    retrieved_at_utc = _utc_now_iso()
    with _CACHE_LOCK:
        for key in [
            key for key, item in _CACHE.items() if item["expires_at"] <= now
        ]:
            _CACHE.pop(key, None)
        if len(_CACHE) >= CACHE_MAX_ENTRIES:
            _CACHE.pop(next(iter(_CACHE)), None)
        _CACHE[url] = {
            "payload": deepcopy(payload),
            "retrieved_at_utc": retrieved_at_utc,
            "expires_at": now + CACHE_TTL_SECONDS,
        }
    return payload, retrieved_at_utc, False


def _normalize_periods(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [
        {
            "period": _to_int(item.get("period")),
            "period_type": _clean_text(item.get("periodType")),
            "score": _to_int(item.get("score")),
        }
        for item in raw
        if isinstance(item, dict)
    ]


def _player_stats(raw: Any) -> dict[str, Any]:
    stats = raw if isinstance(raw, dict) else {}
    return {
        "minutes": _clean_text(stats.get("minutes")),
        "points": _to_int(stats.get("points")),
        "rebounds": _to_int(stats.get("reboundsTotal")),
        "offensive_rebounds": _to_int(stats.get("reboundsOffensive")),
        "defensive_rebounds": _to_int(stats.get("reboundsDefensive")),
        "assists": _to_int(stats.get("assists")),
        "steals": _to_int(stats.get("steals")),
        "blocks": _to_int(stats.get("blocks")),
        "turnovers": _to_int(stats.get("turnovers")),
        "personal_fouls": _to_int(stats.get("foulsPersonal")),
        "field_goals_made": _to_int(stats.get("fieldGoalsMade")),
        "field_goals_attempted": _to_int(stats.get("fieldGoalsAttempted")),
        "field_goal_percentage": _to_float(stats.get("fieldGoalsPercentage")),
        "three_pointers_made": _to_int(stats.get("threePointersMade")),
        "three_pointers_attempted": _to_int(stats.get("threePointersAttempted")),
        "three_point_percentage": _to_float(stats.get("threePointersPercentage")),
        "free_throws_made": _to_int(stats.get("freeThrowsMade")),
        "free_throws_attempted": _to_int(stats.get("freeThrowsAttempted")),
        "free_throw_percentage": _to_float(stats.get("freeThrowsPercentage")),
        "plus_minus": _to_float(stats.get("plusMinusPoints")),
    }


def _normalize_live_player(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": _to_int(raw.get("personId")),
        "name": _clean_text(raw.get("name")),
        "name_initial": _clean_text(raw.get("nameI")),
        "first_name": _clean_text(raw.get("firstName")),
        "family_name": _clean_text(raw.get("familyName")),
        "jersey_number": _clean_text(raw.get("jerseyNum")),
        "position": _clean_text(raw.get("position")),
        "starter": _clean_text(raw.get("starter")),
        "on_court": _to_bool(raw.get("oncourt")),
        "played": _to_bool(raw.get("played")),
        "statistics": _player_stats(raw.get("statistics")),
    }


def _normalize_live_team(raw: dict[str, Any], season: int) -> dict[str, Any]:
    registry = _registry_team_from_live(raw, season)
    players_raw = raw.get("players")
    players = [
        _normalize_live_player(player)
        for player in players_raw
        if isinstance(player, dict)
    ] if isinstance(players_raw, list) else []
    on_court = [player for player in players if player["on_court"] is True]
    return {
        "official_team_id": _to_int(raw.get("teamId")),
        "team_key": registry["team_key"] if registry else None,
        "team_full_name": registry["full_name"] if registry else None,
        "team_abbreviation": _clean_text(raw.get("teamTricode")),
        "team_city": _clean_text(raw.get("teamCity")),
        "team_name": _clean_text(raw.get("teamName")),
        "score": _to_int(raw.get("score")),
        "in_bonus": _to_bool(raw.get("inBonus")),
        "timeouts_remaining": _to_int(raw.get("timeoutsRemaining")),
        "periods": _normalize_periods(raw.get("periods")),
        "player_count": len(players),
        "players": players,
        "on_court_player_ids": [
            player["player_id"] for player in on_court if player["player_id"] is not None
        ],
        "on_court_count": len(on_court),
        "on_court_exactly_five": len(on_court) == 5,
        "mapped_to_registry": registry is not None,
    }


def _normalize_scoreboard_team(raw: dict[str, Any], season: int) -> dict[str, Any]:
    registry = _registry_team_from_live(raw, season)
    return {
        "official_team_id": _to_int(raw.get("teamId")),
        "team_key": registry["team_key"] if registry else None,
        "team_full_name": registry["full_name"] if registry else None,
        "team_abbreviation": _clean_text(raw.get("teamTricode")),
        "score": _to_int(raw.get("score")),
        "wins": _to_int(raw.get("wins")),
        "losses": _to_int(raw.get("losses")),
        "periods": _normalize_periods(raw.get("periods")),
        "mapped_to_registry": registry is not None,
    }


def _normalize_scoreboard_game(raw: dict[str, Any], season: int) -> dict[str, Any]:
    game_id = _clean_text(raw.get("gameId"))
    code = _to_int(raw.get("gameStatus"))
    text = _clean_text(raw.get("gameStatusText"))
    home = _normalize_scoreboard_team(
        raw.get("homeTeam") if isinstance(raw.get("homeTeam"), dict) else {}, season
    )
    away = _normalize_scoreboard_team(
        raw.get("awayTeam") if isinstance(raw.get("awayTeam"), dict) else {}, season
    )
    return {
        "game_id": game_id,
        "game_id_valid": bool(game_id and len(game_id) == 10 and game_id.isdigit()),
        "game_code": _clean_text(raw.get("gameCode")),
        "game_time_utc": _clean_text(raw.get("gameTimeUTC")),
        "game_et": _clean_text(raw.get("gameEt")),
        "status": {"code": code, "text": text, "category": _status_category(code, text)},
        "period": _to_int(raw.get("period")),
        "game_clock": _clean_text(raw.get("gameClock")),
        "clock_seconds_remaining": clock_to_seconds_remaining(raw.get("gameClock")),
        "home": home,
        "away": away,
        "regulation_periods": _to_int(raw.get("regulationPeriods")),
        "series_text": _clean_text(raw.get("seriesText")),
        "if_necessary": _to_bool(raw.get("ifNecessary")),
        "verification": {
            "teams_mapped_to_registry": home["mapped_to_registry"] and away["mapped_to_registry"],
            "home_away_distinct": (
                home["official_team_id"] is not None
                and away["official_team_id"] is not None
                and home["official_team_id"] != away["official_team_id"]
            ),
        },
    }


def get_live_scoreboard_dataset(season: int) -> dict[str, Any]:
    get_wnba_teams(season)
    payload, retrieved_at_utc, cache_hit = _request_json(WNBA_SCOREBOARD_URL)
    scoreboard = payload.get("scoreboard")
    if not isinstance(scoreboard, dict):
        raise WNBALiveUpstreamError(
            "Official WNBA live scoreboard is missing the scoreboard object."
        )
    league_id = _clean_text(scoreboard.get("leagueId"))
    if league_id is not None and league_id != WNBA_LEAGUE_ID:
        raise WNBALiveUpstreamError(
            f"Official WNBA live scoreboard returned unexpected leagueId {league_id!r}."
        )
    raw_games = scoreboard.get("games")
    if not isinstance(raw_games, list):
        raise WNBALiveUpstreamError("Official WNBA live scoreboard is missing games.")
    games = [
        _normalize_scoreboard_game(game, season)
        for game in raw_games
        if isinstance(game, dict)
    ]
    ids = [game["game_id"] for game in games if game["game_id"] is not None]
    duplicates = sorted({game_id for game_id in ids if ids.count(game_id) > 1})
    unmapped = sum(not game["verification"]["teams_mapped_to_registry"] for game in games)
    return {
        "source": WNBA_LIVE_SOURCE,
        "source_url": WNBA_SCOREBOARD_URL,
        "data_type": "official_live_scoreboard",
        "league_id": league_id or WNBA_LEAGUE_ID,
        "season": season,
        "game_date": _clean_text(scoreboard.get("gameDate")),
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "game_count": len(games),
        "live_game_count": sum(game["status"]["category"] == "live" for game in games),
        "games": games,
        "verification": {
            "all_game_ids_valid": all(game["game_id_valid"] for game in games),
            "game_ids_unique": not duplicates,
            "duplicate_game_ids": duplicates,
            "all_teams_mapped_to_registry": unmapped == 0,
            "unmapped_game_count": unmapped,
        },
    }


def _event_category(action_type: Any, sub_type: Any) -> str:
    action = (_clean_text(action_type) or "").casefold().replace("_", "")
    sub = (_clean_text(sub_type) or "").casefold().replace("_", "")
    joined = f"{action} {sub}"
    if "freethrow" in joined:
        return "free_throw"
    if action in {"2pt", "3pt", "fieldgoal", "shot"} or any(
        phrase in joined for phrase in ("jump shot", "layup", "dunk")
    ):
        return "shot"
    if "rebound" in joined:
        return "rebound"
    if "turnover" in joined:
        return "turnover"
    if "foul" in joined:
        return "foul"
    if "substitution" in joined or action == "sub":
        return "substitution"
    if "timeout" in joined:
        return "timeout"
    if "jumpball" in joined or "jump ball" in joined:
        return "jump_ball"
    if "period" in joined or action in {"startperiod", "endperiod"}:
        return "period"
    if "violation" in joined:
        return "violation"
    return "other"


def _normalize_action(raw: dict[str, Any], season: int) -> dict[str, Any]:
    period = _to_int(raw.get("period"))
    clock = _clean_text(raw.get("clock"))
    clock_seconds = clock_to_seconds_remaining(clock)
    team = _registry_team_from_tricode(raw.get("teamTricode"), season)
    return {
        "action_number": _to_int(raw.get("actionNumber")),
        "action_id": _clean_text(raw.get("actionId")),
        "period": period,
        "clock": clock,
        "clock_seconds_remaining": clock_seconds,
        "elapsed_game_seconds": _elapsed_game_seconds(period, clock_seconds),
        "team_id": _to_int(raw.get("teamId")),
        "team_tricode": _clean_text(raw.get("teamTricode")),
        "team_key": team["team_key"] if team else None,
        "person_id": _to_int(raw.get("personId")),
        "player_name": _clean_text(raw.get("playerName")),
        "player_name_initial": _clean_text(raw.get("playerNameI")),
        "description": _clean_text(raw.get("description")),
        "action_type": _clean_text(raw.get("actionType")),
        "sub_type": _clean_text(raw.get("subType")),
        "event_category": _event_category(raw.get("actionType"), raw.get("subType")),
        "shot_result": _clean_text(raw.get("shotResult")),
        "shot_distance_feet": _to_float(raw.get("shotDistance")),
        "is_field_goal": _to_bool(raw.get("isFieldGoal")),
        "x_legacy": _to_float(raw.get("xLegacy")),
        "y_legacy": _to_float(raw.get("yLegacy")),
        "score_home": _to_int(raw.get("scoreHome")),
        "score_away": _to_int(raw.get("scoreAway")),
        "points_total": _to_int(raw.get("pointsTotal")),
        "location": _clean_text(raw.get("location")),
        "video_available": _to_bool(raw.get("videoAvailable")),
        "assist_person_id": _to_int(raw.get("assistPersonId")),
        "assist_player_name": _clean_text(raw.get("assistPlayerNameInitial")),
        "block_person_id": _to_int(raw.get("blockPersonId")),
        "rebound_total": _to_int(raw.get("reboundTotal")),
        "rebound_offensive_total": _to_int(raw.get("reboundOffensiveTotal")),
        "rebound_defensive_total": _to_int(raw.get("reboundDefensiveTotal")),
        "foul_personal_total": _to_int(raw.get("foulPersonalTotal")),
        "qualifiers": deepcopy(raw.get("qualifiers")) if isinstance(raw.get("qualifiers"), list) else [],
        "points_scored_on_action": None,
        "scoring_side": None,
    }


def _annotate_score_deltas(actions: list[dict[str, Any]]) -> None:
    previous_home = 0
    previous_away = 0
    for action in actions:
        current_home = action.get("score_home")
        current_away = action.get("score_away")
        if current_home is None or current_away is None:
            continue
        delta_home = current_home - previous_home
        delta_away = current_away - previous_away
        if delta_home >= 0 and delta_away >= 0 and not (delta_home and delta_away):
            if delta_home > 0:
                action["points_scored_on_action"] = delta_home
                action["scoring_side"] = "home"
            elif delta_away > 0:
                action["points_scored_on_action"] = delta_away
                action["scoring_side"] = "away"
            else:
                action["points_scored_on_action"] = 0
        previous_home = current_home
        previous_away = current_away


def _play_by_play_root(payload: dict[str, Any], game_id: str) -> dict[str, Any]:
    game = payload.get("game")
    if not isinstance(game, dict):
        raise WNBALiveUpstreamError("Official WNBA play-by-play payload is missing game.")
    returned_id = _clean_text(game.get("gameId"))
    if returned_id is not None and returned_id != game_id:
        raise WNBALiveUpstreamError(
            "Official WNBA play-by-play game ID did not match the requested game ID."
        )
    if not isinstance(game.get("actions"), list):
        raise WNBALiveUpstreamError("Official WNBA play-by-play payload is missing actions.")
    return game


def get_play_by_play_dataset(
    game_id: str,
    season: int,
    *,
    event_category: str = "All",
    limit: int = 0,
) -> dict[str, Any]:
    get_wnba_teams(season)
    game_id = _validate_game_id(game_id)
    category = _normalize_choice(event_category, ALLOWED_EVENT_CATEGORIES, "event_category")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0 or limit > 1000:
        raise ValueError("WNBA play-by-play limit must be an integer from 0 through 1000.")

    url = WNBA_PLAY_BY_PLAY_URL.format(game_id=game_id)
    payload, retrieved_at_utc, cache_hit = _request_json(url)
    game = _play_by_play_root(payload, game_id)
    actions = [
        _normalize_action(item, season)
        for item in game.get("actions", [])
        if isinstance(item, dict)
    ]
    _annotate_score_deltas(actions)
    action_ids = [action["action_id"] for action in actions if action["action_id"] is not None]
    duplicates = sorted({value for value in action_ids if action_ids.count(value) > 1})
    unmapped = sum(
        action["team_tricode"] is not None and action["team_key"] is None
        for action in actions
    )
    filtered = actions if category == "All" else [
        action for action in actions if action["event_category"] == category
    ]
    if limit > 0:
        filtered = filtered[-limit:]
    return {
        "source": WNBA_LIVE_SOURCE,
        "source_url": url,
        "data_type": "official_live_play_by_play",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "game_id": game_id,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "filters": {"event_category": category, "limit": limit},
        "source_action_count": len(actions),
        "action_count": len(filtered),
        "latest_event": actions[-1] if actions else None,
        "actions": filtered,
        "verification": {
            "requested_game_id_matches_source": True,
            "action_ids_unique_when_present": not duplicates,
            "duplicate_action_ids": duplicates,
            "unmapped_team_event_count": unmapped,
            "all_team_events_mapped_to_registry": unmapped == 0,
            "source_order_preserved": True,
        },
    }


def _box_game_root(payload: dict[str, Any], game_id: str) -> dict[str, Any]:
    game = payload.get("game")
    if not isinstance(game, dict):
        raise WNBALiveUpstreamError("Official WNBA live box score payload is missing game.")
    returned_id = _clean_text(game.get("gameId"))
    if returned_id is not None and returned_id != game_id:
        raise WNBALiveUpstreamError(
            "Official WNBA live box-score game ID did not match the requested game ID."
        )
    return game


def _normalize_live_state_from_box(
    game: dict[str, Any], game_id: str, season: int
) -> dict[str, Any]:
    code = _to_int(game.get("gameStatus"))
    text = _clean_text(game.get("gameStatusText"))
    period = _to_int(game.get("period"))
    clock = _clean_text(game.get("gameClock"))
    clock_seconds = clock_to_seconds_remaining(clock)
    home_raw = game.get("homeTeam") if isinstance(game.get("homeTeam"), dict) else None
    away_raw = game.get("awayTeam") if isinstance(game.get("awayTeam"), dict) else None
    if home_raw is None or away_raw is None:
        raise WNBALiveUpstreamError(
            "Official WNBA live box score is missing homeTeam or awayTeam."
        )
    home = _normalize_live_team(home_raw, season)
    away = _normalize_live_team(away_raw, season)
    if not home["mapped_to_registry"] or not away["mapped_to_registry"]:
        raise WNBALiveUpstreamError(
            "Official WNBA live box score contains an unmapped team identity."
        )
    if (
        home["official_team_id"] is None
        or away["official_team_id"] is None
        or home["official_team_id"] == away["official_team_id"]
    ):
        raise WNBALiveUpstreamError(
            "Official WNBA live box score contains invalid home/away team identity."
        )
    return {
        "game_id": game_id,
        "status": {"code": code, "text": text, "category": _status_category(code, text)},
        "period": period,
        "period_type": _clean_text(game.get("periodType")),
        "game_clock": clock,
        "clock_seconds_remaining": clock_seconds,
        "elapsed_game_seconds": _elapsed_game_seconds(period, clock_seconds),
        "game_time_local": _clean_text(game.get("gameTimeLocal")),
        "game_time_utc": _clean_text(game.get("gameTimeUTC")),
        "attendance": _to_int(game.get("attendance")),
        "sellout": _clean_text(game.get("sellout")),
        "home": home,
        "away": away,
    }


def get_live_game_state_dataset(game_id: str, season: int) -> dict[str, Any]:
    get_wnba_teams(season)
    game_id = _validate_game_id(game_id)
    box_url = WNBA_BOX_SCORE_URL.format(game_id=game_id)
    payload, retrieved_at_utc, cache_hit = _request_json(box_url)
    state = _normalize_live_state_from_box(_box_game_root(payload, game_id), game_id, season)

    pbp_dataset = None
    pbp_error = None
    try:
        pbp_dataset = get_play_by_play_dataset(game_id, season)
    except (WNBALiveNotFoundError, WNBALiveUpstreamError) as exc:
        pbp_error = str(exc)

    latest = pbp_dataset["latest_event"] if pbp_dataset else None
    score_matches = None
    if latest is not None:
        latest_home = latest.get("score_home")
        latest_away = latest.get("score_away")
        if latest_home is not None and latest_away is not None:
            score_matches = (
                latest_home == state["home"]["score"]
                and latest_away == state["away"]["score"]
            )
    return {
        "source": WNBA_LIVE_SOURCE,
        "source_url": box_url,
        "play_by_play_source_url": (
            pbp_dataset["source_url"] if pbp_dataset
            else WNBA_PLAY_BY_PLAY_URL.format(game_id=game_id)
        ),
        "data_type": "official_live_game_state",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        **state,
        "play_by_play": {
            "available": pbp_dataset is not None,
            "error": pbp_error,
            "event_count": pbp_dataset["source_action_count"] if pbp_dataset else None,
            "latest_event": latest,
        },
        "verification": {
            "requested_game_id_matches_source": True,
            "teams_mapped_to_registry": True,
            "home_away_distinct": True,
            "home_on_court_exactly_five": state["home"]["on_court_exactly_five"],
            "away_on_court_exactly_five": state["away"]["on_court_exactly_five"],
            "play_by_play_available": pbp_dataset is not None,
            "box_score_matches_latest_play_by_play_score": score_matches,
            "no_model_derived_live_fields": True,
        },
    }
