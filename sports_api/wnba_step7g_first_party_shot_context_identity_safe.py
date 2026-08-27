"""Identity-safe overlay for Step 7G first-party Step-4L player shot context.

WNBA.com ``player.latestGames`` is a useful bounded recent-game ID surface, but
its display matchup text is not authoritative enough to certify player/team
identity for every row. This overlay therefore uses latestGames only to select
exact recent regular-season game IDs, then verifies every selected game through
the official WNBA.com game-page box score before any shot is admitted.

The player must occur on exactly one box-score team, that team must match the
certified Step-4N schedule participants, and the box away/home identities must
match Step-4N. This is a stricter identity bridge; no mismatch is guessed or
repaired. Opponent-defense and current-team-vs-opponent paths continue to use
the base first-party Step-4L adapter.
"""
from __future__ import annotations

from typing import Any

import sports_api.wnba_step7g_first_party_shot_context as base
from sports_api.wnba_shot_context import (
    WNBAShotContextNotFoundError,
    WNBAShotContextUpstreamError,
)
from sports_api.wnba_step7g_first_party_history import (
    WNBAStep7GFirstPartyNotFoundError,
    WNBAStep7GFirstPartyUpstreamError,
    get_first_party_game_box_score_dataset,
)

SOURCE_VARIANT = base.SOURCE_VARIANT + "+box_score_player_identity_v1"


def _selected_recent_games_box_verified(
    player_id: int,
    season: int,
    last_n_games: int,
    schedule_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None, list[dict[str, Any]]]:
    if last_n_games == 0:
        raise WNBAShotContextNotFoundError(
            "Step 7G first-party recent player page does not certify season-to-date shot-chart completeness when last_n_games=0."
        )
    try:
        history = base.get_first_party_player_recent_game_log_dataset(
            player_id,
            season,
            season_type=base.CERTIFIED_SEASON_TYPE,
        )
    except WNBAStep7GFirstPartyNotFoundError as exc:
        raise WNBAShotContextNotFoundError(str(exc)) from exc
    except WNBAStep7GFirstPartyUpstreamError as exc:
        raise WNBAShotContextUpstreamError(str(exc)) from exc

    rows = history.get("games")
    if not isinstance(rows, list):
        raise WNBAShotContextUpstreamError("First-party player latestGames has malformed games.")

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if base._to_int(row.get("player_id")) not in {None, player_id}:
            raise WNBAShotContextUpstreamError(
                "First-party latestGames returned conflicting player identity."
            )
        game_id = base._clean(row.get("game_id"))
        if not game_id or not base._regular_game_id(game_id, season):
            continue
        if game_id in seen:
            raise WNBAShotContextUpstreamError(
                "First-party player latestGames contains duplicate regular-season game IDs."
            )
        seen.add(game_id)
        game = schedule_by_id.get(game_id)
        if game is None:
            raise WNBAShotContextUpstreamError(
                f"First-party player game {game_id} was not found in certified Step 4N schedule."
            )
        if not base._is_final_regular(game, season):
            continue
        candidates.append(game)

    candidates.sort(key=base._game_sort_key, reverse=True)
    selected = candidates[:last_n_games]
    identity_evidence: list[dict[str, Any]] = []
    names: set[str] = set()

    for game in selected:
        game_id = str(game["game_id"])
        try:
            box = get_first_party_game_box_score_dataset(game_id, season)
        except WNBAStep7GFirstPartyNotFoundError as exc:
            raise WNBAShotContextNotFoundError(str(exc)) from exc
        except WNBAStep7GFirstPartyUpstreamError as exc:
            raise WNBAShotContextUpstreamError(str(exc)) from exc

        if base._clean(box.get("game_id")) != game_id:
            raise WNBAShotContextUpstreamError(
                f"Official box score returned the wrong game ID for recent game {game_id}."
            )
        schedule_away, schedule_home = base._participants(game)
        box_away = box.get("away")
        box_home = box.get("home")
        if not isinstance(box_away, dict) or not isinstance(box_home, dict):
            raise WNBAShotContextUpstreamError(
                f"Official box score is missing away/home identity for recent game {game_id}."
            )
        if (
            base._clean(box_away.get("team_key")) != schedule_away
            or base._clean(box_home.get("team_key")) != schedule_home
        ):
            raise WNBAShotContextUpstreamError(
                f"Official box-score teams disagree with Step 4N for recent game {game_id}."
            )

        player_matches: list[tuple[str, dict[str, Any]]] = []
        for side_name, team in (("away", box_away), ("home", box_home)):
            players = team.get("players")
            if not isinstance(players, list):
                raise WNBAShotContextUpstreamError(
                    f"Official box-score {side_name} players are malformed for game {game_id}."
                )
            for row in players:
                if isinstance(row, dict) and base._to_int(row.get("player_id")) == player_id:
                    player_matches.append((side_name, row))
        if len(player_matches) != 1:
            raise WNBAShotContextUpstreamError(
                f"Player {player_id} did not resolve to exactly one official box-score team in recent game {game_id}."
            )
        side_name, player_row = player_matches[0]
        team = box_away if side_name == "away" else box_home
        player_team_key = base._clean(team.get("team_key"))
        if player_team_key not in {schedule_away, schedule_home}:
            raise WNBAShotContextUpstreamError(
                f"Player {player_id}'s box-score team is not a Step 4N participant in game {game_id}."
            )
        if player_row.get("appeared") is not True:
            raise WNBAShotContextUpstreamError(
                f"WNBA.com latestGames listed game {game_id}, but the official box score does not mark player {player_id} as appeared."
            )
        name = base._clean(player_row.get("full_name"))
        if name:
            names.add(name)
        identity_evidence.append(
            {
                "game_id": game_id,
                "player_team_key": player_team_key,
                "player_side": side_name,
                "box_schedule_away_match": True,
                "box_schedule_home_match": True,
                "player_resolved_once": True,
                "player_appeared": True,
            }
        )

    if len(names) > 1:
        raise WNBAShotContextUpstreamError(
            "Official recent-game box scores returned conflicting player names."
        )
    return selected, next(iter(names), None), identity_evidence


def get_first_party_player_shot_chart_dataset(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 0,
    opponent_team_key: str | None = None,
) -> dict[str, Any]:
    if opponent_team_key is not None:
        return base.get_first_party_player_shot_chart_dataset(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            opponent_team_key=opponent_team_key,
        )

    player_id = base._validate_player_id(player_id)
    season_type = base._validate_scope(season, season_type)
    last_n_games = base._validate_last_n(last_n_games)
    schedule_dataset, schedule_by_id = base._schedule(season)
    games, player_name, identity_evidence = _selected_recent_games_box_verified(
        player_id,
        season,
        last_n_games,
        schedule_by_id,
    )
    shots, source_urls = base._player_shots_from_games(player_id, games, season)
    observed_names = sorted(
        {row["player_name"] for row in shots if row.get("player_name")}
    )
    if len(observed_names) > 1:
        raise WNBAShotContextUpstreamError(
            "First-party shot actions returned conflicting player names."
        )
    if observed_names:
        if player_name and observed_names[0] != player_name:
            raise WNBAShotContextUpstreamError(
                "Official shot-action player name disagrees with official box-score player name."
            )
        player_name = observed_names[0]

    zones = base._aggregate_shots(shots)
    attempts = len(shots)
    made = sum(bool(row["made"]) for row in shots)
    return {
        "source": base.SOURCE,
        "source_url": base.SOURCE_URL,
        "source_urls": source_urls,
        "source_endpoint": (
            "wnba.com player latestGames IDs + game box score identity + game playByPlay + certified Step 4N schedule"
        ),
        "source_variant": SOURCE_VARIANT,
        "data_type": "official_player_shot_chart",
        "league_id": base.WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "player_name": player_name,
        "filters": {
            "last_n_games": last_n_games,
            "opponent_team_key": None,
            "opponent_official_team_id": None,
            "current_team_key_when_opponent_filter_used": None,
        },
        "retrieved_at_utc": schedule_dataset.get("retrieved_at_utc"),
        "cache_hit": bool(schedule_dataset.get("cache_hit")),
        "cache_ttl_seconds": None,
        "selected_game_count": len(games),
        "selected_game_ids": [game["game_id"] for game in games],
        "shot_count": len(shots),
        "attempt_count": attempts,
        "made_count": made,
        "field_goal_percentage": base._pct(made, attempts),
        "zone_summary": zones,
        "corner_three_composite": base._corner_composite(
            zones, "field_goals_made", "field_goals_attempted"
        ),
        "league_average_rows": [],
        "shots": shots,
        "recent_game_identity_evidence": identity_evidence,
        "derivation": {
            "game_selection": "official_player_latestGames_exact_ids",
            "player_team_identity": "official_game_box_score_cross_checked_to_certified_step4n_schedule",
            "zone_classification": "official description + preserved official legacy x/y geometry",
            "legacy_coordinate_units_preserved": True,
            "league_average_rows_not_reconstructed": True,
            "player_page_matchup_text_not_used_as_authoritative_identity": True,
            "not_a_projection": True,
        },
        "verification": {
            "requested_player_matches_all_rows": all(
                row["player_id"] == player_id for row in shots
            ),
            "shot_event_keys_unique": True,
            "all_game_ids_valid": True,
            "invalid_game_ids": [],
            "all_shot_teams_mapped_to_registry": True,
            "unmapped_shot_count": 0,
            "recent_game_box_schedule_identity_cross_checked": True,
            "recent_player_resolved_exactly_once_per_selected_box": True,
            "coordinates_preserved_in_source_units": True,
            "zone_labels_explicitly_derived_not_source_claimed": True,
            "only_certified_regular_season_game_ids_admitted": True,
            "no_model_derived_probabilities": True,
            "third_party_sources_used": False,
            "production_provider_replaced": False,
        },
    }


def get_first_party_opponent_defense_by_shot_zone_dataset(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return base.get_first_party_opponent_defense_by_shot_zone_dataset(*args, **kwargs)
