from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-stats"])

MLB_PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people"
ARIZONA_TZ = ZoneInfo("America/Phoenix")

HITTING_FIELDS = (
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
    "intentionalWalks",
    "strikeOuts",
    "hitByPitch",
    "avg",
    "obp",
    "slg",
    "ops",
    "stolenBases",
    "caughtStealing",
    "stolenBasePercentage",
    "groundIntoDoublePlay",
    "totalBases",
    "leftOnBase",
    "sacBunts",
    "sacFlies",
)

PITCHING_FIELDS = (
    "gamesPlayed",
    "gamesStarted",
    "gamesPitched",
    "inningsPitched",
    "battersFaced",
    "wins",
    "losses",
    "saves",
    "saveOpportunities",
    "holds",
    "blownSaves",
    "earnedRuns",
    "era",
    "whip",
    "hits",
    "homeRuns",
    "baseOnBalls",
    "intentionalWalks",
    "strikeOuts",
    "strikeoutsPer9Inn",
    "walksPer9Inn",
    "hitsPer9Inn",
    "homeRunsPer9",
    "strikeoutWalkRatio",
    "numberOfPitches",
    "strikes",
    "strikePercentage",
    "pitchesPerInning",
    "groundOutsToAirouts",
    "hitBatsmen",
    "wildPitches",
)


def _fetch_season_split(player_id: int, season: int, group: str):
    url = f"{MLB_PEOPLE_URL}/{player_id}/stats"
    params = {
        "stats": "season",
        "group": group,
        "season": season,
    }

    try:
        response = httpx.get(url, params=params, timeout=15.0)
        if response.status_code == 404:
            return None
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MLB upstream request failed for {group} stats: {exc}",
        ) from exc

    payload = response.json()

    for block in payload.get("stats", []):
        for split in block.get("splits", []):
            if str(split.get("season")) == str(season):
                return split

    return None


def _normalize_split(split, fields):
    if not split:
        return None

    stat = split.get("stat", {})
    team = split.get("team", {})
    league = split.get("league", {})
    player = split.get("player", {})

    return {
        "player_id": player.get("id"),
        "player_name": player.get("fullName"),
        "team_id": team.get("id"),
        "team_name": team.get("name"),
        "league_id": league.get("id"),
        "league_name": league.get("name"),
        "game_type": split.get("gameType"),
        "stats": {field: stat.get(field) for field in fields},
    }


@router.get("/players/{player_id}/stats/season")
def get_mlb_player_season_stats(
    player_id: int,
    season: int | None = Query(
        default=None,
        ge=1876,
        le=2100,
        description="MLB season year. Defaults to the current Arizona calendar year.",
    ),
):
    target_season = season or datetime.now(ARIZONA_TZ).year

    hitting_split = _fetch_season_split(player_id, target_season, "hitting")
    pitching_split = _fetch_season_split(player_id, target_season, "pitching")

    hitting = _normalize_split(hitting_split, HITTING_FIELDS)
    pitching = _normalize_split(pitching_split, PITCHING_FIELDS)

    player_name = None
    if hitting:
        player_name = hitting.get("player_name")
    elif pitching:
        player_name = pitching.get("player_name")

    return {
        "source": "MLB Stats API",
        "player_id": player_id,
        "player_name": player_name,
        "season": target_season,
        "has_hitting_stats": hitting is not None,
        "has_pitching_stats": pitching is not None,
        "hitting": hitting,
        "pitching": pitching,
    }
