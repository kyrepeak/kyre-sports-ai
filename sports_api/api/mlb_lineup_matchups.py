from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

from sports_api.api.mlb_arsenal_matchup import (
    MIN_TRACKED_PITCHES,
    _build_pitch_matchups,
    _coverage,
    _weighted_context,
)
from sports_api.api.mlb_batter_pitcher import _effective_batter_side
from sports_api.api.mlb_hitter_pitch_type import (
    _normalize_pitch_row as _normalize_hitter_pitch_row,
    _row_player_id as _hitter_row_player_id,
)
from sports_api.api.mlb_pitch_type_effectiveness import (
    SAVANT_PITCH_STATS_URL,
    _fetch_csv_rows,
    _normalize_pitch_row as _normalize_pitcher_pitch_row,
    _row_player_id as _pitcher_row_player_id,
)
from sports_api.api.mlb_starting_pitchers import MLB_LIVE_FEED_URL

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-lineup-matchups"])

ARIZONA_TZ = ZoneInfo("America/Phoenix")


def _fetch_game(game_pk: int):
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

    return response.json()


def _target_season(game_data, requested_season):
    if requested_season is not None:
        return requested_season

    official_date = game_data.get("datetime", {}).get("officialDate")
    if official_date:
        try:
            return int(str(official_date)[:4])
        except (TypeError, ValueError):
            pass

    return datetime.now(ARIZONA_TZ).year


def _first_pitcher_id(team_box):
    pitchers = team_box.get("pitchers", [])
    return pitchers[0] if pitchers else None


def _resolve_starter(side, team_box, probable_pitchers, game_players):
    confirmed_id = _first_pitcher_id(team_box)
    probable = probable_pitchers.get(side, {})
    probable_id = probable.get("id")
    starter_id = confirmed_id or probable_id

    if confirmed_id is not None:
        designation = "confirmed"
    elif probable_id is not None:
        designation = "probable"
    else:
        designation = "unknown"

    player = game_players.get(f"ID{starter_id}", {}) if starter_id is not None else {}

    return {
        "starter_id": starter_id,
        "starter_name": player.get("fullName") or probable.get("fullName"),
        "designation": designation,
        "probable_pitcher_id": probable_id,
        "confirmed_starting_pitcher_id": confirmed_id,
        "pitch_hand": player.get("pitchHand", {}).get("code"),
        "pitch_hand_description": player.get("pitchHand", {}).get("description"),
    }


def _lineup_from_box(team_box):
    batting_order = list(team_box.get("battingOrder", []) or [])

    if not batting_order:
        candidates = []
        for key, player in team_box.get("players", {}).items():
            batting_order_value = player.get("battingOrder")
            if batting_order_value in (None, ""):
                continue

            person = player.get("person", {})
            player_id = person.get("id")
            if not isinstance(player_id, int):
                try:
                    player_id = int(str(key).replace("ID", ""))
                except (TypeError, ValueError):
                    continue

            try:
                sort_value = int(batting_order_value)
            except (TypeError, ValueError):
                continue

            candidates.append((sort_value, player_id))

        candidates.sort(key=lambda item: item[0])
        batting_order = [player_id for _, player_id in candidates]

    unique_order = []
    for player_id in batting_order:
        if isinstance(player_id, int) and player_id not in unique_order:
            unique_order.append(player_id)

    return unique_order


def _player_profile(game_players, player_id: int):
    player = game_players.get(f"ID{player_id}", {})
    return {
        "player_id": player_id,
        "full_name": player.get("fullName"),
        "bat_side": player.get("batSide", {}).get("code"),
        "bat_side_description": player.get("batSide", {}).get("description"),
        "primary_position": player.get("primaryPosition", {}).get("abbreviation"),
    }


def _normalize_pitcher_board(rows):
    by_player = {}
    for row in rows:
        player_id = _pitcher_row_player_id(row)
        if not isinstance(player_id, int):
            continue

        pitch = _normalize_pitcher_pitch_row(row, {})
        if not pitch.get("pitch_type"):
            continue

        by_player.setdefault(player_id, []).append(pitch)

    return by_player


def _normalize_hitter_board(rows):
    by_player = {}
    for row in rows:
        player_id = _hitter_row_player_id(row)
        if not isinstance(player_id, int):
            continue

        pitch = _normalize_hitter_pitch_row(row)
        if not pitch.get("pitch_type"):
            continue

        by_player.setdefault(player_id, []).append(pitch)

    return by_player


def _hitter_matchup(
    batting_order_slot: int,
    player_id: int,
    game_players,
    pitcher,
    pitcher_pitches,
    hitter_pitches,
):
    profile = _player_profile(game_players, player_id)
    pitcher_hand = pitcher.get("pitch_hand")
    effective_side = _effective_batter_side(profile.get("bat_side"), pitcher_hand)

    pitch_matchups = _build_pitch_matchups(pitcher_pitches, hitter_pitches)
    overlap_types = {matchup.get("pitch_type") for matchup in pitch_matchups}
    qualified_types = {
        matchup.get("pitch_type")
        for matchup in pitch_matchups
        if matchup.get("qualified_for_summary") is True
    }

    weighted_context = _weighted_context(pitch_matchups)
    pitcher_usage_coverage = _coverage(pitcher_pitches, overlap_types)
    qualified_usage_coverage = _coverage(pitcher_pitches, qualified_types)

    components_available = {
        "pitcher_pitch_type_data": len(pitcher_pitches) > 0,
        "hitter_pitch_type_data": len(hitter_pitches) > 0,
        "overlapping_pitch_types": len(pitch_matchups) > 0,
        "qualified_overlap": len(qualified_types) > 0,
    }

    return {
        "batting_order_slot": batting_order_slot,
        "hitter": {
            **profile,
            "effective_batter_side": effective_side,
        },
        "opposing_pitcher": {
            "player_id": pitcher.get("starter_id"),
            "full_name": pitcher.get("starter_name"),
            "pitch_hand": pitcher_hand,
            "designation": pitcher.get("designation"),
        },
        "overlap": {
            "overlapping_pitch_types": len(pitch_matchups),
            "qualified_overlapping_pitch_types": len(qualified_types),
            "pitcher_usage_coverage_pct": pitcher_usage_coverage,
            "qualified_pitcher_usage_coverage_pct": qualified_usage_coverage,
        },
        "weighted_context": weighted_context,
        "data_quality": {
            "components_available": components_available,
            "complete": all(components_available.values()),
        },
        "pitch_matchups": pitch_matchups,
    }


def _average(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _team_summary(matchups, lineup_confirmed, starter):
    hitters_with_data = sum(
        1
        for matchup in matchups
        if matchup.get("data_quality", {})
        .get("components_available", {})
        .get("hitter_pitch_type_data") is True
    )
    hitters_with_overlap = sum(
        1
        for matchup in matchups
        if matchup.get("data_quality", {})
        .get("components_available", {})
        .get("overlapping_pitch_types") is True
    )
    hitters_with_qualified_overlap = sum(
        1
        for matchup in matchups
        if matchup.get("data_quality", {})
        .get("components_available", {})
        .get("qualified_overlap") is True
    )

    usage_coverage_values = [
        matchup.get("overlap", {}).get("pitcher_usage_coverage_pct")
        for matchup in matchups
    ]
    qualified_coverage_values = [
        matchup.get("overlap", {}).get("qualified_pitcher_usage_coverage_pct")
        for matchup in matchups
    ]
    xwoba_gap_values = [
        matchup.get("weighted_context", {}).get("weighted_xwoba_context_gap")
        for matchup in matchups
    ]

    board_ready = (
        lineup_confirmed
        and starter.get("starter_id") is not None
        and len(matchups) >= 9
        and hitters_with_overlap >= 7
        and hitters_with_qualified_overlap >= 5
    )

    blocking_reasons = []
    if not lineup_confirmed:
        blocking_reasons.append("lineup_not_confirmed")
    if starter.get("starter_id") is None:
        blocking_reasons.append("opposing_starter_not_identified")
    if len(matchups) < 9:
        blocking_reasons.append("fewer_than_9_lineup_matchups")
    if hitters_with_overlap < 7:
        blocking_reasons.append("insufficient_pitch_type_overlap")
    if hitters_with_qualified_overlap < 5:
        blocking_reasons.append("insufficient_qualified_overlap")

    return {
        "lineup_confirmed": lineup_confirmed,
        "lineup_spots_analyzed": len(matchups),
        "hitters_with_pitch_type_data": hitters_with_data,
        "hitters_with_overlap": hitters_with_overlap,
        "hitters_with_qualified_overlap": hitters_with_qualified_overlap,
        "average_pitcher_usage_coverage_pct": _average(usage_coverage_values),
        "average_qualified_usage_coverage_pct": _average(qualified_coverage_values),
        "average_weighted_xwoba_context_gap": _average(xwoba_gap_values),
        "board_ready": board_ready,
        "blocking_reasons": blocking_reasons,
    }


def _build_offense_board(
    offense_side,
    offense_team,
    offense_team_box,
    opposing_starter,
    pitcher_board,
    hitter_board,
    game_players,
):
    lineup_ids = _lineup_from_box(offense_team_box)
    lineup_confirmed = len(lineup_ids) >= 9
    starter_id = opposing_starter.get("starter_id")
    pitcher_pitches = pitcher_board.get(starter_id, []) if starter_id is not None else []

    matchups = []
    for slot, hitter_id in enumerate(lineup_ids[:9], start=1):
        matchups.append(
            _hitter_matchup(
                slot,
                hitter_id,
                game_players,
                opposing_starter,
                pitcher_pitches,
                hitter_board.get(hitter_id, []),
            )
        )

    return {
        "offense_side": offense_side,
        "team_id": offense_team.get("id"),
        "team_name": offense_team.get("name"),
        "opposing_starter": opposing_starter,
        "lineup_player_ids": lineup_ids[:9],
        "summary": _team_summary(matchups, lineup_confirmed, opposing_starter),
        "lineup_matchups": matchups,
    }


@router.get("/games/{game_pk}/lineup-matchups")
def get_mlb_lineup_matchup_board(
    game_pk: int,
    season: int | None = Query(
        default=None,
        ge=2015,
        le=2100,
        description=(
            "Statcast season used for arsenal-vs-hitter context. Defaults to the game's "
            "official season when available."
        ),
    ),
):
    payload = _fetch_game(game_pk)
    game_data = payload.get("gameData", {})
    live_data = payload.get("liveData", {})

    target_season = _target_season(game_data, season)
    teams = game_data.get("teams", {})
    game_players = game_data.get("players", {})
    probable_pitchers = game_data.get("probablePitchers", {})
    team_boxes = live_data.get("boxscore", {}).get("teams", {})

    away_starter = _resolve_starter(
        "away",
        team_boxes.get("away", {}),
        probable_pitchers,
        game_players,
    )
    home_starter = _resolve_starter(
        "home",
        team_boxes.get("home", {}),
        probable_pitchers,
        game_players,
    )

    pitcher_rows, pitcher_error = _fetch_csv_rows(
        SAVANT_PITCH_STATS_URL,
        {
            "type": "pitcher",
            "year": target_season,
            "team": "",
            "min": 1,
            "minPitches": 1,
            "csv": "true",
        },
    )
    hitter_rows, hitter_error = _fetch_csv_rows(
        SAVANT_PITCH_STATS_URL,
        {
            "type": "batter",
            "year": target_season,
            "team": "",
            "min": 1,
            "minPitches": 1,
            "csv": "true",
        },
    )

    source_errors = []
    if pitcher_error:
        source_errors.append({"source": "pitcher_pitch_types", "error": pitcher_error})
    if hitter_error:
        source_errors.append({"source": "hitter_pitch_types", "error": hitter_error})

    if pitcher_error or hitter_error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Baseball Savant lineup matchup sources are unavailable.",
                "source_errors": source_errors,
            },
        )

    pitcher_board = _normalize_pitcher_board(pitcher_rows)
    hitter_board = _normalize_hitter_board(hitter_rows)

    away_offense = _build_offense_board(
        "away",
        teams.get("away", {}),
        team_boxes.get("away", {}),
        home_starter,
        pitcher_board,
        hitter_board,
        game_players,
    )
    home_offense = _build_offense_board(
        "home",
        teams.get("home", {}),
        team_boxes.get("home", {}),
        away_starter,
        pitcher_board,
        hitter_board,
        game_players,
    )

    status = game_data.get("status", {})
    datetime_data = game_data.get("datetime", {})
    venue = game_data.get("venue", {})

    both_boards_ready = (
        away_offense.get("summary", {}).get("board_ready") is True
        and home_offense.get("summary", {}).get("board_ready") is True
    )

    return {
        "sources": ["MLB Stats API", "Baseball Savant / MLB Statcast"],
        "calculated_by": "Kyre Sports API",
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
        "starter_status": {
            "away": away_starter,
            "home": home_starter,
            "both_identified": (
                away_starter.get("starter_id") is not None
                and home_starter.get("starter_id") is not None
            ),
            "both_confirmed": (
                away_starter.get("designation") == "confirmed"
                and home_starter.get("designation") == "confirmed"
            ),
        },
        "board_readiness": {
            "away_offense_ready": away_offense.get("summary", {}).get("board_ready"),
            "home_offense_ready": home_offense.get("summary", {}).get("board_ready"),
            "both_boards_ready": both_boards_ready,
        },
        "away_offense_vs_home_starter": away_offense,
        "home_offense_vs_away_starter": home_offense,
        "data_quality": {
            "pitcher_board_players": len(pitcher_board),
            "hitter_board_players": len(hitter_board),
            "source_errors": source_errors,
        },
        "modeling_notes": {
            "performance": (
                "The full Savant pitcher board and hitter board are each fetched once per request, "
                "then reused across all lineup spots instead of repeating upstream calls per hitter."
            ),
            "qualified_overlap": (
                f"Pitch-type weighted summaries inherit the Step 3F minimum of {MIN_TRACKED_PITCHES} "
                "tracked pitches for both pitcher and hitter on each included pitch type."
            ),
            "readiness": (
                "A team board is marked ready only with a confirmed nine-player lineup, an identified "
                "opposing starter, at least seven hitters with pitch-type overlap, and at least five "
                "hitters with qualified overlap."
            ),
            "use": (
                "This is descriptive lineup matchup context. It does not yet project plate appearances, "
                "hits, home runs, strikeouts, fair odds, EV, or Monte Carlo probabilities."
            ),
        },
    }
