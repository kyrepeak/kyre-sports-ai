import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-advanced-hitting"])

SAVANT_STATCAST_URL = "https://baseballsavant.mlb.com/leaderboard/statcast"
SAVANT_EXPECTED_URL = "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
ARIZONA_TZ = ZoneInfo("America/Phoenix")

SAVANT_HEADERS = {
    "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.8",
    "User-Agent": "KyreSportsAPI/0.1 (sports analytics application)",
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


def _find_player_row(rows, player_id: int):
    for row in rows:
        try:
            row_player_id = int(float(str(row.get("player_id") or "")))
        except (TypeError, ValueError):
            continue
        if row_player_id == player_id:
            return row
    return None


def _normalize_contact_quality(row):
    if not row:
        return None

    return {
        "player_id": _to_int(row.get("player_id")),
        "player_name": row.get("last_name, first_name"),
        "batted_ball_events": _to_int(row.get("attempts")),
        "avg_launch_angle_deg": _to_float(row.get("avg_hit_angle")),
        "sweet_spot_pct": _to_float(row.get("anglesweetspotpercent")),
        "max_exit_velocity_mph": _to_float(row.get("max_hit_speed")),
        "avg_exit_velocity_mph": _to_float(row.get("avg_hit_speed")),
        "ev50_mph": _to_float(row.get("ev50")),
        "fly_ball_line_drive_ev_mph": _to_float(row.get("fbld")),
        "ground_ball_ev_mph": _to_float(row.get("gb")),
        "max_distance_ft": _to_float(row.get("max_distance")),
        "avg_distance_ft": _to_float(row.get("avg_distance")),
        "avg_home_run_distance_ft": _to_float(row.get("avg_hr_distance")),
        "hard_hit_95plus_count": _to_int(row.get("ev95plus")),
        "hard_hit_pct": _to_float(row.get("ev95percent")),
        "barrels": _to_int(row.get("barrels")),
        "barrel_per_bbe_pct": _to_float(row.get("brl_percent")),
        "barrel_per_pa_pct": _to_float(row.get("brl_pa")),
    }


def _normalize_expected_stats(row):
    if not row:
        return None

    ba = _to_float(row.get("ba"))
    xba = _to_float(row.get("est_ba"))
    slg = _to_float(row.get("slg"))
    xslg = _to_float(row.get("est_slg"))
    woba = _to_float(row.get("woba"))
    xwoba = _to_float(row.get("est_woba"))

    return {
        "player_id": _to_int(row.get("player_id")),
        "player_name": row.get("last_name, first_name"),
        "season": _to_int(row.get("year")),
        "plate_appearances": _to_int(row.get("pa")),
        "balls_in_play": _to_int(row.get("bip")),
        "batting_average": ba,
        "expected_batting_average": xba,
        "ba_minus_xba": _round_or_none(ba - xba if ba is not None and xba is not None else None),
        "slugging": slg,
        "expected_slugging": xslg,
        "slg_minus_xslg": _round_or_none(slg - xslg if slg is not None and xslg is not None else None),
        "woba": woba,
        "expected_woba": xwoba,
        "woba_minus_xwoba": _round_or_none(
            woba - xwoba if woba is not None and xwoba is not None else None
        ),
    }


def _sample_label(contact_quality, expected_stats):
    bbe = (contact_quality or {}).get("batted_ball_events") or 0
    pa = (expected_stats or {}).get("plate_appearances") or 0

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


@router.get("/players/{player_id}/advanced-hitting")
def get_mlb_advanced_hitting(
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
            "type": "batter",
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
            "type": "batter",
            "year": target_season,
            "position": "",
            "team": "",
            "filterType": "pa",
            "min": 1,
            "csv": "true",
        },
    )

    contact_row = _find_player_row(contact_rows, player_id)
    expected_row = _find_player_row(expected_rows, player_id)

    contact_quality = _normalize_contact_quality(contact_row)
    expected_stats = _normalize_expected_stats(expected_row)

    source_errors = []
    if contact_error:
        source_errors.append({"source": "statcast_contact_quality", "error": contact_error})
    if expected_error:
        source_errors.append({"source": "expected_statistics", "error": expected_error})

    if contact_error and expected_error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Baseball Savant advanced hitting sources are unavailable.",
                "source_errors": source_errors,
            },
        )

    components_available = {
        "contact_quality": contact_quality is not None,
        "expected_statistics": expected_stats is not None,
    }

    missing_components = [
        name for name, available in components_available.items() if not available
    ]

    player_name = None
    if contact_quality:
        player_name = contact_quality.get("player_name")
    elif expected_stats:
        player_name = expected_stats.get("player_name")

    return {
        "source": "Baseball Savant / MLB Statcast",
        "calculated_by": "Kyre Sports API",
        "player_id": player_id,
        "player_name": player_name,
        "season": target_season,
        "contact_quality": contact_quality,
        "expected_statistics": expected_stats,
        "data_quality": {
            "components_available": components_available,
            "missing_components": missing_components,
            "sample_size_label": _sample_label(contact_quality, expected_stats),
            "complete": len(missing_components) == 0,
            "source_errors": source_errors,
        },
        "modeling_notes": {
            "hard_hit_definition": "Batted ball with exit velocity of at least 95 mph.",
            "expected_stats": (
                "xBA, xSLG, and xwOBA describe expected outcomes from Statcast contact quality "
                "rather than simply copying actual results."
            ),
            "use": (
                "These metrics are model inputs, not standalone betting probabilities. "
                "Small samples should receive reduced weight."
            ),
        },
    }
