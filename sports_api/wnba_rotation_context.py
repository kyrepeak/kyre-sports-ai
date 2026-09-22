"""Official WNBA game rotation and exact stint context.

Step 4R prefers the official WNBA Stats API ``gamerotation`` endpoint. When
that transport is unavailable, Step 7G may use the separately certified,
fail-closed WNBA.com period-aware reconstruction. Successful but malformed
Stats responses are never masked by the fallback.
"""
from __future__ import annotations

from typing import Any, Iterable

from sports_api.wnba_game_history import (
    ALLOWED_SEASON_TYPES,
    WNBA_HISTORY_SOURCE,
    WNBA_HISTORY_SOURCE_URL,
    WNBAHistoryNotFoundError,
    WNBAHistoryUpstreamError,
    WNBA_LEAGUE_ID,
    _registry_team_from_values,
    _request_stats_json,
    get_player_game_log_dataset,
)
from sports_api.wnba_league import get_wnba_teams

ROTATION_ENDPOINT = "gamerotation"
ALLOWED_ROTATION_STATS = ("PLAYER_PTS", "PT_DIFF", "USG_PCT")
MAX_RECENT_GAMES = 20
_REQUIRED_HEADERS = {
    "GAME_ID", "TEAM_ID", "TEAM_CITY", "TEAM_NAME", "PERSON_ID",
    "PLAYER_FIRST", "PLAYER_LAST", "IN_TIME_REAL", "OUT_TIME_REAL",
    "PLAYER_PTS", "PT_DIFF", "USG_PCT",
}


class WNBARotationUpstreamError(RuntimeError):
    """Raised when official WNBA rotation data cannot be consumed safely."""


class WNBARotationNotFoundError(LookupError):
    """Raised when requested WNBA rotation data is unavailable."""


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    try:
        return int(float(_clean(value))) if _clean(value) is not None else None
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(_clean(value)) if _clean(value) is not None else None
    except (TypeError, ValueError):
        return None


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _choice(value: str, allowed: Iterable[str], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(str(value).strip().casefold())
    if result is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return result


def _recent_game_count(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= MAX_RECENT_GAMES
    ):
        raise ValueError("WNBA last_n_games must be an integer from 1 through 20.")
    return value


def _result_set(payload: dict[str, Any], name: str) -> list[dict[str, Any]]:
    raw = payload.get("resultSets")
    if raw is None:
        raw = payload.get("resultSet")
    candidates = [raw] if isinstance(raw, dict) else raw
    if not isinstance(candidates, list):
        raise WNBARotationUpstreamError(
            f"WNBA rotation payload is missing result sets for {name}."
        )
    selected = next(
        (
            item for item in candidates
            if isinstance(item, dict)
            and (_clean(item.get("name")) or "").casefold() == name.casefold()
        ),
        None,
    )
    if selected is None:
        raise WNBARotationUpstreamError(
            f"WNBA rotation payload is missing the {name} result set."
        )
    headers, row_set = selected.get("headers"), selected.get("rowSet")
    if not isinstance(headers, list) or not isinstance(row_set, list):
        raise WNBARotationUpstreamError(
            f"WNBA {name} rotation result set has an unexpected schema."
        )
    headers = [str(item) for item in headers]
    missing = sorted(_REQUIRED_HEADERS - set(headers))
    if missing:
        raise WNBARotationUpstreamError(
            f"WNBA {name} rotation result set is missing required fields: "
            + ", ".join(missing)
            + "."
        )
    rows: list[dict[str, Any]] = []
    for raw_row in row_set:
        if not isinstance(raw_row, (list, tuple)) or len(raw_row) != len(headers):
            raise WNBARotationUpstreamError(
                f"WNBA {name} rotation result set contains a malformed row."
            )
        rows.append(dict(zip(headers, raw_row)))
    return rows


def _clock_from_tenths(raw_tenths: int, *, boundary_role: str) -> dict[str, Any]:
    if raw_tenths < 0:
        raise ValueError("rotation time cannot be negative")
    if boundary_role not in {"in", "out"}:
        raise ValueError("boundary_role must be 'in' or 'out'")
    q, regulation_end, ot = 6000, 24000, 3000
    if raw_tenths == 0:
        period, length, offset = 1, q, 0
    elif raw_tenths < regulation_end:
        exact = raw_tenths % q == 0
        if exact and boundary_role == "out":
            period, length, offset = raw_tenths // q, q, q
        else:
            period = raw_tenths // q + 1
            length = q
            offset = raw_tenths - (period - 1) * q
    else:
        after = raw_tenths - regulation_end
        exact = after % ot == 0
        if exact and boundary_role == "out":
            if after == 0:
                period, length, offset = 4, q, q
            else:
                ot_number = after // ot
                period, length, offset = 4 + ot_number, ot, ot
        else:
            ot_number = after // ot + 1
            period = 4 + ot_number
            length = ot
            offset = after - (ot_number - 1) * ot
    remaining_tenths = max(0, length - offset)
    remaining_seconds = remaining_tenths / 10.0
    minutes = int(remaining_seconds // 60)
    seconds = remaining_seconds - minutes * 60
    return {
        "period": int(period),
        "period_label": f"Q{period}" if period <= 4 else f"OT{period - 4}",
        "game_clock": f"{minutes}:{seconds:04.1f}",
        "seconds_remaining_in_period": round(remaining_seconds, 1),
        "derived_from_source_elapsed_time": True,
    }


def _normalize_stint(
    row: dict[str, Any], side: str, season: int, game_id: str
) -> dict[str, Any]:
    if _clean(row.get("GAME_ID")) != game_id:
        raise WNBARotationUpstreamError(
            f"WNBA rotation returned game ID {_clean(row.get('GAME_ID'))!r}; expected {game_id}."
        )
    team_id = _to_int(row.get("TEAM_ID"))
    player_id = _to_int(row.get("PERSON_ID"))
    in_raw = _to_float(row.get("IN_TIME_REAL"))
    out_raw = _to_float(row.get("OUT_TIME_REAL"))
    if team_id in (None, 0) or player_id in (None, 0):
        raise WNBARotationUpstreamError(
            "WNBA rotation returned a missing team or player ID."
        )
    if in_raw is None or out_raw is None:
        raise WNBARotationUpstreamError("WNBA rotation returned a missing in/out time.")
    if in_raw < 0 or out_raw < in_raw:
        raise WNBARotationUpstreamError(
            "WNBA rotation returned an invalid in/out time interval."
        )
    team = _registry_team_from_values(
        season=season,
        team_name=row.get("TEAM_NAME"),
        team_city=row.get("TEAM_CITY"),
    )
    if team is None:
        raise WNBARotationUpstreamError(
            "WNBA rotation returned a team that does not map to the verified registry."
        )
    in_tenths, out_tenths = int(round(in_raw)), int(round(out_raw))
    duration = out_tenths - in_tenths
    first = _clean(row.get("PLAYER_FIRST"))
    last = _clean(row.get("PLAYER_LAST"))
    return {
        "side": side,
        "game_id": game_id,
        "official_team_id": team_id,
        "team_key": team["team_key"],
        "team_full_name": team["full_name"],
        "player_id": player_id,
        "player_first_name": first,
        "player_last_name": last,
        "player_name": " ".join(item for item in (first, last) if item) or None,
        "in_time_real": in_raw,
        "out_time_real": out_raw,
        "in_elapsed_seconds": round(in_tenths / 10.0, 1),
        "out_elapsed_seconds": round(out_tenths / 10.0, 1),
        "in_elapsed_minutes": round(in_tenths / 600.0, 4),
        "out_elapsed_minutes": round(out_tenths / 600.0, 4),
        "duration_seconds": round(duration / 10.0, 1),
        "duration_minutes": round(duration / 600.0, 4),
        "start": _clock_from_tenths(in_tenths, boundary_role="in"),
        "end": _clock_from_tenths(out_tenths, boundary_role="out"),
        "player_points_during_stint": _to_float(row.get("PLAYER_PTS")),
        "team_point_differential_during_stint": _to_float(row.get("PT_DIFF")),
        "usage_percentage_during_stint": _to_float(row.get("USG_PCT")),
    }


def _player_summary(
    stints: list[dict[str, Any]], game_end_tenths: int
) -> dict[str, Any]:
    ordered = sorted(
        stints, key=lambda item: (item["in_time_real"], item["out_time_real"])
    )
    total_seconds = sum(item["duration_seconds"] for item in ordered)
    durations = [item["duration_seconds"] for item in ordered]
    points = [
        item["player_points_during_stint"]
        for item in ordered
        if item["player_points_during_stint"] is not None
    ]
    diffs = [
        item["team_point_differential_during_stint"]
        for item in ordered
        if item["team_point_differential_during_stint"] is not None
    ]
    usage = [
        (item["usage_percentage_during_stint"], item["duration_seconds"])
        for item in ordered
        if item["usage_percentage_during_stint"] is not None
        and item["duration_seconds"] > 0
    ]
    usage_den = sum(seconds for _, seconds in usage)
    first, last = ordered[0], ordered[-1]
    return {
        "player_id": first["player_id"],
        "player_name": first["player_name"],
        "official_team_id": first["official_team_id"],
        "team_key": first["team_key"],
        "team_full_name": first["team_full_name"],
        "stint_count": len(ordered),
        "tracked_seconds": round(total_seconds, 1),
        "tracked_minutes": round(total_seconds / 60.0, 4),
        "average_stint_seconds": round(total_seconds / len(ordered), 1),
        "longest_stint_seconds": round(max(durations), 1),
        "shortest_stint_seconds": round(min(durations), 1),
        "player_points_during_stints": round(sum(points), 4) if points else None,
        "team_point_differential_during_stints": round(sum(diffs), 4) if diffs else None,
        "time_weighted_usage_percentage": (
            round(
                sum(value * seconds for value, seconds in usage) / usage_den,
                6,
            )
            if usage_den
            else None
        ),
        "started_game": int(round(first["in_time_real"])) == 0,
        "finished_game": int(round(last["out_time_real"])) == game_end_tenths,
        "first_entry_elapsed_seconds": first["in_elapsed_seconds"],
        "last_exit_elapsed_seconds": last["out_elapsed_seconds"],
        "stints": ordered,
    }


def _normalize_side(
    rows: list[dict[str, Any]], side: str, season: int, game_id: str
) -> dict[str, Any]:
    stints = [_normalize_stint(item, side, season, game_id) for item in rows]
    if not stints:
        raise WNBARotationUpstreamError(f"WNBA {side} rotation has no stint rows.")
    if (
        len({item["official_team_id"] for item in stints}) != 1
        or len({item["team_key"] for item in stints}) != 1
    ):
        raise WNBARotationUpstreamError(
            f"WNBA {side} rotation result set contains multiple team identities."
        )
    seen: set[tuple[int, int, int]] = set()
    for item in stints:
        key = (
            item["player_id"],
            int(round(item["in_time_real"])),
            int(round(item["out_time_real"])),
        )
        if key in seen:
            raise WNBARotationUpstreamError(
                f"WNBA {side} rotation result set contains duplicate stint intervals."
            )
        seen.add(key)
    game_end = max(int(round(item["out_time_real"])) for item in stints)
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in stints:
        grouped.setdefault(item["player_id"], []).append(item)
    players = [_player_summary(items, game_end) for items in grouped.values()]
    players.sort(key=lambda item: (item["player_name"] or "", item["player_id"]))
    stints.sort(
        key=lambda item: (
            item["in_time_real"], item["out_time_real"], item["player_id"]
        )
    )
    first = stints[0]
    return {
        "side": side,
        "official_team_id": first["official_team_id"],
        "team_key": first["team_key"],
        "team_full_name": first["team_full_name"],
        "player_count": len(players),
        "stint_count": len(stints),
        "maximum_source_time_tenths": game_end,
        "maximum_elapsed_seconds": round(game_end / 10.0, 1),
        "players": players,
        "stints": stints,
    }


def _validate_two_sides(
    away: dict[str, Any], home: dict[str, Any]
) -> None:
    if (
        away["official_team_id"] == home["official_team_id"]
        or away["team_key"] == home["team_key"]
    ):
        raise WNBARotationUpstreamError(
            "WNBA rotation returned identical away and home teams."
        )
    overlap = sorted(
        {item["player_id"] for item in away["players"]}
        & {item["player_id"] for item in home["players"]}
    )
    if overlap:
        raise WNBARotationUpstreamError(
            "WNBA rotation returned player IDs on both teams: "
            + ", ".join(str(item) for item in overlap)
            + "."
        )


def get_game_rotation(
    game_id: str,
    season: int,
    *,
    rotation_stat: str = "PLAYER_PTS",
) -> dict[str, Any]:
    get_wnba_teams(season)
    game_id = _game_id(game_id)
    rotation_stat = _choice(rotation_stat, ALLOWED_ROTATION_STATS, "rotation_stat")
    params = [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("GameID", game_id),
        ("RotationStat", rotation_stat),
    ]

    fallback = None
    try:
        payload, retrieved_at_utc, cache_hit, cache_ttl_seconds = _request_stats_json(
            ROTATION_ENDPOINT, params
        )
    except WNBAHistoryNotFoundError as exc:
        raise WNBARotationNotFoundError(str(exc)) from exc
    except WNBAHistoryUpstreamError as direct_exc:
        from sports_api.wnba_rotation_reconstruction import (
            WNBARotationReconstructionError,
            reconstruct_game_rotation_rows,
        )
        try:
            fallback = reconstruct_game_rotation_rows(game_id, season)
        except WNBARotationReconstructionError as fallback_exc:
            raise WNBARotationUpstreamError(
                "Official WNBA Stats gamerotation transport failed and the "
                f"certified first-party fallback also failed: {fallback_exc}"
            ) from direct_exc
        away_rows = fallback["away_rows"]
        home_rows = fallback["home_rows"]
        retrieved_at_utc = fallback["retrieved_at_utc"]
        cache_hit = fallback["cache_hit"]
        cache_ttl_seconds = fallback["cache_ttl_seconds"]
    else:
        away_rows = _result_set(payload, "AwayTeam")
        home_rows = _result_set(payload, "HomeTeam")
        if not away_rows and not home_rows:
            raise WNBARotationNotFoundError(
                f"WNBA rotation data is not available for game {game_id}."
            )
        if not away_rows or not home_rows:
            raise WNBARotationUpstreamError(
                "WNBA rotation returned only one team result set with stint rows."
            )

    away = _normalize_side(away_rows, "away", season, game_id)
    home = _normalize_side(home_rows, "home", season, game_id)
    _validate_two_sides(away, home)

    if fallback is None:
        return {
            "source": WNBA_HISTORY_SOURCE,
            "source_url": WNBA_HISTORY_SOURCE_URL,
            "source_endpoint": ROTATION_ENDPOINT,
            "data_type": "official_game_rotation_stints",
            "league_id": WNBA_LEAGUE_ID,
            "season": season,
            "game_id": game_id,
            "rotation_stat": rotation_stat,
            "retrieved_at_utc": retrieved_at_utc,
            "cache_hit": cache_hit,
            "cache_ttl_seconds": cache_ttl_seconds,
            "time_basis": {
                "source_fields": ["IN_TIME_REAL", "OUT_TIME_REAL"],
                "source_units": "tenths_of_a_second_elapsed_from_game_start",
                "derived_seconds_divisor": 10,
                "wnba_regulation_period_minutes": 10,
                "wnba_overtime_period_minutes": 5,
            },
            "away": away,
            "home": home,
            "verification": {
                "required_rotation_schema_verified": True,
                "requested_game_id_matches_all_stints": True,
                "away_home_team_identity_distinct": True,
                "player_ids_do_not_cross_teams": True,
                "duplicate_stints_rejected": True,
                "period_clocks_are_derived_from_source_elapsed_time": True,
                "rotation_data_is_descriptive_not_projected": True,
                "no_projected_minutes_created": True,
                "no_rotation_grade_created": True,
                "no_betting_probability_created": True,
            },
        }

    return {
        "source": fallback["source"],
        "source_url": fallback["source_urls"]["box_score"],
        "source_urls": fallback["source_urls"],
        "source_endpoint": fallback["source_endpoint"],
        "provider_mode": "first_party_reconstruction_fallback",
        "data_type": "official_game_rotation_stints",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "game_id": game_id,
        "rotation_stat": rotation_stat,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": cache_ttl_seconds,
        "time_basis": {
            "source_fields": ["WNBA.com PBP elapsed_game_seconds"],
            "compatibility_fields": ["IN_TIME_REAL", "OUT_TIME_REAL"],
            "source_units": "tenths_of_a_second_elapsed_from_game_start",
            "derived_seconds_divisor": 10,
            "wnba_regulation_period_minutes": 10,
            "wnba_overtime_period_minutes": 5,
        },
        "away": away,
        "home": home,
        "fallback_diagnostics": fallback["diagnostics"],
        "verification": {
            "required_rotation_schema_verified": True,
            "requested_game_id_matches_all_stints": True,
            "away_home_team_identity_distinct": True,
            "player_ids_do_not_cross_teams": True,
            "duplicate_stints_rejected": True,
            "period_clocks_are_derived_from_source_elapsed_time": True,
            "rotation_data_is_descriptive_not_projected": True,
            "no_projected_minutes_created": True,
            "no_rotation_grade_created": True,
            "no_betting_probability_created": True,
            "stats_transport_failed_before_fallback": True,
            "period_aware_reconstruction": True,
            "first_participation_evidence_used": True,
            "unique_solution_required": True,
            "official_minutes_reconciled": True,
            "per_stint_player_points_available": False,
            "per_stint_point_differential_available": False,
            "per_stint_usage_percentage_available": False,
            "fabricated_stint_metrics": False,
        },
    }


def _find_player(game: dict[str, Any], player_id: int) -> dict[str, Any] | None:
    matches = [
        player
        for side in (game["away"], game["home"])
        for player in side["players"]
        if player["player_id"] == player_id
    ]
    if len(matches) > 1:
        raise WNBARotationUpstreamError(
            f"WNBA rotation returned player {player_id} more than once across team summaries."
        )
    return matches[0] if matches else None


def get_game_player_rotation(
    game_id: str,
    player_id: int,
    season: int,
    *,
    rotation_stat: str = "PLAYER_PTS",
) -> dict[str, Any]:
    player_id = _player_id(player_id)
    game = get_game_rotation(game_id, season, rotation_stat=rotation_stat)
    player = _find_player(game, player_id)
    if player is None:
        raise WNBARotationNotFoundError(
            f"No WNBA rotation stints were found for player {player_id} in game {game['game_id']}."
        )
    result = {
        "source": game["source"],
        "source_url": game["source_url"],
        "source_endpoint": game["source_endpoint"],
        "data_type": "official_game_player_rotation_stints",
        "league_id": game["league_id"],
        "season": season,
        "game_id": game["game_id"],
        "rotation_stat": game["rotation_stat"],
        "time_basis": game["time_basis"],
        "player": player,
        "verification": {
            "player_resolved_from_official_game_rotation": True,
            "stints_are_observed_not_projected": True,
            "no_projected_minutes_created": True,
        },
    }
    if "provider_mode" in game:
        result["provider_mode"] = game["provider_mode"]
        result["source_urls"] = game.get("source_urls")
    return result


def get_player_recent_rotation_context(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    rotation_stat: str = "PLAYER_PTS",
) -> dict[str, Any]:
    get_wnba_teams(season)
    player_id = _player_id(player_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _recent_game_count(last_n_games)
    rotation_stat = _choice(rotation_stat, ALLOWED_ROTATION_STATS, "rotation_stat")
    try:
        history = get_player_game_log_dataset(
            player_id, season, season_type=season_type
        )
    except WNBAHistoryUpstreamError as exc:
        raise WNBARotationUpstreamError(str(exc)) from exc
    games = history.get("games")
    if not isinstance(games, list):
        raise WNBARotationUpstreamError(
            "WNBA player game log returned a malformed games field."
        )
    selected = games[:last_n_games]
    if not selected:
        raise WNBARotationNotFoundError(
            f"No WNBA games were found for player {player_id} in {season}."
        )

    rows: list[dict[str, Any]] = []
    all_stints: list[dict[str, Any]] = []
    missing: list[str] = []
    team_keys: list[str] = []
    for history_game in selected:
        gid = _clean(history_game.get("game_id"))
        if not gid:
            continue
        try:
            game = get_game_rotation(gid, season, rotation_stat=rotation_stat)
        except WNBARotationNotFoundError:
            missing.append(gid)
            continue
        player = _find_player(game, player_id)
        if player is None:
            missing.append(gid)
            continue
        all_stints.extend(player["stints"])
        if player["team_key"] not in team_keys:
            team_keys.append(player["team_key"])
        rows.append({
            "game_id": gid,
            "game_date": history_game.get("game_date"),
            "matchup": history_game.get("matchup"),
            "player_rotation": player,
        })
    if not rows:
        raise WNBARotationNotFoundError(
            f"Official rotation data was unavailable for the selected recent games for player {player_id}."
        )

    total_seconds = sum(item["duration_seconds"] for item in all_stints)
    usage = [
        (item["usage_percentage_during_stint"], item["duration_seconds"])
        for item in all_stints
        if item["usage_percentage_during_stint"] is not None
        and item["duration_seconds"] > 0
    ]
    usage_den = sum(seconds for _, seconds in usage)
    points = [
        item["player_points_during_stint"]
        for item in all_stints
        if item["player_points_during_stint"] is not None
    ]
    diffs = [
        item["team_point_differential_during_stint"]
        for item in all_stints
        if item["team_point_differential_during_stint"] is not None
    ]
    starts = sum(
        1 for item in rows if item["player_rotation"]["started_game"]
    )
    return {
        "source": WNBA_HISTORY_SOURCE,
        "source_url": WNBA_HISTORY_SOURCE_URL,
        "source_endpoint": ROTATION_ENDPOINT,
        "data_type": "official_recent_player_rotation_context",
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "team_keys_observed": team_keys,
        "requested_last_n_games": last_n_games,
        "selected_game_count": len(selected),
        "rotation_game_count": len(rows),
        "missing_rotation_game_ids": missing,
        "aggregate": {
            "stint_count": len(all_stints),
            "tracked_seconds": round(total_seconds, 1),
            "tracked_minutes": round(total_seconds / 60.0, 4),
            "tracked_minutes_per_rotation_game": round(
                total_seconds / 60.0 / len(rows), 4
            ),
            "average_stint_seconds": (
                round(total_seconds / len(all_stints), 1)
                if all_stints
                else None
            ),
            "starts_in_rotation_games": starts,
            "start_share": round(starts / len(rows), 6),
            "player_points_during_stints": round(sum(points), 4) if points else None,
            "team_point_differential_during_stints": (
                round(sum(diffs), 4) if diffs else None
            ),
            "time_weighted_usage_percentage": (
                round(
                    sum(value * seconds for value, seconds in usage) / usage_den,
                    6,
                )
                if usage_den
                else None
            ),
        },
        "games": rows,
        "verification": {
            "selected_games_come_from_official_player_game_log": True,
            "missing_rotation_games_are_reported_not_fabricated": True,
            "multi_team_history_preserved": len(team_keys) > 1,
            "rotation_context_is_descriptive_not_predictive": True,
            "no_projected_minutes_created": True,
            "no_rotation_grade_created": True,
        },
    }
