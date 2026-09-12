"""Read-only live certification probe for NFL Passing Yards Step 5 V2."""
from __future__ import annotations

import json
import math

import nfl_passing_yards_identity_v1 as identity
import nfl_passing_yards_personnel_v2 as personnel

EVENT_ID = "401872925"
CUTOFF = "2026-09-13"
YEAR = 2026
SEASON_TYPE = 2


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _team(abbr: str, name: str, injury_map: dict, injury_ok: bool) -> dict:
    row = identity.resolve_team_qb_identity(abbr, name, YEAR, injury_map, injury_ok)
    assert row.get("identity_verified"), f"{abbr} QB1 identity did not verify"
    assert str(row.get("team_id") or "").isdigit(), f"{abbr} team id missing"
    return row


def _diag_row(row: dict) -> dict:
    return {
        "ready": row.get("ready"),
        "reason": row.get("reason"),
        "weapon_usage_ready": row.get("weapon_usage_ready"),
        "weapon_usage_state": row.get("weapon_usage_state"),
        "weapon_usage_games": row.get("weapon_usage_games"),
        "weapon_usage_event_ids": row.get("weapon_usage_event_ids"),
        "offense_depth_http": row.get("offense_depth_http"),
        "depth_rows_count": len(row.get("offense_depth_rows") or []),
        "depth_rows_sample": (row.get("offense_depth_rows") or [])[:12],
        "top_weapons": row.get("top_weapons") or [],
        "skill_injuries": row.get("skill_injuries") or [],
    }


def _assert_profile(row: dict, offense_id: str, defense_id: str) -> None:
    assert row.get("ready"), row.get("reason")
    assert row.get("weapon_usage_ready"), row.get("weapon_usage_state")
    assert row.get("offense_team_id") == offense_id
    assert row.get("defense_team_id") == defense_id
    assert int(row.get("weapon_usage_games") or 0) >= 1
    assert row.get("projection_adjustment") == 0.0
    assert row.get("sportsbook_influence") == 0.0
    weapons = list(row.get("top_weapons") or [])
    verified = [w for w in weapons if w.get("target_share_verified") and _finite(w.get("target_share"))]
    assert verified, f"no exact-ID weapon target share recovered: {weapons}"
    assert all(str(w.get("athlete_id") or "").isdigit() for w in weapons)
    assert all(0.0 <= float(w.get("target_share")) <= 100.0 for w in verified)


def main() -> None:
    injury_map, diag = identity.load_current_injury_map()
    assert diag.get("ok"), f"ESPN injury feed failed: {diag}"
    tb = _team("TB", "Tampa Bay Buccaneers", injury_map, True)
    cin = _team("CIN", "Cincinnati Bengals", injury_map, True)

    baker = personnel.build_personnel_matchup(tb, cin, YEAR, SEASON_TYPE, math.nan, cutoff_date=CUTOFF)
    burrow = personnel.build_personnel_matchup(cin, tb, YEAR, SEASON_TYPE, math.nan, cutoff_date=CUTOFF)
    print("STEP5_LIVE_DIAGNOSTIC " + json.dumps({"baker": _diag_row(baker), "burrow": _diag_row(burrow)}, sort_keys=True, default=str))

    _assert_profile(baker, "27", "4")
    _assert_profile(burrow, "4", "27")

    evidence = {
        "event_id": EVENT_ID,
        "cutoff": CUTOFF,
        "baker": {
            "status": baker.get("personnel_label"),
            "usage_state": baker.get("weapon_usage_state"),
            "hard_target_share": baker.get("hard_target_share"),
            "top_weapons": [
                {"athlete_id": w.get("athlete_id"), "name": w.get("name"), "position": w.get("position"), "targets": w.get("targets"), "target_share": w.get("target_share")}
                for w in (baker.get("top_weapons") or [])[:4]
            ],
        },
        "burrow": {
            "status": burrow.get("personnel_label"),
            "usage_state": burrow.get("weapon_usage_state"),
            "hard_target_share": burrow.get("hard_target_share"),
            "top_weapons": [
                {"athlete_id": w.get("athlete_id"), "name": w.get("name"), "position": w.get("position"), "targets": w.get("targets"), "target_share": w.get("target_share")}
                for w in (burrow.get("top_weapons") or [])[:4]
            ],
        },
    }
    print("NFL_PASSING_YARDS_STEP5_LIVE_GREEN")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
