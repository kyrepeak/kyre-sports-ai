"""Step 4U: projection-ready WNBA player event and floor-context features.

This layer consumes Step 4T event-lineup reconstruction and conservative
possession segments. It creates descriptive player features only. It does not
create projections, betting probabilities, official usage percentage, official
possession counts, or individual defender assignments.

Important semantics:
- co-presence is counted in feature-eligible play-by-play events, not minutes;
- possession exposure uses Step 4T derived possession segments, not an official
  possession feed;
- action shares are descriptive event-derived shares, not official USG%.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from typing import Any

from sports_api.wnba_event_lineup_context import (
    WNBAEventLineupNotFoundError,
    WNBAEventLineupUpstreamError,
    get_game_event_lineups,
    get_game_possession_event_context,
)
from sports_api.wnba_game_history import (
    ALLOWED_SEASON_TYPES,
    WNBAHistoryUpstreamError,
    get_player_game_log_dataset,
)

FEATURE_SOURCE = "WNBA Step 4T Event-Lineup + Derived Possession Context"
MAX_RECENT_GAMES = 20
_COUNT_KEYS = (
    "field_goals_attempted",
    "field_goals_made",
    "three_pointers_attempted",
    "three_pointers_made",
    "free_throws_attempted",
    "free_throws_made",
    "offensive_rebounds",
    "defensive_rebounds",
    "rebounds",
    "assists",
    "turnovers",
    "blocks",
    "personal_fouls",
    "points",
)


class WNBAPlayerEventFeatureUpstreamError(RuntimeError):
    """Raised when Step 4T/history data cannot support features safely."""


class WNBAPlayerEventFeatureNotFoundError(LookupError):
    """Raised when requested player event context is not available."""


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _positive_player_id(value: int, label: str = "player_id") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"WNBA {label} must be a positive integer.")
    return value


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _last_n(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
        or value > MAX_RECENT_GAMES
    ):
        raise ValueError("WNBA last_n_games must be an integer from 1 through 20.")
    return value


def _choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(str(value).strip().casefold())
    if result is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return result


def _empty_counts() -> dict[str, int]:
    return {key: 0 for key in _COUNT_KEYS}


def _made(action: dict[str, Any]) -> bool:
    result = (_clean(action.get("shot_result")) or "").casefold()
    return result.startswith(("made", "make"))


def _is_three(action: dict[str, Any]) -> bool:
    text = " ".join(
        value
        for value in (
            _clean(action.get("action_type")),
            _clean(action.get("sub_type")),
            _clean(action.get("description")),
        )
        if value
    ).casefold().replace("_", " ")
    if any(token in text for token in ("3pt", "3 pt", "3-point", "3 point", "three point")):
        return True
    return action.get("event_category") == "shot" and _to_int(action.get("points_scored_on_action")) == 3


def _rebound_kind(action: dict[str, Any]) -> str | None:
    text = " ".join(
        value
        for value in (_clean(action.get("sub_type")), _clean(action.get("description")))
        if value
    ).casefold().replace("_", " ")
    if "offensive" in text or text.strip() in {"off", "off rebound"}:
        return "offensive"
    if "defensive" in text or text.strip() in {"def", "def rebound"}:
        return "defensive"
    return None


def _selected(row: dict[str, Any]) -> dict[str, Any] | None:
    context = row.get("lineup_context")
    if not isinstance(context, dict):
        raise WNBAPlayerEventFeatureUpstreamError(
            "Step 4T event row is missing lineup_context."
        )
    selected = context.get("selected")
    if selected is not None and not isinstance(selected, dict):
        raise WNBAPlayerEventFeatureUpstreamError(
            "Step 4T event row contains malformed selected lineup context."
        )
    return selected


def _side_ids(selected: dict[str, Any], side: str) -> list[int]:
    raw = selected.get(side)
    if not isinstance(raw, dict):
        raise WNBAPlayerEventFeatureUpstreamError(
            f"Step 4T selected lineup is missing {side} side."
        )
    ids = raw.get("player_ids")
    if not isinstance(ids, list):
        raise WNBAPlayerEventFeatureUpstreamError(
            f"Step 4T selected {side} lineup has malformed player_ids."
        )
    result: list[int] = []
    for value in ids:
        player_id = _to_int(value)
        if player_id is None or player_id <= 0:
            raise WNBAPlayerEventFeatureUpstreamError(
                f"Step 4T selected {side} lineup contains invalid player ID."
            )
        if player_id in result:
            raise WNBAPlayerEventFeatureUpstreamError(
                f"Step 4T selected {side} lineup contains duplicate player ID."
            )
        result.append(player_id)
    return result


def _player_side(selected: dict[str, Any], player_id: int) -> str | None:
    away = _side_ids(selected, "away")
    home = _side_ids(selected, "home")
    if player_id in away and player_id in home:
        raise WNBAPlayerEventFeatureUpstreamError(
            f"Step 4T selected lineup places player {player_id} on both teams."
        )
    if player_id in away:
        return "away"
    if player_id in home:
        return "home"
    return None


def _opposite(side: str) -> str:
    if side == "away":
        return "home"
    if side == "home":
        return "away"
    raise WNBAPlayerEventFeatureUpstreamError(f"Unexpected WNBA side {side!r}.")


def _catalog(events: list[dict[str, Any]], teams: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in events:
        if not isinstance(row, dict):
            raise WNBAPlayerEventFeatureUpstreamError("Step 4T events contains malformed row.")
        selected = _selected(row)
        if selected is None:
            continue
        for side in ("away", "home"):
            side_obj = selected.get(side)
            if not isinstance(side_obj, dict):
                raise WNBAPlayerEventFeatureUpstreamError(
                    f"Step 4T selected lineup is missing {side} object."
                )
            players = side_obj.get("players")
            if not isinstance(players, list):
                raise WNBAPlayerEventFeatureUpstreamError(
                    f"Step 4T selected {side} lineup has malformed players."
                )
            team = teams.get(side)
            if not isinstance(team, dict):
                raise WNBAPlayerEventFeatureUpstreamError(
                    f"Step 4T teams object is missing {side}."
                )
            for player in players:
                if not isinstance(player, dict):
                    raise WNBAPlayerEventFeatureUpstreamError(
                        "Step 4T selected lineup contains malformed player object."
                    )
                player_id = _to_int(player.get("player_id"))
                if player_id is None or player_id <= 0:
                    raise WNBAPlayerEventFeatureUpstreamError(
                        "Step 4T selected lineup contains invalid player ID."
                    )
                item = {
                    "player_id": player_id,
                    "player_name": player.get("player_name"),
                    "side": side,
                    "official_team_id": team.get("official_team_id"),
                    "team_key": team.get("team_key"),
                    "team_full_name": team.get("team_full_name"),
                }
                previous = result.get(player_id)
                if previous is not None and (
                    previous["side"] != side
                    or previous["official_team_id"] != item["official_team_id"]
                    or previous["team_key"] != item["team_key"]
                ):
                    raise WNBAPlayerEventFeatureUpstreamError(
                        f"Step 4T event lineups contain inconsistent identity for player {player_id}."
                    )
                if previous is None or (not previous.get("player_name") and item.get("player_name")):
                    result[player_id] = item
    return result


def _add_event_counts(
    counts_by_side: dict[str, dict[str, int]],
    row: dict[str, Any],
    selected: dict[str, Any],
) -> None:
    action = row.get("event")
    if not isinstance(action, dict):
        raise WNBAPlayerEventFeatureUpstreamError("Step 4T event row is missing event object.")
    category = action.get("event_category")
    event_side = row.get("event_side")
    scoring_side = action.get("scoring_side")
    if event_side not in {None, "away", "home"}:
        raise WNBAPlayerEventFeatureUpstreamError("Step 4T event row has invalid event_side.")
    if scoring_side not in {None, "away", "home"}:
        raise WNBAPlayerEventFeatureUpstreamError("Step 4T event has invalid scoring_side.")

    if event_side in counts_by_side:
        target = counts_by_side[event_side]
        if category == "shot":
            target["field_goals_attempted"] += 1
            if _made(action):
                target["field_goals_made"] += 1
            if _is_three(action):
                target["three_pointers_attempted"] += 1
                if _made(action):
                    target["three_pointers_made"] += 1
        elif category == "free_throw":
            target["free_throws_attempted"] += 1
            if _made(action):
                target["free_throws_made"] += 1
        elif category == "rebound":
            target["rebounds"] += 1
            kind = _rebound_kind(action)
            if kind == "offensive":
                target["offensive_rebounds"] += 1
            elif kind == "defensive":
                target["defensive_rebounds"] += 1
        elif category == "turnover":
            target["turnovers"] += 1
        elif category == "foul":
            target["personal_fouls"] += 1

    points = _to_int(action.get("points_scored_on_action"))
    if scoring_side in counts_by_side and points is not None and points > 0:
        counts_by_side[scoring_side]["points"] += points

    assist_id = _to_int(action.get("assist_person_id"))
    if assist_id is not None and assist_id > 0:
        assist_side = _player_side(selected, assist_id)
        if assist_side in counts_by_side:
            counts_by_side[assist_side]["assists"] += 1

    block_id = _to_int(action.get("block_person_id"))
    if block_id is not None and block_id > 0:
        block_side = _player_side(selected, block_id)
        if block_side in counts_by_side:
            counts_by_side[block_side]["blocks"] += 1


def _add_player_action_counts(
    counts: dict[str, int],
    row: dict[str, Any],
    player_id: int,
    player_side: str,
) -> None:
    action = row.get("event")
    if not isinstance(action, dict):
        raise WNBAPlayerEventFeatureUpstreamError("Step 4T event row is missing event object.")
    category = action.get("event_category")
    actor = _to_int(action.get("person_id"))
    if actor == player_id:
        if category == "shot":
            counts["field_goals_attempted"] += 1
            if _made(action):
                counts["field_goals_made"] += 1
            if _is_three(action):
                counts["three_pointers_attempted"] += 1
                if _made(action):
                    counts["three_pointers_made"] += 1
        elif category == "free_throw":
            counts["free_throws_attempted"] += 1
            if _made(action):
                counts["free_throws_made"] += 1
        elif category == "rebound":
            counts["rebounds"] += 1
            kind = _rebound_kind(action)
            if kind == "offensive":
                counts["offensive_rebounds"] += 1
            elif kind == "defensive":
                counts["defensive_rebounds"] += 1
        elif category == "turnover":
            counts["turnovers"] += 1
        elif category == "foul":
            counts["personal_fouls"] += 1

    if _to_int(action.get("assist_person_id")) == player_id:
        counts["assists"] += 1
    if _to_int(action.get("block_person_id")) == player_id:
        counts["blocks"] += 1
    points = _to_int(action.get("points_scored_on_action"))
    if actor == player_id and action.get("scoring_side") == player_side and points is not None and points > 0:
        counts["points"] += points


def _share(numerator: int | float, denominator: int | float) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _event_action_shares(own: dict[str, int], team: dict[str, int]) -> dict[str, float | None]:
    return {
        "field_goal_attempt_share": _share(
            own["field_goals_attempted"], team["field_goals_attempted"]
        ),
        "three_point_attempt_share": _share(
            own["three_pointers_attempted"], team["three_pointers_attempted"]
        ),
        "free_throw_attempt_share": _share(
            own["free_throws_attempted"], team["free_throws_attempted"]
        ),
        "rebound_event_share": _share(own["rebounds"], team["rebounds"]),
        "assist_event_share": _share(own["assists"], team["assists"]),
        "turnover_event_share": _share(own["turnovers"], team["turnovers"]),
        "points_share": _share(own["points"], team["points"]),
    }


def _shot_profile(counts: dict[str, int]) -> dict[str, float | None]:
    fga = counts["field_goals_attempted"]
    return {
        "field_goal_percentage": _share(counts["field_goals_made"], fga),
        "three_point_attempt_rate": _share(counts["three_pointers_attempted"], fga),
        "three_point_percentage": _share(
            counts["three_pointers_made"], counts["three_pointers_attempted"]
        ),
        "free_throw_attempts_per_field_goal_attempt": _share(
            counts["free_throws_attempted"], fga
        ),
        "free_throw_percentage": _share(
            counts["free_throws_made"], counts["free_throws_attempted"]
        ),
    }


def _co_presence_rows(
    counts: Counter[int],
    catalog: dict[int, dict[str, Any]],
    denominator: int,
) -> list[dict[str, Any]]:
    rows = []
    for player_id, count in counts.items():
        identity = catalog.get(player_id, {})
        rows.append(
            {
                "player_id": player_id,
                "player_name": identity.get("player_name"),
                "team_key": identity.get("team_key"),
                "shared_feature_eligible_event_count": count,
                "share_of_focal_player_feature_eligible_events": _share(count, denominator),
            }
        )
    rows.sort(
        key=lambda item: (
            -item["shared_feature_eligible_event_count"],
            item["player_name"] or "",
            item["player_id"],
        )
    )
    return rows


def _lineup_rows(
    counts: Counter[tuple[tuple[int, ...], tuple[int, ...]]],
    player_side: str,
    catalog: dict[int, dict[str, Any]],
    denominator: int,
) -> list[dict[str, Any]]:
    rows = []
    for (away_ids, home_ids), count in counts.items():
        own_ids = away_ids if player_side == "away" else home_ids
        opponent_ids = home_ids if player_side == "away" else away_ids
        rows.append(
            {
                "own_team_player_ids": list(own_ids),
                "opponent_player_ids": list(opponent_ids),
                "own_team_players": [
                    {
                        "player_id": pid,
                        "player_name": catalog.get(pid, {}).get("player_name"),
                    }
                    for pid in own_ids
                ],
                "opponent_players": [
                    {
                        "player_id": pid,
                        "player_name": catalog.get(pid, {}).get("player_name"),
                    }
                    for pid in opponent_ids
                ],
                "feature_eligible_event_count": count,
                "share_of_focal_player_feature_eligible_events": _share(count, denominator),
            }
        )
    rows.sort(
        key=lambda item: (
            -item["feature_eligible_event_count"],
            item["own_team_player_ids"],
            item["opponent_player_ids"],
        )
    )
    return rows


def _possession_exposure(
    player_id: int,
    player_side: str,
    event_rows: list[dict[str, Any]],
    possessions: list[dict[str, Any]],
) -> dict[str, Any]:
    by_index: dict[int, dict[str, Any]] = {}
    for row in event_rows:
        source_index = _to_int(row.get("source_index"))
        if source_index is None or source_index < 0 or source_index in by_index:
            raise WNBAPlayerEventFeatureUpstreamError(
                "Step 4T event rows contain invalid/duplicate source_index."
            )
        by_index[source_index] = row

    stable_complete = 0
    stable_incomplete = 0
    offense_count = defense_count = 0
    offense_points = defense_points_allowed = 0
    unstable_presence = 0
    ineligible = 0

    for possession in possessions:
        if not isinstance(possession, dict):
            raise WNBAPlayerEventFeatureUpstreamError(
                "Step 4T possessions contains malformed possession."
            )
        refs = possession.get("event_refs")
        if not isinstance(refs, list) or not refs:
            raise WNBAPlayerEventFeatureUpstreamError(
                "Step 4T possession contains malformed event_refs."
            )
        rows = []
        for ref in refs:
            if not isinstance(ref, dict):
                raise WNBAPlayerEventFeatureUpstreamError(
                    "Step 4T possession contains malformed event ref."
                )
            source_index = _to_int(ref.get("source_index"))
            if source_index is None or source_index not in by_index:
                raise WNBAPlayerEventFeatureUpstreamError(
                    "Step 4T possession references an event outside the event-lineup dataset."
                )
            rows.append(by_index[source_index])

        eligibility = []
        presence = []
        sides = []
        for row in rows:
            context = row.get("lineup_context")
            if not isinstance(context, dict):
                raise WNBAPlayerEventFeatureUpstreamError(
                    "Step 4T possession event is missing lineup context."
                )
            eligibility.append(bool(context.get("eligible_for_player_event_features")))
            selected = _selected(row)
            side = _player_side(selected, player_id) if selected is not None else None
            presence.append(side is not None)
            sides.append(side)

        if not all(eligibility):
            if any(presence):
                ineligible += 1
            continue
        if any(presence) and not all(presence):
            unstable_presence += 1
            continue
        if not all(presence):
            continue
        if any(side != player_side for side in sides):
            raise WNBAPlayerEventFeatureUpstreamError(
                f"Step 4T possession lineups change team side for player {player_id}."
            )

        complete = bool(possession.get("complete"))
        if not complete:
            stable_incomplete += 1
            continue

        stable_complete += 1
        offense_side = possession.get("offense_side")
        points = _to_int(possession.get("points_scored_by_offense")) or 0
        if points < 0:
            raise WNBAPlayerEventFeatureUpstreamError(
                "Step 4T possession contains negative offense points."
            )
        if offense_side == player_side:
            offense_count += 1
            offense_points += points
        elif offense_side == _opposite(player_side):
            defense_count += 1
            defense_points_allowed += points

    return {
        "classification": "conservative_derived_possession_exposure",
        "stable_complete_segment_count": stable_complete,
        "stable_incomplete_segment_count": stable_incomplete,
        "stable_complete_offensive_segment_count": offense_count,
        "stable_complete_defensive_segment_count": defense_count,
        "unstable_player_presence_segment_count": unstable_presence,
        "player_present_but_lineup_ineligible_segment_count": ineligible,
        "offensive_points_in_stable_complete_segments": offense_points,
        "defensive_points_allowed_in_stable_complete_segments": defense_points_allowed,
        "offensive_points_per_100_stable_complete_segments": (
            round(offense_points * 100.0 / offense_count, 4) if offense_count else None
        ),
        "defensive_points_allowed_per_100_stable_complete_segments": (
            round(defense_points_allowed * 100.0 / defense_count, 4)
            if defense_count else None
        ),
        "guardrails": {
            "segments_are_derived_not_official_possessions": True,
            "rates_are_per_100_derived_segments_not_official_ratings": True,
            "segments_with_mid_segment_player_presence_change_are_excluded": True,
            "segments_with_ineligible_lineup_events_are_excluded": True,
        },
    }


def _player_features(
    identity: dict[str, Any],
    events: list[dict[str, Any]],
    possessions: list[dict[str, Any]],
    catalog: dict[int, dict[str, Any]],
    teams: dict[str, Any],
) -> dict[str, Any]:
    player_id = identity["player_id"]
    player_side = identity["side"]
    opponent_side = _opposite(player_side)
    own = _empty_counts()
    by_side = {"away": _empty_counts(), "home": _empty_counts()}
    teammate_counts: Counter[int] = Counter()
    opponent_counts: Counter[int] = Counter()
    lineup_counts: Counter[tuple[tuple[int, ...], tuple[int, ...]]] = Counter()
    selected_event_count = 0
    eligible_event_count = 0

    for row in events:
        selected = _selected(row)
        if selected is None:
            continue
        side = _player_side(selected, player_id)
        if side is None:
            continue
        if side != player_side:
            raise WNBAPlayerEventFeatureUpstreamError(
                f"Step 4T event lineups change team side for player {player_id}."
            )
        selected_event_count += 1
        context = row.get("lineup_context")
        if not isinstance(context, dict):
            raise WNBAPlayerEventFeatureUpstreamError("Step 4T event is missing lineup context.")
        if not context.get("eligible_for_player_event_features"):
            continue
        eligible_event_count += 1
        _add_event_counts(by_side, row, selected)
        _add_player_action_counts(own, row, player_id, player_side)
        own_ids = _side_ids(selected, player_side)
        opponent_ids = _side_ids(selected, opponent_side)
        for teammate_id in own_ids:
            if teammate_id != player_id:
                teammate_counts[teammate_id] += 1
        for opponent_id in opponent_ids:
            opponent_counts[opponent_id] += 1
        away_ids = tuple(sorted(_side_ids(selected, "away")))
        home_ids = tuple(sorted(_side_ids(selected, "home")))
        lineup_counts[(away_ids, home_ids)] += 1

    if selected_event_count == 0:
        raise WNBAPlayerEventFeatureNotFoundError(
            f"Player {player_id} did not appear in any reconstructed Step 4T event lineup."
        )

    team_counts = by_side[player_side]
    opponent_counts_environment = by_side[opponent_side]
    team = teams.get(player_side)
    opponent = teams.get(opponent_side)
    if not isinstance(team, dict) or not isinstance(opponent, dict):
        raise WNBAPlayerEventFeatureUpstreamError(
            "Step 4T teams object is incomplete for player feature construction."
        )

    return {
        "player": deepcopy(identity),
        "team": deepcopy(team),
        "opponent": deepcopy(opponent),
        "data_quality": {
            "selected_lineup_event_count": selected_event_count,
            "feature_eligible_event_count": eligible_event_count,
            "feature_eligible_share_of_selected_lineup_events": _share(
                eligible_event_count, selected_event_count
            ),
            "feature_eligible_event_definition": (
                "Step 4T selected exact 5v5 lineup, no duplicate active intervals, "
                "known event participants consistent with selected court, and no ambiguous boundary."
            ),
        },
        "own_event_counts": own,
        "own_shot_profile": _shot_profile(own),
        "on_court_event_environment": {
            "team": team_counts,
            "opponent": opponent_counts_environment,
            "action_shares_of_team_events": _event_action_shares(own, team_counts),
            "team_shot_profile": _shot_profile(team_counts),
            "opponent_shot_profile": _shot_profile(opponent_counts_environment),
            "semantics": "Counts include only Step 4T feature-eligible events while the focal player was on court.",
        },
        "co_presence": {
            "teammates": _co_presence_rows(
                teammate_counts, catalog, eligible_event_count
            ),
            "opponents": _co_presence_rows(
                opponent_counts, catalog, eligible_event_count
            ),
            "semantics": "Shared counts are feature-eligible play-by-play events, not shared minutes.",
        },
        "lineup_event_context": {
            "unique_lineup_count": len(lineup_counts),
            "lineups": _lineup_rows(
                lineup_counts, player_side, catalog, eligible_event_count
            ),
            "semantics": "Lineup frequency is measured by eligible event observations, not duration.",
        },
        "derived_possession_exposure": _possession_exposure(
            player_id, player_side, events, possessions
        ),
        "guardrails": {
            "features_are_observed_descriptive_inputs_not_projections": True,
            "action_shares_are_not_official_usage_percentage": True,
            "co_presence_events_are_not_shared_minutes": True,
            "derived_possession_segments_are_not_official_possessions": True,
            "court_context_is_not_defender_assignment": True,
            "no_primary_defender_assignment_inferred": True,
            "no_player_vs_defender_possession_inferred": True,
            "no_causal_defensive_effect_created": True,
            "no_projection_created": True,
            "no_betting_probability_created": True,
        },
    }


def _game_sources(game_id: str, season: int) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        events = get_game_event_lineups(
            game_id,
            season,
            event_category="All",
            limit=0,
        )
        possessions = get_game_possession_event_context(game_id, season, limit=0)
    except WNBAEventLineupNotFoundError as exc:
        raise WNBAPlayerEventFeatureNotFoundError(str(exc)) from exc
    except WNBAEventLineupUpstreamError as exc:
        raise WNBAPlayerEventFeatureUpstreamError(str(exc)) from exc
    if _clean(events.get("game_id")) != game_id or _clean(possessions.get("game_id")) != game_id:
        raise WNBAPlayerEventFeatureUpstreamError(
            "Step 4T event-lineup/possession game IDs do not match the requested game."
        )
    return events, possessions


def get_game_player_event_features(
    game_id: str,
    season: int,
    *,
    player_id: int | None = None,
) -> dict[str, Any]:
    game_id = _game_id(game_id)
    if player_id is not None:
        player_id = _positive_player_id(player_id)
    event_dataset, possession_dataset = _game_sources(game_id, season)
    events = event_dataset.get("events")
    possessions = possession_dataset.get("possessions")
    teams = event_dataset.get("teams")
    possession_teams = possession_dataset.get("teams")
    if not isinstance(events, list) or not isinstance(possessions, list):
        raise WNBAPlayerEventFeatureUpstreamError(
            "Step 4T datasets contain malformed event/possession collections."
        )
    if not isinstance(teams, dict) or not isinstance(possession_teams, dict):
        raise WNBAPlayerEventFeatureUpstreamError("Step 4T datasets are missing teams.")
    for side in ("away", "home"):
        if teams.get(side) != possession_teams.get(side):
            raise WNBAPlayerEventFeatureUpstreamError(
                "Step 4T event-lineup and possession team identities do not agree."
            )

    catalog = _catalog(events, teams)
    if player_id is not None:
        identity = catalog.get(player_id)
        if identity is None:
            raise WNBAPlayerEventFeatureNotFoundError(
                f"Player {player_id} was not observed in reconstructed Step 4T event lineups for game {game_id}."
            )
        player_ids = [player_id]
    else:
        player_ids = sorted(catalog)
        if not player_ids:
            raise WNBAPlayerEventFeatureNotFoundError(
                f"No players were observed in reconstructed Step 4T event lineups for game {game_id}."
            )

    players = [
        _player_features(catalog[pid], events, possessions, catalog, teams)
        for pid in player_ids
    ]
    return {
        "source": FEATURE_SOURCE,
        "data_type": "observed_player_event_floor_context_features",
        "season": season,
        "game_id": game_id,
        "player_id_filter": player_id,
        "source_datasets": {
            "event_lineups": {
                "source": event_dataset.get("source"),
                "data_type": event_dataset.get("data_type"),
                "source_action_count": event_dataset.get("source_action_count"),
                "feature_eligible_event_count": event_dataset.get("feature_eligible_event_count"),
            },
            "possessions": {
                "source": possession_dataset.get("source"),
                "data_type": possession_dataset.get("data_type"),
                "possession_count": possession_dataset.get("possession_count"),
                "complete_possession_count": possession_dataset.get("complete_possession_count"),
            },
        },
        "teams": deepcopy(teams),
        "player_count": len(players),
        "players": players,
        "verification": {
            "requested_game_id_matches_step_4t_sources": True,
            "event_and_possession_team_identities_agree": True,
            "features_use_only_step_4t_feature_eligible_events": True,
            "action_shares_are_labeled_descriptive_not_official_usage": True,
            "co_presence_is_event_count_not_minutes": True,
            "derived_possession_exposure_is_not_official_possession_count": True,
            "court_context_is_not_defender_assignment": True,
            "no_primary_defender_assignment_inferred": True,
            "no_player_vs_defender_possession_inferred": True,
            "no_projection_created": True,
            "no_betting_probability_created": True,
        },
    }


def _sum_counts(items: list[dict[str, int]]) -> dict[str, int]:
    total = _empty_counts()
    for item in items:
        for key in _COUNT_KEYS:
            value = item.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise WNBAPlayerEventFeatureUpstreamError(
                    f"Step 4U game feature has invalid count for {key}."
                )
            total[key] += value
    return total


def _aggregate_co_presence(
    games: list[dict[str, Any]],
    relation: str,
    total_eligible_events: int,
) -> list[dict[str, Any]]:
    counts: Counter[int] = Counter()
    game_counts: Counter[int] = Counter()
    names: dict[int, str | None] = {}
    team_keys: dict[int, str | None] = {}
    for game in games:
        rows = game["features"]["co_presence"].get(relation)
        if not isinstance(rows, list):
            raise WNBAPlayerEventFeatureUpstreamError(
                f"Step 4U game feature has malformed {relation} co-presence rows."
            )
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise WNBAPlayerEventFeatureUpstreamError("Step 4U co-presence row is malformed.")
            player_id = _to_int(row.get("player_id"))
            count = _to_int(row.get("shared_feature_eligible_event_count"))
            if player_id is None or player_id <= 0 or count is None or count < 0:
                raise WNBAPlayerEventFeatureUpstreamError("Step 4U co-presence row contains invalid values.")
            counts[player_id] += count
            if player_id not in seen and count > 0:
                game_counts[player_id] += 1
                seen.add(player_id)
            if row.get("player_name"):
                names[player_id] = row.get("player_name")
            if row.get("team_key"):
                team_keys[player_id] = row.get("team_key")
    result = [
        {
            "player_id": player_id,
            "player_name": names.get(player_id),
            "team_key": team_keys.get(player_id),
            "shared_feature_eligible_event_count": count,
            "games_observed_together": game_counts[player_id],
            "share_of_focal_player_feature_eligible_events": _share(
                count, total_eligible_events
            ),
        }
        for player_id, count in counts.items()
    ]
    result.sort(
        key=lambda item: (
            -item["shared_feature_eligible_event_count"],
            -item["games_observed_together"],
            item["player_name"] or "",
            item["player_id"],
        )
    )
    return result


def _sum_possession_exposure(games: list[dict[str, Any]]) -> dict[str, Any]:
    keys = (
        "stable_complete_segment_count",
        "stable_incomplete_segment_count",
        "stable_complete_offensive_segment_count",
        "stable_complete_defensive_segment_count",
        "unstable_player_presence_segment_count",
        "player_present_but_lineup_ineligible_segment_count",
        "offensive_points_in_stable_complete_segments",
        "defensive_points_allowed_in_stable_complete_segments",
    )
    total = {key: 0 for key in keys}
    for game in games:
        exposure = game["features"].get("derived_possession_exposure")
        if not isinstance(exposure, dict):
            raise WNBAPlayerEventFeatureUpstreamError(
                "Step 4U game feature is missing derived possession exposure."
            )
        for key in keys:
            value = _to_int(exposure.get(key))
            if value is None or value < 0:
                raise WNBAPlayerEventFeatureUpstreamError(
                    f"Step 4U possession exposure has invalid {key}."
                )
            total[key] += value
    offense = total["stable_complete_offensive_segment_count"]
    defense = total["stable_complete_defensive_segment_count"]
    return {
        "classification": "conservative_derived_possession_exposure",
        **total,
        "offensive_points_per_100_stable_complete_segments": (
            round(total["offensive_points_in_stable_complete_segments"] * 100.0 / offense, 4)
            if offense else None
        ),
        "defensive_points_allowed_per_100_stable_complete_segments": (
            round(total["defensive_points_allowed_in_stable_complete_segments"] * 100.0 / defense, 4)
            if defense else None
        ),
        "guardrails": {
            "segments_are_derived_not_official_possessions": True,
            "rates_are_per_100_derived_segments_not_official_ratings": True,
        },
    }


def get_player_recent_event_feature_context(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)
    try:
        history = get_player_game_log_dataset(
            player_id,
            season,
            season_type=season_type,
        )
    except WNBAHistoryUpstreamError as exc:
        raise WNBAPlayerEventFeatureUpstreamError(str(exc)) from exc
    games = history.get("games")
    if not isinstance(games, list):
        raise WNBAPlayerEventFeatureUpstreamError(
            "WNBA player game log returned malformed games collection."
        )
    selected = games[:last_n_games]
    if not selected:
        raise WNBAPlayerEventFeatureNotFoundError(
            f"No WNBA games were found for player {player_id} in {season}."
        )

    rows = []
    missing = []
    team_keys = []
    opponent_keys = []
    for history_game in selected:
        if not isinstance(history_game, dict):
            raise WNBAPlayerEventFeatureUpstreamError(
                "WNBA player game log contains malformed game row."
            )
        gid = _clean(history_game.get("game_id"))
        if gid is None or len(gid) != 10 or not gid.isdigit():
            raise WNBAPlayerEventFeatureUpstreamError(
                "WNBA player game log contains invalid game ID in selected recent window."
            )
        try:
            game_features = get_game_player_event_features(
                gid,
                season,
                player_id=player_id,
            )
        except WNBAPlayerEventFeatureNotFoundError:
            missing.append(gid)
            continue
        player_rows = game_features.get("players")
        if not isinstance(player_rows, list) or len(player_rows) != 1:
            raise WNBAPlayerEventFeatureUpstreamError(
                "Targeted Step 4U game feature response did not contain exactly one player."
            )
        features = player_rows[0]
        if features.get("player", {}).get("player_id") != player_id:
            raise WNBAPlayerEventFeatureUpstreamError(
                "Targeted Step 4U game feature returned the wrong player ID."
            )
        matchup = history_game.get("matchup")
        if isinstance(matchup, dict):
            history_team = matchup.get("team_key")
            history_opponent = matchup.get("opponent_team_key")
            feature_team = features.get("team", {}).get("team_key")
            feature_opponent = features.get("opponent", {}).get("team_key")
            if history_team is not None and feature_team != history_team:
                raise WNBAPlayerEventFeatureUpstreamError(
                    f"Step 4U team identity for player {player_id} does not match official game log for {gid}."
                )
            if history_opponent is not None and feature_opponent != history_opponent:
                raise WNBAPlayerEventFeatureUpstreamError(
                    f"Step 4U opponent identity for player {player_id} does not match official game log for {gid}."
                )
        team_key = features.get("team", {}).get("team_key")
        opponent_key = features.get("opponent", {}).get("team_key")
        if team_key and team_key not in team_keys:
            team_keys.append(team_key)
        if opponent_key and opponent_key not in opponent_keys:
            opponent_keys.append(opponent_key)
        rows.append(
            {
                "game_id": gid,
                "game_date": history_game.get("game_date"),
                "matchup": deepcopy(matchup),
                "features": features,
            }
        )

    if not rows:
        raise WNBAPlayerEventFeatureNotFoundError(
            f"Step 4U event features were unavailable for the selected recent games for player {player_id}."
        )

    own = _sum_counts([row["features"]["own_event_counts"] for row in rows])
    team_environment = _sum_counts(
        [row["features"]["on_court_event_environment"]["team"] for row in rows]
    )
    opponent_environment = _sum_counts(
        [row["features"]["on_court_event_environment"]["opponent"] for row in rows]
    )
    selected_lineup_events = sum(
        row["features"]["data_quality"]["selected_lineup_event_count"] for row in rows
    )
    eligible_events = sum(
        row["features"]["data_quality"]["feature_eligible_event_count"] for row in rows
    )

    return {
        "source": FEATURE_SOURCE,
        "data_type": "official_recent_player_event_floor_context_features",
        "season": season,
        "season_type": season_type,
        "player_id": player_id,
        "requested_last_n_games": last_n_games,
        "selected_game_count": len(selected),
        "feature_game_count": len(rows),
        "missing_feature_game_ids": missing,
        "team_keys_observed": team_keys,
        "opponent_team_keys_observed": opponent_keys,
        "aggregate": {
            "data_quality": {
                "selected_lineup_event_count": selected_lineup_events,
                "feature_eligible_event_count": eligible_events,
                "feature_eligible_share_of_selected_lineup_events": _share(
                    eligible_events, selected_lineup_events
                ),
            },
            "own_event_counts": own,
            "own_shot_profile": _shot_profile(own),
            "on_court_event_environment": {
                "team": team_environment,
                "opponent": opponent_environment,
                "action_shares_of_team_events": _event_action_shares(
                    own, team_environment
                ),
                "team_shot_profile": _shot_profile(team_environment),
                "opponent_shot_profile": _shot_profile(opponent_environment),
            },
            "co_presence": {
                "teammates": _aggregate_co_presence(rows, "teammates", eligible_events),
                "opponents": _aggregate_co_presence(rows, "opponents", eligible_events),
                "semantics": "Shared counts are feature-eligible play-by-play events, not shared minutes.",
            },
            "derived_possession_exposure": _sum_possession_exposure(rows),
        },
        "games": rows,
        "verification": {
            "selected_games_come_from_official_player_game_log": True,
            "available_games_use_step_4t_event_lineups_and_possessions": True,
            "official_game_log_team_identity_checked_when_available": True,
            "features_use_only_step_4t_feature_eligible_events": True,
            "action_shares_are_labeled_descriptive_not_official_usage": True,
            "co_presence_is_event_count_not_minutes": True,
            "derived_possession_exposure_is_not_official_possession_count": True,
            "court_context_is_not_defender_assignment": True,
            "no_primary_defender_assignment_inferred": True,
            "no_player_vs_defender_possession_inferred": True,
            "no_projection_created": True,
            "no_betting_probability_created": True,
        },
    }
