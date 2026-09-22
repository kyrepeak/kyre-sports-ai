import csv
import io
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-pitch-type-effectiveness"])

SAVANT_PITCH_STATS_URL = "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
SAVANT_ARSENALS_URL = "https://baseballsavant.mlb.com/leaderboard/pitch-arsenals"
ARIZONA_TZ = ZoneInfo("America/Phoenix")

SAVANT_HEADERS = {
    "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.8",
    "User-Agent": "KyreSportsAPI/0.1 (sports analytics application)",
}

PITCH_NAMES = {
    "FF": "4-Seam Fastball",
    "SI": "Sinker",
    "FC": "Cutter",
    "SL": "Slider",
    "ST": "Sweeper",
    "CU": "Curveball",
    "KC": "Knuckle Curve",
    "CH": "Changeup",
    "FS": "Splitter",
    "SV": "Slurve",
    "KN": "Knuckleball",
}


def _normalize_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _normalized_row(row):
    return {_normalize_key(key): value for key, value in (row or {}).items()}


def _first_value(row, aliases):
    normalized = _normalized_row(row)
    for alias in aliases:
        value = normalized.get(_normalize_key(alias))
        if value not in (None, ""):
            return value
    return None


def _to_float(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "":
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
                "pitcher",
                "pitcher_id",
                "mlbam_id",
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


def _sample_label(pitches, plate_appearances):
    sample = max(pitches or 0, plate_appearances or 0)
    if sample <= 0:
        return "none"
    if sample < 25:
        return "very_small"
    if sample < 75:
        return "small"
    if sample < 150:
        return "moderate"
    return "large"


def _velocity_map(rows, player_id: int):
    row = next((item for item in rows if _row_player_id(item) == player_id), None)
    if not row:
        return {}, None

    normalized = _normalized_row(row)
    velocities = {}

    for pitch_code, pitch_name in PITCH_NAMES.items():
        key = _normalize_key(f"{pitch_code.lower()}_avg_speed")
        velocity = _to_float(normalized.get(key))
        if velocity is not None:
            velocities[pitch_code] = {
                "pitch_type": pitch_code,
                "pitch_name": pitch_name,
                "average_velocity_mph": velocity,
            }

    return velocities, _player_name(row)


def _normalize_pitch_row(row, velocities):
    pitch_type = str(_first_value(row, ("pitch_type",)) or "").upper() or None
    pitch_name = _first_value(row, ("pitch_name",))
    pitches = _to_int(_first_value(row, ("pitches",)))
    plate_appearances = _to_int(_first_value(row, ("pa", "plate_appearances")))

    velocity = None
    if pitch_type and pitch_type in velocities:
        velocity = velocities[pitch_type].get("average_velocity_mph")

    return {
        "pitch_type": pitch_type,
        "pitch_name": pitch_name or PITCH_NAMES.get(pitch_type),
        "team": _first_value(row, ("team_name_alt", "team")),
        "average_velocity_mph": velocity,
        "run_value_per_100_pitches": _to_float(
            _first_value(row, ("run_value_per_100",))
        ),
        "run_value": _to_float(_first_value(row, ("run_value",))),
        "pitches": pitches,
        "usage_pct": _to_float(_first_value(row, ("pitch_usage", "usage"))),
        "plate_appearances": plate_appearances,
        "batting_average_allowed": _to_float(_first_value(row, ("ba",))),
        "slugging_allowed": _to_float(_first_value(row, ("slg",))),
        "woba_allowed": _to_float(_first_value(row, ("woba",))),
        "whiff_pct": _to_float(_first_value(row, ("whiff_percent", "whiff_pct"))),
        "strikeout_pct": _to_float(_first_value(row, ("k_percent", "k_pct"))),
        "put_away_pct": _to_float(_first_value(row, ("put_away", "put_away_pct"))),
        "expected_batting_average_allowed": _to_float(
            _first_value(row, ("est_ba", "xba"))
        ),
        "expected_slugging_allowed": _to_float(
            _first_value(row, ("est_slg", "xslg"))
        ),
        "expected_woba_allowed": _to_float(
            _first_value(row, ("est_woba", "xwoba"))
        ),
        "hard_hit_allowed_pct": _to_float(
            _first_value(row, ("hard_hit_percent", "hard_hit_pct"))
        ),
        "sample_size_label": _sample_label(pitches, plate_appearances),
    }


def _arsenal_summary(pitches):
    if not pitches:
        return {
            "pitch_types_available": 0,
            "total_tracked_pitches": 0,
            "primary_pitch": None,
            "highest_whiff_pitch": None,
        }

    total_pitches = sum(pitch.get("pitches") or 0 for pitch in pitches)
    primary = max(
        pitches,
        key=lambda pitch: (
            pitch.get("usage_pct") if pitch.get("usage_pct") is not None else -1,
            pitch.get("pitches") or 0,
        ),
    )

    whiff_candidates = [
        pitch
        for pitch in pitches
        if pitch.get("whiff_pct") is not None and (pitch.get("pitches") or 0) >= 25
    ]
    highest_whiff = (
        max(whiff_candidates, key=lambda pitch: pitch.get("whiff_pct"))
        if whiff_candidates
        else None
    )

    return {
        "pitch_types_available": len(pitches),
        "total_tracked_pitches": total_pitches,
        "primary_pitch": {
            "pitch_type": primary.get("pitch_type"),
            "pitch_name": primary.get("pitch_name"),
            "usage_pct": primary.get("usage_pct"),
            "average_velocity_mph": primary.get("average_velocity_mph"),
        },
        "highest_whiff_pitch": (
            {
                "pitch_type": highest_whiff.get("pitch_type"),
                "pitch_name": highest_whiff.get("pitch_name"),
                "whiff_pct": highest_whiff.get("whiff_pct"),
                "pitches": highest_whiff.get("pitches"),
            }
            if highest_whiff
            else None
        ),
    }


@router.get("/players/{player_id}/pitch-type-effectiveness")
def get_mlb_pitch_type_effectiveness(
    player_id: int,
    season: int | None = Query(
        default=None,
        ge=2015,
        le=2100,
        description="Statcast season year. Defaults to the current Arizona calendar year.",
    ),
):
    target_season = season or datetime.now(ARIZONA_TZ).year

    stats_rows, stats_error = _fetch_csv_rows(
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

    velocity_rows, velocity_error = _fetch_csv_rows(
        SAVANT_ARSENALS_URL,
        {
            "year": target_season,
            "type": "avg_speed",
            "min": 1,
            "csv": "true",
        },
    )

    if stats_error and velocity_error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Baseball Savant pitch-type sources are unavailable.",
                "source_errors": [
                    {"source": "pitch_arsenal_stats", "error": stats_error},
                    {"source": "pitch_arsenal_velocity", "error": velocity_error},
                ],
            },
        )

    velocities, velocity_player_name = _velocity_map(velocity_rows, player_id)
    player_rows = [row for row in stats_rows if _row_player_id(row) == player_id]

    pitches = [_normalize_pitch_row(row, velocities) for row in player_rows]
    pitches.sort(
        key=lambda pitch: (
            pitch.get("usage_pct") if pitch.get("usage_pct") is not None else -1,
            pitch.get("pitches") or 0,
        ),
        reverse=True,
    )

    player_name = velocity_player_name
    if player_name is None and player_rows:
        player_name = _player_name(player_rows[0])

    source_errors = []
    if stats_error:
        source_errors.append({"source": "pitch_arsenal_stats", "error": stats_error})
    if velocity_error:
        source_errors.append({"source": "pitch_arsenal_velocity", "error": velocity_error})

    components_available = {
        "pitch_type_outcomes": len(pitches) > 0,
        "pitch_velocity": len(velocities) > 0,
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
        "arsenal_summary": _arsenal_summary(pitches),
        "pitches": pitches,
        "data_quality": {
            "components_available": components_available,
            "missing_components": missing_components,
            "complete": len(missing_components) == 0,
            "source_errors": source_errors,
        },
        "modeling_notes": {
            "savant_rate_context": (
                "On Baseball Savant's Pitch Arsenal Stats leaderboard, Run Value and Whiff% "
                "are defined on a per-pitch basis; the other displayed outcome rates are on a "
                "per-plate-appearance basis."
            ),
            "highest_whiff_rule": (
                "Kyre Sports API only labels a highest-whiff pitch when that pitch has at least "
                "25 tracked pitches in the selected season."
            ),
            "use": (
                "Pitch-type metrics are model inputs, not standalone betting probabilities. "
                "Usage and effectiveness should later be matched against the opposing lineup's "
                "performance by pitch type."
            ),
        },
    }
