from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

from sports_api.collectors.mlb_fanduel_direct import collect_live_mlb_game_odds

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb"])

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"
MLB_PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people"
ARIZONA_TZ = ZoneInfo("America/Phoenix")


@router.get("/games/today")
def get_mlb_games_today(
    date: str | None = Query(
        default=None,
        description="Schedule date in YYYY-MM-DD format. Defaults to today's Arizona date.",
    )
):
    target_date = date or datetime.now(ARIZONA_TZ).date().isoformat()

    params = {
        "sportId": 1,
        "date": target_date,
        "hydrate": "probablePitcher,venue",
    }

    try:
        response = httpx.get(MLB_SCHEDULE_URL, params=params, timeout=15.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MLB upstream request failed: {exc}",
        ) from exc

    payload = response.json()
    games = []

    for date_block in payload.get("dates", []):
        for game in date_block.get("games", []):
            away = game.get("teams", {}).get("away", {})
            home = game.get("teams", {}).get("home", {})

            games.append(
                {
                    "game_pk": game.get("gamePk"),
                    "game_date_utc": game.get("gameDate"),
                    "status": game.get("status", {}).get("detailedState"),
                    "venue": game.get("venue", {}).get("name"),
                    "away_team": away.get("team", {}).get("name"),
                    "home_team": home.get("team", {}).get("name"),
                    "away_probable_pitcher": away.get("probablePitcher", {}).get("fullName"),
                    "home_probable_pitcher": home.get("probablePitcher", {}).get("fullName"),
                }
            )

    return {
        "source": "MLB Stats API",
        "date": target_date,
        "game_count": len(games),
        "games": games,
    }


@router.get("/odds")
def get_mlb_odds(
    max_events: int = Query(
        default=30,
        ge=1,
        le=50,
        description="Maximum number of upcoming FanDuel MLB events to inspect.",
    ),
    fully_priced_only: bool = Query(
        default=True,
        description="When true, return only games with moneyline, run line, and total pricing.",
    ),
):
    """Return read-only live FanDuel MLB game odds reconciled to official MLB game IDs."""

    try:
        snapshot = collect_live_mlb_game_odds(
            now_utc=datetime.now(timezone.utc),
            max_events=max_events,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="MLB live odds collection failed.",
        ) from exc

    all_games = [game for game in snapshot.get("games", []) if isinstance(game, dict)]
    games = (
        [game for game in all_games if game.get("fully_priced") is True]
        if fully_priced_only
        else all_games
    )

    return {
        "data_type": "mlb_live_odds_api_response_v1",
        "schema_version": 1,
        "source": snapshot.get("provider"),
        "transport": snapshot.get("transport"),
        "http_methods": snapshot.get("http_methods"),
        "sportsbook_region": snapshot.get("sportsbook_region"),
        "collected_at_utc": snapshot.get("collected_at_utc"),
        "fully_priced_only": fully_priced_only,
        "landing_event_count": snapshot.get("landing_event_count"),
        "candidate_pregame_event_count": snapshot.get("candidate_pregame_event_count"),
        "matched_game_count": snapshot.get("matched_game_count"),
        "fully_priced_game_count": snapshot.get("fully_priced_game_count"),
        "game_count": len(games),
        "rejected_event_count": len(snapshot.get("rejected_events") or []),
        "games": games,
    }


@router.get("/teams")
def get_mlb_teams():
    params = {"sportId": 1}

    try:
        response = httpx.get(MLB_TEAMS_URL, params=params, timeout=15.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MLB upstream request failed: {exc}",
        ) from exc

    payload = response.json()
    teams = []

    for team in payload.get("teams", []):
        teams.append(
            {
                "team_id": team.get("id"),
                "name": team.get("name"),
                "abbreviation": team.get("abbreviation"),
                "location": team.get("locationName"),
                "league": team.get("league", {}).get("name"),
                "division": team.get("division", {}).get("name"),
                "venue": team.get("venue", {}).get("name"),
                "first_year_of_play": team.get("firstYearOfPlay"),
                "active": team.get("active"),
            }
        )

    teams.sort(key=lambda team: (team.get("name") or ""))

    return {
        "source": "MLB Stats API",
        "team_count": len(teams),
        "teams": teams,
    }


@router.get("/teams/{team_id}/roster")
def get_mlb_team_roster(team_id: int):
    url = f"{MLB_TEAMS_URL}/{team_id}/roster"
    params = {"rosterType": "active"}

    try:
        response = httpx.get(url, params=params, timeout=15.0)
        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"MLB team {team_id} was not found.",
            )
        response.raise_for_status()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MLB upstream request failed: {exc}",
        ) from exc

    payload = response.json()
    roster = []

    for entry in payload.get("roster", []):
        person = entry.get("person", {})
        position = entry.get("position", {})

        roster.append(
            {
                "player_id": person.get("id"),
                "full_name": person.get("fullName"),
                "jersey_number": entry.get("jerseyNumber"),
                "position_code": position.get("code"),
                "position_name": position.get("name"),
                "position_type": position.get("type"),
                "position_abbreviation": position.get("abbreviation"),
                "status_code": entry.get("status", {}).get("code"),
                "status_description": entry.get("status", {}).get("description"),
            }
        )

    roster.sort(key=lambda player: (player.get("full_name") or ""))

    return {
        "source": "MLB Stats API",
        "team_id": team_id,
        "roster_type": "active",
        "player_count": len(roster),
        "players": roster,
    }


@router.get("/players/{player_id}")
def get_mlb_player_profile(player_id: int):
    url = f"{MLB_PEOPLE_URL}/{player_id}"
    params = {"hydrate": "currentTeam"}

    try:
        response = httpx.get(url, params=params, timeout=15.0)
        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"MLB player {player_id} was not found.",
            )
        response.raise_for_status()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MLB upstream request failed: {exc}",
        ) from exc

    payload = response.json()
    people = payload.get("people", [])

    if not people:
        raise HTTPException(
            status_code=404,
            detail=f"MLB player {player_id} was not found.",
        )

    person = people[0]
    position = person.get("primaryPosition", {})
    current_team = person.get("currentTeam", {})
    bat_side = person.get("batSide", {})
    pitch_hand = person.get("pitchHand", {})

    return {
        "source": "MLB Stats API",
        "player": {
            "player_id": person.get("id"),
            "full_name": person.get("fullName"),
            "first_name": person.get("firstName"),
            "last_name": person.get("lastName"),
            "active": person.get("active"),
            "current_age": person.get("currentAge"),
            "birth_date": person.get("birthDate"),
            "birth_city": person.get("birthCity"),
            "birth_state_province": person.get("birthStateProvince"),
            "birth_country": person.get("birthCountry"),
            "height": person.get("height"),
            "weight_lbs": person.get("weight"),
            "mlb_debut_date": person.get("mlbDebutDate"),
            "primary_position_code": position.get("code"),
            "primary_position_name": position.get("name"),
            "primary_position_type": position.get("type"),
            "primary_position_abbreviation": position.get("abbreviation"),
            "bat_side_code": bat_side.get("code"),
            "bat_side_description": bat_side.get("description"),
            "pitch_hand_code": pitch_hand.get("code"),
            "pitch_hand_description": pitch_hand.get("description"),
            "current_team_id": current_team.get("id"),
            "current_team_name": current_team.get("name"),
        },
    }
