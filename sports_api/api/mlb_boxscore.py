import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-boxscore"])

MLB_LIVE_FEED_URL = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"


def _player_key(player_id):
    return f"ID{player_id}"


def _normalize_player(players, player_id):
    player = players.get(_player_key(player_id), {})
    person = player.get("person", {})
    position = player.get("position", {})
    stats = player.get("stats", {})

    return {
        "player_id": person.get("id") or player_id,
        "full_name": person.get("fullName"),
        "jersey_number": player.get("jerseyNumber"),
        "position_code": position.get("code"),
        "position_name": position.get("name"),
        "position_abbreviation": position.get("abbreviation"),
        "batting_order": player.get("battingOrder"),
        "hitting": stats.get("batting"),
        "pitching": stats.get("pitching"),
        "fielding": stats.get("fielding"),
    }


def _normalize_team_box(team_box, team_meta, line_score):
    players = team_box.get("players", {})
    batting_order_ids = team_box.get("battingOrder", [])
    pitcher_ids = team_box.get("pitchers", [])
    batter_ids = team_box.get("batters", [])
    bench_ids = team_box.get("bench", [])
    bullpen_ids = team_box.get("bullpen", [])

    batting_order = [
        _normalize_player(players, player_id)
        for player_id in batting_order_ids
    ]

    pitchers_used = [
        _normalize_player(players, player_id)
        for player_id in pitcher_ids
    ]

    return {
        "team_id": team_meta.get("id"),
        "team_name": team_meta.get("name"),
        "score": {
            "runs": line_score.get("runs"),
            "hits": line_score.get("hits"),
            "errors": line_score.get("errors"),
            "left_on_base": line_score.get("leftOnBase"),
        },
        "team_stats": team_box.get("teamStats", {}),
        "batting_order": batting_order,
        "batters": [
            _normalize_player(players, player_id)
            for player_id in batter_ids
        ],
        "starting_pitcher": pitchers_used[0] if pitchers_used else None,
        "pitchers_used": pitchers_used,
        "bench": [
            _normalize_player(players, player_id)
            for player_id in bench_ids
        ],
        "bullpen": [
            _normalize_player(players, player_id)
            for player_id in bullpen_ids
        ],
    }


@router.get("/games/{game_pk}/boxscore")
def get_mlb_game_boxscore(game_pk: int):
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
    boxscore = live_data.get("boxscore", {})
    linescore = live_data.get("linescore", {})

    teams_meta = game_data.get("teams", {})
    teams_box = boxscore.get("teams", {})
    line_teams = linescore.get("teams", {})

    away = _normalize_team_box(
        teams_box.get("away", {}),
        teams_meta.get("away", {}),
        line_teams.get("away", {}),
    )
    home = _normalize_team_box(
        teams_box.get("home", {}),
        teams_meta.get("home", {}),
        line_teams.get("home", {}),
    )

    status = game_data.get("status", {})
    datetime_data = game_data.get("datetime", {})
    venue = game_data.get("venue", {})

    return {
        "source": "MLB Stats API",
        "game_pk": game_pk,
        "status": {
            "abstract_game_state": status.get("abstractGameState"),
            "detailed_state": status.get("detailedState"),
            "coded_game_state": status.get("codedGameState"),
        },
        "game_datetime_utc": datetime_data.get("dateTime"),
        "official_date": datetime_data.get("officialDate"),
        "venue": {
            "venue_id": venue.get("id"),
            "name": venue.get("name"),
        },
        "inning_state": {
            "current_inning": linescore.get("currentInning"),
            "current_inning_ordinal": linescore.get("currentInningOrdinal"),
            "inning_state": linescore.get("inningState"),
            "inning_half": linescore.get("inningHalf"),
            "outs": linescore.get("outs"),
        },
        "away": away,
        "home": home,
        "officials": boxscore.get("officials", []),
        "game_info": boxscore.get("info", []),
    }
