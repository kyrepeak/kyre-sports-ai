from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

from sports_api.api.mlb_stats import (
    PITCHING_FIELDS,
    _fetch_season_split,
    _normalize_split,
)

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-starting-pitchers"])

MLB_LIVE_FEED_URL = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
ARIZONA_TZ = ZoneInfo("America/Phoenix")


def _player_key(player_id: int):
    return f"ID{player_id}"


def _first_pitcher_id(team_box):
    pitchers = team_box.get("pitchers", [])
    return pitchers[0] if pitchers else None


def _probable_pitcher_id(probable_pitchers, side: str):
    pitcher = probable_pitchers.get(side, {})
    return pitcher.get("id")


def _player_profile(game_players, player_id: int | None):
    if player_id is None:
        return None

    player = game_players.get(_player_key(player_id), {})
    pitch_hand = player.get("pitchHand", {})
    position = player.get("primaryPosition", {})
    current_team = player.get("currentTeam", {})

    return {
        "player_id": player.get("id") or player_id,
        "full_name": player.get("fullName"),
        "active": player.get("active"),
        "current_age": player.get("currentAge"),
        "height": player.get("height"),
        "weight_lbs": player.get("weight"),
        "mlb_debut_date": player.get("mlbDebutDate"),
        "pitch_hand_code": pitch_hand.get("code"),
        "pitch_hand_description": pitch_hand.get("description"),
        "position_code": position.get("code"),
        "position_name": position.get("name"),
        "position_abbreviation": position.get("abbreviation"),
        "current_team_id": current_team.get("id"),
        "current_team_name": current_team.get("name"),
    }


def _starter_block(
    side: str,
    team_meta,
    team_box,
    probable_pitchers,
    game_players,
    season: int,
):
    confirmed_id = _first_pitcher_id(team_box)
    probable_id = _probable_pitcher_id(probable_pitchers, side)
    starter_id = confirmed_id or probable_id

    if confirmed_id is not None:
        designation = "confirmed"
    elif probable_id is not None:
        designation = "probable"
    else:
        designation = "unknown"

    profile = _player_profile(game_players, starter_id)
    season_stats = None

    if starter_id is not None:
        pitching_split = _fetch_season_split(starter_id, season, "pitching")
        season_stats = _normalize_split(pitching_split, PITCHING_FIELDS)

    return {
        "side": side,
        "team_id": team_meta.get("id"),
        "team_name": team_meta.get("name"),
        "designation": designation,
        "probable_pitcher_id": probable_id,
        "confirmed_starting_pitcher_id": confirmed_id,
        "starter": profile,
        "season_pitching": season_stats,
    }


@router.get("/games/{game_pk}/starting-pitchers")
def get_mlb_starting_pitcher_matchup(
    game_pk: int,
    season: int | None = Query(
        default=None,
        ge=1876,
        le=2100,
        description=(
            "Season used for starter pitching stats. Defaults to the game's official year "
            "when available, otherwise the current Arizona calendar year."
        ),
    ),
):
    url = MLB_LIVE_FEED_URL.format(game_pk=game_pk)

    try:
        response = httpx.get(url, timeout=20.0)
        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"MLB game {game_pk} was not found.",
            )
        response.raise_for_status()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MLB upstream request failed for game {game_pk}: {exc}",
        ) from exc

    payload = response.json()
    game_data = payload.get("gameData", {})
    live_data = payload.get("liveData", {})

    datetime_data = game_data.get("datetime", {})
    official_date = datetime_data.get("officialDate")

    game_year = None
    if official_date:
        try:
            game_year = int(str(official_date)[:4])
        except (TypeError, ValueError):
            game_year = None

    target_season = season or game_year or datetime.now(ARIZONA_TZ).year

    teams_meta = game_data.get("teams", {})
    probable_pitchers = game_data.get("probablePitchers", {})
    game_players = game_data.get("players", {})
    teams_box = live_data.get("boxscore", {}).get("teams", {})
    status = game_data.get("status", {})
    venue = game_data.get("venue", {})

    away = _starter_block(
        "away",
        teams_meta.get("away", {}),
        teams_box.get("away", {}),
        probable_pitchers,
        game_players,
        target_season,
    )
    home = _starter_block(
        "home",
        teams_meta.get("home", {}),
        teams_box.get("home", {}),
        probable_pitchers,
        game_players,
        target_season,
    )

    both_identified = (
        away.get("starter") is not None
        and home.get("starter") is not None
    )
    both_confirmed = (
        away.get("designation") == "confirmed"
        and home.get("designation") == "confirmed"
    )

    return {
        "source": "MLB Stats API",
        "game_pk": game_pk,
        "official_date": official_date,
        "game_datetime_utc": datetime_data.get("dateTime"),
        "season": target_season,
        "status": {
            "abstract_game_state": status.get("abstractGameState"),
            "detailed_state": status.get("detailedState"),
        },
        "venue": {
            "venue_id": venue.get("id"),
            "name": venue.get("name"),
        },
        "starter_status": {
            "both_identified": both_identified,
            "both_confirmed": both_confirmed,
        },
        "away": away,
        "home": home,
    }
