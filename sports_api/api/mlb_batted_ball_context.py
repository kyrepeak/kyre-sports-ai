from copy import deepcopy

from fastapi import APIRouter, Query

from sports_api.api.mlb_advanced_hitting import _fetch_csv_rows
from sports_api.api.mlb_hit_defense_context import get_mlb_hit_defense_context

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-hit-batted-ball-context"])

SAVANT_BATTED_BALL_URL = "https://baseballsavant.mlb.com/leaderboard/batted-ball"
SAVANT_SPRINT_SPEED_URL = "https://baseballsavant.mlb.com/leaderboard/sprint_speed"
MLB_AVG_SPRINT_SPEED_FT_PER_SEC = 27.0


def _to_float(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "--", "null", "None"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    number = _to_float(value)
    return int(number) if number is not None else None


def _as_pct(value):
    number = _to_float(value)
    if number is None:
        return None
    # Savant's batted-ball CSV currently returns rates as fractions (0-1),
    # but normalize defensively if a display-percent shape is returned later.
    if -1.5 <= number <= 1.5:
        number *= 100.0
    return round(number, 3)


def _row_player_id(row):
    for key in ("id", "player_id", "batter_id", "mlbam_id"):
        value = _to_int((row or {}).get(key))
        if value is not None:
            return value
    return None


def _find_player_row(rows, player_id: int):
    return next((row for row in rows if _row_player_id(row) == player_id), None)


def _normalize_batted_ball(row):
    if not row:
        return None

    return {
        "player_id": _row_player_id(row),
        "player_name": row.get("name") or row.get("last_name, first_name"),
        "batted_ball_events": _to_int(row.get("bbe")),
        "trajectory": {
            "ground_ball_pct": _as_pct(row.get("gb_rate")),
            "air_ball_pct": _as_pct(row.get("air_rate")),
            "fly_ball_pct": _as_pct(row.get("fb_rate")),
            "line_drive_pct": _as_pct(row.get("ld_rate")),
            "popup_pct": _as_pct(row.get("pu_rate")),
        },
        "spray": {
            "pull_pct": _as_pct(row.get("pull_rate")),
            "straight_pct": _as_pct(row.get("straight_rate")),
            "opposite_field_pct": _as_pct(row.get("oppo_rate")),
        },
        "ground_ball_direction": {
            "pull_pct": _as_pct(row.get("pull_gb_rate")),
            "straight_pct": _as_pct(row.get("straight_gb_rate")),
            "opposite_field_pct": _as_pct(row.get("oppo_gb_rate")),
        },
        "air_ball_direction": {
            "pull_pct": _as_pct(row.get("pull_air_rate")),
            "straight_pct": _as_pct(row.get("straight_air_rate")),
            "opposite_field_pct": _as_pct(row.get("oppo_air_rate")),
        },
    }


def _normalize_sprint_speed(row):
    if not row:
        return None

    competitive_runs = _to_int(row.get("competitive_runs"))
    bolts = _to_int(row.get("bolts"))
    sprint_speed = _to_float(row.get("sprint_speed"))

    bolt_rate = None
    if competitive_runs and competitive_runs > 0 and bolts is not None:
        bolt_rate = round((bolts / competitive_runs) * 100.0, 3)

    speed_vs_average = None
    if sprint_speed is not None:
        speed_vs_average = round(
            sprint_speed - MLB_AVG_SPRINT_SPEED_FT_PER_SEC,
            3,
        )

    return {
        "player_id": _row_player_id(row),
        "player_name": row.get("last_name, first_name") or row.get("name"),
        "team_id": _to_int(row.get("team_id")),
        "team": row.get("team"),
        "position": row.get("position"),
        "age": _to_int(row.get("age")),
        "competitive_runs": competitive_runs,
        "bolts": bolts,
        "bolt_rate_pct": bolt_rate,
        "home_to_first_sec": _to_float(row.get("hp_to_1b")),
        "sprint_speed_ft_per_sec": sprint_speed,
        "mlb_average_sprint_speed_ft_per_sec": MLB_AVG_SPRINT_SPEED_FT_PER_SEC,
        "sprint_speed_vs_mlb_average_ft_per_sec": speed_vs_average,
    }


def _compact_profile(batted_ball, sprint_speed, avg_launch_angle):
    trajectory = (batted_ball or {}).get("trajectory") or {}
    spray = (batted_ball or {}).get("spray") or {}
    air_direction = (batted_ball or {}).get("air_ball_direction") or {}

    return {
        "batted_ball_events": (batted_ball or {}).get("batted_ball_events"),
        "avg_launch_angle_deg": avg_launch_angle,
        "ground_ball_pct": trajectory.get("ground_ball_pct"),
        "air_ball_pct": trajectory.get("air_ball_pct"),
        "fly_ball_pct": trajectory.get("fly_ball_pct"),
        "line_drive_pct": trajectory.get("line_drive_pct"),
        "popup_pct": trajectory.get("popup_pct"),
        "pull_pct": spray.get("pull_pct"),
        "straight_pct": spray.get("straight_pct"),
        "opposite_field_pct": spray.get("opposite_field_pct"),
        "pulled_air_pct": air_direction.get("pull_pct"),
        "straight_air_pct": air_direction.get("straight_pct"),
        "opposite_field_air_pct": air_direction.get("opposite_field_pct"),
        "sprint_speed_ft_per_sec": (sprint_speed or {}).get(
            "sprint_speed_ft_per_sec"
        ),
        "sprint_speed_vs_mlb_average_ft_per_sec": (sprint_speed or {}).get(
            "sprint_speed_vs_mlb_average_ft_per_sec"
        ),
        "competitive_runs": (sprint_speed or {}).get("competitive_runs"),
        "bolts": (sprint_speed or {}).get("bolts"),
        "bolt_rate_pct": (sprint_speed or {}).get("bolt_rate_pct"),
        "home_to_first_sec": (sprint_speed or {}).get("home_to_first_sec"),
        # These are descriptive contact shares that a later calibrated model can
        # use to decide how much infield/outfield defense should matter.
        "infield_contact_relevance_pct": trajectory.get("ground_ball_pct"),
        "air_outfield_contact_relevance_pct": trajectory.get("air_ball_pct"),
    }


def _attach_profiles(team_block, batted_ball_rows, sprint_rows):
    team = deepcopy(team_block)
    batted_ball_available = 0
    sprint_speed_available = 0
    complete_profiles = 0

    for hitter in team.get("hitters", []):
        player = hitter.get("player") or {}
        player_id = player.get("player_id")

        batted_ball = _normalize_batted_ball(
            _find_player_row(batted_ball_rows, player_id)
        ) if isinstance(player_id, int) else None
        sprint_speed = _normalize_sprint_speed(
            _find_player_row(sprint_rows, player_id)
        ) if isinstance(player_id, int) else None

        contact_quality = (
            hitter.get("advanced_hitting", {}).get("contact_quality") or {}
        )
        avg_launch_angle = contact_quality.get("avg_launch_angle_deg")
        compact = _compact_profile(batted_ball, sprint_speed, avg_launch_angle)

        if batted_ball is not None:
            batted_ball_available += 1
        if sprint_speed is not None:
            sprint_speed_available += 1
        if batted_ball is not None and sprint_speed is not None:
            complete_profiles += 1

        hitter["batted_ball_profile"] = batted_ball
        hitter["sprint_speed_context"] = sprint_speed
        hitter["contact_shape_context"] = compact

        feature_vector = hitter.setdefault("feature_vector", {})
        feature_vector.update(compact)

        readiness = hitter.setdefault("feature_readiness", {})
        readiness["contact_shape_components"] = {
            "batted_ball_profile": batted_ball is not None,
            "sprint_speed": sprint_speed is not None,
            "average_launch_angle": avg_launch_angle is not None,
        }
        readiness["contact_shape_missing_components"] = [
            name
            for name, available in readiness["contact_shape_components"].items()
            if not available
        ]
        readiness["complete_contact_shape_context"] = (
            batted_ball is not None and sprint_speed is not None
        )

    summary = team.setdefault("summary", {})
    lineup_count = len(team.get("hitters", []))
    summary.update(
        {
            "batted_ball_profiles_available": batted_ball_available,
            "sprint_speed_profiles_available": sprint_speed_available,
            "complete_contact_shape_profiles": complete_profiles,
            "contact_shape_board_ready": (
                lineup_count >= 9
                and batted_ball_available >= 7
                and sprint_speed_available >= 5
            ),
        }
    )

    return team


@router.get("/games/{game_pk}/hit-batted-ball-context")
def get_mlb_hit_batted_ball_context(
    game_pk: int,
    season: int | None = Query(
        default=None,
        ge=2017,
        le=2100,
        description=(
            "Statcast season used for batted-ball and Sprint Speed context. Defaults to the "
            "game season through the underlying hit-defense profile."
        ),
    ),
    bullpen_lookback_days: int = Query(
        default=7,
        ge=3,
        le=14,
        description="Passed through to the underlying hit-defense/environment context.",
    ),
):
    base = get_mlb_hit_defense_context(
        game_pk=game_pk,
        season=season,
        bullpen_lookback_days=bullpen_lookback_days,
    )
    target_season = base.get("season")
    source_errors = list(base.get("data_quality", {}).get("source_errors") or [])

    batted_ball_rows, batted_ball_error = _fetch_csv_rows(
        SAVANT_BATTED_BALL_URL,
        {
            "type": "batter",
            "year": target_season,
            "min": 1,
            "csv": "true",
        },
    )
    sprint_rows, sprint_error = _fetch_csv_rows(
        SAVANT_SPRINT_SPEED_URL,
        {
            "year": target_season,
            "position": "",
            "team": "",
            "min": 1,
            "csv": "true",
        },
    )

    if batted_ball_error:
        source_errors.append(
            {"source": "savant_batted_ball_profile", "error": batted_ball_error}
        )
    if sprint_error:
        source_errors.append(
            {"source": "savant_sprint_speed", "error": sprint_error}
        )

    away = _attach_profiles(base.get("away", {}), batted_ball_rows, sprint_rows)
    home = _attach_profiles(base.get("home", {}), batted_ball_rows, sprint_rows)

    away_ready = away.get("summary", {}).get("contact_shape_board_ready") is True
    home_ready = home.get("summary", {}).get("contact_shape_board_ready") is True

    return {
        "sources": [
            "MLB Stats API",
            "Baseball Savant / MLB Statcast",
            "National Weather Service",
        ],
        "calculated_by": "Kyre Sports API",
        "feature_profile_version": "hit-batted-ball-context v0.1",
        "game_pk": game_pk,
        "season": target_season,
        "official_date": base.get("official_date"),
        "game_datetime_utc": base.get("game_datetime_utc"),
        "status": base.get("status"),
        "venue": base.get("venue"),
        "starter_status": base.get("starter_status"),
        "game_environment": base.get("game_environment"),
        "bullpen_workload": base.get("bullpen_workload"),
        "team_defense": base.get("team_defense"),
        "readiness": {
            **(base.get("readiness") or {}),
            "away_contact_shape_ready": away_ready,
            "home_contact_shape_ready": home_ready,
            "both_contact_shape_boards_ready": away_ready and home_ready,
        },
        "away": away,
        "home": home,
        "data_quality": {
            "source_errors": source_errors,
            "partial_data_allowed": True,
            "batted_ball_board_available": bool(batted_ball_rows),
            "sprint_speed_board_available": bool(sprint_rows),
        },
        "modeling_notes": {
            "batted_ball_profile": (
                "Savant AIR% is all non-ground batted balls (line drives, fly balls, and popups). "
                "Rates are normalized to percentage points in this API response."
            ),
            "defense_bridge": (
                "Ground-ball rate is exposed as descriptive infield-contact relevance and AIR% as "
                "descriptive air/outfield-contact relevance. These are not calibrated defense adjustments."
            ),
            "sprint_speed": (
                "Sprint Speed is source-native Statcast running context. The API reports the player's "
                "season speed, competitive runs, Bolts, home-to-first time, and difference from the "
                "27 ft/sec MLB competitive-play reference value."
            ),
            "no_probability": (
                "This remains a feature/context layer. It does not convert batted-ball shape, speed, "
                "or defense into 1+ hit probability, expected hits, fair odds, EV, or Monte Carlo output."
            ),
        },
    }
