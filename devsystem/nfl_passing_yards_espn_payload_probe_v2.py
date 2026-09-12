"""Diagnostic V2 for ESPN NFL Passing Yards source shape and UTC recovery."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import nfl_passing_yards_defense_v1 as defense
import nfl_passing_yards_defense_v3 as defense_v3
import nfl_passing_yards_environment_v1 as environment
import nfl_passing_yards_espn_stat_split_v1 as stats

OUTPUT = os.path.join(ROOT, "nfl_passing_yards_espn_payload_probe_v2.json")


def category_summary(payload: dict) -> list[dict]:
    splits = (payload or {}).get("splits") or {}
    categories = splits.get("categories") if isinstance(splits, dict) else []
    out = []
    for category in categories or []:
        if not isinstance(category, dict):
            continue
        rows = []
        for stat in category.get("stats") or []:
            if not isinstance(stat, dict):
                continue
            rows.append({
                "name": stat.get("name"),
                "displayName": stat.get("displayName"),
                "abbreviation": stat.get("abbreviation"),
                "value": stat.get("value"),
                "displayValue": stat.get("displayValue"),
                "perGameValue": stat.get("perGameValue"),
            })
        out.append({
            "name": category.get("name"),
            "displayName": category.get("displayName"),
            "abbreviation": category.get("abbreviation"),
            "stats": rows,
        })
    return out


def main() -> None:
    report = {"athletes": {}, "teams": {}}

    for name, athlete_id in (("Baker Mayfield", "3052587"), ("Joe Burrow", "3915511")):
        payload, diag = stats.athlete_stats_payload(2025, 2, athlete_id)
        report["athletes"][name] = {"diag": diag, "categories": category_summary(payload)}

    for name, team_id in (("Tampa Bay Buccaneers", "27"), ("Cincinnati Bengals", "4")):
        payload, diag = stats.team_stats_payload(2025, 2, team_id)
        parsed_defense = defense.parse_season_pass_defense(payload)
        recovered_season, recovered_rows, recovered_diag = defense_v3._verified_boxscore_season(
            team_id,
            2025,
            2,
            "2026-09-13",
            partial_season=parsed_defense,
        )
        report["teams"][name] = {
            "diag": diag,
            "categories": category_summary(payload),
            "parsed_defense": parsed_defense,
            "parsed_pace": environment.parse_team_pace(payload),
            "boxscore_recovery_diag": recovered_diag,
            "boxscore_recovered_season": recovered_season,
            "boxscore_recovered_rows": recovered_rows,
        }

    with open(OUTPUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    print(f"WROTE_DIAGNOSTIC={OUTPUT}")


if __name__ == "__main__":
    main()
