from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-slate-verification"])

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
MLB_LIVE_FEED_URL = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
ARIZONA_TZ = ZoneInfo("America/Phoenix")

NON_PLAYABLE_DETAILED_STATES = {
    "Postponed",
    "Cancelled",
    "Canceled",
    "Suspended",
    "Delayed",
}


def _fetch_schedule(target_date: str):
    params = {
        "sportId": 1,
        "date": target_date,
        "hydrate": "probablePitcher,venue",
    }

    try:
        response = httpx.get(MLB_SCHEDULE_URL, params=params, timeout=20.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MLB upstream schedule request failed: {exc}",
        ) from exc

    return response.json()


def _fetch_live_feed(game_pk: int):
    url = MLB_LIVE_FEED_URL.format(game_pk=game_pk)

    try:
        response = httpx.get(url, timeout=12.0)
        if response.status_code == 404:
            return None, f"MLB live feed did not find game {game_pk}."
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return None, f"MLB live feed request failed: {exc}"

    return response.json(), None


def _first_pitcher_id(team_box):
    pitchers = team_box.get("pitchers", [])
    return pitchers[0] if pitchers else None


def _lineup_state(team_box):
    batting_order = team_box.get("battingOrder", [])
    return {
        "confirmed": len(batting_order) >= 9,
        "batting_order_count": len(batting_order),
        "batting_order_player_ids": batting_order,
    }


def _starter_state(schedule_side, live_game_data, live_team_box, side: str):
    schedule_probable = schedule_side.get("probablePitcher", {})
    live_probable = live_game_data.get("probablePitchers", {}).get(side, {})
    confirmed_id = _first_pitcher_id(live_team_box)

    probable_id = live_probable.get("id") or schedule_probable.get("id")
    probable_name = live_probable.get("fullName") or schedule_probable.get("fullName")

    if confirmed_id is not None:
        designation = "confirmed"
        starter_id = confirmed_id
    elif probable_id is not None:
        designation = "probable"
        starter_id = probable_id
    else:
        designation = "unknown"
        starter_id = None

    players = live_game_data.get("players", {})
    player = players.get(f"ID{starter_id}", {}) if starter_id is not None else {}

    return {
        "designation": designation,
        "starter_id": starter_id,
        "starter_name": player.get("fullName") or probable_name,
        "probable_pitcher_id": probable_id,
        "probable_pitcher_name": probable_name,
        "confirmed_starting_pitcher_id": confirmed_id,
        "pitch_hand": player.get("pitchHand", {}).get("code"),
    }


def _normalize_game(game):
    game_pk = game.get("gamePk")
    teams = game.get("teams", {})
    away_side = teams.get("away", {})
    home_side = teams.get("home", {})
    away_team = away_side.get("team", {})
    home_team = home_side.get("team", {})
    status = game.get("status", {})

    live_payload = None
    live_error = None
    if isinstance(game_pk, int):
        live_payload, live_error = _fetch_live_feed(game_pk)

    live_game_data = (live_payload or {}).get("gameData", {})
    live_data = (live_payload or {}).get("liveData", {})
    live_boxscore = live_data.get("boxscore", {})
    live_teams_box = live_boxscore.get("teams", {})

    away_team_box = live_teams_box.get("away", {})
    home_team_box = live_teams_box.get("home", {})

    away_lineup = _lineup_state(away_team_box)
    home_lineup = _lineup_state(home_team_box)

    away_starter = _starter_state(
        away_side,
        live_game_data,
        away_team_box,
        "away",
    )
    home_starter = _starter_state(
        home_side,
        live_game_data,
        home_team_box,
        "home",
    )

    detailed_state = (
        live_game_data.get("status", {}).get("detailedState")
        or status.get("detailedState")
    )
    abstract_state = (
        live_game_data.get("status", {}).get("abstractGameState")
        or status.get("abstractGameState")
    )

    game_pk_valid = isinstance(game_pk, int) and game_pk > 0
    teams_identified = (
        isinstance(away_team.get("id"), int)
        and isinstance(home_team.get("id"), int)
        and away_team.get("id") != home_team.get("id")
    )
    starters_identified = (
        away_starter.get("starter_id") is not None
        and home_starter.get("starter_id") is not None
    )
    starters_confirmed = (
        away_starter.get("designation") == "confirmed"
        and home_starter.get("designation") == "confirmed"
    )
    lineups_confirmed = (
        away_lineup.get("confirmed") is True
        and home_lineup.get("confirmed") is True
    )
    playable_status = (
        abstract_state != "Final"
        and detailed_state not in NON_PLAYABLE_DETAILED_STATES
    )

    blocking_reasons = []
    if not game_pk_valid:
        blocking_reasons.append("missing_or_invalid_game_pk")
    if not teams_identified:
        blocking_reasons.append("teams_not_identified")
    if live_error is not None:
        blocking_reasons.append("live_feed_unavailable")
    if not starters_identified:
        blocking_reasons.append("starting_pitchers_not_identified")
    if not lineups_confirmed:
        blocking_reasons.append("lineups_not_confirmed")
    if not playable_status:
        blocking_reasons.append("game_not_in_playable_pregame_state")

    pregame_model_ready = (
        game_pk_valid
        and teams_identified
        and starters_identified
        and lineups_confirmed
        and playable_status
    )

    return {
        "game_pk": game_pk,
        "official_date": game.get("officialDate"),
        "game_datetime_utc": game.get("gameDate"),
        "game_type": game.get("gameType"),
        "scheduled_innings": game.get("scheduledInnings"),
        "doubleheader": {
            "code": game.get("doubleHeader"),
            "game_number": game.get("gameNumber"),
        },
        "status": {
            "abstract_game_state": abstract_state,
            "detailed_state": detailed_state,
            "coded_game_state": (
                live_game_data.get("status", {}).get("codedGameState")
                or status.get("codedGameState")
            ),
        },
        "venue": {
            "venue_id": game.get("venue", {}).get("id"),
            "name": game.get("venue", {}).get("name"),
        },
        "away": {
            "team_id": away_team.get("id"),
            "team_name": away_team.get("name"),
            "starter": away_starter,
            "lineup": away_lineup,
        },
        "home": {
            "team_id": home_team.get("id"),
            "team_name": home_team.get("name"),
            "starter": home_starter,
            "lineup": home_lineup,
        },
        "verification": {
            "game_pk_valid": game_pk_valid,
            "teams_identified": teams_identified,
            "live_feed_available": live_error is None,
            "starters_identified": starters_identified,
            "starters_confirmed": starters_confirmed,
            "lineups_confirmed": lineups_confirmed,
            "playable_status": playable_status,
            "pregame_model_ready": pregame_model_ready,
            "blocking_reasons": blocking_reasons,
        },
        "live_feed_error": live_error,
    }


@router.get("/slate/verify")
def verify_mlb_daily_slate(
    date: str | None = Query(
        default=None,
        description="Slate date in YYYY-MM-DD format. Defaults to today's Arizona date.",
    ),
):
    target_date = date or datetime.now(ARIZONA_TZ).date().isoformat()

    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="date must use YYYY-MM-DD format.",
        ) from exc

    payload = _fetch_schedule(target_date)

    raw_games = []
    for date_block in payload.get("dates", []):
        raw_games.extend(date_block.get("games", []))

    games = [_normalize_game(game) for game in raw_games]

    game_pks = [game.get("game_pk") for game in games if game.get("game_pk") is not None]
    unique_game_pks = set(game_pks)
    duplicate_game_pks = sorted(
        {
            game_pk
            for game_pk in game_pks
            if game_pks.count(game_pk) > 1
        }
    )

    reported_total_games = payload.get("totalGames")
    normalized_game_count = len(games)
    game_count_matches_source = (
        reported_total_games is None
        or reported_total_games == normalized_game_count
    )
    all_game_pks_unique = len(unique_game_pks) == len(game_pks)
    all_game_pks_valid = all(
        game.get("verification", {}).get("game_pk_valid") is True
        for game in games
    )

    ready_games = sum(
        1
        for game in games
        if game.get("verification", {}).get("pregame_model_ready") is True
    )
    lineup_ready_games = sum(
        1
        for game in games
        if game.get("verification", {}).get("lineups_confirmed") is True
    )
    starter_ready_games = sum(
        1
        for game in games
        if game.get("verification", {}).get("starters_identified") is True
    )

    slate_integrity_pass = (
        game_count_matches_source
        and all_game_pks_unique
        and all_game_pks_valid
    )

    return {
        "source": "MLB Stats API",
        "verified_by": "Kyre Sports API",
        "date": target_date,
        "verified_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        "slate": {
            "reported_total_games": reported_total_games,
            "normalized_game_count": normalized_game_count,
            "game_count_matches_source": game_count_matches_source,
            "all_game_pks_unique": all_game_pks_unique,
            "all_game_pks_valid": all_game_pks_valid,
            "duplicate_game_pks": duplicate_game_pks,
            "slate_integrity_pass": slate_integrity_pass,
        },
        "readiness": {
            "starter_ready_games": starter_ready_games,
            "lineup_ready_games": lineup_ready_games,
            "pregame_model_ready_games": ready_games,
            "all_games_pregame_ready": (
                normalized_game_count > 0
                and ready_games == normalized_game_count
            ),
        },
        "games": games,
    }
