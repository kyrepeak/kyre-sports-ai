import json
import re
from copy import deepcopy

import httpx
from fastapi import APIRouter, HTTPException, Query

from sports_api.api.mlb_batted_ball_context import get_mlb_hit_batted_ball_context

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-hit-park-factor-context"])

SAVANT_PARK_FACTORS_URL = (
    "https://baseballsavant.mlb.com/leaderboard/statcast-park-factors"
)
SAVANT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
    "User-Agent": "KyreSportsAPI/0.1 (sports analytics application)",
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
    if text in {"", "--", "null", "None"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    number = _to_float(value)
    return int(number) if number is not None else None


def _extract_embedded_json(text: str):
    decoder = json.JSONDecoder()

    for match in re.finditer(r"\bdata\s*=\s*", text):
        tail = text[match.end():].lstrip()
        if not tail or tail[0] not in "[{":
            continue

        try:
            payload, _ = decoder.raw_decode(tail)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
            return payload

        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                    return value

    return []


def _fetch_park_factor_rows(season: int, bat_side: str, rolling_years: int):
    params = {
        "type": "year",
        "year": season,
        "batSide": bat_side,
        "stat": "index_wOBA",
        "condition": "All",
        "rolling": rolling_years,
        "parks": "mlb",
    }

    try:
        response = httpx.get(
            SAVANT_PARK_FACTORS_URL,
            params=params,
            headers=SAVANT_HEADERS,
            timeout=25.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return [], str(exc)

    rows = _extract_embedded_json(response.text)
    if not rows:
        return [], "embedded_park_factor_json_not_found"

    return rows, None


def _venue_id(row):
    return _to_int(
        _first_value(
            row,
            (
                "venue_id",
                "venueId",
                "stadium_id",
                "stadiumId",
                "park_id",
            ),
        )
    )


def _venue_name(row):
    return _first_value(
        row,
        (
            "venue_name",
            "venueName",
            "stadium_name",
            "park_name",
            "venue",
        ),
    )


def _normalize_name(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower()) or None


def _find_venue_row(rows, venue_id, venue_name):
    if isinstance(venue_id, int):
        by_id = next((row for row in rows if _venue_id(row) == venue_id), None)
        if by_id is not None:
            return by_id

    target = _normalize_name(venue_name)
    if target is None:
        return None

    return next(
        (
            row
            for row in rows
            if _normalize_name(_venue_name(row)) == target
        ),
        None,
    )


def _index_metric(row, aliases):
    return _to_float(_first_value(row, aliases))


def _all_index_metrics(row):
    metrics = {}
    for key, value in (row or {}).items():
        normalized = str(key or "").lower()
        if not normalized.startswith("index_"):
            continue
        number = _to_float(value)
        if number is not None:
            metrics[normalized] = number
    return metrics


def _normalize_park_factor_row(row, bat_side, rolling_years):
    if not row:
        return None

    return {
        "venue_id": _venue_id(row),
        "venue_name": _venue_name(row),
        "team": _first_value(row, ("team_name", "team", "club")),
        "season": _to_int(_first_value(row, ("year", "season"))),
        "bat_side": bat_side or "Both",
        "rolling_years": rolling_years,
        "indices": {
            "woba": _index_metric(row, ("index_woba",)),
            "woba_on_contact": _index_metric(
                row,
                ("index_wobacon", "index_woba_con", "index_wobaconcontact"),
            ),
            "batting_average_on_contact": _index_metric(
                row,
                ("index_bacon", "index_ba_con", "index_battingaverageoncontact"),
            ),
            "hit": _index_metric(row, ("index_hit", "index_hits")),
            "single": _index_metric(row, ("index_1b", "index_single")),
            "double": _index_metric(row, ("index_2b", "index_double")),
            "triple": _index_metric(row, ("index_3b", "index_triple")),
            "home_run": _index_metric(row, ("index_hr", "index_homerun")),
            "hard_hit": _index_metric(row, ("index_hardhit", "index_hard_hit")),
            "walk": _index_metric(row, ("index_bb", "index_walk")),
            "strikeout": _index_metric(row, ("index_so", "index_k", "index_strikeout")),
        },
        "raw_index_metrics": _all_index_metrics(row),
    }


def _effective_batter_side(hitter):
    player = hitter.get("player") or {}
    listed = player.get("bat_side")

    if listed in {"L", "R"}:
        return listed

    if listed == "S":
        starter_hand = (
            hitter.get("arsenal_matchup", {})
            .get("opposing_starter", {})
            .get("pitch_hand")
        )
        if starter_hand == "R":
            return "L"
        if starter_hand == "L":
            return "R"

    return None


def _directional_geometry(hitter, park):
    side = _effective_batter_side(hitter)
    field = (park or {}).get("field") or {}
    feature_vector = hitter.get("feature_vector") or {}

    if side == "R":
        pull_line = field.get("left_line_ft")
        pull_gap = field.get("left_center_ft")
        oppo_gap = field.get("right_center_ft")
        oppo_line = field.get("right_line_ft")
        pull_field = "left"
        opposite_field = "right"
    elif side == "L":
        pull_line = field.get("right_line_ft")
        pull_gap = field.get("right_center_ft")
        oppo_gap = field.get("left_center_ft")
        oppo_line = field.get("left_line_ft")
        pull_field = "right"
        opposite_field = "left"
    else:
        pull_line = pull_gap = oppo_gap = oppo_line = None
        pull_field = opposite_field = None

    return {
        "effective_batter_side": side,
        "pull_field": pull_field,
        "opposite_field": opposite_field,
        "park_dimensions_ft": {
            "pull_line": pull_line,
            "pull_gap": pull_gap,
            "center": field.get("center_ft"),
            "opposite_gap": oppo_gap,
            "opposite_line": oppo_line,
        },
        "hitter_spray": {
            "pull_pct": feature_vector.get("pull_pct"),
            "straight_pct": feature_vector.get("straight_pct"),
            "opposite_field_pct": feature_vector.get("opposite_field_pct"),
            "pulled_air_pct": feature_vector.get("pulled_air_pct"),
            "straight_air_pct": feature_vector.get("straight_air_pct"),
            "opposite_field_air_pct": feature_vector.get("opposite_field_air_pct"),
        },
        "source_note": (
            "Directional geometry combines MLB venue dimensions already carried by the game "
            "environment layer with the hitter's Savant spray profile. It is not an official "
            "Statcast directional park-factor index."
        ),
    }


def _selected_side_factor(side, park_factors):
    if side == "R":
        return park_factors.get("right_handed")
    if side == "L":
        return park_factors.get("left_handed")
    return park_factors.get("both")


def _attach_park_context(team_block, park_factors, park):
    team = deepcopy(team_block)
    team["statcast_park_factors"] = park_factors

    both_available = park_factors.get("both") is not None
    handed_available = {
        "R": park_factors.get("right_handed") is not None,
        "L": park_factors.get("left_handed") is not None,
    }

    hitters_with_side_factor = 0
    hitters_with_directional_geometry = 0

    for hitter in team.get("hitters", []):
        side = _effective_batter_side(hitter)
        selected = _selected_side_factor(side, park_factors)
        geometry = _directional_geometry(hitter, park)

        if selected is not None:
            hitters_with_side_factor += 1

        dimensions = geometry.get("park_dimensions_ft") or {}
        if any(value is not None for value in dimensions.values()):
            hitters_with_directional_geometry += 1

        context = {
            "effective_batter_side": side,
            "overall_park_factor": park_factors.get("both"),
            "selected_handedness_park_factor": selected,
            "directional_geometry": geometry,
        }
        hitter["park_factor_context"] = context

        indices = (selected or park_factors.get("both") or {}).get("indices") or {}
        feature_vector = hitter.setdefault("feature_vector", {})
        feature_vector.update(
            {
                "park_factor_batter_side": side,
                "park_factor_woba": indices.get("woba"),
                "park_factor_woba_on_contact": indices.get("woba_on_contact"),
                "park_factor_batting_average_on_contact": indices.get(
                    "batting_average_on_contact"
                ),
                "park_factor_hit": indices.get("hit"),
                "park_factor_single": indices.get("single"),
                "park_factor_double": indices.get("double"),
                "park_factor_triple": indices.get("triple"),
                "park_factor_home_run": indices.get("home_run"),
                "park_factor_hard_hit": indices.get("hard_hit"),
                "park_pull_line_ft": dimensions.get("pull_line"),
                "park_pull_gap_ft": dimensions.get("pull_gap"),
                "park_center_ft": dimensions.get("center"),
                "park_opposite_gap_ft": dimensions.get("opposite_gap"),
                "park_opposite_line_ft": dimensions.get("opposite_line"),
            }
        )

        readiness = hitter.setdefault("feature_readiness", {})
        readiness["park_factor_components"] = {
            "overall_statcast_park_factor": both_available,
            "handedness_statcast_park_factor": selected is not None,
            "directional_park_geometry": any(
                value is not None for value in dimensions.values()
            ),
        }
        readiness["park_factor_missing_components"] = [
            name
            for name, available in readiness["park_factor_components"].items()
            if not available
        ]
        readiness["complete_park_factor_context"] = all(
            readiness["park_factor_components"].values()
        )

    summary = team.setdefault("summary", {})
    lineup_count = len(team.get("hitters", []))
    summary.update(
        {
            "statcast_park_factor_available": both_available,
            "right_handed_park_factor_available": handed_available["R"],
            "left_handed_park_factor_available": handed_available["L"],
            "hitters_with_selected_handedness_park_factor": hitters_with_side_factor,
            "hitters_with_directional_park_geometry": hitters_with_directional_geometry,
            "park_factor_board_ready": (
                lineup_count >= 9
                and both_available
                and hitters_with_side_factor >= 7
            ),
        }
    )

    return team


@router.get("/games/{game_pk}/hit-park-factor-context")
def get_mlb_hit_park_factor_context(
    game_pk: int,
    season: int | None = Query(
        default=None,
        ge=2015,
        le=2100,
        description=(
            "Season used for Statcast park factors and the underlying hitter feature layers. "
            "Defaults to the game's official season."
        ),
    ),
    bullpen_lookback_days: int = Query(
        default=7,
        ge=3,
        le=14,
        description="Passed through to the underlying environment/bullpen feature layers.",
    ),
    park_rolling_years: int = Query(
        default=3,
        description=(
            "Statcast Park Factors rolling window. Supported values are 1 or 3. "
            "Three-year rolling includes the selected year and two previous seasons."
        ),
    ),
):
    if park_rolling_years not in {1, 3}:
        raise HTTPException(
            status_code=400,
            detail="park_rolling_years must be either 1 or 3.",
        )

    base = get_mlb_hit_batted_ball_context(
        game_pk=game_pk,
        season=season,
        bullpen_lookback_days=bullpen_lookback_days,
    )
    target_season = base.get("season")
    source_errors = list(base.get("data_quality", {}).get("source_errors") or [])

    venue = base.get("venue") or {}
    game_environment = base.get("game_environment") or {}
    park = game_environment.get("park") or {}
    venue_id = venue.get("venue_id") or park.get("venue_id")
    venue_name = venue.get("name") or park.get("name")

    boards = {}
    for key, bat_side in (
        ("both", ""),
        ("right_handed", "R"),
        ("left_handed", "L"),
    ):
        rows, error = _fetch_park_factor_rows(
            target_season,
            bat_side,
            park_rolling_years,
        )
        if error:
            source_errors.append(
                {
                    "source": "savant_statcast_park_factors",
                    "bat_side": bat_side or "Both",
                    "error": error,
                }
            )

        boards[key] = _normalize_park_factor_row(
            _find_venue_row(rows, venue_id, venue_name),
            bat_side,
            park_rolling_years,
        )

    away = _attach_park_context(base.get("away", {}), boards, park)
    home = _attach_park_context(base.get("home", {}), boards, park)

    away_ready = away.get("summary", {}).get("park_factor_board_ready") is True
    home_ready = home.get("summary", {}).get("park_factor_board_ready") is True

    return {
        "sources": [
            "MLB Stats API",
            "Baseball Savant / MLB Statcast",
            "National Weather Service",
        ],
        "calculated_by": "Kyre Sports API",
        "feature_profile_version": "hit-park-factor-context v0.1",
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
        "statcast_park_factors": {
            "scale": "100 = league average for the selected metric/context",
            "rolling_years": park_rolling_years,
            **boards,
        },
        "readiness": {
            **(base.get("readiness") or {}),
            "away_park_factor_ready": away_ready,
            "home_park_factor_ready": home_ready,
            "both_park_factor_boards_ready": away_ready and home_ready,
        },
        "away": away,
        "home": home,
        "data_quality": {
            "source_errors": source_errors,
            "partial_data_allowed": True,
            "overall_park_factor_available": boards.get("both") is not None,
            "right_handed_park_factor_available": boards.get("right_handed") is not None,
            "left_handed_park_factor_available": boards.get("left_handed") is not None,
        },
        "modeling_notes": {
            "statcast_scale": (
                "Baseball Savant Statcast park factors use 100 as league average. A value above "
                "100 means the displayed event occurred more often in that park for comparable "
                "players; it is not a direct percentage adjustment to a hitter projection."
            ),
            "rolling_window": (
                "The default is Savant's three-year rolling context: the selected season plus the "
                "two previous seasons. One-year context can be requested explicitly."
            ),
            "handedness": (
                "Separate Both, RHB, and LHB park-factor boards are fetched. Switch hitters use "
                "their effective batting side against the identified opposing starter when possible."
            ),
            "directional_geometry": (
                "Pull/opposite-field wall distances are derived from the venue dimensions and the "
                "hitter's effective batting side, then paired with Savant spray rates. This geometry "
                "is intentionally labeled separately from official Statcast park-factor indices."
            ),
            "html_parser": (
                "The current Statcast Park Factors leaderboard embeds its data as JSON in the HTML "
                "rather than exposing the same CSV pattern used by many other Savant leaderboards."
            ),
            "no_probability": (
                "This remains a feature/context layer. Park indices and directional geometry are not "
                "yet converted into 1+ hit probability, expected hits, fair odds, EV, or Monte Carlo output."
            ),
        },
    }
