from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb"])

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"
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
