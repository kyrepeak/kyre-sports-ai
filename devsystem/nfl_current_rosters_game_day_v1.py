"""Live Step 2 roster audit for all 32 NFL teams + Atlanta game-day QB."""
from __future__ import annotations

import json

import nfl_game_day_availability_v1 as game_day
import nfl_passing_yards_identity_v1 as identity


def main() -> int:
    audit = game_day.audit_all_32_rosters()
    if not audit.get("ready"):
        bad = {
            team: row for team, row in audit["teams"].items()
            if not (row["ok"] and row["players"] >= 40 and row["skill_counts"]["QB"] >= 1)
        }
        raise AssertionError(f"32-team roster audit failed: {json.dumps(bad, sort_keys=True)}")

    atl_game = {
        "game_id": "401872933",
        "away_abbr": "CAR",
        "away_team": "Carolina Panthers",
        "home_abbr": "ATL",
        "home_team": "Atlanta Falcons",
    }
    matchup = identity.resolve_matchup_identity(atl_game, 2026)
    atl = matchup.get("home") or {}
    qb = atl.get("qb1") or {}
    if qb.get("name") != "Cooper Rush":
        raise AssertionError(
            "Atlanta game-day QB mismatch: "
            + json.dumps({
                "qb1": qb,
                "qbs": atl.get("qbs"),
                "injuries": atl.get("injuries"),
                "event_injury_http": matchup.get("event_injury_http"),
            }, default=str, sort_keys=True)
        )

    print(json.dumps({
        "teams_verified": audit["teams_verified"],
        "teams_total": audit["teams_total"],
        "atlanta_qb1": qb.get("name"),
        "atlanta_athlete_id": qb.get("athlete_id"),
        "event_injury_http": matchup.get("event_injury_http"),
    }, indent=2, sort_keys=True))
    print("NFL_CURRENT_ROSTERS_GAME_DAY_V1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
