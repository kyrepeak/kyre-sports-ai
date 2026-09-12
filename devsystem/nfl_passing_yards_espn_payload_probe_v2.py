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


def boxscore_shape(summary: dict) -> list[dict]:
    """Keep only the exact team/stat fields needed to diagnose the parser."""
    out = []
    for team_row in ((summary or {}).get("boxscore") or {}).get("teams") or []:
        if not isinstance(team_row, dict):
            continue
        team = team_row.get("team") or {}
        stat_rows = []
        for stat in team_row.get("statistics") or []:
            if not isinstance(stat, dict):
                continue
            stat_rows.append({
                "name": stat.get("name"),
                "label": stat.get("label"),
                "abbreviation": stat.get("abbreviation"),
                "value": stat.get("value"),
                "displayValue": stat.get("displayValue"),
            })
        out.append({
            "team_id": team.get("id"),
            "team_name": team.get("displayName") or team.get("name"),
            "statistics": stat_rows,
        })
    return out


def sample_event_probe(team_id: str) -> dict:
    schedule, schedule_diag = defense._team_schedule_payload(2025, 2, team_id)
    events = defense_v3._completed_event_rows_utc(schedule, "2026-09-13", max_games=25) if schedule_diag.get("ok") else []
    if not events:
        return {"schedule_diag": schedule_diag, "event": None, "summary_diag": None, "boxscore": []}
    event = events[0]
    summary, summary_diag = defense._summary_payload(str(event.get("event_id") or ""))
    return {
        "schedule_diag": schedule_diag,
        "event": {"event_id": str(event.get("event_id") or ""), "date": str(event.get("date") or "")},
        "summary_diag": summary_diag,
        "boxscore": boxscore_shape(summary),
        "parsed_defense_game": defense.parse_recent_defense_game(summary, team_id) if summary_diag.get("ok") else {},
    }


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
            "sample_event_probe": sample_event_probe(team_id),
            "boxscore_recovery_diag": recovered_diag,
            "boxscore_recovered_season": recovered_season,
            "boxscore_recovered_rows": recovered_rows,
        }

    with open(OUTPUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    print(f"WROTE_DIAGNOSTIC={OUTPUT}")


if __name__ == "__main__":
    main()
