from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-team-analytics"])

MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"
MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
ARIZONA_TZ = ZoneInfo("America/Phoenix")
WINDOWS = (5, 10, 20)

TEAM_HITTING_FIELDS = (
    "gamesPlayed",
    "plateAppearances",
    "atBats",
    "runs",
    "hits",
    "doubles",
    "triples",
    "homeRuns",
    "rbi",
    "baseOnBalls",
    "strikeOuts",
    "avg",
    "obp",
    "slg",
    "ops",
    "stolenBases",
    "caughtStealing",
    "totalBases",
    "leftOnBase",
)

TEAM_PITCHING_FIELDS = (
    "gamesPlayed",
    "gamesStarted",
    "inningsPitched",
    "runs",
    "earnedRuns",
    "era",
    "whip",
    "hits",
    "homeRuns",
    "baseOnBalls",
    "strikeOuts",
    "strikeoutsPer9Inn",
    "walksPer9Inn",
    "hitsPer9Inn",
    "homeRunsPer9",
    "strikeoutWalkRatio",
    "saves",
    "saveOpportunities",
    "holds",
    "blownSaves",
)


def _fetch_team_season_stats(team_id: int, season: int, group: str):
    url = f"{MLB_TEAMS_URL}/{team_id}/stats"
    params = {
        "stats": "season",
        "group": group,
        "season": season,
    }

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
            detail=f"MLB upstream request failed for {group} team stats: {exc}",
        ) from exc

    payload = response.json()

    for block in payload.get("stats", []):
        splits = block.get("splits", [])
        if splits:
            return splits[0]

    return None


def _normalize_team_stat_split(split, fields):
    if not split:
        return None

    stat = split.get("stat", {})
    team = split.get("team", {})
    league = split.get("league", {})

    return {
        "team_id": team.get("id"),
        "team_name": team.get("name"),
        "league_id": league.get("id"),
        "league_name": league.get("name"),
        "game_type": split.get("gameType"),
        "stats": {field: stat.get(field) for field in fields},
    }


def _fetch_team_schedule(team_id: int, season: int):
    params = {
        "sportId": 1,
        "teamId": team_id,
        "startDate": f"{season}-01-01",
        "endDate": f"{season}-12-31",
        "gameTypes": "R",
    }

    try:
        response = httpx.get(MLB_SCHEDULE_URL, params=params, timeout=20.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MLB upstream request failed for team schedule: {exc}",
        ) from exc

    payload = response.json()
    games = []

    for date_block in payload.get("dates", []):
        games.extend(date_block.get("games", []))

    return games


def _is_completed_game(game):
    status = game.get("status", {})
    abstract_state = status.get("abstractGameState")
    detailed_state = status.get("detailedState")

    if abstract_state == "Final":
        return True

    return detailed_state in {
        "Final",
        "Game Over",
        "Completed Early",
    }


def _normalize_team_game(game, team_id: int):
    teams = game.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})

    away_team = away.get("team", {})
    home_team = home.get("team", {})

    is_home = home_team.get("id") == team_id
    team_side = home if is_home else away
    opponent_side = away if is_home else home
    team_meta = team_side.get("team", {})
    opponent_meta = opponent_side.get("team", {})

    runs_for = team_side.get("score")
    runs_against = opponent_side.get("score")

    won = None
    if isinstance(runs_for, int) and isinstance(runs_against, int):
        won = runs_for > runs_against

    return {
        "game_pk": game.get("gamePk"),
        "official_date": game.get("officialDate"),
        "game_date_utc": game.get("gameDate"),
        "is_home": is_home,
        "team_id": team_meta.get("id"),
        "team_name": team_meta.get("name"),
        "opponent_id": opponent_meta.get("id"),
        "opponent_name": opponent_meta.get("name"),
        "runs_for": runs_for,
        "runs_against": runs_against,
        "run_differential": (
            runs_for - runs_against
            if isinstance(runs_for, int) and isinstance(runs_against, int)
            else None
        ),
        "won": won,
        "status": game.get("status", {}).get("detailedState"),
        "doubleheader": game.get("doubleHeader"),
        "game_number": game.get("gameNumber"),
    }


def _recent_window(games, requested_window: int):
    sample = games[:requested_window]
    games_available = len(sample)

    if games_available == 0:
        return {
            "requested_window": requested_window,
            "games_available": 0,
            "complete_window": False,
            "metrics": None,
            "games": [],
        }

    wins = sum(1 for game in sample if game.get("won") is True)
    losses = sum(1 for game in sample if game.get("won") is False)
    runs_for = sum(game.get("runs_for") or 0 for game in sample)
    runs_against = sum(game.get("runs_against") or 0 for game in sample)
    home_games = sum(1 for game in sample if game.get("is_home"))
    away_games = games_available - home_games

    home_wins = sum(
        1 for game in sample
        if game.get("is_home") and game.get("won") is True
    )
    away_wins = sum(
        1 for game in sample
        if not game.get("is_home") and game.get("won") is True
    )

    decided_games = wins + losses
    win_pct = round(wins / decided_games, 4) if decided_games else None

    return {
        "requested_window": requested_window,
        "games_available": games_available,
        "complete_window": games_available >= requested_window,
        "date_range": {
            "most_recent": sample[0].get("official_date"),
            "oldest": sample[-1].get("official_date"),
        },
        "metrics": {
            "wins": wins,
            "losses": losses,
            "win_pct": win_pct,
            "runs_for": runs_for,
            "runs_against": runs_against,
            "run_differential": runs_for - runs_against,
            "runs_for_per_game": round(runs_for / games_available, 3),
            "runs_against_per_game": round(runs_against / games_available, 3),
            "run_differential_per_game": round(
                (runs_for - runs_against) / games_available,
                3,
            ),
            "home_games": home_games,
            "home_wins": home_wins,
            "away_games": away_games,
            "away_wins": away_wins,
        },
        "games": sample,
    }


@router.get("/teams/{team_id}/stats/season")
def get_mlb_team_season_stats(
    team_id: int,
    season: int | None = Query(
        default=None,
        ge=1876,
        le=2100,
        description="MLB season year. Defaults to the current Arizona calendar year.",
    ),
):
    target_season = season or datetime.now(ARIZONA_TZ).year

    hitting_split = _fetch_team_season_stats(team_id, target_season, "hitting")
    pitching_split = _fetch_team_season_stats(team_id, target_season, "pitching")

    hitting = _normalize_team_stat_split(hitting_split, TEAM_HITTING_FIELDS)
    pitching = _normalize_team_stat_split(pitching_split, TEAM_PITCHING_FIELDS)

    team_name = None
    if hitting:
        team_name = hitting.get("team_name")
    elif pitching:
        team_name = pitching.get("team_name")

    return {
        "source": "MLB Stats API",
        "team_id": team_id,
        "team_name": team_name,
        "season": target_season,
        "hitting": hitting,
        "pitching": pitching,
    }


@router.get("/teams/{team_id}/recent-form")
def get_mlb_team_recent_form(
    team_id: int,
    season: int | None = Query(
        default=None,
        ge=1876,
        le=2100,
        description="MLB season year. Defaults to the current Arizona calendar year.",
    ),
):
    target_season = season or datetime.now(ARIZONA_TZ).year

    schedule = _fetch_team_schedule(team_id, target_season)
    completed = [
        _normalize_team_game(game, team_id)
        for game in schedule
        if _is_completed_game(game)
    ]
    completed.sort(
        key=lambda game: (
            game.get("official_date") or "",
            game.get("game_date_utc") or "",
            game.get("game_number") or 0,
        ),
        reverse=True,
    )

    team_name = completed[0].get("team_name") if completed else None

    return {
        "source": "MLB Stats API",
        "calculated_by": "Kyre Sports API",
        "team_id": team_id,
        "team_name": team_name,
        "season": target_season,
        "completed_games_available": len(completed),
        "windows": {
            f"last_{window}": _recent_window(completed, window)
            for window in WINDOWS
        },
    }
