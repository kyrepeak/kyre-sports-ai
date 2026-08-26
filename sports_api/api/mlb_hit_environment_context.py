from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from sports_api.api.mlb_bullpen import get_mlb_bullpen_usage
from sports_api.api.mlb_environment import get_mlb_game_environment
from sports_api.api.mlb_hit_opportunity_features import get_mlb_hit_opportunity_features

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-hit-environment-context"])

ARIZONA_TZ = ZoneInfo("America/Phoenix")


def _safe_environment(game_pk: int, source_errors):
    try:
        return get_mlb_game_environment(game_pk)
    except HTTPException as exc:
        source_errors.append(
            {
                "source": "game_environment",
                "game_pk": game_pk,
                "error": exc.detail,
            }
        )
        return {
            "park": {},
            "weather": {
                "available": False,
                "reason": "environment_unavailable",
            },
            "environment_readiness": {
                "venue_identified": False,
                "venue_details_available": False,
                "coordinates_available": False,
                "weather_available": False,
                "weather_relevance": "unknown",
            },
        }


def _safe_bullpen(team_id, analysis_date: str, lookback_days: int, source_errors):
    if not isinstance(team_id, int):
        return {
            "available": False,
            "team_id": team_id,
            "reason": "team_id_missing",
            "team_summary": None,
            "relievers_found": 0,
        }

    try:
        payload = get_mlb_bullpen_usage(
            team_id=team_id,
            date=analysis_date,
            lookback_days=lookback_days,
        )
        return {
            "available": True,
            **payload,
        }
    except HTTPException as exc:
        source_errors.append(
            {
                "source": "opposing_bullpen_workload",
                "team_id": team_id,
                "error": exc.detail,
            }
        )
        return {
            "available": False,
            "team_id": team_id,
            "reason": "bullpen_workload_unavailable",
            "team_summary": None,
            "relievers_found": 0,
        }


def _weather_context_status(environment):
    park = environment.get("park") or {}
    weather = environment.get("weather") or {}
    relevance = park.get("weather_relevance") or "unknown"
    available = weather.get("available") is True

    if relevance == "low":
        return "not_required"
    if relevance == "high":
        return "ready" if available else "missing_weather"
    if relevance == "conditional":
        return "needs_roof_state_confirmation"
    return "unknown"


def _compact_environment(environment):
    park = environment.get("park") or {}
    field = park.get("field") or {}
    weather = environment.get("weather") or {}
    weather_status = _weather_context_status(environment)

    return {
        "park": {
            "venue_id": park.get("venue_id"),
            "name": park.get("name"),
            "turf_type": field.get("turf_type"),
            "roof_type": field.get("roof_type"),
            "left_line_ft": field.get("left_line_ft"),
            "left_center_ft": field.get("left_center_ft"),
            "center_ft": field.get("center_ft"),
            "right_center_ft": field.get("right_center_ft"),
            "right_line_ft": field.get("right_line_ft"),
        },
        "weather": {
            "relevance": park.get("weather_relevance"),
            "context_status": weather_status,
            "available": weather.get("available") is True,
            "temperature": weather.get("temperature"),
            "temperature_unit": weather.get("temperature_unit"),
            "wind_speed": weather.get("wind_speed"),
            "wind_direction": weather.get("wind_direction"),
            "short_forecast": weather.get("short_forecast"),
            "precipitation_probability_pct": weather.get(
                "precipitation_probability_pct"
            ),
            "relative_humidity_pct": weather.get("relative_humidity_pct"),
            "dewpoint": weather.get("dewpoint"),
            "reason": weather.get("reason"),
        },
        "environment_readiness": environment.get("environment_readiness") or {},
    }


def _compact_bullpen(bullpen):
    summary = bullpen.get("team_summary") or {}
    return {
        "available": bullpen.get("available") is True,
        "team_id": bullpen.get("team_id"),
        "team_name": bullpen.get("team_name"),
        "analysis_date": bullpen.get("analysis_date"),
        "lookback_days": bullpen.get("lookback_days"),
        "relievers_found": bullpen.get("relievers_found"),
        "fatigue_method": bullpen.get("fatigue_method"),
        "bullpen_fatigue_level": summary.get("bullpen_fatigue_level"),
        "high_fatigue_relievers": summary.get("high_fatigue_relievers"),
        "moderate_fatigue_relievers": summary.get("moderate_fatigue_relievers"),
        "low_fatigue_relievers": summary.get("low_fatigue_relievers"),
        "team_pitches_last_1_day": summary.get("team_pitches_last_1_day"),
        "team_pitches_last_3_days": summary.get("team_pitches_last_3_days"),
        "team_reliever_appearances_last_3_days": summary.get(
            "team_reliever_appearances_last_3_days"
        ),
        "reason": bullpen.get("reason"),
    }


def _late_game_context(side: str):
    is_home = side == "home"

    return {
        "offense_side": side,
        "is_home": is_home,
        "is_away": not is_home,
        "bottom_ninth_may_be_skipped_if_home_team_ahead": is_home,
        "walkoff_can_end_home_half_inning_early": is_home,
        "away_team_bats_top_ninth_if_game_reaches_ninth": not is_home,
        "extra_innings_possible": True,
        "opportunity_note": (
            "Home hitters can lose the bottom of the ninth when their team is already ahead, "
            "and a walk-off can end a home half-inning before three outs."
            if is_home
            else
            "Away hitters do not face the home-team bottom-of-ninth skip rule; they bat in the "
            "top of the ninth if the game reaches that inning."
        ),
    }


def _environment_component_status(environment_context, bullpen_context):
    weather_status = (
        environment_context.get("weather", {}).get("context_status")
    )
    park_available = environment_context.get("park", {}).get("venue_id") is not None
    weather_resolved = weather_status in {"ready", "not_required"}
    bullpen_available = bullpen_context.get("available") is True

    components = {
        "park_context": park_available,
        "weather_context_resolved": weather_resolved,
        "opposing_bullpen_workload": bullpen_available,
        "late_game_rules": True,
    }

    missing = [name for name, available in components.items() if not available]

    return {
        "components": components,
        "weather_context_status": weather_status,
        "missing_components": missing,
        "complete_environment_context": len(missing) == 0,
    }


def _attach_environment_to_team(team_block, side, environment_context, opposing_bullpen):
    team = deepcopy(team_block)
    bullpen_context = _compact_bullpen(opposing_bullpen)
    late_game = _late_game_context(side)
    environment_status = _environment_component_status(
        environment_context,
        bullpen_context,
    )

    compact_context = {
        "home_away": "home" if side == "home" else "away",
        "park_weather": environment_context,
        "opposing_bullpen": bullpen_context,
        "late_game_opportunity": late_game,
        "readiness": environment_status,
    }

    team["game_environment_context"] = compact_context

    summary = team.setdefault("summary", {})
    summary["environment_context_ready"] = environment_status.get(
        "complete_environment_context"
    )
    summary["environment_missing_components"] = environment_status.get(
        "missing_components"
    )

    for hitter in team.get("hitters", []):
        feature_vector = hitter.setdefault("feature_vector", {})
        weather = environment_context.get("weather", {})

        feature_vector.update(
            {
                "is_home": side == "home",
                "weather_relevance": weather.get("relevance"),
                "weather_context_status": weather.get("context_status"),
                "temperature": weather.get("temperature"),
                "wind_speed": weather.get("wind_speed"),
                "wind_direction": weather.get("wind_direction"),
                "precipitation_probability_pct": weather.get(
                    "precipitation_probability_pct"
                ),
                "opposing_bullpen_fatigue_level": bullpen_context.get(
                    "bullpen_fatigue_level"
                ),
                "opposing_bullpen_high_fatigue_relievers": bullpen_context.get(
                    "high_fatigue_relievers"
                ),
                "opposing_bullpen_pitches_last_1_day": bullpen_context.get(
                    "team_pitches_last_1_day"
                ),
                "opposing_bullpen_pitches_last_3_days": bullpen_context.get(
                    "team_pitches_last_3_days"
                ),
                "bottom_ninth_may_be_skipped": late_game.get(
                    "bottom_ninth_may_be_skipped_if_home_team_ahead"
                ),
                "walkoff_can_end_half_inning_early": late_game.get(
                    "walkoff_can_end_home_half_inning_early"
                ),
            }
        )

        hitter["game_environment_context"] = compact_context

        readiness = hitter.setdefault("feature_readiness", {})
        readiness["environment_components"] = environment_status.get("components")
        readiness["environment_missing_components"] = environment_status.get(
            "missing_components"
        )
        readiness["complete_environment_context"] = environment_status.get(
            "complete_environment_context"
        )

    return team


@router.get("/games/{game_pk}/hit-environment-context")
def get_mlb_hit_environment_context(
    game_pk: int,
    season: int | None = Query(
        default=None,
        ge=2015,
        le=2100,
        description=(
            "Season used for the underlying hit-opportunity feature profile. Defaults to the "
            "game's official season when available."
        ),
    ),
    bullpen_lookback_days: int = Query(
        default=7,
        ge=3,
        le=14,
        description="Calendar-day lookback used for opposing bullpen workload context.",
    ),
):
    base = get_mlb_hit_opportunity_features(game_pk=game_pk, season=season)
    source_errors = list(base.get("data_quality", {}).get("source_errors") or [])

    official_date = base.get("official_date") or datetime.now(ARIZONA_TZ).date().isoformat()
    away_team_id = base.get("away", {}).get("team_id")
    home_team_id = base.get("home", {}).get("team_id")

    environment_raw = _safe_environment(game_pk, source_errors)
    environment_context = _compact_environment(environment_raw)

    away_bullpen = _safe_bullpen(
        away_team_id,
        official_date,
        bullpen_lookback_days,
        source_errors,
    )
    home_bullpen = _safe_bullpen(
        home_team_id,
        official_date,
        bullpen_lookback_days,
        source_errors,
    )

    away = _attach_environment_to_team(
        base.get("away", {}),
        "away",
        environment_context,
        home_bullpen,
    )
    home = _attach_environment_to_team(
        base.get("home", {}),
        "home",
        environment_context,
        away_bullpen,
    )

    away_environment_ready = away.get("summary", {}).get("environment_context_ready") is True
    home_environment_ready = home.get("summary", {}).get("environment_context_ready") is True

    return {
        "sources": [
            "MLB Stats API",
            "Baseball Savant / MLB Statcast",
            "National Weather Service",
        ],
        "calculated_by": "Kyre Sports API",
        "feature_profile_version": "hit-environment-context v0.1",
        "game_pk": game_pk,
        "season": base.get("season"),
        "official_date": official_date,
        "game_datetime_utc": base.get("game_datetime_utc"),
        "status": base.get("status"),
        "venue": base.get("venue"),
        "starter_status": base.get("starter_status"),
        "game_environment": environment_context,
        "bullpen_workload": {
            "away_team_bullpen": _compact_bullpen(away_bullpen),
            "home_team_bullpen": _compact_bullpen(home_bullpen),
        },
        "readiness": {
            "base_away_ready": base.get("readiness", {}).get("away_ready"),
            "base_home_ready": base.get("readiness", {}).get("home_ready"),
            "away_environment_ready": away_environment_ready,
            "home_environment_ready": home_environment_ready,
            "both_environment_contexts_ready": (
                away_environment_ready and home_environment_ready
            ),
        },
        "away": away,
        "home": home,
        "data_quality": {
            "source_errors": source_errors,
            "partial_data_allowed": True,
            "weather_context_status": environment_context.get("weather", {}).get(
                "context_status"
            ),
        },
        "modeling_notes": {
            "park_weather": (
                "This layer preserves source-native park and weather context. It does not invent a "
                "park-factor multiplier or convert wind/temperature directly into hit probability."
            ),
            "roof_rule": (
                "Retractable-roof parks remain unresolved until actual roof state is confirmed. "
                "Fixed/dome parks do not require outdoor weather for context completeness."
            ),
            "bullpen": (
                "Bullpen fatigue is a workload heuristic, not a medical assessment and not a direct "
                "performance probability. Away hitters receive the home bullpen context and home "
                "hitters receive the away bullpen context."
            ),
            "late_game": (
                "Home hitters can lose late plate appearances when the bottom of the ninth is not "
                "needed, while walk-offs can end a home half-inning early. This layer flags those "
                "structural rules but does not yet quantify their probability."
            ),
            "no_probability": (
                "This remains a feature/context endpoint. It does not output 1+ hit probability, "
                "expected hits, fair odds, EV, or Monte Carlo results."
            ),
        },
    }
