"""Step 7G first-party Step-4L shot-context adapter.

Frozen Step 4L normally reads ``stats.wnba.com`` shot-chart / shot-location
endpoints. Hosted runners cannot reliably reach those transports. This isolated
adapter reconstructs the Step-4L model-input shapes from official WNBA.com
first-party evidence already certified by Step 7G:

* player ``latestGames`` identity for bounded recent-game selection;
* official Step-4N season schedule for exact game/team/date identity; and
* official WNBA.com game-page play-by-play actions for shot result, player/team
  identity, description, source distance, and legacy x/y court coordinates.

WNBA.com play-by-play does not expose pre-labeled ``SHOT_ZONE_BASIC`` values.
Zone labels in this adapter are therefore explicit deterministic *observed-data
classifications* from the preserved official description/coordinates. They are
not model probabilities, projections, defender assignments, or fabricated shot
events. Ambiguous game/team/player identity fails closed.

Certified scope: 2026 Regular Season, current-roster focal players used by the
Step-4W/4X pregame readiness path. Production remains default-OFF through the
Step-7G integration flag.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from math import hypot
from time import sleep
from typing import Any

from sports_api.wnba_rosters import WNBAStatsUpstreamError
from sports_api.wnba_schedule import WNBAScheduleUpstreamError
from sports_api.wnba_schedule_context import WNBARestTravelUpstreamError
from sports_api.wnba_shot_context import (
    WNBAShotContextNotFoundError,
    WNBAShotContextUpstreamError,
)
from sports_api.wnba_step7g_first_party_history import (
    WNBAStep7GFirstPartyNotFoundError,
    WNBAStep7GFirstPartyUpstreamError,
    get_first_party_player_recent_game_log_dataset,
    get_first_party_play_by_play_dataset,
)
from sports_api.wnba_step7g_first_party_rosters import (
    get_first_party_current_players_dataset,
)
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)

SOURCE = "WNBA.com First-Party Page Data"
SOURCE_URL = "https://www.wnba.com/"
SOURCE_VARIANT = "step7g_step4l_pbp_coordinate_observed_zone_derivation_v1"
WNBA_LEAGUE_ID = "10"
CERTIFIED_SEASON = 2026
CERTIFIED_SEASON_TYPE = "Regular Season"
REGULAR_SEASON_GAME_PREFIX_BY_SEASON = {2026: "10226"}
PBP_ATTEMPTS = 2
PBP_RETRY_WAIT_SECONDS = 0.5

_ZONE_LABELS = {
    "restricted_area": "Restricted Area",
    "paint_non_ra": "In The Paint (Non-RA)",
    "mid_range": "Mid-Range",
    "left_corner_3": "Left Corner 3",
    "right_corner_3": "Right Corner 3",
    "above_the_break_3": "Above the Break 3",
    "backcourt": "Backcourt",
}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _validate_scope(season: int, season_type: str) -> str:
    if season != CERTIFIED_SEASON:
        raise ValueError("Step 7G first-party shot context is certified for 2026 only.")
    normalized = str(season_type).strip()
    if normalized.casefold() != CERTIFIED_SEASON_TYPE.casefold():
        raise ValueError(
            "Step 7G first-party shot context is certified for Regular Season only."
        )
    return CERTIFIED_SEASON_TYPE


def _validate_last_n(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
        raise ValueError("WNBA last_n_games must be an integer from 0 through 100.")
    return value


def _validate_player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _regular_game_id(game_id: Any, season: int) -> bool:
    text = _clean(game_id)
    prefix = REGULAR_SEASON_GAME_PREFIX_BY_SEASON.get(season)
    return bool(text and prefix and len(text) == 10 and text.isdigit() and text.startswith(prefix))


def _participants(game: dict[str, Any]) -> tuple[str, str]:
    away = game.get("away")
    home = game.get("home")
    if not isinstance(away, dict) or not isinstance(home, dict):
        raise WNBAShotContextUpstreamError("Step 4N game is missing away/home identity.")
    away_key = _clean(away.get("team_key"))
    home_key = _clean(home.get("team_key"))
    if not away_key or not home_key or away_key == home_key:
        raise WNBAShotContextUpstreamError("Step 4N game has invalid away/home team identity.")
    verification = game.get("verification")
    if not isinstance(verification, dict) or (
        verification.get("game_id_valid") is not True
        or verification.get("teams_mapped_to_registry") is not True
        or verification.get("home_away_distinct") is not True
    ):
        raise WNBAShotContextUpstreamError("Step 4N game failed shot-context identity verification.")
    return away_key, home_key


def _schedule(season: int) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    try:
        dataset = get_step7g_step4n_season_schedule_dataset(season)
    except (WNBAScheduleUpstreamError, WNBARestTravelUpstreamError) as exc:
        raise WNBAShotContextUpstreamError(
            f"Step 7G first-party schedule was unavailable for Step 4L: {exc}"
        ) from exc
    games = dataset.get("games")
    if not isinstance(games, list):
        raise WNBAShotContextUpstreamError("Step 4N season schedule has malformed games.")
    by_id: dict[str, dict[str, Any]] = {}
    for game in games:
        if not isinstance(game, dict):
            continue
        game_id = _clean(game.get("game_id"))
        if not game_id:
            continue
        if game_id in by_id:
            raise WNBAShotContextUpstreamError(
                f"Step 4N schedule contains duplicate game ID {game_id}."
            )
        _participants(game)
        by_id[game_id] = game
    return dataset, by_id


def _is_final_regular(game: dict[str, Any], season: int) -> bool:
    if not _regular_game_id(game.get("game_id"), season):
        return False
    status = game.get("status")
    return isinstance(status, dict) and _clean(status.get("category")) == "final"


def _game_sort_key(game: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _clean(game.get("game_datetime_utc")) or "",
        _clean(game.get("official_schedule_date")) or "",
        _clean(game.get("game_id")) or "",
    )


def _current_player_team(player_id: int, season: int) -> tuple[str, str | None]:
    try:
        roster = get_first_party_current_players_dataset(season)
    except WNBAStatsUpstreamError as exc:
        raise WNBAShotContextUpstreamError(
            f"Step 7G current roster was unavailable for Step 4L: {exc}"
        ) from exc
    players = roster.get("players")
    if not isinstance(players, list):
        raise WNBAShotContextUpstreamError("Step 7G current roster has malformed players.")
    rows = [
        row for row in players
        if isinstance(row, dict) and _to_int(row.get("player_id")) == player_id
    ]
    if len(rows) != 1:
        raise WNBAShotContextNotFoundError(
            f"Current official WNBA roster did not resolve exactly one row for player {player_id}."
        )
    team_key = _clean(rows[0].get("team_key"))
    if not team_key:
        raise WNBAShotContextUpstreamError("Current official roster row is missing team identity.")
    return team_key, _clean(rows[0].get("full_name"))


def _fetch_pbp(game_id: str, season: int) -> dict[str, Any]:
    last_error: BaseException | None = None
    for attempt in range(PBP_ATTEMPTS):
        try:
            return get_first_party_play_by_play_dataset(
                game_id,
                season,
                event_category="shot",
                limit=0,
            )
        except WNBAStep7GFirstPartyNotFoundError as exc:
            raise WNBAShotContextNotFoundError(str(exc)) from exc
        except WNBAStep7GFirstPartyUpstreamError as exc:
            last_error = exc
            if attempt + 1 < PBP_ATTEMPTS:
                sleep(PBP_RETRY_WAIT_SECONDS)
                continue
            break
    assert last_error is not None
    raise WNBAShotContextUpstreamError(
        f"Official WNBA.com play-by-play was unavailable for game {game_id}: {last_error}"
    ) from last_error


def _geometry_radius_units(action: dict[str, Any]) -> float | None:
    x = _to_float(action.get("x_legacy"))
    y = _to_float(action.get("y_legacy"))
    if x is None or y is None:
        return None
    return hypot(x, y)


def _is_three(action: dict[str, Any]) -> bool:
    description = (_clean(action.get("description")) or "").upper()
    if "3PT" in description:
        return True
    if _to_int(action.get("points_scored_on_action")) == 3:
        return True
    radius = _geometry_radius_units(action)
    return radius is not None and radius >= 220.0


def classify_official_shot_zone(action: dict[str, Any]) -> tuple[str, str, str]:
    """Classify one official shot action using preserved WNBA.com geometry.

    Legacy x/y are tenths-of-feet style court coordinates centered on the basket
    (the same family exposed by official liveData). Thresholds mirror standard
    court geometry: ~4 ft restricted radius, 8 ft half-lane, ~19 ft paint
    extent, ~22 ft three-point radius, and corner x/y bounds.
    """
    x = _to_float(action.get("x_legacy"))
    y = _to_float(action.get("y_legacy"))
    radius = _geometry_radius_units(action)
    source_distance = _to_float(action.get("shot_distance_feet"))
    is_three = _is_three(action)

    if radius is not None and radius >= 470.0:
        key = "backcourt"
    elif is_three:
        if x is not None and y is not None and abs(x) >= 220.0 and y <= 92.0:
            key = "left_corner_3" if x < 0 else "right_corner_3"
        else:
            key = "above_the_break_3"
    elif (
        (source_distance is not None and 0 < source_distance <= 4.0)
        or (radius is not None and radius <= 40.0)
    ):
        key = "restricted_area"
    elif x is not None and y is not None and abs(x) <= 80.0 and -50.0 <= y <= 190.0:
        key = "paint_non_ra"
    else:
        key = "mid_range"

    area: str
    if key == "left_corner_3":
        area = "Left Side(L)"
    elif key == "right_corner_3":
        area = "Right Side(R)"
    elif x is None:
        area = "Unknown"
    elif x < -80:
        area = "Left Side(L)"
    elif x > 80:
        area = "Right Side(R)"
    else:
        area = "Center(C)"

    effective_distance = source_distance
    if (effective_distance is None or effective_distance <= 0) and radius is not None:
        effective_distance = radius / 10.0
    if effective_distance is None:
        range_label = "Unknown"
    elif effective_distance < 8:
        range_label = "Less Than 8 ft."
    elif effective_distance < 16:
        range_label = "8-16 ft."
    elif effective_distance < 24:
        range_label = "16-24 ft."
    else:
        range_label = "24+ ft."
    return key, area, range_label


def _side_for_action(game: dict[str, Any], team_key: str) -> dict[str, Any]:
    away = game["away"]
    home = game["home"]
    matches = [side for side in (away, home) if _clean(side.get("team_key")) == team_key]
    if len(matches) != 1:
        raise WNBAShotContextUpstreamError(
            "Official shot action team does not resolve to exactly one scheduled side."
        )
    side = matches[0]
    if _to_int(side.get("official_team_id")) in (None, 0):
        raise WNBAShotContextUpstreamError("Scheduled shot team is missing official team ID.")
    return side


def _normalize_shot(
    action: dict[str, Any],
    game: dict[str, Any],
    *,
    expected_player_id: int | None = None,
) -> dict[str, Any]:
    if _clean(action.get("event_category")) != "shot":
        raise WNBAShotContextUpstreamError("Non-shot play-by-play action reached Step 4L normalization.")
    player_id = _to_int(action.get("person_id"))
    if expected_player_id is not None and player_id != expected_player_id:
        raise WNBAShotContextUpstreamError("Shot action player identity disagrees with requested player.")
    team_key = _clean(action.get("team_key"))
    if not team_key:
        raise WNBAShotContextUpstreamError("Official shot action is missing mapped team identity.")
    side = _side_for_action(game, team_key)
    result = (_clean(action.get("shot_result")) or "").casefold()
    if result not in {"made", "missed"}:
        action_type = (_clean(action.get("action_type")) or "").casefold()
        if action_type.startswith("made"):
            result = "made"
        elif action_type.startswith("miss"):
            result = "missed"
        else:
            raise WNBAShotContextUpstreamError(
                "Official shot action does not expose a deterministic made/missed result."
            )
    made = result == "made"
    three = _is_three(action)
    zone_key, area, range_label = classify_official_shot_zone(action)
    zone_label = _ZONE_LABELS[zone_key]
    away = game["away"]
    home = game["home"]
    return {
        "game_id": _clean(game.get("game_id")),
        "game_id_valid": _regular_game_id(game.get("game_id"), CERTIFIED_SEASON),
        "game_event_id": _to_int(action.get("action_number")),
        "player_id": player_id,
        "player_name": _clean(action.get("player_name")),
        "official_team_id": _to_int(side.get("official_team_id")),
        "team_name_source": _clean(side.get("full_name")) or _clean(side.get("team_name")),
        "team_key": team_key,
        "mapped_to_registry": True,
        "period": _to_int(action.get("period")),
        "minutes_remaining": (
            int(float(action.get("clock_seconds_remaining")) // 60)
            if _to_float(action.get("clock_seconds_remaining")) is not None
            else None
        ),
        "seconds_remaining": (
            int(float(action.get("clock_seconds_remaining")) % 60)
            if _to_float(action.get("clock_seconds_remaining")) is not None
            else None
        ),
        "event_type": _clean(action.get("action_type")),
        "action_type": _clean(action.get("sub_type")),
        "shot_type": "3PT Field Goal" if three else "2PT Field Goal",
        "shot_zone_basic": zone_label,
        "shot_zone_area": area,
        "shot_zone_range": range_label,
        "canonical_zone": zone_key,
        "shot_distance_feet": _to_float(action.get("shot_distance_feet")),
        "location_x_source": _to_float(action.get("x_legacy")),
        "location_y_source": _to_float(action.get("y_legacy")),
        "coordinate_system": "official_wnba_liveData_legacy_xy_source_units",
        "attempted": True,
        "made": made,
        "points_if_made": 3 if three else 2,
        "points_scored": (3 if three else 2) if made else 0,
        "game_date": _clean(game.get("official_schedule_date")),
        "home_team_tricode": _clean(home.get("team_tricode")),
        "visitor_team_tricode": _clean(away.get("team_tricode")),
        "zone_derivation": {
            "type": "deterministic_observed_coordinate_classification",
            "description_3pt_marker_used": "3PT" in ((_clean(action.get("description")) or "").upper()),
            "source_description": _clean(action.get("description")),
            "source_action_id": _clean(action.get("action_id")),
            "source_coordinates_preserved": True,
            "not_a_projection": True,
        },
    }


def _pct(made: float, attempts: float) -> float | None:
    return round(made / attempts, 4) if attempts > 0 else None


def _aggregate_shots(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    total = len(shots)
    for shot in shots:
        key = str(shot["canonical_zone"])
        item = groups.setdefault(
            key,
            {
                "shot_zone_basic": shot["shot_zone_basic"],
                "canonical_zone": key,
                "field_goals_made": 0.0,
                "field_goals_attempted": 0.0,
                "points_scored": 0.0,
            },
        )
        item["field_goals_attempted"] += 1.0
        if shot["made"]:
            item["field_goals_made"] += 1.0
            item["points_scored"] += float(shot["points_scored"])
    out: list[dict[str, Any]] = []
    for item in groups.values():
        attempts = item["field_goals_attempted"]
        item["field_goal_percentage"] = _pct(item["field_goals_made"], attempts)
        item["attempt_share"] = round(attempts / total, 4) if total else None
        item["observed_points_per_attempt"] = (
            round(item["points_scored"] / attempts, 4) if attempts else None
        )
        out.append(item)
    return sorted(out, key=lambda row: (-row["field_goals_attempted"], row["shot_zone_basic"]))


def _corner_composite(
    zones: list[dict[str, Any]],
    made_key: str,
    attempt_key: str,
) -> dict[str, Any] | None:
    parts = [
        row for row in zones
        if row.get("canonical_zone") in {"left_corner_3", "right_corner_3"}
    ]
    if not parts:
        return None
    made = sum(float(row.get(made_key) or 0.0) for row in parts)
    attempts = sum(float(row.get(attempt_key) or 0.0) for row in parts)
    result = {
        "shot_zone_basic": "Corner 3",
        "canonical_zone": "corner_3",
        made_key: made,
        attempt_key: attempts,
        "derived_from": ["Left Corner 3", "Right Corner 3"],
    }
    if made_key == "field_goals_made_allowed":
        result["field_goal_percentage_allowed"] = _pct(made, attempts)
    else:
        result["field_goal_percentage"] = _pct(made, attempts)
    return result


def _validate_shot_keys(shots: list[dict[str, Any]]) -> None:
    keys = [
        (shot.get("game_id"), shot.get("game_event_id"))
        for shot in shots
        if shot.get("game_id") and shot.get("game_event_id") is not None
    ]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise WNBAShotContextUpstreamError(
            "First-party Step 4L produced duplicate game/event shot keys: "
            + ", ".join(f"{game}:{event}" for game, event in duplicates)
        )
    if any(not shot.get("game_id_valid") for shot in shots):
        raise WNBAShotContextUpstreamError("First-party Step 4L admitted a non-regular/invalid game ID.")
    if any(not shot.get("mapped_to_registry") for shot in shots):
        raise WNBAShotContextUpstreamError("First-party Step 4L admitted an unmapped shot team.")


def _recent_player_games(
    player_id: int,
    season: int,
    last_n_games: int,
    schedule_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    if last_n_games == 0:
        raise WNBAShotContextNotFoundError(
            "Step 7G first-party recent player page does not certify season-to-date shot-chart completeness when last_n_games=0."
        )
    try:
        history = get_first_party_player_recent_game_log_dataset(
            player_id,
            season,
            season_type=CERTIFIED_SEASON_TYPE,
        )
    except WNBAStep7GFirstPartyNotFoundError as exc:
        raise WNBAShotContextNotFoundError(str(exc)) from exc
    except WNBAStep7GFirstPartyUpstreamError as exc:
        raise WNBAShotContextUpstreamError(str(exc)) from exc
    rows = history.get("games")
    if not isinstance(rows, list):
        raise WNBAShotContextUpstreamError("First-party player latestGames has malformed games.")

    candidates: list[dict[str, Any]] = []
    names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _to_int(row.get("player_id")) not in {None, player_id}:
            raise WNBAShotContextUpstreamError("First-party latestGames returned conflicting player identity.")
        game_id = _clean(row.get("game_id"))
        if not game_id or not _regular_game_id(game_id, season):
            continue
        game = schedule_by_id.get(game_id)
        if game is None:
            raise WNBAShotContextUpstreamError(
                f"First-party player game {game_id} was not found in certified Step 4N schedule."
            )
        if not _is_final_regular(game, season):
            continue
        matchup = row.get("matchup")
        if not isinstance(matchup, dict):
            raise WNBAShotContextUpstreamError("First-party player game has malformed matchup identity.")
        team_key = _clean(matchup.get("team_key"))
        opponent_key = _clean(matchup.get("opponent_team_key"))
        away_key, home_key = _participants(game)
        if not team_key or not opponent_key or {team_key, opponent_key} != {away_key, home_key}:
            raise WNBAShotContextUpstreamError(
                f"First-party player matchup identity disagrees with Step 4N for game {game_id}."
            )
        candidates.append(game)
    candidates.sort(key=_game_sort_key, reverse=True)
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for game in candidates:
        game_id = str(game["game_id"])
        if game_id in seen:
            raise WNBAShotContextUpstreamError("First-party player latestGames contains duplicate game IDs.")
        seen.add(game_id)
        unique.append(game)
    return unique[:last_n_games], next(iter(names), None) if len(names) == 1 else None


def _h2h_games(
    player_id: int,
    opponent_team_key: str,
    season: int,
    last_n_games: int,
    schedule_games: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str, str | None]:
    current_team_key, player_name = _current_player_team(player_id, season)
    if opponent_team_key == current_team_key:
        raise ValueError("WNBA opponent_team_key cannot equal the player's current team.")
    games = [
        game for game in schedule_games
        if isinstance(game, dict)
        and _is_final_regular(game, season)
        and set(_participants(game)) == {current_team_key, opponent_team_key}
    ]
    games.sort(key=_game_sort_key, reverse=True)
    if last_n_games > 0:
        games = games[:last_n_games]
    return games, current_team_key, player_name


def _player_shots_from_games(
    player_id: int,
    games: list[dict[str, Any]],
    season: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    shots: list[dict[str, Any]] = []
    source_urls: list[str] = []
    for game in games:
        game_id = str(game["game_id"])
        pbp = _fetch_pbp(game_id, season)
        source_url = _clean(pbp.get("source_url"))
        if source_url and source_url not in source_urls:
            source_urls.append(source_url)
        actions = pbp.get("actions")
        if not isinstance(actions, list):
            raise WNBAShotContextUpstreamError("First-party play-by-play has malformed actions.")
        for action in actions:
            if not isinstance(action, dict) or _clean(action.get("event_category")) != "shot":
                continue
            if _to_int(action.get("person_id")) != player_id:
                continue
            shots.append(_normalize_shot(action, game, expected_player_id=player_id))
    _validate_shot_keys(shots)
    return shots, source_urls


def get_first_party_player_shot_chart_dataset(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    opponent_team_key: str | None = None,
) -> dict[str, Any]:
    player_id = _validate_player_id(player_id)
    season_type = _validate_scope(season, season_type)
    last_n_games = _validate_last_n(last_n_games)
    schedule_dataset, schedule_by_id = _schedule(season)
    schedule_games = schedule_dataset["games"]

    player_name: str | None = None
    current_team_key: str | None = None
    if opponent_team_key is None:
        games, player_name = _recent_player_games(
            player_id, season, last_n_games, schedule_by_id
        )
        selection = "official_player_latestGames_recent_window"
    else:
        opponent_team_key = str(opponent_team_key).strip()
        registered = {
            key
            for game in schedule_games
            if isinstance(game, dict)
            for key in _participants(game)
        }
        if opponent_team_key not in registered:
            raise ValueError(f"WNBA team key {opponent_team_key!r} was not found for the 2026 season.")
        games, current_team_key, player_name = _h2h_games(
            player_id, opponent_team_key, season, last_n_games, schedule_games
        )
        selection = "current_roster_team_vs_opponent_final_regular_season_games"

    shots, source_urls = _player_shots_from_games(player_id, games, season)
    observed_names = sorted({shot["player_name"] for shot in shots if shot.get("player_name")})
    if len(observed_names) > 1:
        raise WNBAShotContextUpstreamError("First-party shot actions returned conflicting player names.")
    if observed_names:
        player_name = observed_names[0]

    zones = _aggregate_shots(shots)
    attempts = len(shots)
    made = sum(bool(shot["made"]) for shot in shots)
    return {
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "source_urls": source_urls,
        "source_endpoint": "wnba.com game playByPlay + certified Step 4N schedule",
        "source_variant": SOURCE_VARIANT,
        "data_type": "official_player_shot_chart",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "player_name": player_name,
        "filters": {
            "last_n_games": last_n_games,
            "opponent_team_key": opponent_team_key,
            "opponent_official_team_id": None,
            "current_team_key_when_opponent_filter_used": current_team_key,
        },
        "retrieved_at_utc": schedule_dataset.get("retrieved_at_utc"),
        "cache_hit": bool(schedule_dataset.get("cache_hit")),
        "cache_ttl_seconds": None,
        "selected_game_count": len(games),
        "selected_game_ids": [game["game_id"] for game in games],
        "shot_count": len(shots),
        "attempt_count": attempts,
        "made_count": made,
        "field_goal_percentage": _pct(made, attempts),
        "zone_summary": zones,
        "corner_three_composite": _corner_composite(
            zones, "field_goals_made", "field_goals_attempted"
        ),
        "league_average_rows": [],
        "shots": shots,
        "derivation": {
            "game_selection": selection,
            "zone_classification": "official description + preserved official legacy x/y geometry",
            "legacy_coordinate_units_preserved": True,
            "league_average_rows_not_reconstructed": True,
            "not_a_projection": True,
        },
        "verification": {
            "requested_player_matches_all_rows": all(shot["player_id"] == player_id for shot in shots),
            "shot_event_keys_unique": True,
            "all_game_ids_valid": True,
            "invalid_game_ids": [],
            "all_shot_teams_mapped_to_registry": True,
            "unmapped_shot_count": 0,
            "coordinates_preserved_in_source_units": True,
            "zone_labels_explicitly_derived_not_source_claimed": True,
            "only_certified_regular_season_game_ids_admitted": True,
            "no_model_derived_probabilities": True,
            "third_party_sources_used": False,
            "production_provider_replaced": False,
        },
    }


def _aggregate_opponent_rows(
    shots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_team: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for shot in shots:
        team_id = _to_int(shot.get("official_team_id"))
        team_key = _clean(shot.get("team_key"))
        if team_id in (None, 0) or not team_key:
            raise WNBAShotContextUpstreamError("Opponent shot is missing official shooting-team identity.")
        by_team[(team_id, team_key)].append(shot)
    rows: list[dict[str, Any]] = []
    for (team_id, team_key), team_shots in by_team.items():
        zones = _aggregate_shots(team_shots)
        converted = [
            {
                "shot_zone_basic": zone["shot_zone_basic"],
                "canonical_zone": zone["canonical_zone"],
                "field_goals_made": zone["field_goals_made"],
                "field_goals_attempted": zone["field_goals_attempted"],
                "field_goal_percentage_source": None,
                "field_goal_percentage_recomputed": zone["field_goal_percentage"],
                "is_composite_zone": False,
            }
            for zone in zones
        ]
        rows.append(
            {
                "official_team_id": team_id,
                "team_name_source": next(
                    (shot.get("team_name_source") for shot in team_shots if shot.get("team_name_source")),
                    None,
                ),
                "team_key": team_key,
                "mapped_to_registry": True,
                "zones": converted,
            }
        )
    return sorted(rows, key=lambda row: row["team_key"])


def get_first_party_opponent_defense_by_shot_zone_dataset(
    team_key: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
) -> dict[str, Any]:
    season_type = _validate_scope(season, season_type)
    last_n_games = _validate_last_n(last_n_games)
    defending_team_key = str(team_key).strip()
    schedule_dataset, _ = _schedule(season)
    schedule_games = schedule_dataset["games"]
    registered = {
        key
        for game in schedule_games
        if isinstance(game, dict)
        for key in _participants(game)
    }
    if defending_team_key not in registered:
        raise ValueError(f"WNBA team key {defending_team_key!r} was not found for the 2026 season.")

    games = [
        game for game in schedule_games
        if isinstance(game, dict)
        and _is_final_regular(game, season)
        and defending_team_key in set(_participants(game))
    ]
    games.sort(key=_game_sort_key, reverse=True)
    if last_n_games > 0:
        games = games[:last_n_games]

    opponent_shots: list[dict[str, Any]] = []
    source_urls: list[str] = []
    defending_team_ids: set[int] = set()
    for game in games:
        away_key, home_key = _participants(game)
        defending_side = game["away"] if away_key == defending_team_key else game["home"]
        defending_id = _to_int(defending_side.get("official_team_id"))
        if defending_id in (None, 0):
            raise WNBAShotContextUpstreamError("Defending schedule side is missing official team ID.")
        defending_team_ids.add(defending_id)
        pbp = _fetch_pbp(str(game["game_id"]), season)
        source_url = _clean(pbp.get("source_url"))
        if source_url and source_url not in source_urls:
            source_urls.append(source_url)
        actions = pbp.get("actions")
        if not isinstance(actions, list):
            raise WNBAShotContextUpstreamError("First-party play-by-play has malformed actions.")
        for action in actions:
            if not isinstance(action, dict) or _clean(action.get("event_category")) != "shot":
                continue
            shooting_team_key = _clean(action.get("team_key"))
            if shooting_team_key == defending_team_key:
                continue
            if shooting_team_key not in {away_key, home_key}:
                raise WNBAShotContextUpstreamError(
                    "Opponent shot team identity disagrees with the certified schedule game."
                )
            opponent_shots.append(_normalize_shot(action, game))
    if len(defending_team_ids) > 1:
        raise WNBAShotContextUpstreamError("Defending team official ID changed across selected schedule games.")
    _validate_shot_keys(opponent_shots)

    rows = _aggregate_opponent_rows(opponent_shots)
    groups: dict[str, dict[str, Any]] = {}
    for shot in opponent_shots:
        zone_key = str(shot["canonical_zone"])
        item = groups.setdefault(
            zone_key,
            {
                "shot_zone_basic": shot["shot_zone_basic"],
                "canonical_zone": zone_key,
                "field_goals_made_allowed": 0.0,
                "field_goals_attempted_allowed": 0.0,
                "is_composite_zone": False,
            },
        )
        item["field_goals_attempted_allowed"] += 1.0
        if shot["made"]:
            item["field_goals_made_allowed"] += 1.0
    zones_allowed = []
    for item in groups.values():
        item["field_goal_percentage_allowed"] = _pct(
            item["field_goals_made_allowed"], item["field_goals_attempted_allowed"]
        )
        zones_allowed.append(item)
    zones_allowed.sort(key=lambda row: row["shot_zone_basic"])

    defending_id = next(iter(defending_team_ids), None)
    return {
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "source_urls": source_urls,
        "source_endpoint": "wnba.com game playByPlay + certified Step 4N schedule",
        "source_variant": SOURCE_VARIANT,
        "data_type": "observed_opponent_shooting_by_defensive_team",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "defending_team_key": defending_team_key,
        "defending_official_team_id": defending_id,
        "last_n_games_source_filter": last_n_games,
        "retrieved_at_utc": schedule_dataset.get("retrieved_at_utc"),
        "cache_hit": bool(schedule_dataset.get("cache_hit")),
        "cache_ttl_seconds": None,
        "selected_game_count": len(games),
        "selected_game_ids": [game["game_id"] for game in games],
        "source_header_count": 0,
        "opponent_shooting_team_count": len(rows),
        "opponent_shooting_rows": rows,
        "zones_allowed": zones_allowed,
        "corner_three_composite": _corner_composite(
            zones_allowed,
            "field_goals_made_allowed",
            "field_goals_attempted_allowed",
        ),
        "derivation": {
            "type": "observed_aggregation_from_official_play_by_play",
            "description": (
                "Aggregates official WNBA.com shot actions by deterministic observed court zone "
                "for opponents in the defending team's selected final regular-season games."
            ),
            "zone_classification": "official description + preserved official legacy x/y geometry",
            "not_a_causal_defensive_effect": True,
            "not_a_projection": True,
        },
        "verification": {
            "defending_team_resolved_from_certified_schedule": True,
            "defending_official_team_id_consistent_across_games": len(defending_team_ids) <= 1,
            "all_opponent_rows_mapped_to_registry": True,
            "unmapped_opponent_row_count": 0,
            "zone_percentages_recomputed_from_makes_attempts": True,
            "only_certified_regular_season_game_ids_admitted": True,
            "zone_labels_explicitly_derived_not_source_claimed": True,
            "no_model_derived_probabilities": True,
            "third_party_sources_used": False,
            "production_provider_replaced": False,
        },
    }
