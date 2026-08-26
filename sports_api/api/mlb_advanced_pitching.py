import csv
import io
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-advanced-pitching"])

SAVANT_STATCAST_URL = "https://baseballsavant.mlb.com/leaderboard/statcast"
SAVANT_EXPECTED_URL = "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
SAVANT_ARSENALS_URL = "https://baseballsavant.mlb.com/leaderboard/pitch-arsenals"
ARIZONA_TZ = ZoneInfo("America/Phoenix")

SAVANT_HEADERS = {
    "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.8",
    "User-Agent": "KyreSportsAPI/0.1 (sports analytics application)",
}

PITCH_TYPES = {
    "four_seam_fastball": ("ff", "4seamer", "4seam", "fourseam", "fourseamer"),
    "sinker": ("si", "sinker"),
    "cutter": ("fc", "cutter"),
    "slider": ("sl", "slider"),
    "changeup": ("ch", "changeup"),
    "curveball": ("cu", "curve", "curveball"),
    "splitter": ("fs", "splitter", "splitfinger"),
    "sweeper": ("st", "sweeper"),
    "slurve": ("sv", "slurve"),
}


def _to_float(value):
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    number = _to_float(value)
    if number is None:
        return None
    return int(number)


def _round_or_none(value, digits=3):
    if value is None:
        return None
    return round(value, digits)


def _normalized_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _normalized_row(row):
    return {_normalized_key(key): value for key, value in (row or {}).items()}


def _first_value(row, aliases):
    normalized = _normalized_row(row)
    for alias in aliases:
        value = normalized.get(_normalized_key(alias))
        if value not in (None, ""):
            return value
    return None


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
    value = _first_value(
        row,
        (
            "player_id",
            "pitcher_id",
            "pitcherid",
            "mlbam_id",
            "mlbamid",
        ),
    )
    return _to_int(value)


def _find_player_row(rows, player_id: int):
    for row in rows:
        if _row_player_id(row) == player_id:
            return row
    return None


def _player_name(row):
    return _first_value(
        row,
        (
            "last_name, first_name",
            "last_name_first_name",
            "player_name",
            "pitcher_name",
            "name",
        ),
    )


def _normalize_contact_allowed(row):
    if not row:
        return None

    return {
        "player_id": _row_player_id(row),
        "player_name": _player_name(row),
        "batted_ball_events_allowed": _to_int(_first_value(row, ("attempts", "bbe"))),
        "avg_launch_angle_allowed_deg": _to_float(_first_value(row, ("avg_hit_angle",))),
        "sweet_spot_allowed_pct": _to_float(
            _first_value(row, ("anglesweetspotpercent", "sweet_spot_percent"))
        ),
        "max_exit_velocity_allowed_mph": _to_float(
            _first_value(row, ("max_hit_speed", "exit_velocity_max"))
        ),
        "avg_exit_velocity_allowed_mph": _to_float(
            _first_value(row, ("avg_hit_speed", "exit_velocity_avg"))
        ),
        "ev50_allowed_mph": _to_float(_first_value(row, ("ev50",))),
        "fly_ball_line_drive_ev_allowed_mph": _to_float(_first_value(row, ("fbld",))),
        "ground_ball_ev_allowed_mph": _to_float(_first_value(row, ("gb",))),
        "max_distance_allowed_ft": _to_float(_first_value(row, ("max_distance",))),
        "avg_distance_allowed_ft": _to_float(_first_value(row, ("avg_distance",))),
        "hard_hit_95plus_allowed_count": _to_int(
            _first_value(row, ("ev95plus", "hard_hit_ct"))
        ),
        "hard_hit_allowed_pct": _to_float(
            _first_value(row, ("ev95percent", "hard_hit_percent"))
        ),
        "barrels_allowed": _to_int(_first_value(row, ("barrels",))),
        "barrel_per_bbe_allowed_pct": _to_float(
            _first_value(row, ("brl_percent", "barrel_batted_rate"))
        ),
        "barrel_per_pa_allowed_pct": _to_float(
            _first_value(row, ("brl_pa", "barrel_pa"))
        ),
    }


def _normalize_expected_allowed(row):
    if not row:
        return None

    ba = _to_float(_first_value(row, ("ba",)))
    xba = _to_float(_first_value(row, ("est_ba", "xba")))
    slg = _to_float(_first_value(row, ("slg",)))
    xslg = _to_float(_first_value(row, ("est_slg", "xslg")))
    woba = _to_float(_first_value(row, ("woba",)))
    xwoba = _to_float(_first_value(row, ("est_woba", "xwoba")))
    era = _to_float(_first_value(row, ("era",)))
    xera = _to_float(_first_value(row, ("xera", "est_era", "expected_era")))

    return {
        "player_id": _row_player_id(row),
        "player_name": _player_name(row),
        "season": _to_int(_first_value(row, ("year", "season"))),
        "plate_appearances_faced": _to_int(_first_value(row, ("pa",))),
        "balls_in_play_allowed": _to_int(_first_value(row, ("bip",))),
        "batting_average_allowed": ba,
        "expected_batting_average_allowed": xba,
        "ba_allowed_minus_xba": _round_or_none(
            ba - xba if ba is not None and xba is not None else None
        ),
        "slugging_allowed": slg,
        "expected_slugging_allowed": xslg,
        "slg_allowed_minus_xslg": _round_or_none(
            slg - xslg if slg is not None and xslg is not None else None
        ),
        "woba_allowed": woba,
        "expected_woba_allowed": xwoba,
        "woba_allowed_minus_xwoba": _round_or_none(
            woba - xwoba if woba is not None and xwoba is not None else None
        ),
        "era": era,
        "expected_era": xera,
        "era_minus_xera": _round_or_none(
            era - xera if era is not None and xera is not None else None
        ),
    }


def _pitch_metric_value(row, aliases):
    return _to_float(_first_value(row, aliases))


def _normalize_arsenal(row, metric_name: str, unit: str):
    if not row:
        return None

    pitches = {}
    for pitch_name, aliases in PITCH_TYPES.items():
        expanded_aliases = list(aliases)
        for alias in aliases:
            expanded_aliases.extend(
                (
                    f"{alias}_{metric_name}",
                    f"{alias}{metric_name}",
                )
            )
        value = _pitch_metric_value(row, expanded_aliases)
        if value is not None:
            pitches[pitch_name] = value

    return {
        "player_id": _row_player_id(row),
        "player_name": _player_name(row),
        "metric": metric_name,
        "unit": unit,
        "pitches": pitches,
        "pitch_types_available": len(pitches),
    }


def _sample_label(contact_allowed, expected_allowed):
    bbe = (contact_allowed or {}).get("batted_ball_events_allowed") or 0
    pa = (expected_allowed or {}).get("plate_appearances_faced") or 0
    sample = max(bbe, pa)

    if sample <= 0:
        return "none"
    if sample < 25:
        return "very_small"
    if sample < 75:
        return "small"
    if sample < 150:
        return "moderate"
    return "large"


@router.get("/players/{player_id}/advanced-pitching")
def get_mlb_advanced_pitching(
    player_id: int,
    season: int | None = Query(
        default=None,
        ge=2015,
        le=2100,
        description="Statcast season year. Defaults to the current Arizona calendar year.",
    ),
):
    target_season = season or datetime.now(ARIZONA_TZ).year

    contact_rows, contact_error = _fetch_csv_rows(
        SAVANT_STATCAST_URL,
        {
            "type": "pitcher",
            "year": target_season,
            "position": "",
            "team": "",
            "min": 1,
            "csv": "true",
        },
    )

    expected_rows, expected_error = _fetch_csv_rows(
        SAVANT_EXPECTED_URL,
        {
            "type": "pitcher",
            "year": target_season,
            "position": "",
            "team": "",
            "filterType": "pa",
            "min": 1,
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

    spin_rows, spin_error = _fetch_csv_rows(
        SAVANT_ARSENALS_URL,
        {
            "year": target_season,
            "type": "avg_spin",
            "min": 1,
            "csv": "true",
        },
    )

    contact_allowed = _normalize_contact_allowed(_find_player_row(contact_rows, player_id))
    expected_allowed = _normalize_expected_allowed(_find_player_row(expected_rows, player_id))
    velocity_arsenal = _normalize_arsenal(
        _find_player_row(velocity_rows, player_id),
        "average_velocity",
        "mph",
    )
    spin_arsenal = _normalize_arsenal(
        _find_player_row(spin_rows, player_id),
        "average_spin",
        "rpm",
    )

    source_errors = []
    for source, error in (
        ("statcast_contact_allowed", contact_error),
        ("expected_statistics_allowed", expected_error),
        ("pitch_arsenal_velocity", velocity_error),
        ("pitch_arsenal_spin", spin_error),
    ):
        if error:
            source_errors.append({"source": source, "error": error})

    if contact_error and expected_error and velocity_error and spin_error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Baseball Savant advanced pitching sources are unavailable.",
                "source_errors": source_errors,
            },
        )

    components_available = {
        "contact_quality_allowed": contact_allowed is not None,
        "expected_statistics_allowed": expected_allowed is not None,
        "pitch_arsenal_velocity": velocity_arsenal is not None,
        "pitch_arsenal_spin": spin_arsenal is not None,
    }
    missing_components = [
        name for name, available in components_available.items() if not available
    ]

    player_name = None
    for component in (contact_allowed, expected_allowed, velocity_arsenal, spin_arsenal):
        if component and component.get("player_name"):
            player_name = component.get("player_name")
            break

    return {
        "source": "Baseball Savant / MLB Statcast",
        "calculated_by": "Kyre Sports API",
        "player_id": player_id,
        "player_name": player_name,
        "season": target_season,
        "contact_quality_allowed": contact_allowed,
        "expected_statistics_allowed": expected_allowed,
        "pitch_arsenal": {
            "average_velocity": velocity_arsenal,
            "average_spin": spin_arsenal,
        },
        "data_quality": {
            "components_available": components_available,
            "missing_components": missing_components,
            "sample_size_label": _sample_label(contact_allowed, expected_allowed),
            "complete": len(missing_components) == 0,
            "source_errors": source_errors,
        },
        "modeling_notes": {
            "hard_hit_definition": "Batted ball with exit velocity of at least 95 mph.",
            "ev50_pitcher_definition": (
                "For pitchers, EV50 is the average of the softest 50% of batted balls allowed."
            ),
            "xera_definition": (
                "xERA is Baseball Savant's xwOBA translated to the ERA scale. "
                "Kyre Sports API does not invent xERA when the source does not provide it."
            ),
            "use": (
                "These are descriptive/model-input metrics, not standalone betting probabilities. "
                "Small samples and partial Savant availability should receive reduced model weight."
            ),
        },
    }
