"""WNBA individual-matchup source guardrails and exact opponent overlap context.

Step 4S deliberately does *not* claim player-vs-defender assignments. Current
WNBA tooling marks ``boxscorematchupsv3`` as unavailable/defunct for WNBA
matchup data. Instead, this module uses the official WNBA ``gamerotation``
feed from Step 4R to calculate exact observed court-time overlap between
opposing players.

Shared court time answers "were these players on the floor at the same time?"
It does not answer "who guarded whom?" and is never labeled as matchup
possessions, primary-defender minutes, or causal defensive effect.
"""

from __future__ import annotations

from typing import Any

from sports_api.wnba_game_history import (
    ALLOWED_SEASON_TYPES,
    WNBAHistoryUpstreamError,
    get_player_game_log_dataset,
)
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_rotation_context import (
    WNBARotationNotFoundError,
    WNBARotationUpstreamError,
    get_game_rotation,
)

MATCHUP_SOURCE_NAME = "WNBA individual defender matchup source status"
MATCHUP_SOURCE_STATUS = "official_player_vs_defender_feed_unavailable"
MATCHUP_RESEARCH_ENDPOINT = "boxscorematchupsv3"
OVERLAP_SOURCE_ENDPOINT = "gamerotation"
MAX_RECENT_GAMES = 20


class WNBAMatchupContextUpstreamError(RuntimeError):
    """Raised when official rotation/history data cannot support the context safely."""


class WNBAMatchupContextNotFoundError(LookupError):
    """Raised when a requested player or overlap context cannot be found."""


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_player_id(value: int, label: str = "player_id") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"WNBA {label} must be a positive integer.")
    return value


def _choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    resolved = lookup.get(str(value).strip().casefold())
    if resolved is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return resolved


def _last_n(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
        or value > MAX_RECENT_GAMES
    ):
        raise ValueError("WNBA last_n_games must be an integer from 1 through 20.")
    return value


def get_matchup_source_status(season: int) -> dict[str, Any]:
    """Describe which individual matchup claims are and are not supportable."""

    get_wnba_teams(season)
    return {
        "source": MATCHUP_SOURCE_NAME,
        "season": season,
        "status": MATCHUP_SOURCE_STATUS,
        "official_player_vs_defender_matchup_feed_available": False,
        "research_endpoint": MATCHUP_RESEARCH_ENDPOINT,
        "research_finding": (
            "Current WNBA tooling documents boxscorematchupsv3 as defunct for WNBA "
            "because WNBA matchup data are not available from that feed."
        ),
        "unsupported_claims": [
            "primary_defender_assignment",
            "matchup_minutes_as_defender_assignment",
            "matchup_partial_possessions",
            "shots_against_named_defender",
            "points_against_named_defender",
            "turnovers_forced_by_named_defender",
            "switches_onto_named_defender",
        ],
        "supported_alternative": {
            "endpoint": OVERLAP_SOURCE_ENDPOINT,
            "context": "exact_observed_opposing_player_court_time_overlap",
            "description": (
                "Step 4R official game-rotation stints can verify when opposing "
                "players shared the court, without inferring who guarded whom."
            ),
        },
        "guardrails": {
            "do_not_fabricate_defender_assignments": True,
            "shared_court_time_is_not_defender_time": True,
            "shared_court_time_is_not_matchup_possessions": True,
            "no_causal_defensive_effect_created": True,
            "no_matchup_grade_created": True,
            "no_betting_probability_created": True,
        },
    }


def _player_side(game: dict[str, Any], player_id: int) -> tuple[str, dict[str, Any], dict[str, Any]]:
    matches: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for side_name in ("away", "home"):
        side = game.get(side_name)
        if not isinstance(side, dict):
            raise WNBAMatchupContextUpstreamError(
                "WNBA rotation context is missing an away/home side object."
            )
        players = side.get("players")
        if not isinstance(players, list):
            raise WNBAMatchupContextUpstreamError(
                f"WNBA {side_name} rotation context contains a malformed players field."
            )
        for player in players:
            if isinstance(player, dict) and player.get("player_id") == player_id:
                matches.append((side_name, side, player))
    if len(matches) > 1:
        raise WNBAMatchupContextUpstreamError(
            f"WNBA rotation context returned player {player_id} on multiple sides."
        )
    if not matches:
        raise WNBAMatchupContextNotFoundError(
            f"Player {player_id} was not found in the official game rotation."
        )
    return matches[0]


def _merged_intervals(player: dict[str, Any]) -> list[tuple[int, int]]:
    stints = player.get("stints")
    if not isinstance(stints, list):
        raise WNBAMatchupContextUpstreamError(
            "WNBA player rotation summary contains a malformed stints field."
        )
    intervals: list[tuple[int, int]] = []
    for stint in stints:
        if not isinstance(stint, dict):
            raise WNBAMatchupContextUpstreamError(
                "WNBA player rotation summary contains a malformed stint."
            )
        try:
            start = int(round(float(stint.get("in_time_real"))))
            end = int(round(float(stint.get("out_time_real"))))
        except (TypeError, ValueError) as exc:
            raise WNBAMatchupContextUpstreamError(
                "WNBA player rotation stint contains an invalid in/out source time."
            ) from exc
        if start < 0 or end < start:
            raise WNBAMatchupContextUpstreamError(
                "WNBA player rotation stint contains an invalid in/out interval."
            )
        if end > start:
            intervals.append((start, end))

    intervals.sort()
    merged: list[list[int]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _overlap_segments(
    left_player: dict[str, Any], right_player: dict[str, Any]
) -> list[dict[str, Any]]:
    left = _merged_intervals(left_player)
    right = _merged_intervals(right_player)
    segments: list[dict[str, Any]] = []
    i = j = 0
    while i < len(left) and j < len(right):
        start = max(left[i][0], right[j][0])
        end = min(left[i][1], right[j][1])
        if end > start:
            duration_tenths = end - start
            segments.append(
                {
                    "start_time_real": start,
                    "end_time_real": end,
                    "start_elapsed_seconds": round(start / 10.0, 1),
                    "end_elapsed_seconds": round(end / 10.0, 1),
                    "duration_seconds": round(duration_tenths / 10.0, 1),
                    "duration_minutes": round(duration_tenths / 600.0, 4),
                }
            )
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return segments


def _pair_row(
    away_player: dict[str, Any], home_player: dict[str, Any]
) -> dict[str, Any] | None:
    segments = _overlap_segments(away_player, home_player)
    if not segments:
        return None
    shared_seconds = round(sum(item["duration_seconds"] for item in segments), 1)
    away_seconds = float(away_player.get("tracked_seconds") or 0.0)
    home_seconds = float(home_player.get("tracked_seconds") or 0.0)
    return {
        "away_player": {
            "player_id": away_player.get("player_id"),
            "player_name": away_player.get("player_name"),
            "team_key": away_player.get("team_key"),
            "team_full_name": away_player.get("team_full_name"),
            "tracked_seconds": away_seconds,
        },
        "home_player": {
            "player_id": home_player.get("player_id"),
            "player_name": home_player.get("player_name"),
            "team_key": home_player.get("team_key"),
            "team_full_name": home_player.get("team_full_name"),
            "tracked_seconds": home_seconds,
        },
        "shared_court_seconds": shared_seconds,
        "shared_court_minutes": round(shared_seconds / 60.0, 4),
        "shared_court_share_of_away_tracked_time": (
            round(shared_seconds / away_seconds, 6) if away_seconds > 0 else None
        ),
        "shared_court_share_of_home_tracked_time": (
            round(shared_seconds / home_seconds, 6) if home_seconds > 0 else None
        ),
        "overlap_segment_count": len(segments),
        "segments": segments,
        "interpretation": {
            "opposing_players_shared_court": True,
            "defender_assignment_inferred": False,
            "matchup_possessions_inferred": False,
        },
    }


def get_game_opponent_overlap(
    game_id: str,
    season: int,
    *,
    player_id: int | None = None,
) -> dict[str, Any]:
    """Return exact observed overlap between opposing-player rotation stints."""

    get_wnba_teams(season)
    if player_id is not None:
        player_id = _positive_player_id(player_id)
    try:
        rotation = get_game_rotation(game_id, season)
    except WNBARotationNotFoundError as exc:
        raise WNBAMatchupContextNotFoundError(str(exc)) from exc
    except WNBARotationUpstreamError as exc:
        raise WNBAMatchupContextUpstreamError(str(exc)) from exc

    away = rotation.get("away")
    home = rotation.get("home")
    if not isinstance(away, dict) or not isinstance(home, dict):
        raise WNBAMatchupContextUpstreamError(
            "WNBA rotation context is missing away/home team data."
        )
    away_players, home_players = away.get("players"), home.get("players")
    if not isinstance(away_players, list) or not isinstance(home_players, list):
        raise WNBAMatchupContextUpstreamError(
            "WNBA rotation context contains malformed player lists."
        )

    focal_side = None
    focal_player = None
    if player_id is not None:
        focal_side, _, focal_player = _player_side(rotation, player_id)
        if focal_side == "away":
            away_players = [focal_player]
        else:
            home_players = [focal_player]

    pairs: list[dict[str, Any]] = []
    for away_player in away_players:
        if not isinstance(away_player, dict):
            continue
        for home_player in home_players:
            if not isinstance(home_player, dict):
                continue
            pair = _pair_row(away_player, home_player)
            if pair is not None:
                pairs.append(pair)
    pairs.sort(
        key=lambda item: (
            -item["shared_court_seconds"],
            item["away_player"]["player_id"] or 0,
            item["home_player"]["player_id"] or 0,
        )
    )

    return {
        "source": rotation.get("source"),
        "source_url": rotation.get("source_url"),
        "source_endpoint": OVERLAP_SOURCE_ENDPOINT,
        "data_type": "official_rotation_opponent_court_time_overlap",
        "season": season,
        "game_id": rotation.get("game_id") or str(game_id).strip(),
        "player_id_filter": player_id,
        "focal_side": focal_side,
        "focal_player": focal_player,
        "away_team": {
            "official_team_id": away.get("official_team_id"),
            "team_key": away.get("team_key"),
            "team_full_name": away.get("team_full_name"),
        },
        "home_team": {
            "official_team_id": home.get("official_team_id"),
            "team_key": home.get("team_key"),
            "team_full_name": home.get("team_full_name"),
        },
        "pair_count": len(pairs),
        "pairs": pairs,
        "source_status": get_matchup_source_status(season),
        "verification": {
            "overlap_derived_only_from_official_rotation_intervals": True,
            "overlapping_or_touching_same_player_intervals_merged_before_pairing": True,
            "zero_duration_overlap_omitted": True,
            "shared_court_time_is_not_defender_time": True,
            "no_primary_defender_assignment_inferred": True,
            "no_matchup_possessions_inferred": True,
            "no_causal_defensive_effect_created": True,
            "no_matchup_grade_created": True,
            "no_betting_probability_created": True,
        },
    }


def _opponent_from_pair(pair: dict[str, Any], focal_side: str) -> dict[str, Any]:
    return pair["home_player"] if focal_side == "away" else pair["away_player"]


def _focal_share_from_pair(pair: dict[str, Any], focal_side: str) -> float | None:
    key = (
        "shared_court_share_of_away_tracked_time"
        if focal_side == "away"
        else "shared_court_share_of_home_tracked_time"
    )
    return pair.get(key)


def get_player_recent_opponent_overlap_context(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    opponent_player_id: int | None = None,
) -> dict[str, Any]:
    """Aggregate observed opposing-player court overlap across recent games."""

    get_wnba_teams(season)
    player_id = _positive_player_id(player_id)
    if opponent_player_id is not None:
        opponent_player_id = _positive_player_id(
            opponent_player_id, label="opponent_player_id"
        )
        if opponent_player_id == player_id:
            raise ValueError("WNBA opponent_player_id must differ from player_id.")
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)

    try:
        history = get_player_game_log_dataset(
            player_id, season, season_type=season_type
        )
    except WNBAHistoryUpstreamError as exc:
        raise WNBAMatchupContextUpstreamError(str(exc)) from exc
    games = history.get("games")
    if not isinstance(games, list):
        raise WNBAMatchupContextUpstreamError(
            "WNBA player game log returned a malformed games field."
        )
    selected = games[:last_n_games]
    if not selected:
        raise WNBAMatchupContextNotFoundError(
            f"No WNBA games were found for player {player_id} in {season}."
        )

    aggregates: dict[int, dict[str, Any]] = {}
    game_rows: list[dict[str, Any]] = []
    missing_rotation_game_ids: list[str] = []
    total_focal_tracked_seconds = 0.0
    rotation_game_count = 0

    for history_game in selected:
        gid = _clean(history_game.get("game_id"))
        if not gid:
            continue
        try:
            game = get_game_opponent_overlap(
                gid, season, player_id=player_id
            )
        except WNBAMatchupContextNotFoundError:
            missing_rotation_game_ids.append(gid)
            continue

        focal_side = game.get("focal_side")
        focal = game.get("focal_player")
        if focal_side not in {"away", "home"} or not isinstance(focal, dict):
            raise WNBAMatchupContextUpstreamError(
                "WNBA focal-player overlap context is malformed."
            )
        focal_seconds = float(focal.get("tracked_seconds") or 0.0)
        total_focal_tracked_seconds += focal_seconds
        rotation_game_count += 1

        game_pairs: list[dict[str, Any]] = []
        for pair in game.get("pairs", []):
            if not isinstance(pair, dict):
                continue
            opponent = _opponent_from_pair(pair, focal_side)
            opponent_id = opponent.get("player_id")
            if not isinstance(opponent_id, int):
                continue
            if opponent_player_id is not None and opponent_id != opponent_player_id:
                continue

            shared_seconds = float(pair.get("shared_court_seconds") or 0.0)
            aggregate = aggregates.setdefault(
                opponent_id,
                {
                    "opponent_player_id": opponent_id,
                    "opponent_player_name": opponent.get("player_name"),
                    "opponent_team_keys": [],
                    "games_with_overlap": 0,
                    "shared_court_seconds": 0.0,
                    "focal_tracked_seconds_in_overlap_games": 0.0,
                    "maximum_single_game_shared_seconds": 0.0,
                    "game_ids": [],
                },
            )
            team_key = opponent.get("team_key")
            if team_key and team_key not in aggregate["opponent_team_keys"]:
                aggregate["opponent_team_keys"].append(team_key)
            aggregate["games_with_overlap"] += 1
            aggregate["shared_court_seconds"] += shared_seconds
            aggregate["focal_tracked_seconds_in_overlap_games"] += focal_seconds
            aggregate["maximum_single_game_shared_seconds"] = max(
                aggregate["maximum_single_game_shared_seconds"], shared_seconds
            )
            aggregate["game_ids"].append(gid)
            game_pairs.append(
                {
                    "opponent_player_id": opponent_id,
                    "opponent_player_name": opponent.get("player_name"),
                    "opponent_team_key": team_key,
                    "shared_court_seconds": shared_seconds,
                    "shared_court_minutes": pair.get("shared_court_minutes"),
                    "shared_court_share_of_focal_tracked_time": _focal_share_from_pair(
                        pair, focal_side
                    ),
                    "overlap_segment_count": pair.get("overlap_segment_count"),
                }
            )

        game_rows.append(
            {
                "game_id": gid,
                "game_date": history_game.get("game_date"),
                "matchup": history_game.get("matchup"),
                "focal_side": focal_side,
                "focal_team_key": focal.get("team_key"),
                "focal_tracked_seconds": focal_seconds,
                "opponent_pair_count": len(game_pairs),
                "opponent_pairs": sorted(
                    game_pairs,
                    key=lambda item: (
                        -item["shared_court_seconds"],
                        item["opponent_player_id"],
                    ),
                ),
            }
        )

    if rotation_game_count == 0:
        raise WNBAMatchupContextNotFoundError(
            f"Official rotation overlap data were unavailable for the selected recent games for player {player_id}."
        )
    if opponent_player_id is not None and opponent_player_id not in aggregates:
        raise WNBAMatchupContextNotFoundError(
            f"No shared-court overlap was found between players {player_id} and {opponent_player_id} in the selected games."
        )

    opponents: list[dict[str, Any]] = []
    for aggregate in aggregates.values():
        shared = aggregate["shared_court_seconds"]
        denom = aggregate["focal_tracked_seconds_in_overlap_games"]
        games_count = aggregate["games_with_overlap"]
        opponents.append(
            {
                **aggregate,
                "shared_court_seconds": round(shared, 1),
                "shared_court_minutes": round(shared / 60.0, 4),
                "average_shared_seconds_per_overlap_game": round(
                    shared / games_count, 1
                ),
                "maximum_single_game_shared_seconds": round(
                    aggregate["maximum_single_game_shared_seconds"], 1
                ),
                "shared_court_share_of_focal_time_in_overlap_games": (
                    round(shared / denom, 6) if denom > 0 else None
                ),
            }
        )
    opponents.sort(
        key=lambda item: (-item["shared_court_seconds"], item["opponent_player_id"])
    )

    return {
        "source": "WNBA Stats API via official game rotation + player game log",
        "data_type": "recent_opposing_player_court_time_overlap",
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "opponent_player_id_filter": opponent_player_id,
        "requested_last_n_games": last_n_games,
        "selected_game_count": len(selected),
        "rotation_game_count": rotation_game_count,
        "missing_rotation_game_ids": missing_rotation_game_ids,
        "total_focal_tracked_seconds": round(total_focal_tracked_seconds, 1),
        "total_focal_tracked_minutes": round(total_focal_tracked_seconds / 60.0, 4),
        "unique_opponent_count": len(opponents),
        "opponents": opponents,
        "games": game_rows,
        "source_status": get_matchup_source_status(season),
        "verification": {
            "selected_games_come_from_official_player_game_log": True,
            "overlap_comes_from_official_rotation_intervals": True,
            "missing_rotation_games_are_reported_not_fabricated": True,
            "shared_court_time_is_not_defender_time": True,
            "no_primary_defender_assignment_inferred": True,
            "no_matchup_possessions_inferred": True,
            "no_causal_defensive_effect_created": True,
            "no_matchup_grade_created": True,
            "no_betting_probability_created": True,
        },
    }
