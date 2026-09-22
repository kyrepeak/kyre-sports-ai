import csv
import io
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-hitter-pitch-type"])

SAVANT_PITCH_STATS_URL = "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
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


def _row_player_id(row):
    return _to_int(
        _first_value(
            row,
            (
                "player_id",
                "batter",
                "batter_id",
                "hitter_id",
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
            "batter_name",
            "hitter_name",
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


def _normalize_pitch_row(row):
    pitch_type = str(_first_value(row, ("pitch_type",)) or "").upper() or None
    pitch_name = _first_value(row, ("pitch_name",))
    pitches = _to_int(_first_value(row, ("pitches",)))
    plate_appearances = _to_int(_first_value(row, ("pa", "plate_appearances")))

    ba = _to_float(_first_value(row, ("ba",)))
    xba = _to_float(_first_value(row, ("est_ba", "xba")))
    slg = _to_float(_first_value(row, ("slg",)))
    xslg = _to_float(_first_value(row, ("est_slg", "xslg")))
    woba = _to_float(_first_value(row, ("woba",)))
    xwoba = _to_float(_first_value(row, ("est_woba", "xwoba")))

    return {
        "pitch_type": pitch_type,
        "pitch_name": pitch_name or PITCH_NAMES.get(pitch_type),
        "team": _first_value(row, ("team_name_alt", "team")),
        "run_value_per_100_pitches": _to_float(
            _first_value(row, ("run_value_per_100",))
        ),
        "run_value": _to_float(_first_value(row, ("run_value",))),
        "pitches_seen": pitches,
        "pitch_usage_seen_pct": _to_float(
            _first_value(row, ("pitch_usage", "usage"))
        ),
        "plate_appearances": plate_appearances,
        "batting_average": ba,
        "slugging": slg,
        "woba": woba,
        "whiff_pct": _to_float(
            _first_value(row, ("whiff_percent", "whiff_pct"))
        ),
        "strikeout_pct": _to_float(_first_value(row, ("k_percent", "k_pct"))),
        "put_away_pct": _to_float(
            _first_value(row, ("put_away", "put_away_pct"))
        ),
        "expected_batting_average": xba,
        "expected_slugging": xslg,
        "expected_woba": xwoba,
        "hard_hit_pct": _to_float(
            _first_value(row, ("hard_hit_percent", "hard_hit_pct"))
        ),
        "ba_minus_xba": _round_or_none(
            ba - xba if ba is not None and xba is not None else None
        ),
        "slg_minus_xslg": _round_or_none(
            slg - xslg if slg is not None and xslg is not None else None
        ),
        "woba_minus_xwoba": _round_or_none(
            woba - xwoba if woba is not None and xwoba is not None else None
        ),
        "sample_size_label": _sample_label(pitches, plate_appearances),
    }


def _summary_item(pitch, metric_name):
    if pitch is None:
        return None
    return {
        "pitch_type": pitch.get("pitch_type"),
        "pitch_name": pitch.get("pitch_name"),
        metric_name: pitch.get(metric_name),
        "pitches_seen": pitch.get("pitches_seen"),
        "plate_appearances": pitch.get("plate_appearances"),
        "sample_size_label": pitch.get("sample_size_label"),
    }


def _hitter_summary(pitches):
    if not pitches:
        return {
            "pitch_types_available": 0,
            "total_tracked_pitches_seen": 0,
            "highest_run_value_pitch": None,
            "lowest_run_value_pitch": None,
            "highest_whiff_pitch_faced": None,
            "highest_expected_woba_pitch": None,
            "minimum_pitches_for_highlight": 25,
        }

    eligible = [pitch for pitch in pitches if (pitch.get("pitches_seen") or 0) >= 25]

    rv_candidates = [
        pitch for pitch in eligible if pitch.get("run_value_per_100_pitches") is not None
    ]
    whiff_candidates = [
        pitch for pitch in eligible if pitch.get("whiff_pct") is not None
    ]
    xwoba_candidates = [
        pitch for pitch in eligible if pitch.get("expected_woba") is not None
    ]

    highest_rv = (
        max(rv_candidates, key=lambda pitch: pitch.get("run_value_per_100_pitches"))
        if rv_candidates
        else None
    )
    lowest_rv = (
        min(rv_candidates, key=lambda pitch: pitch.get("run_value_per_100_pitches"))
        if rv_candidates
        else None
    )
    highest_whiff = (
        max(whiff_candidates, key=lambda pitch: pitch.get("whiff_pct"))
        if whiff_candidates
        else None
    )
    highest_xwoba = (
        max(xwoba_candidates, key=lambda pitch: pitch.get("expected_woba"))
        if xwoba_candidates
        else None
    )

    return {
        "pitch_types_available": len(pitches),
        "total_tracked_pitches_seen": sum(pitch.get("pitches_seen") or 0 for pitch in pitches),
        "highest_run_value_pitch": _summary_item(
            highest_rv,
            "run_value_per_100_pitches",
        ),
        "lowest_run_value_pitch": _summary_item(
            lowest_rv,
            "run_value_per_100_pitches",
        ),
        "highest_whiff_pitch_faced": _summary_item(
            highest_whiff,
            "whiff_pct",
        ),
        "highest_expected_woba_pitch": _summary_item(
            highest_xwoba,
            "expected_woba",
        ),
        "minimum_pitches_for_highlight": 25,
    }


@router.get("/players/{player_id}/hitter-pitch-type")
def get_mlb_hitter_pitch_type_performance(
    player_id: int,
    season: int | None = Query(
        default=None,
        ge=2015,
        le=2100,
        description="Statcast season year. Defaults to the current Arizona calendar year.",
    ),
):
    target_season = season or datetime.now(ARIZONA_TZ).year

    rows, source_error = _fetch_csv_rows(
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

    if source_error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Baseball Savant hitter pitch-type source is unavailable.",
                "source_error": source_error,
            },
        )

    player_rows = [row for row in rows if _row_player_id(row) == player_id]
    pitches = [_normalize_pitch_row(row) for row in player_rows]
    pitches.sort(
        key=lambda pitch: (
            pitch.get("pitches_seen") or 0,
            pitch.get("plate_appearances") or 0,
        ),
        reverse=True,
    )

    player_name = _player_name(player_rows[0]) if player_rows else None

    return {
        "source": "Baseball Savant / MLB Statcast",
        "calculated_by": "Kyre Sports API",
        "player_id": player_id,
        "player_name": player_name,
        "season": target_season,
        "hitter_summary": _hitter_summary(pitches),
        "pitches": pitches,
        "data_quality": {
            "pitch_type_performance_available": len(pitches) > 0,
            "pitch_types_available": len(pitches),
            "complete": len(pitches) > 0,
            "source_error": None,
        },
        "modeling_notes": {
            "savant_rate_context": (
                "On Baseball Savant's Pitch Arsenal Stats leaderboard, Run Value and Whiff% "
                "are defined on a per-pitch basis; the other displayed outcome rates are on a "
                "per-plate-appearance basis."
            ),
            "highlight_rule": (
                "Kyre Sports API requires at least 25 tracked pitches of a pitch type before "
                "using it in best/worst or whiff-based summary highlights."
            ),
            "interpretation": (
                "Higher batter Run Value/100 generally describes stronger results against that "
                "pitch type; higher Whiff% describes more swing-and-miss. These remain descriptive "
                "inputs and are not standalone betting probabilities."
            ),
        },
    }
