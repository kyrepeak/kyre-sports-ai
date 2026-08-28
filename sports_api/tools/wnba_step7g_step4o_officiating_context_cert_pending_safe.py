"""Pending-assignment-safe wrapper for the Step 7G Step-4O live cert.

Frozen Step 4O treats an empty current-game officials list as a valid assignment
state when names have not yet been published. This wrapper changes only that
assertion; the underlying candidate cert still requires the full first-party
whistle environment, real FastAPI Officiating PASS, previously certified Shot /
Advanced / Availability PASS, zero blockers, and all production switches OFF.
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


base._assert_official_assignment = _assert_official_assignment


if __name__ == "__main__":
    raise SystemExit(base.main())
