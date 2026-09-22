"""Step 4 live NFL game-day availability audit for 2026-09-20."""
from __future__ import annotations

import json

import nfl_game_day_availability_v1 as game_day


DATE = "2026-09-20"
ATL_GAME_ID = "401872933"


def _names(rows):
    return {str(row.get("name") or "").strip() for row in rows}


def main() -> int:
    audit = game_day.audit_game_day_availability(DATE)

    if audit.get("games_total") != 14:
        raise AssertionError(f"expected 14 Sunday games, got {audit.get('games_total')}: {audit}")
    if audit.get("teams_total") != 28:
        raise AssertionError(f"expected 28 Sunday teams, got {audit.get('teams_total')}: {audit}")
    if audit.get("unverified_games") != 0:
        raise AssertionError(
            "exact-event availability provider failed for at least one game: "
            + json.dumps(audit, default=str, sort_keys=True)[:16000]
        )

    atl = next(
        (row for row in audit["games"] if row.get("game_id") == ATL_GAME_ID),
        None,
    )
    if not atl:
        raise AssertionError("Atlanta-Carolina event missing from live audit")

    atl_unavailable = _names(atl.get("home_unavailable") or [])
    if "Michael Penix Jr." not in atl_unavailable:
        raise AssertionError(
            "Michael Penix Jr. missing from exact-event unavailable data: "
            + json.dumps(atl, default=str, sort_keys=True)
        )
    if atl.get("state") != "CONFIRMED" or not atl.get("prop_gate_open"):
        raise AssertionError(
            "Atlanta-Carolina availability should be confirmed once live: "
            + json.dumps(atl, default=str, sort_keys=True)
        )

    if audit.get("confirmed_games", 0) + audit.get("pending_games", 0) != 14:
        raise AssertionError("every game must be either CONFIRMED or safely PENDING")

    print(json.dumps({
        "date": DATE,
        "games_total": audit["games_total"],
        "teams_total": audit["teams_total"],
        "confirmed_games": audit["confirmed_games"],
        "pending_games": audit["pending_games"],
        "unverified_games": audit["unverified_games"],
        "atlanta_state": atl["state"],
        "atlanta_unavailable": sorted(atl_unavailable),
    }, indent=2, sort_keys=True))
    print("NFL_GAME_DAY_INACTIVES_V1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
