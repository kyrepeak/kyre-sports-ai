"""WNBA shot charts, shot zones, and observed opponent shooting by location.

Step 4L is descriptive data only: no projections, probabilities, or causal
matchup adjustments are created here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_rosters import (
    CACHE_TTL_SECONDS,
    WNBA_LEAGUE_ID,
    WNBA_STATS_SOURCE,
    WNBA_STATS_SOURCE_URL,
    WNBAEntityNotFoundError,
    WNBAStatsUpstreamError,
    _clean_text,
    _request_stats_json,
    _resolve_official_team_id,
    _to_float,
    _to_int,
)

SHOT_CHART_ENDPOINT = "shotchartdetail"
TEAM_SHOT_LOCATIONS_ENDPOINT = "leaguedashteamshotlocations"
ZONE_KEYS = {
    "restricted area": "restricted_area",
    "in the paint (non-ra)": "paint_non_ra",
    "mid-range": "mid_range",
    "left corner 3": "left_corner_3",
    "right corner 3": "right_corner_3",
    "above the break 3": "above_the_break_3",
    "backcourt": "backcourt",
    "corner 3": "corner_3",
}


class WNBAShotContextUpstreamError(RuntimeError):
    pass


class WNBAShotContextNotFoundError(LookupError):
    pass


def _call(endpoint: str, params: list[tuple[str, Any]]) -> tuple[dict[str, Any], str, bool]:
    try:
        return _request_stats_json(endpoint, params)
    except WNBAEntityNotFoundError as exc:
        raise WNBAShotContextNotFoundError(str(exc)) from exc
    except WNBAStatsUpstreamError as exc:
        raise WNBAShotContextUpstreamError(str(exc)) from exc


def _choice(value: str, allowed: Iterable[str], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    resolved = lookup.get(str(value).strip().casefold())
    if resolved is None:
        raise ValueError(f"Unsupported WNBA {label} {value!r}. Allowed values: {', '.join(allowed)}.")
    return resolved


def _last_n(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
        raise ValueError("WNBA last_n_games must be an integer from 0 through 100.")
    return value


def _player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _team_key(value: str, season: int) -> str:
    wanted = str(value).strip().casefold()
    for team in get_wnba_teams(season):
        if team["team_key"].casefold() == wanted:
            return team["team_key"]
    raise ValueError(f"WNBA team key {value!r} was not found for the {season} season.")


def _registry_team(name: Any, season: int) -> dict[str, Any] | None:
    value = (_clean_text(name) or "").casefold()
    for team in get_wnba_teams(season):
        if value in {
            team["team_key"].casefold(), team["slug"].casefold(),
            team["abbreviation"].casefold(), team["nickname"].casefold(),
            team["full_name"].casefold(),
        }:
            return team
    return None


def _result(payload: dict[str, Any], name: str) -> dict[str, Any]:
    raw = payload.get("resultSets", payload.get("resultSet"))
    items = [raw] if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise WNBAShotContextUpstreamError(f"WNBA payload is missing result sets for {name}.")
    selected = next((x for x in items if isinstance(x, dict) and (_clean_text(x.get("name")) or "").casefold() == name.casefold()), None)
    if selected is None and len(items) == 1 and isinstance(items[0], dict):
        selected = items[0]
    if selected is None:
        raise WNBAShotContextUpstreamError(f"WNBA payload is missing the {name} result set.")
    return selected


def _flat_rows(payload: dict[str, Any], name: str) -> tuple[list[str], list[dict[str, Any]]]:
    result = _result(payload, name)
    headers, row_set = result.get("headers"), result.get("rowSet")
    if not isinstance(headers, list) or not all(isinstance(x, str) for x in headers) or not isinstance(row_set, list):
        raise WNBAShotContextUpstreamError(f"WNBA {name} result set has an unexpected flat schema.")
    rows = []
    for row in row_set:
        if not isinstance(row, (list, tuple)):
            continue
        if len(row) != len(headers):
            raise WNBAShotContextUpstreamError(f"WNBA {name} row length does not match headers.")
        rows.append(dict(zip(headers, row)))
    return [str(x) for x in headers], rows


def _date_iso(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _zone_key(value: Any) -> str:
    text = (_clean_text(value) or "unknown").casefold()
    return ZONE_KEYS.get(text, text.replace(" ", "_").replace("-", "_"))


def _pct(made: float, attempts: float) -> float | None:
    return round(made / attempts, 4) if attempts > 0 else None


def _shot(row: dict[str, Any], season: int) -> dict[str, Any]:
    game_id = _clean_text(row.get("GAME_ID"))
    team = _registry_team(row.get("TEAM_NAME"), season)
    made = _to_int(row.get("SHOT_MADE_FLAG")) == 1
    attempted = _to_int(row.get("SHOT_ATTEMPTED_FLAG")) == 1
    shot_type = _clean_text(row.get("SHOT_TYPE"))
    points_if_made = 3 if shot_type and "3PT" in shot_type.upper() else 2
    return {
        "game_id": game_id,
        "game_id_valid": bool(game_id and len(game_id) == 10 and game_id.isdigit()),
        "game_event_id": _to_int(row.get("GAME_EVENT_ID")),
        "player_id": _to_int(row.get("PLAYER_ID")),
        "player_name": _clean_text(row.get("PLAYER_NAME")),
        "official_team_id": _to_int(row.get("TEAM_ID")),
        "team_name_source": _clean_text(row.get("TEAM_NAME")),
        "team_key": team["team_key"] if team else None,
        "mapped_to_registry": team is not None,
        "period": _to_int(row.get("PERIOD")),
        "minutes_remaining": _to_int(row.get("MINUTES_REMAINING")),
        "seconds_remaining": _to_int(row.get("SECONDS_REMAINING")),
        "event_type": _clean_text(row.get("EVENT_TYPE")),
        "action_type": _clean_text(row.get("ACTION_TYPE")),
        "shot_type": shot_type,
        "shot_zone_basic": _clean_text(row.get("SHOT_ZONE_BASIC")),
        "shot_zone_area": _clean_text(row.get("SHOT_ZONE_AREA")),
        "shot_zone_range": _clean_text(row.get("SHOT_ZONE_RANGE")),
        "canonical_zone": _zone_key(row.get("SHOT_ZONE_BASIC")),
        "shot_distance_feet": _to_float(row.get("SHOT_DISTANCE")),
        "location_x_source": _to_float(row.get("LOC_X")),
        "location_y_source": _to_float(row.get("LOC_Y")),
        "coordinate_system": "official_stats_source_units",
        "attempted": attempted,
        "made": made,
        "points_if_made": points_if_made,
        "points_scored": points_if_made if made else 0,
        "game_date": _date_iso(row.get("GAME_DATE")),
        "home_team_tricode": _clean_text(row.get("HTM")),
        "visitor_team_tricode": _clean_text(row.get("VTM")),
    }


def _aggregate_shots(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = sum(bool(s["attempted"]) for s in shots)
    groups: dict[str, dict[str, Any]] = {}
    for shot in shots:
        if not shot["attempted"]:
            continue
        name = shot["shot_zone_basic"] or "Unknown"
        item = groups.setdefault(name, {"shot_zone_basic": name, "canonical_zone": shot["canonical_zone"], "field_goals_made": 0.0, "field_goals_attempted": 0.0, "points_scored": 0.0})
        item["field_goals_attempted"] += 1
        if shot["made"]:
            item["field_goals_made"] += 1
            item["points_scored"] += shot["points_scored"]
    out = []
    for item in groups.values():
        a = item["field_goals_attempted"]
        item["field_goal_percentage"] = _pct(item["field_goals_made"], a)
        item["attempt_share"] = round(a / total, 4) if total else None
        item["observed_points_per_attempt"] = round(item["points_scored"] / a, 4) if a else None
        out.append(item)
    return sorted(out, key=lambda x: (-x["field_goals_attempted"], x["shot_zone_basic"]))


def _corner(zones: list[dict[str, Any]], made_field="field_goals_made", attempts_field="field_goals_attempted") -> dict[str, Any] | None:
    existing = next((z for z in zones if z.get("canonical_zone") == "corner_3"), None)
    if existing:
        return deepcopy(existing)
    parts = [z for z in zones if z.get("canonical_zone") in {"left_corner_3", "right_corner_3"}]
    if not parts:
        return None
    made = sum(float(z.get(made_field) or 0) for z in parts)
    attempts = sum(float(z.get(attempts_field) or 0) for z in parts)
    return {"shot_zone_basic": "Corner 3", "canonical_zone": "corner_3", made_field: made, attempts_field: attempts, "field_goal_percentage": _pct(made, attempts), "derived_from": ["Left Corner 3", "Right Corner 3"]}


def _shot_params(season: int, season_type: str, player_id: int, last_n: int, opponent_id: int) -> list[tuple[str, Any]]:
    return [
        ("LeagueID", WNBA_LEAGUE_ID), ("Season", str(season)), ("SeasonType", season_type),
        ("PlayerID", str(player_id)), ("TeamID", "0"), ("OpponentTeamID", str(opponent_id)),
        ("ContextMeasure", "FGA"), ("LastNGames", str(last_n)), ("Month", "0"), ("Period", "0"),
        ("DateFrom", ""), ("DateTo", ""), ("GameID", ""), ("GameSegment", ""),
        ("Location", ""), ("Outcome", ""), ("PlayerPosition", ""), ("RookieYear", ""),
        ("SeasonSegment", ""), ("VsConference", ""), ("VsDivision", ""),
    ]


def get_player_shot_chart_dataset(player_id: int, season: int, *, season_type="Regular Season", last_n_games=0, opponent_team_key: str | None = None) -> dict[str, Any]:
    get_wnba_teams(season)
    player_id, last_n_games = _player_id(player_id), _last_n(last_n_games)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    opponent_key = _team_key(opponent_team_key, season) if opponent_team_key else None
    try:
        opponent_id = _resolve_official_team_id(opponent_key, season) if opponent_key else 0
    except (WNBAEntityNotFoundError, WNBAStatsUpstreamError) as exc:
        raise WNBAShotContextNotFoundError(str(exc)) from exc
    payload, retrieved, cache_hit = _call(SHOT_CHART_ENDPOINT, _shot_params(season, season_type, player_id, last_n_games, opponent_id))
    headers, rows = _flat_rows(payload, "Shot_Chart_Detail")
    required = {"GAME_ID", "GAME_EVENT_ID", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_NAME", "PERIOD", "MINUTES_REMAINING", "SECONDS_REMAINING", "EVENT_TYPE", "ACTION_TYPE", "SHOT_TYPE", "SHOT_ZONE_BASIC", "SHOT_ZONE_AREA", "SHOT_ZONE_RANGE", "SHOT_DISTANCE", "LOC_X", "LOC_Y", "SHOT_ATTEMPTED_FLAG", "SHOT_MADE_FLAG", "GAME_DATE", "HTM", "VTM"}
    missing = sorted(required - set(headers))
    if missing:
        raise WNBAShotContextUpstreamError("WNBA shot-chart response is missing required fields: " + ", ".join(missing) + ".")
    _, league_rows = _flat_rows(payload, "LeagueAverages")
    shots = [_shot(row, season) for row in rows]
    if any(s["player_id"] not in {None, player_id} for s in shots):
        raise WNBAShotContextUpstreamError("WNBA shot chart returned rows for a player other than the requested player.")
    keys = [(s["game_id"], s["game_event_id"]) for s in shots if s["game_id"] and s["game_event_id"] is not None]
    dup = sorted({x for x in keys if keys.count(x) > 1})
    if dup:
        raise WNBAShotContextUpstreamError("WNBA shot chart returned duplicate game/event shot rows: " + ", ".join(f"{g}:{e}" for g, e in dup))
    zones = _aggregate_shots(shots)
    attempts, made = sum(s["attempted"] for s in shots), sum(s["made"] for s in shots)
    league = [{"shot_zone_basic": _clean_text(r.get("SHOT_ZONE_BASIC")), "shot_zone_area": _clean_text(r.get("SHOT_ZONE_AREA")), "shot_zone_range": _clean_text(r.get("SHOT_ZONE_RANGE")), "canonical_zone": _zone_key(r.get("SHOT_ZONE_BASIC")), "field_goals_attempted": _to_float(r.get("FGA")), "field_goals_made": _to_float(r.get("FGM")), "field_goal_percentage": _to_float(r.get("FG_PCT"))} for r in league_rows]
    names = sorted({s["player_name"] for s in shots if s["player_name"]})
    invalid_ids = sorted({s["game_id"] for s in shots if s["game_id"] and not s["game_id_valid"]})
    unmapped = sum(s["team_name_source"] is not None and not s["mapped_to_registry"] for s in shots)
    return {
        "source": WNBA_STATS_SOURCE, "source_url": WNBA_STATS_SOURCE_URL, "source_endpoint": SHOT_CHART_ENDPOINT,
        "data_type": "official_player_shot_chart", "league_id": WNBA_LEAGUE_ID, "season": season,
        "season_type": season_type, "player_id": player_id, "player_name": names[0] if len(names) == 1 else None,
        "filters": {"last_n_games": last_n_games, "opponent_team_key": opponent_key, "opponent_official_team_id": opponent_id or None},
        "retrieved_at_utc": retrieved, "cache_hit": cache_hit, "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "shot_count": len(shots), "attempt_count": attempts, "made_count": made, "field_goal_percentage": _pct(made, attempts),
        "zone_summary": zones, "corner_three_composite": _corner(zones), "league_average_rows": league, "shots": shots,
        "verification": {"requested_player_matches_all_rows": True, "shot_event_keys_unique": True, "all_game_ids_valid": not invalid_ids, "invalid_game_ids": invalid_ids, "all_shot_teams_mapped_to_registry": unmapped == 0, "unmapped_shot_count": unmapped, "coordinates_preserved_in_source_units": True, "no_model_derived_probabilities": True},
    }


def _flatten_shot_location_headers(headers: Any) -> list[str]:
    if not isinstance(headers, list) or not headers:
        raise WNBAShotContextUpstreamError("WNBA ShotLocations response has no headers.")
    if all(isinstance(x, str) for x in headers):
        return [str(x) for x in headers]
    if not all(isinstance(x, dict) for x in headers):
        raise WNBAShotContextUpstreamError("WNBA ShotLocations response has an unsupported header schema.")
    cat = next((x for x in headers if (_clean_text(x.get("name")) or "").upper() == "SHOT_CATEGORY"), None)
    cols = next((x for x in headers if (_clean_text(x.get("name")) or "").casefold() == "columns"), None)
    if not cat or not cols:
        raise WNBAShotContextUpstreamError("WNBA ShotLocations response is missing multi-level header metadata.")
    zones, names = [str(x) for x in cat.get("columnNames", [])], [str(x) for x in cols.get("columnNames", [])]
    span, skip = _to_int(cat.get("columnSpan")) or 3, _to_int(cat.get("columnsToSkip")) or 2
    if span <= 0 or len(names) < skip or (len(names) - skip) % span:
        raise WNBAShotContextUpstreamError("WNBA ShotLocations header metadata is invalid.")
    groups = (len(names) - skip) // span
    if groups == len(zones) + 1 and "Left Corner 3" in zones and "Right Corner 3" in zones:
        zones.append("Corner 3")
    if groups != len(zones):
        raise WNBAShotContextUpstreamError("WNBA ShotLocations metric groups do not match named shot zones.")
    out, i = names[:skip], skip
    for zone in zones:
        for _ in range(span):
            out.append(f"{zone}|{names[i]}")
            i += 1
    return out


def _location_rows(payload: dict[str, Any], season: int) -> tuple[list[str], list[dict[str, Any]]]:
    result = _result(payload, "ShotLocations")
    headers = _flatten_shot_location_headers(result.get("headers"))
    raw_rows = result.get("rowSet")
    if not isinstance(raw_rows, list):
        raise WNBAShotContextUpstreamError("WNBA ShotLocations result set is missing rowSet.")
    out = []
    for raw in raw_rows:
        if not isinstance(raw, (list, tuple)):
            continue
        if len(raw) != len(headers):
            raise WNBAShotContextUpstreamError("WNBA ShotLocations row length does not match headers.")
        row = dict(zip(headers, raw)); team = _registry_team(row.get("TEAM_NAME"), season); zones = []
        zone_names = []
        for key in row:
            if "|" in key and key.split("|", 1)[0] not in zone_names:
                zone_names.append(key.split("|", 1)[0])
        for zone in zone_names:
            m, a = _to_float(row.get(f"{zone}|FGM")) or 0.0, _to_float(row.get(f"{zone}|FGA")) or 0.0
            zones.append({"shot_zone_basic": zone, "canonical_zone": _zone_key(zone), "field_goals_made": m, "field_goals_attempted": a, "field_goal_percentage_source": _to_float(row.get(f"{zone}|FG_PCT")), "field_goal_percentage_recomputed": _pct(m, a), "is_composite_zone": zone == "Corner 3"})
        out.append({"official_team_id": _to_int(row.get("TEAM_ID")), "team_name_source": _clean_text(row.get("TEAM_NAME")), "team_key": team["team_key"] if team else None, "mapped_to_registry": team is not None, "zones": zones})
    return headers, out


def _location_params(season: int, season_type: str, last_n: int, team_id: int | str, opponent_id: int) -> list[tuple[str, Any]]:
    return [("LeagueID", WNBA_LEAGUE_ID), ("Season", str(season)), ("SeasonType", season_type), ("TeamID", str(team_id)), ("OpponentTeamID", str(opponent_id)), ("DistanceRange", "By Zone"), ("LastNGames", str(last_n)), ("MeasureType", "Base"), ("Month", "0"), ("PaceAdjust", "N"), ("PerMode", "Totals"), ("Period", "0"), ("PlusMinus", "N"), ("Rank", "N"), ("Conference", ""), ("DateFrom", ""), ("DateTo", ""), ("Division", ""), ("GameScope", ""), ("GameSegment", ""), ("Location", ""), ("Outcome", ""), ("PORound", ""), ("PlayerExperience", ""), ("PlayerPosition", ""), ("SeasonSegment", ""), ("ShotClockRange", ""), ("StarterBench", ""), ("VsConference", ""), ("VsDivision", "")]


def _team_id_or_error(team_key: str, season: int) -> int:
    try:
        return _resolve_official_team_id(team_key, season)
    except WNBAEntityNotFoundError as exc:
        raise WNBAShotContextNotFoundError(str(exc)) from exc
    except WNBAStatsUpstreamError as exc:
        raise WNBAShotContextUpstreamError(str(exc)) from exc


def get_team_shot_zones_dataset(team_key: str, season: int, *, season_type="Regular Season", last_n_games=0) -> dict[str, Any]:
    stable = _team_key(team_key, season); season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type"); last_n_games = _last_n(last_n_games); team_id = _team_id_or_error(stable, season)
    payload, retrieved, cache_hit = _call(TEAM_SHOT_LOCATIONS_ENDPOINT, _location_params(season, season_type, last_n_games, team_id, 0))
    headers, rows = _location_rows(payload, season)
    matches = [r for r in rows if r["official_team_id"] == team_id or r["team_key"] == stable]
    if len(matches) != 1:
        raise WNBAShotContextUpstreamError(f"WNBA team shot locations returned {len(matches)} matching rows for {stable}.")
    zones = matches[0]["zones"]
    return {"source": WNBA_STATS_SOURCE, "source_url": WNBA_STATS_SOURCE_URL, "source_endpoint": TEAM_SHOT_LOCATIONS_ENDPOINT, "data_type": "official_team_shot_zones", "league_id": WNBA_LEAGUE_ID, "season": season, "season_type": season_type, "team_key": stable, "official_team_id": team_id, "last_n_games": last_n_games, "retrieved_at_utc": retrieved, "cache_hit": cache_hit, "cache_ttl_seconds": CACHE_TTL_SECONDS, "source_header_count": len(headers), "zones": zones, "corner_three_composite": _corner(zones), "verification": {"requested_team_matches_source": True, "team_mapped_to_registry": matches[0]["mapped_to_registry"], "zone_percentages_recomputed_from_makes_attempts": True, "no_model_derived_probabilities": True}}


def get_opponent_defense_by_shot_zone_dataset(team_key: str, season: int, *, season_type="Regular Season", last_n_games=0) -> dict[str, Any]:
    stable = _team_key(team_key, season); season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type"); last_n_games = _last_n(last_n_games); team_id = _team_id_or_error(stable, season)
    payload, retrieved, cache_hit = _call(TEAM_SHOT_LOCATIONS_ENDPOINT, _location_params(season, season_type, last_n_games, "", team_id))
    headers, rows = _location_rows(payload, season); groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        for zone in row["zones"]:
            item = groups.setdefault(zone["shot_zone_basic"], {"shot_zone_basic": zone["shot_zone_basic"], "canonical_zone": zone["canonical_zone"], "field_goals_made_allowed": 0.0, "field_goals_attempted_allowed": 0.0, "is_composite_zone": zone["is_composite_zone"]})
            item["field_goals_made_allowed"] += zone["field_goals_made"]; item["field_goals_attempted_allowed"] += zone["field_goals_attempted"]
    zones = []
    for item in groups.values():
        item["field_goal_percentage_allowed"] = _pct(item["field_goals_made_allowed"], item["field_goals_attempted_allowed"]); zones.append(item)
    zones.sort(key=lambda x: x["shot_zone_basic"]); unmapped = sum(not r["mapped_to_registry"] for r in rows)
    return {"source": WNBA_STATS_SOURCE, "source_url": WNBA_STATS_SOURCE_URL, "source_endpoint": TEAM_SHOT_LOCATIONS_ENDPOINT, "data_type": "observed_opponent_shooting_by_defensive_team", "league_id": WNBA_LEAGUE_ID, "season": season, "season_type": season_type, "defending_team_key": stable, "defending_official_team_id": team_id, "last_n_games_source_filter": last_n_games, "retrieved_at_utc": retrieved, "cache_hit": cache_hit, "cache_ttl_seconds": CACHE_TTL_SECONDS, "source_header_count": len(headers), "opponent_shooting_team_count": len({r["official_team_id"] for r in rows if r["official_team_id"] is not None}), "opponent_shooting_rows": rows, "zones_allowed": zones, "corner_three_composite": _corner(zones, "field_goals_made_allowed", "field_goals_attempted_allowed"), "derivation": {"type": "observed_aggregation", "description": "Sums official team shot-location rows returned with OpponentTeamID set to the defending team, then recomputes makes/attempts percentages.", "not_a_causal_defensive_effect": True, "not_a_projection": True}, "verification": {"defending_team_resolved_to_official_id": True, "all_opponent_rows_mapped_to_registry": unmapped == 0, "unmapped_opponent_row_count": unmapped, "zone_percentages_recomputed_from_makes_attempts": True, "no_model_derived_probabilities": True}}
