import csv
import io
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-pitch-movement"])

SAVANT_PITCH_MOVEMENT_URL = "https://baseballsavant.mlb.com/leaderboard/pitch-movement"
SAVANT_ACTIVE_SPIN_URL = "https://baseballsavant.mlb.com/leaderboard/active-spin"
SAVANT_ARM_ANGLE_URL = "https://baseballsavant.mlb.com/leaderboard/pitcher-arm-angles"
SAVANT_PITCH_STATS_URL = "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
ARIZONA_TZ = ZoneInfo("America/Phoenix")

SAVANT_HEADERS = {
    "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.8",
    "User-Agent": "KyreSportsAPI/0.1 (sports analytics application)",
}

PITCH_TYPES = {
    "FF": "4-Seam Fastball",
    "SI": "Sinker",
    "FC": "Cutter",
    "SL": "Slider",
    "ST": "Sweeper",
    "CU": "Curveball",
    "KC": "Knuckle Curve",
    "CH": "Changeup",
    "FS": "Split-Finger",
    "SV": "Slurve",
    "KN": "Knuckleball",
}

ACTIVE_SPIN_ALIASES = {
    "FF": ("ff", "four_seam", "four_seam_fastball", "four-seam"),
    "SI": ("si", "sinker"),
    "FC": ("fc", "cutter"),
    "SL": ("sl", "slider"),
    "ST": ("st", "sweeper"),
    "CU": ("cu", "curve", "curveball"),
    "KC": ("kc", "knuckle_curve", "knucklecurve"),
    "CH": ("ch", "changeup", "change"),
    "FS": ("fs", "splitter", "split_finger", "split-finger"),
    "SV": ("sv", "slurve"),
    "KN": ("kn", "knuckleball"),
}


def _normalize_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _normalized_row(row):
    return {_normalize_key(key): value for key, value in (row or {}).items()}


def _first_value(row, aliases):
    normalized = _normalized_row(row)
    for alias in aliases:
        value = normalized.get(_normalize_key(alias))
        if value not in (None, "", "--"):
            return value
    return None


def _to_float(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "--"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    number = _to_float(value)
    return int(number) if number is not None else None


def _fetch_csv_rows(url: str, params: dict):
    try:
        response = httpx.get(
            url,
            params=params,
            headers=SAVANT_HEADERS,
            timeout=25.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return [], str(exc)

    text = response.text.lstrip("\ufeff").strip()
    if not text:
        return [], "empty_csv_response"

    try:
        rows = list(csv.DictReader(io.StringIO(text)))
    except (csv.Error, UnicodeError) as exc:
        return [], f"csv_parse_error: {exc}"

    if not rows:
        return [], "csv_contains_no_rows"

    return rows, None


def _row_player_id(row):
    return _to_int(
        _first_value(
            row,
            (
                "player_id",
                "pitcher_id",
                "pitcher",
                "mlbam_id",
                "mlbamid",
            ),
        )
    )


def _player_name(row):
    return _first_value(
        row,
        (
            "last_name, first_name",
            "player_name",
            "pitcher_name",
            "name",
        ),
    )


def _discover_pitch_types(player_id: int, season: int):
    rows, error = _fetch_csv_rows(
        SAVANT_PITCH_STATS_URL,
        {
            "type": "pitcher",
            "year": season,
            "team": "",
            "min": 1,
            "minPitches": 1,
            "csv": "true",
        },
    )

    pitch_types = []
    for row in rows:
        if _row_player_id(row) != player_id:
            continue
        pitch_type = str(_first_value(row, ("pitch_type",)) or "").upper()
        if pitch_type and pitch_type not in pitch_types:
            pitch_types.append(pitch_type)

    return pitch_types, error


def _fetch_movement_row(player_id: int, season: int, pitch_type: str):
    rows, error = _fetch_csv_rows(
        SAVANT_PITCH_MOVEMENT_URL,
        {
            "year": season,
            "pitch_type": pitch_type,
            "hand": "",
            "min": 1,
            "csv": "true",
        },
    )

    row = next((item for item in rows if _row_player_id(item) == player_id), None)
    return row, error


def _normalize_movement_row(row, pitch_type: str):
    if not row:
        return None

    return {
        "pitch_type": pitch_type,
        "pitch_name": (
            _first_value(row, ("pitch_name", "pitch_type_name", "pitch"))
            or PITCH_TYPES.get(pitch_type)
        ),
        "player_id": _row_player_id(row),
        "player_name": _player_name(row),
        "team": _first_value(row, ("team_name_alt", "team_name", "team")),
        "throws": _first_value(row, ("pitcher_hand", "hand", "throws")),
        "pitches": _to_int(_first_value(row, ("pitches", "pitch_count", "count"))),
        "average_velocity_mph": _to_float(
            _first_value(row, ("avg_speed", "average_speed", "velocity"))
        ),
        "release_extension_ft": _to_float(
            _first_value(row, ("extension", "release_extension", "avg_extension"))
        ),
        "total_movement": {
            "vertical_drop_inches": _to_float(
                _first_value(row, ("pitcher_break_z", "vertical_drop", "vert_break"))
            ),
            "vertical_vs_comparable_inches": _to_float(
                _first_value(row, ("diff_z", "diff_z_hidden", "vertical_vs_comparable"))
            ),
            "horizontal_break_inches": _to_float(
                _first_value(
                    row,
                    ("pitcher_break_x", "pitcher_break_x_hidden", "horizontal_break"),
                )
            ),
            "horizontal_vs_comparable_inches": _to_float(
                _first_value(
                    row,
                    ("diff_x", "diff_x_hidden", "horizontal_vs_comparable"),
                )
            ),
        },
        "induced_movement": {
            "vertical_break_inches": _to_float(
                _first_value(
                    row,
                    (
                        "pitcher_break_z_induced",
                        "induced_vertical_break",
                        "ivb",
                    ),
                )
            ),
            "vertical_vs_average_inches": _to_float(
                _first_value(
                    row,
                    (
                        "diff_z_induced",
                        "induced_vertical_vs_average",
                        "ivb_vs_avg",
                    ),
                )
            ),
            "horizontal_break_inches": _to_float(
                _first_value(
                    row,
                    (
                        "pitcher_break_x_induced",
                        "induced_horizontal_break",
                    ),
                )
            ),
            "horizontal_vs_average_inches": _to_float(
                _first_value(
                    row,
                    (
                        "diff_x_induced",
                        "induced_horizontal_vs_average",
                    ),
                )
            ),
        },
    }


def _fetch_active_spin(player_id: int, season: int):
    rows, error = _fetch_csv_rows(
        SAVANT_ACTIVE_SPIN_URL,
        {
            "year": f"{season}_spin-based",
            "hand": "",
            "min": 1,
            "csv": "true",
        },
    )

    row = next((item for item in rows if _row_player_id(item) == player_id), None)
    if not row:
        return None, error

    pitches = {}
    for pitch_type, aliases in ACTIVE_SPIN_ALIASES.items():
        value = _to_float(_first_value(row, aliases))
        if value is not None:
            pitches[pitch_type] = {
                "pitch_type": pitch_type,
                "pitch_name": PITCH_TYPES.get(pitch_type),
                "active_spin_pct": value,
            }

    return {
        "player_id": _row_player_id(row),
        "player_name": _player_name(row),
        "throws": _first_value(row, ("pitcher_hand", "hand", "throws")),
        "method": "spin-based",
        "pitches": pitches,
        "pitch_types_available": len(pitches),
    }, error


def _fetch_arm_angle(player_id: int, season: int):
    rows, error = _fetch_csv_rows(
        SAVANT_ARM_ANGLE_URL,
        {
            "year": season,
            "group_by": "season",
            "game_type": "R",
            "csv": "true",
        },
    )

    player_rows = [row for row in rows if _row_player_id(row) == player_id]
    if not player_rows:
        return None, error

    row = player_rows[0]
    return {
        "player_id": _row_player_id(row),
        "player_name": _player_name(row),
        "season": _to_int(_first_value(row, ("year", "season"))) or season,
        "average_arm_angle_deg": _to_float(
            _first_value(row, ("arm_angle", "avg_arm_angle", "average_arm_angle"))
        ),
        "release_position_x_ft": _to_float(
            _first_value(row, ("release_pos_x", "release_x", "release_position_x"))
        ),
        "release_position_z_ft": _to_float(
            _first_value(row, ("release_pos_z", "release_z", "release_position_z"))
        ),
        "release_extension_ft": _to_float(
            _first_value(row, ("release_extension", "extension", "avg_extension"))
        ),
    }, error


def _eligible_shape_candidates(pitches, field_path):
    candidates = []
    for pitch in pitches:
        if (pitch.get("pitches") or 0) < 25:
            continue
        value = pitch
        for key in field_path:
            value = (value or {}).get(key) if isinstance(value, dict) else None
        if value is not None:
            candidates.append((abs(value), value, pitch))
    return candidates


def _shape_summary(pitches):
    horizontal_candidates = _eligible_shape_candidates(
        pitches,
        ("total_movement", "horizontal_vs_comparable_inches"),
    )
    vertical_candidates = _eligible_shape_candidates(
        pitches,
        ("total_movement", "vertical_vs_comparable_inches"),
    )

    biggest_horizontal = max(horizontal_candidates, default=None, key=lambda item: item[0])
    biggest_vertical = max(vertical_candidates, default=None, key=lambda item: item[0])

    def _summary_item(item, metric_name):
        if item is None:
            return None
        _, value, pitch = item
        return {
            "pitch_type": pitch.get("pitch_type"),
            "pitch_name": pitch.get("pitch_name"),
            metric_name: value,
            "pitches": pitch.get("pitches"),
        }

    return {
        "pitch_types_available": len(pitches),
        "total_tracked_pitches": sum(pitch.get("pitches") or 0 for pitch in pitches),
        "largest_horizontal_difference_vs_comparable": _summary_item(
            biggest_horizontal,
            "horizontal_vs_comparable_inches",
        ),
        "largest_vertical_difference_vs_comparable": _summary_item(
            biggest_vertical,
            "vertical_vs_comparable_inches",
        ),
        "minimum_pitches_for_shape_highlight": 25,
    }


@router.get("/players/{player_id}/pitch-movement")
def get_mlb_pitch_movement(
    player_id: int,
    season: int | None = Query(
        default=None,
        ge=2020,
        le=2100,
        description=(
            "Statcast season year. Defaults to the current Arizona calendar year. "
            "2020+ is required so arm-angle and directly measured active-spin context can align."
        ),
    ),
):
    target_season = season or datetime.now(ARIZONA_TZ).year

    discovered_pitch_types, discovery_error = _discover_pitch_types(player_id, target_season)
    pitch_types_to_check = discovered_pitch_types or list(PITCH_TYPES.keys())

    pitches = []
    movement_errors = []

    for pitch_type in pitch_types_to_check:
        row, error = _fetch_movement_row(player_id, target_season, pitch_type)
        if error:
            movement_errors.append({"pitch_type": pitch_type, "error": error})
        movement = _normalize_movement_row(row, pitch_type)
        if movement is not None:
            pitches.append(movement)

    pitches.sort(
        key=lambda pitch: (
            pitch.get("pitches") or 0,
            pitch.get("average_velocity_mph") or 0,
        ),
        reverse=True,
    )

    active_spin, active_spin_error = _fetch_active_spin(player_id, target_season)
    arm_angle, arm_angle_error = _fetch_arm_angle(player_id, target_season)

    source_errors = []
    if discovery_error:
        source_errors.append({"source": "pitch_type_discovery", "error": discovery_error})
    if movement_errors:
        source_errors.append({"source": "pitch_movement", "errors": movement_errors})
    if active_spin_error:
        source_errors.append({"source": "active_spin", "error": active_spin_error})
    if arm_angle_error:
        source_errors.append({"source": "arm_angle", "error": arm_angle_error})

    movement_core_failed = len(pitches) == 0 and bool(movement_errors)
    if movement_core_failed:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Baseball Savant pitch-movement source is unavailable.",
                "source_errors": source_errors,
            },
        )

    player_name = None
    for pitch in pitches:
        if pitch.get("player_name"):
            player_name = pitch.get("player_name")
            break
    if player_name is None and active_spin:
        player_name = active_spin.get("player_name")
    if player_name is None and arm_angle:
        player_name = arm_angle.get("player_name")

    components_available = {
        "pitch_movement": len(pitches) > 0,
        "active_spin": active_spin is not None,
        "arm_angle": arm_angle is not None,
    }
    missing_components = [
        name for name, available in components_available.items() if not available
    ]

    return {
        "source": "Baseball Savant / MLB Statcast",
        "calculated_by": "Kyre Sports API",
        "player_id": player_id,
        "player_name": player_name,
        "season": target_season,
        "shape_summary": _shape_summary(pitches),
        "pitches": pitches,
        "active_spin": active_spin,
        "arm_angle": arm_angle,
        "data_quality": {
            "pitch_types_discovered": discovered_pitch_types,
            "components_available": components_available,
            "missing_components": missing_components,
            "complete": len(missing_components) == 0,
            "source_errors": source_errors,
        },
        "modeling_notes": {
            "total_movement": (
                "Baseball Savant total movement includes gravity and compares a pitch with the same "
                "pitch type within approximately +/-2 mph and +/-0.5 feet of extension/release."
            ),
            "induced_movement": (
                "Induced movement removes gravity to isolate movement generated by spin and pitch "
                "manipulation."
            ),
            "active_spin": (
                "Active Spin is the portion of spin that contributes to pitch movement. The endpoint "
                "requests Savant's directly measured spin-based method when available."
            ),
            "arm_angle": (
                "Arm angle is the average release angle measured from horizontal ground: 0 degrees "
                "is sidearm and 90 degrees is over-the-top."
            ),
            "shape_highlights": (
                "Kyre Sports API highlights movement differences only when a pitch has at least 25 "
                "tracked pitches. No proprietary Stuff+ score is invented in this step."
            ),
        },
    }
