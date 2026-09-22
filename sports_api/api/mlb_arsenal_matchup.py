from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from sports_api.api.mlb_batter_pitcher import _effective_batter_side, _fetch_person
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

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-arsenal-matchup"])

ARIZONA_TZ = ZoneInfo("America/Phoenix")
MIN_TRACKED_PITCHES = 25


def _fetch_pitch_type_rows(player_id: int, season: int, player_type: str):
    rows, error = _fetch_csv_rows(
        SAVANT_PITCH_STATS_URL,
        {
            "type": player_type,
            "year": season,
            "team": "",
            "min": 1,
            "minPitches": 1,
            "csv": "true",
        },
    )

    if player_type == "pitcher":
        player_rows = [row for row in rows if _pitcher_row_player_id(row) == player_id]
        normalized = [_normalize_pitcher_pitch_row(row, {}) for row in player_rows]
    else:
        player_rows = [row for row in rows if _hitter_row_player_id(row) == player_id]
        normalized = [_normalize_hitter_pitch_row(row) for row in player_rows]

    normalized = [row for row in normalized if row.get("pitch_type")]
    return normalized, error


def _by_pitch_type(rows):
    return {
        row.get("pitch_type"): row
        for row in rows
        if row.get("pitch_type")
    }


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _usage_value(pitch):
    value = _safe_float(pitch.get("usage_pct"))
    if value is not None and value > 0:
        return value

    count = _safe_float(pitch.get("pitches"))
    if count is not None and count > 0:
        return count

    return 0.0


def _coverage(pitcher_pitches, included_pitch_types):
    total_weight = sum(_usage_value(pitch) for pitch in pitcher_pitches)
    included_weight = sum(
        _usage_value(pitch)
        for pitch in pitcher_pitches
        if pitch.get("pitch_type") in included_pitch_types
    )

    if total_weight <= 0:
        return None

    return round((included_weight / total_weight) * 100.0, 2)


def _weighted_average(matchups, hitter_field=None, pitcher_field=None):
    weighted_sum = 0.0
    total_weight = 0.0

    for matchup in matchups:
        weight = _safe_float(matchup.get("normalized_pitcher_weight"))
        if weight is None or weight <= 0:
            continue

        if hitter_field is not None:
            value = _safe_float(matchup.get("hitter", {}).get(hitter_field))
        else:
            value = _safe_float(matchup.get("pitcher", {}).get(pitcher_field))

        if value is None:
            continue

        weighted_sum += value * weight
        total_weight += weight

    if total_weight <= 0:
        return None

    return round(weighted_sum / total_weight, 4)


def _build_pitch_matchups(pitcher_pitches, hitter_pitches):
    pitcher_map = _by_pitch_type(pitcher_pitches)
    hitter_map = _by_pitch_type(hitter_pitches)
    overlapping_types = [
        pitch_type
        for pitch_type in pitcher_map
        if pitch_type in hitter_map
    ]

    overlap_weight_total = sum(
        _usage_value(pitcher_map[pitch_type])
        for pitch_type in overlapping_types
    )

    matchups = []
    for pitch_type in overlapping_types:
        pitcher = pitcher_map[pitch_type]
        hitter = hitter_map[pitch_type]
        pitcher_weight = _usage_value(pitcher)
        normalized_weight = (
            pitcher_weight / overlap_weight_total
            if overlap_weight_total > 0
            else None
        )

        pitcher_sample = pitcher.get("pitches") or 0
        hitter_sample = hitter.get("pitches_seen") or 0
        qualified = (
            pitcher_sample >= MIN_TRACKED_PITCHES
            and hitter_sample >= MIN_TRACKED_PITCHES
        )

        matchups.append(
            {
                "pitch_type": pitch_type,
                "pitch_name": pitcher.get("pitch_name") or hitter.get("pitch_name"),
                "pitcher_usage_raw": pitcher.get("usage_pct"),
                "normalized_pitcher_weight": (
                    round(normalized_weight, 6)
                    if normalized_weight is not None
                    else None
                ),
                "qualified_for_summary": qualified,
                "pitcher": {
                    "pitches": pitcher.get("pitches"),
                    "usage_pct": pitcher.get("usage_pct"),
                    "run_value_per_100_pitches": pitcher.get("run_value_per_100_pitches"),
                    "whiff_pct": pitcher.get("whiff_pct"),
                    "strikeout_pct": pitcher.get("strikeout_pct"),
                    "put_away_pct": pitcher.get("put_away_pct"),
                    "expected_batting_average_allowed": pitcher.get("expected_batting_average_allowed"),
                    "expected_slugging_allowed": pitcher.get("expected_slugging_allowed"),
                    "expected_woba_allowed": pitcher.get("expected_woba_allowed"),
                    "hard_hit_allowed_pct": pitcher.get("hard_hit_allowed_pct"),
                    "sample_size_label": pitcher.get("sample_size_label"),
                },
                "hitter": {
                    "pitches_seen": hitter.get("pitches_seen"),
                    "plate_appearances": hitter.get("plate_appearances"),
                    "run_value_per_100_pitches": hitter.get("run_value_per_100_pitches"),
                    "whiff_pct": hitter.get("whiff_pct"),
                    "strikeout_pct": hitter.get("strikeout_pct"),
                    "put_away_pct": hitter.get("put_away_pct"),
                    "expected_batting_average": hitter.get("expected_batting_average"),
                    "expected_slugging": hitter.get("expected_slugging"),
                    "expected_woba": hitter.get("expected_woba"),
                    "hard_hit_pct": hitter.get("hard_hit_pct"),
                    "sample_size_label": hitter.get("sample_size_label"),
                },
            }
        )

    matchups.sort(
        key=lambda matchup: (
            matchup.get("normalized_pitcher_weight") or 0,
            matchup.get("pitcher", {}).get("pitches") or 0,
        ),
        reverse=True,
    )
    return matchups


def _weighted_context(matchups):
    qualified = [
        matchup
        for matchup in matchups
        if matchup.get("qualified_for_summary") is True
    ]

    hitter_xwoba = _weighted_average(qualified, hitter_field="expected_woba")
    pitcher_xwoba = _weighted_average(
        qualified,
        pitcher_field="expected_woba_allowed",
    )

    xwoba_gap = None
    if hitter_xwoba is not None and pitcher_xwoba is not None:
        xwoba_gap = round(hitter_xwoba - pitcher_xwoba, 4)

    return {
        "qualified_pitch_types": len(qualified),
        "minimum_tracked_pitches_per_side": MIN_TRACKED_PITCHES,
        "weighted_hitter_expected_woba_vs_mix": hitter_xwoba,
        "weighted_pitcher_expected_woba_allowed_by_mix": pitcher_xwoba,
        "weighted_xwoba_context_gap": xwoba_gap,
        "weighted_hitter_whiff_pct_vs_mix": _weighted_average(
            qualified,
            hitter_field="whiff_pct",
        ),
        "weighted_pitcher_whiff_pct_by_mix": _weighted_average(
            qualified,
            pitcher_field="whiff_pct",
        ),
        "weighted_hitter_hard_hit_pct_vs_mix": _weighted_average(
            qualified,
            hitter_field="hard_hit_pct",
        ),
        "weighted_pitcher_hard_hit_allowed_pct_by_mix": _weighted_average(
            qualified,
            pitcher_field="hard_hit_allowed_pct",
        ),
        "weighted_hitter_run_value_per_100_vs_mix": _weighted_average(
            qualified,
            hitter_field="run_value_per_100_pitches",
        ),
        "weighted_pitcher_run_value_per_100_by_mix": _weighted_average(
            qualified,
            pitcher_field="run_value_per_100_pitches",
        ),
    }


@router.get("/matchups/batter/{batter_id}/pitcher/{pitcher_id}/arsenal")
def get_mlb_arsenal_matchup(
    batter_id: int,
    pitcher_id: int,
    season: int | None = Query(
        default=None,
        ge=2015,
        le=2100,
        description="Statcast season year. Defaults to the current Arizona calendar year.",
    ),
):
    if batter_id == pitcher_id:
        raise HTTPException(
            status_code=400,
            detail="Batter and pitcher must be different MLB player IDs.",
        )

    target_season = season or datetime.now(ARIZONA_TZ).year

    batter = _fetch_person(batter_id)
    pitcher = _fetch_person(pitcher_id)

    pitcher_pitches, pitcher_error = _fetch_pitch_type_rows(
        pitcher_id,
        target_season,
        "pitcher",
    )
    hitter_pitches, hitter_error = _fetch_pitch_type_rows(
        batter_id,
        target_season,
        "batter",
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
                "message": "Baseball Savant arsenal matchup source is unavailable.",
                "source_errors": source_errors,
            },
        )

    matchups = _build_pitch_matchups(pitcher_pitches, hitter_pitches)
    overlap_types = {matchup.get("pitch_type") for matchup in matchups}
    qualified_types = {
        matchup.get("pitch_type")
        for matchup in matchups
        if matchup.get("qualified_for_summary") is True
    }

    pitcher_hand = pitcher.get("pitch_hand")
    batter_hand = batter.get("bat_side")
    effective_batter_side = _effective_batter_side(batter_hand, pitcher_hand)

    components_available = {
        "pitcher_pitch_type_data": len(pitcher_pitches) > 0,
        "hitter_pitch_type_data": len(hitter_pitches) > 0,
        "overlapping_pitch_types": len(matchups) > 0,
        "qualified_overlap": len(qualified_types) > 0,
    }
    missing_components = [
        name for name, available in components_available.items() if not available
    ]

    return {
        "source": "Baseball Savant / MLB Statcast",
        "calculated_by": "Kyre Sports API",
        "season": target_season,
        "batter": {
            "player_id": batter.get("player_id"),
            "full_name": batter.get("full_name"),
            "bat_side": batter_hand,
            "effective_batter_side": effective_batter_side,
            "current_team_id": batter.get("current_team_id"),
            "current_team_name": batter.get("current_team_name"),
        },
        "pitcher": {
            "player_id": pitcher.get("player_id"),
            "full_name": pitcher.get("full_name"),
            "pitch_hand": pitcher_hand,
            "current_team_id": pitcher.get("current_team_id"),
            "current_team_name": pitcher.get("current_team_name"),
        },
        "overlap": {
            "pitcher_pitch_types": len(pitcher_pitches),
            "hitter_pitch_types": len(hitter_pitches),
            "overlapping_pitch_types": len(matchups),
            "qualified_overlapping_pitch_types": len(qualified_types),
            "pitcher_usage_coverage_pct": _coverage(pitcher_pitches, overlap_types),
            "qualified_pitcher_usage_coverage_pct": _coverage(
                pitcher_pitches,
                qualified_types,
            ),
        },
        "weighted_context": _weighted_context(matchups),
        "pitch_matchups": matchups,
        "data_quality": {
            "components_available": components_available,
            "missing_components": missing_components,
            "complete": len(missing_components) == 0,
            "source_errors": source_errors,
        },
        "modeling_notes": {
            "weighting": (
                "Pitch-type context is weighted by the pitcher's own usage mix. Usage is "
                "normalized internally, so fraction-vs-percent formatting does not change results."
            ),
            "qualified_overlap": (
                "Weighted summary fields use only pitch types with at least 25 tracked pitches "
                "for both the pitcher and hitter in the selected season."
            ),
            "xwoba_gap": (
                "The weighted xwOBA context gap is hitter expected wOBA versus the matched mix "
                "minus pitcher expected wOBA allowed for that mix. It is descriptive context, "
                "not a calibrated probability or standalone edge score."
            ),
            "use": (
                "This endpoint combines arsenal and hitter pitch-type performance. It does not "
                "yet include projected plate appearances, park/weather, bullpen, lineup position, "
                "or Monte Carlo betting probabilities."
            ),
        },
    }
