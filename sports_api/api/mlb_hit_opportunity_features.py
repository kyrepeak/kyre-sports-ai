from fastapi import APIRouter, HTTPException, Query

from sports_api.api.mlb_advanced_hitting import (
    SAVANT_EXPECTED_URL,
    SAVANT_STATCAST_URL,
    _fetch_csv_rows as _fetch_advanced_rows,
    _find_player_row,
    _normalize_contact_quality,
    _normalize_expected_stats,
)
from sports_api.api.mlb_arsenal_matchup import (
    _build_pitch_matchups,
    _coverage,
    _weighted_context,
)
from sports_api.api.mlb_batter_pitcher import _fetch_platoon_splits
from sports_api.api.mlb_game_logs import (
    HITTING_LOG_FIELDS,
    _fetch_game_log_splits,
    _latest_first,
    _normalize_game_log,
)
from sports_api.api.mlb_lineup_matchups import (
    _fetch_game,
    _lineup_from_box,
    _normalize_hitter_board,
    _normalize_pitcher_board,
    _player_profile,
    _resolve_starter,
    _target_season,
)
from sports_api.api.mlb_pitch_type_effectiveness import (
    SAVANT_PITCH_STATS_URL,
    _fetch_csv_rows as _fetch_pitch_type_rows,
)
from sports_api.api.mlb_plate_appearances import (
    _hitter_opportunity,
    _team_pa_environment,
)
from sports_api.api.mlb_recent_form import _hitting_window

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-hit-opportunity-features"])

RECENT_WINDOWS = (5, 10, 20)
CORE_COMPONENTS = (
    "plate_appearance_opportunity",
    "recent_form",
    "statcast_contact_quality",
    "statcast_expected_statistics",
    "platoon_split",
    "qualified_arsenal_overlap",
)


def _empty_team_environment():
    return {
        "games_played": None,
        "plate_appearances": None,
        "plate_appearances_per_game": None,
    }


def _safe_team_environment(team_id, season, source_errors, side):
    if not isinstance(team_id, int):
        return _empty_team_environment()

    try:
        return _team_pa_environment(team_id, season)
    except HTTPException as exc:
        source_errors.append(
            {
                "source": "mlb_team_pa_environment",
                "side": side,
                "team_id": team_id,
                "error": exc.detail,
            }
        )
        return _empty_team_environment()


def _safe_hitter_opportunity(
    slot,
    player_id,
    game_players,
    team_environment,
    season,
    source_errors,
):
    try:
        return _hitter_opportunity(
            slot,
            player_id,
            game_players,
            team_environment,
            season,
        )
    except HTTPException as exc:
        source_errors.append(
            {
                "source": "mlb_player_pa_usage",
                "player_id": player_id,
                "error": exc.detail,
            }
        )
        return {
            "batting_order_slot": slot,
            "player": _player_profile(game_players, player_id),
            "lineup_slot_weight": None,
            "team_slot_environment_projection": None,
            "player_season_usage": {
                "games_played": None,
                "plate_appearances": None,
                "plate_appearances_per_game": None,
            },
            "projected_plate_appearances": None,
            "projection_method": None,
            "opportunity_band": None,
            "data_quality": {
                "team_pa_environment_available": (
                    team_environment.get("plate_appearances_per_game") is not None
                ),
                "player_season_usage_available": False,
                "lineup_slot_available": slot in range(1, 10),
                "projection_available": False,
            },
        }


def _recent_form(player_id, season, source_errors):
    try:
        splits = _fetch_game_log_splits(player_id, season, "hitting")
    except HTTPException as exc:
        source_errors.append(
            {
                "source": "mlb_recent_hitting_logs",
                "player_id": player_id,
                "error": exc.detail,
            }
        )
        splits = []

    logs = [
        _normalize_game_log(split, HITTING_LOG_FIELDS)
        for split in splits
    ]
    logs.sort(key=_latest_first, reverse=True)

    return {
        "games_available": len(logs),
        "windows": {
            f"last_{window}": _hitting_window(logs, window)
            for window in RECENT_WINDOWS
        },
    }


def _platoon_context(player_id, pitcher_hand, season, source_errors):
    try:
        splits = _fetch_platoon_splits(player_id, season, "hitting")
    except HTTPException as exc:
        source_errors.append(
            {
                "source": "mlb_hitter_platoon_split",
                "player_id": player_id,
                "error": exc.detail,
            }
        )
        splits = {}

    split_code = (
        "vl"
        if pitcher_hand == "L"
        else "vr"
        if pitcher_hand == "R"
        else None
    )
    selected = splits.get(split_code) if split_code else None

    return {
        "pitcher_hand": pitcher_hand,
        "selected_split_code": split_code,
        "selected_split": selected,
        "available": selected is not None,
    }


def _advanced_hitting(player_id, contact_rows, expected_rows):
    contact = _normalize_contact_quality(_find_player_row(contact_rows, player_id))
    expected = _normalize_expected_stats(_find_player_row(expected_rows, player_id))

    return {
        "contact_quality": contact,
        "expected_statistics": expected,
    }


def _arsenal_context(player_id, starter, pitcher_board, hitter_board):
    starter_id = starter.get("starter_id")
    pitcher_pitches = pitcher_board.get(starter_id, []) if starter_id else []
    hitter_pitches = hitter_board.get(player_id, [])

    pitch_matchups = _build_pitch_matchups(pitcher_pitches, hitter_pitches)
    overlap_types = {
        matchup.get("pitch_type")
        for matchup in pitch_matchups
        if matchup.get("pitch_type")
    }
    qualified_types = {
        matchup.get("pitch_type")
        for matchup in pitch_matchups
        if matchup.get("qualified_for_summary") is True
    }

    return {
        "opposing_starter": {
            "player_id": starter.get("starter_id"),
            "full_name": starter.get("starter_name"),
            "pitch_hand": starter.get("pitch_hand"),
            "designation": starter.get("designation"),
        },
        "overlap": {
            "overlapping_pitch_types": len(pitch_matchups),
            "qualified_overlapping_pitch_types": len(qualified_types),
            "pitcher_usage_coverage_pct": _coverage(
                pitcher_pitches,
                overlap_types,
            ),
            "qualified_pitcher_usage_coverage_pct": _coverage(
                pitcher_pitches,
                qualified_types,
            ),
        },
        "weighted_context": _weighted_context(pitch_matchups),
        "pitch_matchups": pitch_matchups,
        "qualified_overlap_available": len(qualified_types) > 0,
    }


def _window_metric(recent_form, window, group, field):
    block = recent_form.get("windows", {}).get(f"last_{window}", {})
    metrics = block.get("metrics") or {}
    nested = metrics.get(group) or {}
    return nested.get(field)


def _platoon_stat(platoon, field):
    selected = platoon.get("selected_split") or {}
    stats = selected.get("stats") or {}
    return stats.get(field)


def _feature_vector(opportunity, recent_form, advanced, platoon, arsenal):
    contact = advanced.get("contact_quality") or {}
    expected = advanced.get("expected_statistics") or {}
    weighted = arsenal.get("weighted_context") or {}
    overlap = arsenal.get("overlap") or {}
    band = opportunity.get("opportunity_band") or {}

    return {
        "projected_plate_appearances": opportunity.get("projected_plate_appearances"),
        "projected_pa_low": band.get("low"),
        "projected_pa_high": band.get("high"),
        "last_5_hit_1plus_rate": _window_metric(
            recent_form,
            5,
            "event_rates",
            "hit_1plus_rate",
        ),
        "last_10_hit_1plus_rate": _window_metric(
            recent_form,
            10,
            "event_rates",
            "hit_1plus_rate",
        ),
        "last_20_hit_1plus_rate": _window_metric(
            recent_form,
            20,
            "event_rates",
            "hit_1plus_rate",
        ),
        "last_10_hits_per_game": _window_metric(
            recent_form,
            10,
            "per_game",
            "hits",
        ),
        "last_10_plate_appearances_per_game": _window_metric(
            recent_form,
            10,
            "per_game",
            "plate_appearances",
        ),
        "season_xba": expected.get("expected_batting_average"),
        "season_xslg": expected.get("expected_slugging"),
        "season_xwoba": expected.get("expected_woba"),
        "avg_exit_velocity_mph": contact.get("avg_exit_velocity_mph"),
        "hard_hit_pct": contact.get("hard_hit_pct"),
        "barrel_per_bbe_pct": contact.get("barrel_per_bbe_pct"),
        "sweet_spot_pct": contact.get("sweet_spot_pct"),
        "platoon_avg": _platoon_stat(platoon, "avg"),
        "platoon_obp": _platoon_stat(platoon, "obp"),
        "platoon_slg": _platoon_stat(platoon, "slg"),
        "platoon_ops": _platoon_stat(platoon, "ops"),
        "arsenal_qualified_usage_coverage_pct": overlap.get(
            "qualified_pitcher_usage_coverage_pct"
        ),
        "arsenal_weighted_hitter_xwoba": weighted.get(
            "weighted_hitter_expected_woba_vs_mix"
        ),
        "arsenal_weighted_pitcher_xwoba_allowed": weighted.get(
            "weighted_pitcher_expected_woba_allowed_by_mix"
        ),
        "arsenal_weighted_xwoba_context_gap": weighted.get(
            "weighted_xwoba_context_gap"
        ),
        "arsenal_weighted_hitter_whiff_pct": weighted.get(
            "weighted_hitter_whiff_pct_vs_mix"
        ),
        "arsenal_weighted_hitter_hard_hit_pct": weighted.get(
            "weighted_hitter_hard_hit_pct_vs_mix"
        ),
        "arsenal_weighted_hitter_run_value_per_100": weighted.get(
            "weighted_hitter_run_value_per_100_vs_mix"
        ),
    }


def _component_status(opportunity, recent_form, advanced, platoon, arsenal):
    windows = recent_form.get("windows", {})
    last_10 = windows.get("last_10", {})

    components = {
        "plate_appearance_opportunity": (
            opportunity.get("projected_plate_appearances") is not None
        ),
        "recent_form": (last_10.get("metrics") is not None),
        "statcast_contact_quality": (
            advanced.get("contact_quality") is not None
        ),
        "statcast_expected_statistics": (
            advanced.get("expected_statistics") is not None
        ),
        "platoon_split": platoon.get("available") is True,
        "qualified_arsenal_overlap": (
            arsenal.get("qualified_overlap_available") is True
        ),
    }

    available_count = sum(1 for value in components.values() if value)
    missing = [name for name, value in components.items() if not value]

    return {
        "core_components": components,
        "available_core_components": available_count,
        "required_core_components": len(CORE_COMPONENTS),
        "missing_core_components": missing,
        "complete_feature_profile": available_count == len(CORE_COMPONENTS),
    }


def _build_hitter_feature(
    slot,
    player_id,
    game_players,
    starter,
    team_environment,
    season,
    contact_rows,
    expected_rows,
    pitcher_board,
    hitter_board,
    source_errors,
):
    opportunity = _safe_hitter_opportunity(
        slot,
        player_id,
        game_players,
        team_environment,
        season,
        source_errors,
    )
    recent_form = _recent_form(player_id, season, source_errors)
    platoon = _platoon_context(
        player_id,
        starter.get("pitch_hand"),
        season,
        source_errors,
    )
    advanced = _advanced_hitting(player_id, contact_rows, expected_rows)
    arsenal = _arsenal_context(
        player_id,
        starter,
        pitcher_board,
        hitter_board,
    )

    profile = opportunity.get("player") or _player_profile(game_players, player_id)
    feature_vector = _feature_vector(
        opportunity,
        recent_form,
        advanced,
        platoon,
        arsenal,
    )
    readiness = _component_status(
        opportunity,
        recent_form,
        advanced,
        platoon,
        arsenal,
    )

    return {
        "batting_order_slot": slot,
        "player": profile,
        "opportunity": opportunity,
        "recent_form": recent_form,
        "advanced_hitting": advanced,
        "platoon": platoon,
        "arsenal_matchup": arsenal,
        "feature_vector": feature_vector,
        "feature_readiness": readiness,
    }


def _team_feature_board(
    side,
    team_meta,
    team_box,
    opposing_starter,
    game_players,
    season,
    contact_rows,
    expected_rows,
    pitcher_board,
    hitter_board,
    source_errors,
):
    lineup_ids = _lineup_from_box(team_box)
    lineup_confirmed = len(lineup_ids) >= 9
    team_id = team_meta.get("id")
    team_environment = _safe_team_environment(
        team_id,
        season,
        source_errors,
        side,
    )

    hitters = [
        _build_hitter_feature(
            slot,
            player_id,
            game_players,
            opposing_starter,
            team_environment,
            season,
            contact_rows,
            expected_rows,
            pitcher_board,
            hitter_board,
            source_errors,
        )
        for slot, player_id in enumerate(lineup_ids[:9], start=1)
    ]

    complete_profiles = sum(
        1
        for hitter in hitters
        if hitter.get("feature_readiness", {}).get("complete_feature_profile") is True
    )
    projections_available = sum(
        1
        for hitter in hitters
        if hitter.get("feature_vector", {}).get("projected_plate_appearances") is not None
    )

    blocking_reasons = []
    if not lineup_confirmed:
        blocking_reasons.append("lineup_not_confirmed")
    if opposing_starter.get("starter_id") is None:
        blocking_reasons.append("opposing_starter_not_identified")
    if projections_available < 9:
        blocking_reasons.append("fewer_than_9_pa_projections")
    if complete_profiles < 5:
        blocking_reasons.append("fewer_than_5_complete_feature_profiles")

    board_ready = (
        lineup_confirmed
        and opposing_starter.get("starter_id") is not None
        and projections_available >= 9
        and complete_profiles >= 5
    )

    return {
        "side": side,
        "team_id": team_id,
        "team_name": team_meta.get("name"),
        "lineup_confirmed": lineup_confirmed,
        "lineup_player_ids": lineup_ids[:9],
        "opposing_starter": opposing_starter,
        "team_pa_environment": team_environment,
        "summary": {
            "lineup_spots_analyzed": len(hitters),
            "pa_projections_available": projections_available,
            "complete_feature_profiles": complete_profiles,
            "board_ready": board_ready,
            "blocking_reasons": blocking_reasons,
        },
        "hitters": hitters,
    }


@router.get("/games/{game_pk}/hit-opportunity-features")
def get_mlb_hit_opportunity_features(
    game_pk: int,
    season: int | None = Query(
        default=None,
        ge=2015,
        le=2100,
        description=(
            "Season used for MLB and Statcast hitter features. Defaults to the game's "
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

    source_errors = []

    contact_rows, contact_error = _fetch_advanced_rows(
        SAVANT_STATCAST_URL,
        {
            "type": "batter",
            "year": target_season,
            "position": "",
            "team": "",
            "min": 1,
            "csv": "true",
        },
    )
    expected_rows, expected_error = _fetch_advanced_rows(
        SAVANT_EXPECTED_URL,
        {
            "type": "batter",
            "year": target_season,
            "position": "",
            "team": "",
            "filterType": "pa",
            "min": 1,
            "csv": "true",
        },
    )
    pitcher_rows, pitcher_error = _fetch_pitch_type_rows(
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
    hitter_rows, hitter_error = _fetch_pitch_type_rows(
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

    for source, error in (
        ("statcast_contact_quality", contact_error),
        ("statcast_expected_statistics", expected_error),
        ("pitcher_pitch_type_board", pitcher_error),
        ("hitter_pitch_type_board", hitter_error),
    ):
        if error:
            source_errors.append({"source": source, "error": error})

    pitcher_board = _normalize_pitcher_board(pitcher_rows)
    hitter_board = _normalize_hitter_board(hitter_rows)

    away = _team_feature_board(
        "away",
        teams.get("away", {}),
        team_boxes.get("away", {}),
        home_starter,
        game_players,
        target_season,
        contact_rows,
        expected_rows,
        pitcher_board,
        hitter_board,
        source_errors,
    )
    home = _team_feature_board(
        "home",
        teams.get("home", {}),
        team_boxes.get("home", {}),
        away_starter,
        game_players,
        target_season,
        contact_rows,
        expected_rows,
        pitcher_board,
        hitter_board,
        source_errors,
    )

    status = game_data.get("status", {})
    datetime_data = game_data.get("datetime", {})
    venue = game_data.get("venue", {})

    both_ready = (
        away.get("summary", {}).get("board_ready") is True
        and home.get("summary", {}).get("board_ready") is True
    )

    return {
        "sources": ["MLB Stats API", "Baseball Savant / MLB Statcast"],
        "calculated_by": "Kyre Sports API",
        "feature_profile_version": "hit-opportunity-features v0.1",
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
        },
        "readiness": {
            "away_ready": away.get("summary", {}).get("board_ready"),
            "home_ready": home.get("summary", {}).get("board_ready"),
            "both_teams_ready": both_ready,
        },
        "away": away,
        "home": home,
        "data_quality": {
            "core_components": list(CORE_COMPONENTS),
            "source_errors": source_errors,
            "partial_data_allowed": True,
        },
        "modeling_notes": {
            "purpose": (
                "This endpoint assembles model-ready hitter features from opportunity, recent form, "
                "Statcast quality, platoon context, and pitcher-arsenal overlap."
            ),
            "no_probability": (
                "The feature vector is descriptive input only. It does not produce 1+ hit, 2+ hit, "
                "home-run, fair-odds, expected-value, or Monte Carlo probabilities."
            ),
            "partial_profiles": (
                "Missing components remain explicit rather than being silently imputed. A later "
                "projection model can decide how to weight or replace incomplete inputs."
            ),
            "performance": (
                "Season-level Savant boards are fetched once and reused across the game. Player-specific "
                "MLB recent-form, platoon, and season-usage calls are still uncached in v0.1 and should "
                "move behind the database/cache layer before production-scale polling."
            ),
        },
    }
