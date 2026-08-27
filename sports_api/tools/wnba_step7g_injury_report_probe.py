from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from sports_api.wnba_availability import (
    EASTERN_TZ,
    _fetch_pdf_bytes,
    discover_latest_injury_report_url,
    parse_injury_report_text,
)

OUTPUT = Path("step7g-injury-report-probe.json")
TARGET_DATE = "2026-08-27"
TARGET_TEAM_KEYS = {"washington-mystics", "phoenix-mercury"}


def _extract(content: bytes, *, layout: bool) -> tuple[str, int]:
    reader = PdfReader(BytesIO(content))
    if layout:
        texts = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    else:
        texts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(texts).strip(), len(reader.pages)


def _summary(parsed: dict[str, object]) -> dict[str, object]:
    entries = parsed.get("entries") if isinstance(parsed.get("entries"), list) else []
    submissions = parsed.get("team_submissions") if isinstance(parsed.get("team_submissions"), list) else []
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

    games = [
        {
            **{key: value for key, value in surface.items() if key != "team_keys"},
            "team_keys": sorted(surface["team_keys"]),
        }
        for surface in game_surfaces.values()
    ]
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

    target_games = [
        row
        for row in games
        if row.get("game_date") == TARGET_DATE
        and (
            row.get("away_team_key") in TARGET_TEAM_KEYS
            or row.get("home_team_key") in TARGET_TEAM_KEYS
            or TARGET_TEAM_KEYS.intersection(set(row.get("team_keys") or []))
        )
    ]
    target_submissions = [
        row
        for row in submission_surfaces
        if row.get("game_date") == TARGET_DATE
        and (
            row.get("away_team_key") in TARGET_TEAM_KEYS
            or row.get("home_team_key") in TARGET_TEAM_KEYS
            or row.get("team_key") in TARGET_TEAM_KEYS
        )
    ]
    diagnostics = parsed.get("parser_diagnostics") if isinstance(parsed.get("parser_diagnostics"), dict) else {}
    return {
        "report_timestamp_eastern": parsed.get("report_timestamp_eastern"),
        "entry_count": len(entries),
        "team_submission_count": len(submissions),
        "ignored_line_count": diagnostics.get("ignored_line_count"),
        "all_entries_have_team_mapping": diagnostics.get("all_entries_have_team_mapping"),
        "all_entries_have_matchup": diagnostics.get("all_entries_have_matchup"),
        "matchup_counts": dict(sorted(matchup_counts.items())),
        "games": games,
        "team_submissions": submission_surfaces,
        "target_games": target_games,
        "target_submissions": target_submissions,
    }


def main() -> None:
    started = datetime.now(EASTERN_TZ)
    url, slot, discovery_cache_hit = discover_latest_injury_report_url(as_of_eastern=started)
    content, retrieved_at_utc, pdf_cache_hit = _fetch_pdf_bytes(url)

    default_text, page_count = _extract(content, layout=False)
    layout_text, layout_page_count = _extract(content, layout=True)
    if page_count != layout_page_count:
        raise RuntimeError("Default and layout PDF extraction observed different page counts.")

    default_parsed = parse_injury_report_text(default_text, 2026)
    layout_parsed = parse_injury_report_text(layout_text, 2026)

    output = {
        "data_type": "wnba_step7g_injury_report_extraction_probe_v2",
        "started_at_eastern": started.isoformat(),
        "source_url": url,
        "discovered_report_slot_eastern": slot,
        "retrieved_at_utc": retrieved_at_utc,
        "discovery_cache_hit": discovery_cache_hit,
        "pdf_cache_hit": pdf_cache_hit,
        "page_count": page_count,
        "default_extraction": _summary(default_parsed),
        "layout_extraction": _summary(layout_parsed),
        "target": {
            "expected_date": TARGET_DATE,
            "expected_team_keys": sorted(TARGET_TEAM_KEYS),
        },
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "persistence_performed": False,
            "supabase_mutation_performed": False,
            "full_pdf_text_persisted": False,
            "player_names_persisted": False,
            "player_injury_details_persisted": False,
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
