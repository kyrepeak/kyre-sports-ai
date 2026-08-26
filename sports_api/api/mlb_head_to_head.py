from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from sports_api.api.mlb_team_analytics import (
    _fetch_team_schedule,
    _is_completed_game,
    _normalize_team_game,
)

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-head-to-head"])

ARIZONA_TZ = ZoneInfo("America/Phoenix")


def _is_matchup(game, team_a_id: int, team_b_id: int):
    teams = game.get("teams", {})
    away_id = teams.get("away", {}).get("team", {}).get("id")
    home_id = teams.get("home", {}).get("team", {}).get("id")
    return {away_id, home_id} == {team_a_id, team_b_id}


def _opponent_record(games):
    wins = sum(1 for game in games if game.get("won") is False)
    losses = sum(1 for game in games if game.get("won") is True)
    decided = wins + losses
    return {
        "wins": wins,
        "losses": losses,
        "win_pct": round(wins / decided, 4) if decided else None,
    }


@router.get("/matchups/{team_a_id}/{team_b_id}/head-to-head")
def get_mlb_head_to_head(
    team_a_id: int,
    team_b_id: int,
    season: int | None = Query(
        default=None,
        ge=1876,
        le=2100,
        description="MLB season year. Defaults to the current Arizona calendar year.",
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=100,
        description="Optional number of most recent completed head-to-head games to return.",
    ),
):
    if team_a_id == team_b_id:
        raise HTTPException(
            status_code=400,
            detail="Head-to-head requires two different MLB team IDs.",
        )

    target_season = season or datetime.now(ARIZONA_TZ).year
    schedule = _fetch_team_schedule(team_a_id, target_season)

    matchup_games = [
        _normalize_team_game(game, team_a_id)
        for game in schedule
        if _is_completed_game(game) and _is_matchup(game, team_a_id, team_b_id)
    ]

    matchup_games.sort(
        key=lambda game: (
            game.get("official_date") or "",
            game.get("game_date_utc") or "",
            game.get("game_number") or 0,
        ),
        reverse=True,
    )

    full_sample_count = len(matchup_games)
    if limit is not None:
        matchup_games = matchup_games[:limit]

    games_used = len(matchup_games)
    team_a_wins = sum(1 for game in matchup_games if game.get("won") is True)
    team_a_losses = sum(1 for game in matchup_games if game.get("won") is False)
    decided = team_a_wins + team_a_losses

    team_a_runs = sum(game.get("runs_for") or 0 for game in matchup_games)
    team_b_runs = sum(game.get("runs_against") or 0 for game in matchup_games)

    team_a_name = matchup_games[0].get("team_name") if matchup_games else None
    team_b_name = matchup_games[0].get("opponent_name") if matchup_games else None

    team_a_home_games = sum(1 for game in matchup_games if game.get("is_home"))
    team_a_home_wins = sum(
        1 for game in matchup_games
        if game.get("is_home") and game.get("won") is True
    )
    team_a_away_games = games_used - team_a_home_games
    team_a_away_wins = sum(
        1 for game in matchup_games
        if not game.get("is_home") and game.get("won") is True
    )

    return {
        "source": "MLB Stats API",
        "calculated_by": "Kyre Sports API",
        "season": target_season,
        "limit": limit,
        "completed_matchups_available": full_sample_count,
        "games_used": games_used,
        "team_a": {
            "team_id": team_a_id,
            "team_name": team_a_name,
            "record": {
                "wins": team_a_wins,
                "losses": team_a_losses,
                "win_pct": round(team_a_wins / decided, 4) if decided else None,
            },
            "runs_scored": team_a_runs,
            "runs_allowed": team_b_runs,
            "run_differential": team_a_runs - team_b_runs,
            "runs_per_game": round(team_a_runs / games_used, 3) if games_used else None,
            "runs_allowed_per_game": (
                round(team_b_runs / games_used, 3) if games_used else None
            ),
            "home_games": team_a_home_games,
            "home_wins": team_a_home_wins,
            "away_games": team_a_away_games,
            "away_wins": team_a_away_wins,
        },
        "team_b": {
            "team_id": team_b_id,
            "team_name": team_b_name,
            "record": _opponent_record(matchup_games),
            "runs_scored": team_b_runs,
            "runs_allowed": team_a_runs,
            "run_differential": team_b_runs - team_a_runs,
            "runs_per_game": round(team_b_runs / games_used, 3) if games_used else None,
            "runs_allowed_per_game": (
                round(team_a_runs / games_used, 3) if games_used else None
            ),
        },
        "games": matchup_games,
    }
