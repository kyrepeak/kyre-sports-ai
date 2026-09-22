from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from sports_api.api.mlb_lineup_matchups import (
    _fetch_game,
    _lineup_from_box,
    _player_profile,
    _target_season,
)
from sports_api.api.mlb_stats import _fetch_season_split
from sports_api.api.mlb_team_analytics import _fetch_team_season_stats

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-plate-appearances"])

ARIZONA_TZ = ZoneInfo("America/Phoenix")

# Heuristic lineup opportunity multipliers. They intentionally sum to 9.0 so
# multiplying team PA/game by weight/9 preserves the team's total PA environment.
# These are Kyre Sports API v0.1 modeling weights, not official MLB statistics.
LINEUP_SLOT_WEIGHTS = {
    1: 1.11,
    2: 1.08,
    3: 1.05,
    4: 1.02,
    5: 1.00,
    6: 0.98,
    7: 0.95,
    8: 0.92,
    9: 0.89,
}

SLOT_ENVIRONMENT_WEIGHT = 0.80
PLAYER_USAGE_WEIGHT = 0.20
MIN_PROJECTED_PA = 2.5
MAX_PROJECTED_PA = 5.5
UNCERTAINTY_HALF_WIDTH = 0.60


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _team_pa_environment(team_id: int, season: int):
    split = _fetch_team_season_stats(team_id, season, "hitting")
    stat = (split or {}).get("stat", {})

    games_played = _safe_float(stat.get("gamesPlayed"))
    plate_appearances = _safe_float(stat.get("plateAppearances"))

    pa_per_game = None
    if games_played and games_played > 0 and plate_appearances is not None:
        pa_per_game = plate_appearances / games_played

    return {
        "games_played": int(games_played) if games_played is not None else None,
        "plate_appearances": int(plate_appearances) if plate_appearances is not None else None,
        "plate_appearances_per_game": round(pa_per_game, 4) if pa_per_game is not None else None,
    }


def _player_pa_usage(player_id: int, season: int):
    split = _fetch_season_split(player_id, season, "hitting")
    stat = (split or {}).get("stat", {})

    games_played = _safe_float(stat.get("gamesPlayed"))
    plate_appearances = _safe_float(stat.get("plateAppearances"))

    pa_per_game = None
    if games_played and games_played > 0 and plate_appearances is not None:
        pa_per_game = plate_appearances / games_played

    return {
        "games_played": int(games_played) if games_played is not None else None,
        "plate_appearances": int(plate_appearances) if plate_appearances is not None else None,
        "plate_appearances_per_game": round(pa_per_game, 4) if pa_per_game is not None else None,
    }


def _slot_environment_projection(team_pa_per_game: float | None, slot: int):
    if team_pa_per_game is None:
        return None

    weight = LINEUP_SLOT_WEIGHTS.get(slot)
    if weight is None:
        return None

    return (team_pa_per_game / 9.0) * weight


def _blend_projection(slot_projection, player_pa_per_game):
    if slot_projection is None and player_pa_per_game is None:
        return None, None

    if slot_projection is None:
        projected = player_pa_per_game
        method = "player_usage_only"
    elif player_pa_per_game is None:
        projected = slot_projection
        method = "slot_environment_only"
    else:
        projected = (
            (slot_projection * SLOT_ENVIRONMENT_WEIGHT)
            + (player_pa_per_game * PLAYER_USAGE_WEIGHT)
        )
        method = "slot_environment_plus_player_usage"

    projected = max(MIN_PROJECTED_PA, min(MAX_PROJECTED_PA, projected))
    return round(projected, 3), method


def _uncertainty_band(projected_pa):
    if projected_pa is None:
        return None

    return {
        "low": round(max(2.0, projected_pa - UNCERTAINTY_HALF_WIDTH), 3),
        "high": round(min(6.5, projected_pa + UNCERTAINTY_HALF_WIDTH), 3),
        "type": "heuristic_opportunity_band",
    }


def _hitter_opportunity(slot, player_id, game_players, team_environment, season):
    profile = _player_profile(game_players, player_id)
    player_usage = _player_pa_usage(player_id, season)

    team_pa_per_game = team_environment.get("plate_appearances_per_game")
    slot_projection = _slot_environment_projection(team_pa_per_game, slot)
    player_pa_per_game = player_usage.get("plate_appearances_per_game")

    projected_pa, method = _blend_projection(slot_projection, player_pa_per_game)

    return {
        "batting_order_slot": slot,
        "player": profile,
        "lineup_slot_weight": LINEUP_SLOT_WEIGHTS.get(slot),
        "team_slot_environment_projection": (
            round(slot_projection, 3) if slot_projection is not None else None
        ),
        "player_season_usage": player_usage,
        "projected_plate_appearances": projected_pa,
        "projection_method": method,
        "opportunity_band": _uncertainty_band(projected_pa),
        "data_quality": {
            "team_pa_environment_available": team_pa_per_game is not None,
            "player_season_usage_available": player_pa_per_game is not None,
            "lineup_slot_available": slot in LINEUP_SLOT_WEIGHTS,
            "projection_available": projected_pa is not None,
        },
    }


def _team_board(side, team_meta, team_box, game_players, season):
    team_id = team_meta.get("id")
    lineup_ids = _lineup_from_box(team_box)
    lineup_confirmed = len(lineup_ids) >= 9

    team_environment = (
        _team_pa_environment(team_id, season)
        if isinstance(team_id, int)
        else {
            "games_played": None,
            "plate_appearances": None,
            "plate_appearances_per_game": None,
        }
    )

    hitters = [
        _hitter_opportunity(
            slot,
            player_id,
            game_players,
            team_environment,
            season,
        )
        for slot, player_id in enumerate(lineup_ids[:9], start=1)
    ]

    projections = [
        hitter.get("projected_plate_appearances")
        for hitter in hitters
        if hitter.get("projected_plate_appearances") is not None
    ]

    team_projected_pa = round(sum(projections), 3) if projections else None
    projections_available = len(projections)

    blocking_reasons = []
    if not lineup_confirmed:
        blocking_reasons.append("lineup_not_confirmed")
    if team_environment.get("plate_appearances_per_game") is None:
        blocking_reasons.append("team_pa_environment_unavailable")
    if projections_available < 9:
        blocking_reasons.append("fewer_than_9_pa_projections")

    board_ready = (
        lineup_confirmed
        and team_environment.get("plate_appearances_per_game") is not None
        and projections_available >= 9
    )

    return {
        "side": side,
        "team_id": team_id,
        "team_name": team_meta.get("name"),
        "lineup_confirmed": lineup_confirmed,
        "lineup_player_ids": lineup_ids[:9],
        "team_pa_environment": team_environment,
        "projected_lineup_plate_appearances_sum": team_projected_pa,
        "board_ready": board_ready,
        "blocking_reasons": blocking_reasons,
        "hitters": hitters,
    }


@router.get("/games/{game_pk}/plate-appearances")
def get_mlb_projected_plate_appearances(
    game_pk: int,
    season: int | None = Query(
        default=None,
        ge=1876,
        le=2100,
        description=(
            "Season used for team and player PA context. Defaults to the game's official "
            "season when available."
        ),
    ),
):
    payload = _fetch_game(game_pk)
    game_data = payload.get("gameData", {})
    live_data = payload.get("liveData", {})

    target_season = _target_season(game_data, season)
    teams = game_data.get("teams", {})
    game_players = game_data.get("players", {})
    team_boxes = live_data.get("boxscore", {}).get("teams", {})
    status = game_data.get("status", {})
    datetime_data = game_data.get("datetime", {})
    venue = game_data.get("venue", {})

    away = _team_board(
        "away",
        teams.get("away", {}),
        team_boxes.get("away", {}),
        game_players,
        target_season,
    )
    home = _team_board(
        "home",
        teams.get("home", {}),
        team_boxes.get("home", {}),
        game_players,
        target_season,
    )

    both_ready = away.get("board_ready") is True and home.get("board_ready") is True

    return {
        "source": "MLB Stats API",
        "calculated_by": "Kyre Sports API",
        "projection_model": "plate-appearance opportunity heuristic v0.1",
        "game_pk": game_pk,
        "season": target_season,
        "official_date": datetime_data.get("officialDate"),
        "game_datetime_utc": datetime_data.get("dateTime"),
        "status": {
            "abstract_game_state": status.get("abstractGameState"),
            "detailed_state": status.get("detailedState"),
        },
        "venue": {
            "venue_id": venue.get("id"),
            "name": venue.get("name"),
        },
        "readiness": {
            "away_ready": away.get("board_ready"),
            "home_ready": home.get("board_ready"),
            "both_teams_ready": both_ready,
        },
        "away": away,
        "home": home,
        "modeling_notes": {
            "slot_weights": LINEUP_SLOT_WEIGHTS,
            "slot_weight_sum": round(sum(LINEUP_SLOT_WEIGHTS.values()), 3),
            "blend": {
                "slot_environment_weight": SLOT_ENVIRONMENT_WEIGHT,
                "player_usage_weight": PLAYER_USAGE_WEIGHT,
            },
            "interpretation": (
                "Projected PA is an opportunity heuristic built from team season PA/game, current "
                "batting-order slot, and the hitter's own season PA/game. It is not an official "
                "MLB projection or a calibrated hit probability."
            ),
            "known_limits": (
                "v0.1 does not yet model opponent bullpen quality, projected game score, extra "
                "innings, pinch-hit/substitution risk, or the home team's chance of skipping the "
                "bottom of the ninth. Those can be calibrated in later projection layers."
            ),
        },
    }
