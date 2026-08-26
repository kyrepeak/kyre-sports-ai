from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-game-logs"])

MLB_PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people"
ARIZONA_TZ = ZoneInfo("America/Phoenix")

HITTING_LOG_FIELDS = (
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
    "hitByPitch",
    "avg",
    "obp",
    "slg",
    "ops",
    "stolenBases",
    "caughtStealing",
    "totalBases",
    "leftOnBase",
)

PITCHING_LOG_FIELDS = (
    "gamesPlayed",
    "gamesStarted",
    "inningsPitched",
    "battersFaced",
    "wins",
    "losses",
    "saves",
    "holds",
    "earnedRuns",
    "era",
    "whip",
    "hits",
    "homeRuns",
    "baseOnBalls",
    "strikeOuts",
    "numberOfPitches",
    "strikes",
    "strikePercentage",
    "pitchesPerInning",
    "hitBatsmen",
    "wildPitches",
)


def _fetch_game_log_splits(player_id: int, season: int, group: str):
    url = f"{MLB_PEOPLE_URL}/{player_id}/stats"
    params = {
        "stats": "gameLog",
        "group": group,
        "season": season,
    }

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
            detail=f"MLB upstream request failed for {group} game logs: {exc}",
        ) from exc

    payload = response.json()
    splits = []

    for block in payload.get("stats", []):
        splits.extend(block.get("splits", []))

    return splits


def _normalize_game_log(split, fields):
    stat = split.get("stat", {})
    team = split.get("team", {})
    opponent = split.get("opponent", {})
    league = split.get("league", {})
    player = split.get("player", {})
    game = split.get("game", {})

    return {
        "date": split.get("date"),
        "game_pk": game.get("gamePk"),
        "game_type": split.get("gameType"),
        "is_home": split.get("isHome"),
        "is_win": split.get("isWin"),
        "player_id": player.get("id"),
        "player_name": player.get("fullName"),
        "team_id": team.get("id"),
        "team_name": team.get("name"),
        "opponent_id": opponent.get("id"),
        "opponent_name": opponent.get("name"),
        "league_id": league.get("id"),
        "league_name": league.get("name"),
        "stats": {field: stat.get(field) for field in fields},
    }


def _latest_first(log):
    return log.get("date") or ""


@router.get("/players/{player_id}/game-logs")
def get_mlb_player_game_logs(
    player_id: int,
    season: int | None = Query(
        default=None,
        ge=1876,
        le=2100,
        description="MLB season year. Defaults to the current Arizona calendar year.",
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=200,
        description="Optional number of most recent games to return per stat group.",
    ),
):
    target_season = season or datetime.now(ARIZONA_TZ).year

    hitting_splits = _fetch_game_log_splits(player_id, target_season, "hitting")
    pitching_splits = _fetch_game_log_splits(player_id, target_season, "pitching")

    hitting_logs = [
        _normalize_game_log(split, HITTING_LOG_FIELDS)
        for split in hitting_splits
    ]
    pitching_logs = [
        _normalize_game_log(split, PITCHING_LOG_FIELDS)
        for split in pitching_splits
    ]

    hitting_logs.sort(key=_latest_first, reverse=True)
    pitching_logs.sort(key=_latest_first, reverse=True)

    hitting_total = len(hitting_logs)
    pitching_total = len(pitching_logs)

    if limit is not None:
        hitting_logs = hitting_logs[:limit]
        pitching_logs = pitching_logs[:limit]

    player_name = None
    if hitting_logs:
        player_name = hitting_logs[0].get("player_name")
    elif pitching_logs:
        player_name = pitching_logs[0].get("player_name")

    return {
        "source": "MLB Stats API",
        "player_id": player_id,
        "player_name": player_name,
        "season": target_season,
        "limit": limit,
        "hitting_game_count": hitting_total,
        "pitching_game_count": pitching_total,
        "returned_hitting_games": len(hitting_logs),
        "returned_pitching_games": len(pitching_logs),
        "hitting": hitting_logs,
        "pitching": pitching_logs,
    }
