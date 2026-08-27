from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from sports_api.wnba_availability import EASTERN_TZ, get_latest_injury_report_dataset

OUTPUT = Path("step7g-injury-report-probe.json")
TARGET_DATE = "08/27/2026"
TARGET_TEAM_KEYS = {"washington-mystics", "phoenix-mercury"}


def main() -> None:
    started = datetime.now(EASTERN_TZ)
    report = get_latest_injury_report_dataset(2026, as_of_eastern=started)
    entries = report.get("entries") if isinstance(report.get("entries"), list) else []
    submissions = report.get("team_submissions") if isinstance(report.get("team_submissions"), list) else []

    matchup_counts = Counter(
        str(row.get("matchup"))
        for row in entries
        if isinstance(row, dict) and row.get("matchup")
    )
    game_surfaces: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("game_date") or ""),
            str(row.get("game_time_eastern") or ""),
            str(row.get("matchup") or ""),
        )
        surface = game_surfaces.setdefault(
            key,
            {
                "game_date": row.get("game_date"),
                "game_time_eastern": row.get("game_time_eastern"),
                "matchup": row.get("matchup"),
                "away_team_key": row.get("away_team_key"),
                "home_team_key": row.get("home_team_key"),
                "entry_count": 0,
                "team_keys": set(),
            },
        )
        surface["entry_count"] = int(surface["entry_count"]) + 1
        if row.get("team_key"):
            surface["team_keys"].add(str(row.get("team_key")))

    games = []
    for surface in game_surfaces.values():
        games.append(
            {
                **{key: value for key, value in surface.items() if key != "team_keys"},
                "team_keys": sorted(surface["team_keys"]),
            }
        )
    games.sort(key=lambda row: (str(row.get("game_date")), str(row.get("game_time_eastern")), str(row.get("matchup"))))

    submission_surfaces = []
    for row in submissions:
        if not isinstance(row, dict):
            continue
        submission_surfaces.append(
            {
                "game_date": row.get("game_date"),
                "game_time_eastern": row.get("game_time_eastern"),
                "matchup": row.get("matchup"),
                "away_team_key": row.get("away_team_key"),
                "home_team_key": row.get("home_team_key"),
                "team_key": row.get("team_key"),
                "submission_status": row.get("submission_status"),
            }
        )

    target_related_games = [
        row for row in games
        if row.get("game_date") == TARGET_DATE
        and (
            row.get("away_team_key") in TARGET_TEAM_KEYS
            or row.get("home_team_key") in TARGET_TEAM_KEYS
            or TARGET_TEAM_KEYS.intersection(set(row.get("team_keys") or []))
        )
    ]
    target_related_submissions = [
        row for row in submission_surfaces
        if row.get("game_date") == TARGET_DATE
        and (
            row.get("away_team_key") in TARGET_TEAM_KEYS
            or row.get("home_team_key") in TARGET_TEAM_KEYS
            or row.get("team_key") in TARGET_TEAM_KEYS
        )
    ]

    output = {
        "data_type": "wnba_step7g_injury_report_shape_probe_v1",
        "started_at_eastern": started.isoformat(),
        "report_timestamp_eastern": report.get("report_timestamp_eastern"),
        "discovered_report_slot_eastern": report.get("discovered_report_slot_eastern"),
        "source_url": report.get("source_url"),
        "page_count": report.get("page_count"),
        "entry_count": len(entries),
        "team_submission_count": len(submissions),
        "matchup_counts": dict(sorted(matchup_counts.items())),
        "games": games,
        "team_submissions": submission_surfaces,
        "target": {
            "expected_date": TARGET_DATE,
            "expected_team_keys": sorted(TARGET_TEAM_KEYS),
            "related_games": target_related_games,
            "related_submissions": target_related_submissions,
        },
        "verification": report.get("verification"),
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "persistence_performed": False,
            "supabase_mutation_performed": False,
            "full_pdf_text_persisted": False,
            "player_injury_details_persisted": False,
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
