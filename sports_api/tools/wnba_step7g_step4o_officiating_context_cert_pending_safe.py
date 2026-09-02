"""Pending-assignment-safe wrapper for the Step 7G Step-4O live cert.

Frozen Step 4O treats an empty current-game officials list as a valid assignment
state when names have not yet been published. This wrapper aligns those pending
semantics and the exact frozen profile field names; every other underlying live
certificate requirement remains unchanged.
"""
from __future__ import annotations

from typing import Any

from sports_api.tools import wnba_step7g_step4o_officiating_context_cert as base


def _assert_official_assignment(
    assignment: dict[str, Any],
    *,
    game_id: str,
    away_key: str,
    home_key: str,
) -> None:
    if assignment.get("data_type") != "official_game_official_assignment":
        raise RuntimeError("Step 4O official assignment returned wrong data type.")
    if assignment.get("game_id") != game_id:
        raise RuntimeError("Step 4O official assignment returned wrong game ID.")
    if (assignment.get("away") or {}).get("team_key") != away_key:
        raise RuntimeError("Step 4O official assignment returned wrong away team.")
    if (assignment.get("home") or {}).get("team_key") != home_key:
        raise RuntimeError("Step 4O official assignment returned wrong home team.")

    officials = assignment.get("officials")
    if not isinstance(officials, list):
        raise RuntimeError("Step 4O official rows are malformed.")
    if assignment.get("official_count") != len(officials):
        raise RuntimeError("Step 4O official_count disagrees with official rows.")
    if assignment.get("officials_available") is not bool(officials):
        raise RuntimeError("Step 4O officials_available disagrees with official rows.")

    expected_status = (
        "assigned_from_official_wnba_game_page"
        if officials
        else "not_available_from_official_wnba_game_page"
    )
    if assignment.get("assignment_status") != expected_status:
        raise RuntimeError(
            f"Step 4O assignment status does not match current rows: {assignment.get('assignment_status')!r}."
        )

    person_ids: list[int] = []
    for row in officials:
        if not isinstance(row, dict):
            raise RuntimeError("Step 4O official row is malformed.")
        person_id = row.get("person_id")
        name = str(row.get("name") or "").strip()
        if not isinstance(person_id, int) or isinstance(person_id, bool) or person_id <= 0:
            raise RuntimeError(f"Step 4O official person ID is invalid: {person_id!r}.")
        if not name:
            raise RuntimeError("Step 4O official name is blank.")
        person_ids.append(person_id)
    if len(person_ids) != len(set(person_ids)):
        raise RuntimeError("Step 4O official person IDs are not unique.")

    verification = assignment.get("verification") or {}
    if verification.get("current_page_teams_match_certified_schedule") is not True:
        raise RuntimeError("Step 4O current page did not verify against certified schedule.")
    if verification.get("official_person_ids_unique") is not True:
        raise RuntimeError("Step 4O official identity uniqueness is not verified.")
    if verification.get("official_names_present_for_returned_rows") is not True:
        raise RuntimeError("Step 4O returned an unnamed official row.")
    if not officials and verification.get("pending_assignment_is_valid_frozen_step4o_state") is not True:
        raise RuntimeError("Step 4O pending assignment did not preserve frozen pending semantics.")
    if verification.get("third_party_sources_used") is not False:
        raise RuntimeError("Step 4O official assignment used a third-party source.")
    if verification.get("referee_tendencies_or_bias_inferred") is not False:
        raise RuntimeError("Step 4O improperly inferred referee tendencies or bias.")


def _assert_team_context(
    context: dict[str, Any],
    *,
    expected_team_key: str,
    label: str,
) -> dict[str, Any]:
    if context.get("data_type") != "observed_team_foul_free_throw_context":
        raise RuntimeError(f"{label} returned wrong team context data type.")
    team = context.get("team")
    profile = context.get("profile")
    league_context = context.get("league_context")
    verification = context.get("verification")
    if not isinstance(team, dict) or team.get("team_key") != expected_team_key:
        raise RuntimeError(f"{label} team identity disagrees with selected game.")
    if not isinstance(profile, dict):
        raise RuntimeError(f"{label} profile is missing.")
    if not isinstance(league_context, dict):
        raise RuntimeError(f"{label} league context is missing.")
    if not isinstance(verification, dict):
        raise RuntimeError(f"{label} verification is missing.")

    # Exact frozen Step-4O output key is field_goal_attempts (singular goal),
    # even though its source stat key is field_goals_attempted.
    for field in (
        "minutes",
        "field_goal_attempts",
        "free_throws_made",
        "free_throws_attempted",
        "personal_fouls",
        "personal_fouls_drawn",
        "points",
    ):
        base._numeric(profile.get(field), f"{label}.profile.{field}")
    ft_pct = profile.get("free_throw_percentage")
    if ft_pct is not None and not 0.0 <= base._numeric(
        ft_pct, f"{label}.profile.free_throw_percentage"
    ) <= 1.0:
        raise RuntimeError(f"{label} free-throw percentage is outside fraction units.")
    if abs(base._numeric(profile.get("minutes"), f"{label}.minutes") - 40.0) > 5.01:
        raise RuntimeError(f"{label} team-clock minutes are implausible for recent WNBA games.")

    for key in (
        "personal_fouls_drawn_equals_paired_opponent_personal_fouls",
        "team_clock_minutes_normalized_from_five_player_box_total",
    ):
        if verification.get(key) is not True:
            raise RuntimeError(f"{label} verification flag {key} is not true.")
    if verification.get("third_party_sources_used") is not False:
        raise RuntimeError(f"{label} whistle context used a third-party source.")

    for metric in (
        "free_throws_attempted_per_game",
        "personal_fouls_per_game",
        "personal_fouls_drawn_per_game",
    ):
        row = league_context.get(metric)
        if not isinstance(row, dict):
            raise RuntimeError(f"{label}.{metric} league measure is missing.")
        base._numeric(row.get("value"), f"{label}.{metric}.value")
        base._numeric(row.get("league_average"), f"{label}.{metric}.league_average")
        rank = row.get("higher_value_rank")
        count = row.get("league_team_count")
        if not isinstance(rank, int) or not 1 <= rank <= 15:
            raise RuntimeError(f"{label}.{metric} rank is invalid: {rank!r}.")
        if count != 15:
            raise RuntimeError(f"{label}.{metric} league count is not 15: {count!r}.")

    base._assert_regular_ids(context, label)
    return profile


base._assert_official_assignment = _assert_official_assignment
base._assert_team_context = _assert_team_context


if __name__ == "__main__":
    raise SystemExit(base.main())
