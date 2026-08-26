import re
from copy import deepcopy

from fastapi import APIRouter, Query

from sports_api.api.mlb_advanced_hitting import _fetch_csv_rows
from sports_api.api.mlb_hit_environment_context import get_mlb_hit_environment_context

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-hit-defense-context"])

SAVANT_OAA_URL = "https://baseballsavant.mlb.com/leaderboard/outs_above_average"

# Canonical labels are only used to reconcile MLB team names with Baseball
# Savant's shorter display names when a numeric team id is absent from the CSV.
TEAM_ALIASES = {
    "ari": {
        "arizona diamondbacks",
        "diamondbacks",
        "dbacks",
        "d-backs",
    },
    "atl": {"atlanta braves", "braves"},
    "bal": {"baltimore orioles", "orioles"},
    "bos": {"boston red sox", "red sox"},
    "chc": {"chicago cubs", "cubs"},
    "chw": {"chicago white sox", "white sox"},
    "cin": {"cincinnati reds", "reds"},
    "cle": {"cleveland guardians", "guardians"},
    "col": {"colorado rockies", "rockies"},
    "det": {"detroit tigers", "tigers"},
    "hou": {"houston astros", "astros"},
    "kc": {"kansas city royals", "royals"},
    "laa": {"los angeles angels", "angels"},
    "lad": {"los angeles dodgers", "dodgers"},
    "mia": {"miami marlins", "marlins"},
    "mil": {"milwaukee brewers", "brewers"},
    "min": {"minnesota twins", "twins"},
    "nym": {"new york mets", "mets"},
    "nyy": {"new york yankees", "yankees"},
    "ath": {
        "athletics",
        "oakland athletics",
        "as",
        "a's",
    },
    "phi": {"philadelphia phillies", "phillies"},
    "pit": {"pittsburgh pirates", "pirates"},
    "sd": {"san diego padres", "padres"},
    "sf": {"san francisco giants", "giants"},
    "sea": {"seattle mariners", "mariners"},
    "stl": {"st louis cardinals", "st. louis cardinals", "cardinals"},
    "tb": {"tampa bay rays", "rays"},
    "tex": {"texas rangers", "rangers"},
    "tor": {"toronto blue jays", "blue jays"},
    "wsh": {"washington nationals", "nationals"},
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


def _canonical_team_name(value):
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    compact = normalized.replace(" ", "")

    for code, aliases in TEAM_ALIASES.items():
        for alias in aliases:
            alias_normalized = re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip()
            if normalized == alias_normalized or compact == alias_normalized.replace(" ", ""):
                return code

    return compact or None


def _row_team_id(row):
    return _to_int(
        _first_value(
            row,
            (
                "team_id",
                "teamid",
                "mlb_team_id",
            ),
        )
    )


def _row_team_name(row):
    return _first_value(
        row,
        (
            "team_name",
            "team_name_alt",
            "team",
            "club",
            "name",
        ),
    )


def _find_team_row(rows, team_id, team_name):
    if isinstance(team_id, int):
        by_id = next((row for row in rows if _row_team_id(row) == team_id), None)
        if by_id is not None:
            return by_id

    target = _canonical_team_name(team_name)
    if target is None:
        return None

    return next(
        (
            row
            for row in rows
            if _canonical_team_name(_row_team_name(row)) == target
        ),
        None,
    )


def _normalize_oaa_row(row, position_group):
    if not row:
        return None

    success_rate = _to_float(
        _first_value(
            row,
            (
                "success_rate",
                "actual_success_rate",
                "successrate",
            ),
        )
    )
    estimated_success_rate = _to_float(
        _first_value(
            row,
            (
                "estimated_success_rate",
                "est_success_rate",
                "estimatedsuccessrate",
            ),
        )
    )
    success_rate_added = _to_float(
        _first_value(
            row,
            (
                "success_rate_added",
                "success_rate_diff",
                "successrateadded",
            ),
        )
    )

    if (
        success_rate_added is None
        and success_rate is not None
        and estimated_success_rate is not None
    ):
        success_rate_added = round(success_rate - estimated_success_rate, 3)

    return {
        "position_group": position_group,
        "team_id": _row_team_id(row),
        "team_name": _row_team_name(row),
        "season": _to_int(_first_value(row, ("year", "season"))),
        "runs_prevented": _to_float(
            _first_value(
                row,
                (
                    "runs_prevented",
                    "fielding_runs_prevented",
                    "runsprevented",
                    "runs",
                ),
            )
        ),
        "outs_above_average": _to_float(
            _first_value(
                row,
                (
                    "outs_above_average",
                    "outsaboveaverage",
                    "oaa",
                ),
            )
        ),
        "directional_oaa": {
            "in": _to_float(_first_value(row, ("in", "oaa_in"))),
            "toward_right": _to_float(
                _first_value(
                    row,
                    (
                        "to_player_right",
                        "player_right",
                        "toward_right",
                        "oaa_right",
                        "right",
                    ),
                )
            ),
            "toward_left": _to_float(
                _first_value(
                    row,
                    (
                        "to_player_left",
                        "player_left",
                        "toward_left",
                        "oaa_left",
                        "left",
                    ),
                )
            ),
            "back": _to_float(_first_value(row, ("back", "oaa_back"))),
        },
        "batter_hand_oaa": {
            "vs_rhb": _to_float(
                _first_value(row, ("rhb", "vs_rhb", "oaa_rhb", "right_handed_batter"))
            ),
            "vs_lhb": _to_float(
                _first_value(row, ("lhb", "vs_lhb", "oaa_lhb", "left_handed_batter"))
            ),
        },
        "success_rate_pct": success_rate,
        "estimated_success_rate_pct": estimated_success_rate,
        "success_rate_added_pct": success_rate_added,
    }


def _fetch_team_oaa_board(season: int, position_group: str):
    pos = ""
    if position_group == "infield":
        pos = "if"
    elif position_group == "outfield":
        pos = "of"

    rows, error = _fetch_csv_rows(
        SAVANT_OAA_URL,
        {
            "type": "Fielding_Team",
            "startYear": season,
            "endYear": season,
            "split": "no",
            "team": "",
            "range": "year",
            "min": "q",
            "pos": pos,
            "roles": "",
            "viz": "hide",
            "csv": "true",
        },
    )
    return rows, error


def _team_defense_context(team_id, team_name, overall_rows, infield_rows, outfield_rows):
    overall = _normalize_oaa_row(
        _find_team_row(overall_rows, team_id, team_name),
        "overall",
    )
    infield = _normalize_oaa_row(
        _find_team_row(infield_rows, team_id, team_name),
        "infield",
    )
    outfield = _normalize_oaa_row(
        _find_team_row(outfield_rows, team_id, team_name),
        "outfield",
    )

    components = {
        "overall_oaa": overall is not None,
        "infield_oaa": infield is not None,
        "outfield_oaa": outfield is not None,
    }
    missing = [name for name, available in components.items() if not available]

    return {
        "team_id": team_id,
        "team_name": team_name,
        "overall": overall,
        "infield": infield,
        "outfield": outfield,
        "readiness": {
            "components": components,
            "missing_components": missing,
            "overall_context_available": overall is not None,
            "complete_defense_context": len(missing) == 0,
        },
    }


def _effective_batter_side(hitter):
    player = hitter.get("player") or {}
    arsenal = hitter.get("arsenal_matchup") or {}
    pitch_matchups = arsenal.get("pitch_matchups") or []

    # 3I stores the lineup hitter's listed batting side. If a switch hitter is
    # facing a starter, 3F/3G already resolved the effective side in matchup
    # context; use it when available.
    effective = None
    for matchup in pitch_matchups:
        candidate = matchup.get("effective_batter_side")
        if candidate in {"L", "R"}:
            effective = candidate
            break

    if effective in {"L", "R"}:
        return effective

    listed = player.get("bat_side")
    if listed in {"L", "R"}:
        return listed

    starter_hand = (arsenal.get("opposing_starter") or {}).get("pitch_hand")
    if listed == "S":
        if starter_hand == "R":
            return "L"
        if starter_hand == "L":
            return "R"

    return None


def _handedness_oaa(defense, batter_side):
    overall = defense.get("overall") or {}
    handed = overall.get("batter_hand_oaa") or {}

    if batter_side == "R":
        return handed.get("vs_rhb")
    if batter_side == "L":
        return handed.get("vs_lhb")
    return None


def _compact_defense(defense, batter_side=None):
    overall = defense.get("overall") or {}
    infield = defense.get("infield") or {}
    outfield = defense.get("outfield") or {}

    return {
        "team_id": defense.get("team_id"),
        "team_name": defense.get("team_name"),
        "overall_outs_above_average": overall.get("outs_above_average"),
        "overall_runs_prevented": overall.get("runs_prevented"),
        "overall_success_rate_pct": overall.get("success_rate_pct"),
        "overall_estimated_success_rate_pct": overall.get(
            "estimated_success_rate_pct"
        ),
        "overall_success_rate_added_pct": overall.get("success_rate_added_pct"),
        "batter_side": batter_side,
        "oaa_vs_batter_hand": _handedness_oaa(defense, batter_side),
        "infield_outs_above_average": infield.get("outs_above_average"),
        "infield_runs_prevented": infield.get("runs_prevented"),
        "outfield_outs_above_average": outfield.get("outs_above_average"),
        "outfield_runs_prevented": outfield.get("runs_prevented"),
        "readiness": defense.get("readiness") or {},
    }


def _attach_defense_to_team(team_block, opposing_defense):
    team = deepcopy(team_block)
    team["opposing_defense"] = opposing_defense

    defense_ready = opposing_defense.get("readiness", {}).get(
        "overall_context_available"
    ) is True
    defense_complete = opposing_defense.get("readiness", {}).get(
        "complete_defense_context"
    ) is True

    summary = team.setdefault("summary", {})
    summary["opposing_defense_available"] = defense_ready
    summary["complete_defense_context"] = defense_complete
    summary["defense_missing_components"] = opposing_defense.get(
        "readiness", {}
    ).get("missing_components", [])

    for hitter in team.get("hitters", []):
        batter_side = _effective_batter_side(hitter)
        compact = _compact_defense(opposing_defense, batter_side)
        hitter["opposing_defense_context"] = compact

        feature_vector = hitter.setdefault("feature_vector", {})
        feature_vector.update(
            {
                "opposing_defense_oaa": compact.get(
                    "overall_outs_above_average"
                ),
                "opposing_defense_runs_prevented": compact.get(
                    "overall_runs_prevented"
                ),
                "opposing_defense_success_rate_added_pct": compact.get(
                    "overall_success_rate_added_pct"
                ),
                "opposing_defense_oaa_vs_batter_hand": compact.get(
                    "oaa_vs_batter_hand"
                ),
                "opposing_infield_oaa": compact.get(
                    "infield_outs_above_average"
                ),
                "opposing_outfield_oaa": compact.get(
                    "outfield_outs_above_average"
                ),
            }
        )

        readiness = hitter.setdefault("feature_readiness", {})
        readiness["defense_components"] = opposing_defense.get(
            "readiness", {}
        ).get("components", {})
        readiness["defense_missing_components"] = opposing_defense.get(
            "readiness", {}
        ).get("missing_components", [])
        readiness["opposing_defense_available"] = defense_ready
        readiness["complete_defense_context"] = defense_complete

    return team


@router.get("/games/{game_pk}/hit-defense-context")
def get_mlb_hit_defense_context(
    game_pk: int,
    season: int | None = Query(
        default=None,
        ge=2016,
        le=2100,
        description=(
            "Statcast fielding season. Defaults to the game's official season through the "
            "underlying hit-environment feature profile."
        ),
    ),
    bullpen_lookback_days: int = Query(
        default=7,
        ge=3,
        le=14,
        description="Passed through to the underlying hit-environment context layer.",
    ),
):
    base = get_mlb_hit_environment_context(
        game_pk=game_pk,
        season=season,
        bullpen_lookback_days=bullpen_lookback_days,
    )
    target_season = base.get("season")

    source_errors = list(base.get("data_quality", {}).get("source_errors") or [])

    overall_rows, overall_error = _fetch_team_oaa_board(target_season, "overall")
    infield_rows, infield_error = _fetch_team_oaa_board(target_season, "infield")
    outfield_rows, outfield_error = _fetch_team_oaa_board(target_season, "outfield")

    for source, error in (
        ("savant_team_oaa_overall", overall_error),
        ("savant_team_oaa_infield", infield_error),
        ("savant_team_oaa_outfield", outfield_error),
    ):
        if error:
            source_errors.append({"source": source, "error": error})

    away_team_id = base.get("away", {}).get("team_id")
    away_team_name = base.get("away", {}).get("team_name")
    home_team_id = base.get("home", {}).get("team_id")
    home_team_name = base.get("home", {}).get("team_name")

    away_defense = _team_defense_context(
        away_team_id,
        away_team_name,
        overall_rows,
        infield_rows,
        outfield_rows,
    )
    home_defense = _team_defense_context(
        home_team_id,
        home_team_name,
        overall_rows,
        infield_rows,
        outfield_rows,
    )

    # Away hitters face the home defense; home hitters face the away defense.
    away = _attach_defense_to_team(base.get("away", {}), home_defense)
    home = _attach_defense_to_team(base.get("home", {}), away_defense)

    away_ready = away.get("summary", {}).get("opposing_defense_available") is True
    home_ready = home.get("summary", {}).get("opposing_defense_available") is True

    return {
        "sources": [
            "MLB Stats API",
            "Baseball Savant / MLB Statcast",
            "National Weather Service",
        ],
        "calculated_by": "Kyre Sports API",
        "feature_profile_version": "hit-defense-context v0.1",
        "game_pk": game_pk,
        "season": target_season,
        "official_date": base.get("official_date"),
        "game_datetime_utc": base.get("game_datetime_utc"),
        "status": base.get("status"),
        "venue": base.get("venue"),
        "starter_status": base.get("starter_status"),
        "game_environment": base.get("game_environment"),
        "bullpen_workload": base.get("bullpen_workload"),
        "team_defense": {
            "away_team_defense": away_defense,
            "home_team_defense": home_defense,
        },
        "readiness": {
            **(base.get("readiness") or {}),
            "away_opposing_defense_ready": away_ready,
            "home_opposing_defense_ready": home_ready,
            "both_opposing_defenses_ready": away_ready and home_ready,
        },
        "away": away,
        "home": home,
        "data_quality": {
            "source_errors": source_errors,
            "partial_data_allowed": True,
            "overall_oaa_board_available": overall_error is None,
            "infield_oaa_board_available": infield_error is None,
            "outfield_oaa_board_available": outfield_error is None,
        },
        "modeling_notes": {
            "oaa_definition": (
                "Outs Above Average is Baseball Savant's cumulative credit/debit for fielding "
                "plays after accounting for play difficulty. Positive values indicate more outs "
                "converted than expected; negative values indicate fewer."
            ),
            "runs_prevented": (
                "Runs Prevented is Savant's position-based translation of outs saved into runs "
                "saved. It remains descriptive context here."
            ),
            "handedness": (
                "When available, the hitter feature vector includes the opposing team's OAA "
                "against that batter's effective left/right side."
            ),
            "infield_outfield": (
                "Infield and outfield OAA are exposed separately rather than collapsed into a "
                "homemade defense grade. A later calibrated model can weight them using the "
                "hitter's batted-ball profile."
            ),
            "no_probability": (
                "This layer does not convert OAA, Runs Prevented, or success-rate metrics into a "
                "hit-suppression percentage, 1+ hit probability, fair odds, EV, or Monte Carlo result."
            ),
        },
    }
