from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from sports_api.wnba_availability import (
    EASTERN_TZ,
    GAME_DATE_RE,
    GAME_TIME_RE,
    MATCHUP_RE,
    STATUS_RE,
    _fetch_pdf_bytes,
    _team_maps,
    discover_latest_injury_report_url,
    parse_injury_report_text,
)
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)

OUTPUT = Path("step7g-injury-report-probe.json")
TARGET_GAME_ID = "1022600290"
TARGET_TEAM_KEYS = {"washington-mystics", "phoenix-mercury"}


def _extract(content: bytes, *, layout: bool) -> tuple[str, int]:
    reader = PdfReader(BytesIO(content))
    if layout:
        texts = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    else:
        texts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(texts).strip(), len(reader.pages)


def _summary(parsed: dict[str, object], *, target_date: str | None) -> dict[str, object]:
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
        if (target_date is None or row.get("game_date") == target_date)
        and (
            row.get("away_team_key") in TARGET_TEAM_KEYS
            or row.get("home_team_key") in TARGET_TEAM_KEYS
            or TARGET_TEAM_KEYS.intersection(set(row.get("team_keys") or []))
        )
    ]
    target_submissions = [
        row
        for row in submission_surfaces
        if (target_date is None or row.get("game_date") == target_date)
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


def _schedule_target() -> dict[str, object]:
    dataset = get_step7g_step4n_season_schedule_dataset(2026)
    games = dataset.get("games") if isinstance(dataset.get("games"), list) else []
    matching = [row for row in games if isinstance(row, dict) and str(row.get("game_id")) == TARGET_GAME_ID]
    if len(matching) != 1:
        raise RuntimeError(
            f"Expected exactly one certified Step 4N game {TARGET_GAME_ID}; got {len(matching)}."
        )
    game = matching[0]
    return {
        "game_id": game.get("game_id"),
        "date": game.get("date"),
        "official_schedule_date": game.get("official_schedule_date"),
        "game_datetime_utc": game.get("game_datetime_utc"),
        "game_datetime_eastern": game.get("game_datetime_eastern"),
        "away_team_key": (game.get("away") or {}).get("team_key") if isinstance(game.get("away"), dict) else None,
        "away_team_tricode": (game.get("away") or {}).get("team_tricode") if isinstance(game.get("away"), dict) else None,
        "home_team_key": (game.get("home") or {}).get("team_key") if isinstance(game.get("home"), dict) else None,
        "home_team_tricode": (game.get("home") or {}).get("team_tricode") if isinstance(game.get("home"), dict) else None,
        "status_category": (game.get("status") or {}).get("category") if isinstance(game.get("status"), dict) else None,
    }


def _structural_lines(text: str, *, target_matchup: str | None) -> list[dict[str, object]]:
    teams_by_name, _ = _team_maps(2026)
    team_names = sorted(
        ((team["full_name"], team["team_key"]) for team in teams_by_name.values()),
        key=lambda row: len(row[0]),
        reverse=True,
    )
    rows: list[dict[str, object]] = []
    context_countdown = 0
    for index, raw in enumerate(str(text).splitlines()):
        clean = " ".join(raw.split())
        if not clean:
            if context_countdown > 0:
                context_countdown -= 1
            continue
        date_match = GAME_DATE_RE.search(clean)
        time_match = GAME_TIME_RE.search(clean)
        matchup_match = MATCHUP_RE.search(clean)
        status_match = STATUS_RE.search(clean)
        team_hits = [team_key for full_name, team_key in team_names if full_name.casefold() in clean.casefold()]
        not_submitted = "not yet submitted" in clean.casefold()
        matchup = matchup_match.group(1).upper() if matchup_match else None
        target_marker = bool(target_matchup and matchup == target_matchup)
        if target_marker:
            context_countdown = 8
        structurally_interesting = bool(
            date_match
            or time_match
            or matchup_match
            or team_hits
            or status_match
            or not_submitted
            or context_countdown > 0
        )
        if structurally_interesting:
            rows.append(
                {
                    "line_index": index,
                    "game_date_token": date_match.group(1) if date_match else None,
                    "game_time_token": time_match.group(1) if time_match else None,
                    "matchup_token": matchup,
                    "team_keys_present": sorted(set(team_hits)),
                    "status_token": status_match.group(1).title() if status_match else None,
                    "not_yet_submitted": not_submitted,
                    "target_matchup_line": target_marker,
                    "character_count": len(clean),
                }
            )
        if context_countdown > 0 and not target_marker:
            context_countdown -= 1
    return rows


def main() -> None:
    started = datetime.now(EASTERN_TZ)
    schedule = _schedule_target()
    target_date = str(schedule.get("date") or schedule.get("official_schedule_date") or "") or None
    away_code = str(schedule.get("away_team_tricode") or "")
    home_code = str(schedule.get("home_team_tricode") or "")
    target_matchup = f"{away_code}@{home_code}" if away_code and home_code else None

    url, slot, discovery_cache_hit = discover_latest_injury_report_url(as_of_eastern=started)
    content, retrieved_at_utc, pdf_cache_hit = _fetch_pdf_bytes(url)

    default_text, page_count = _extract(content, layout=False)
    layout_text, layout_page_count = _extract(content, layout=True)
    if page_count != layout_page_count:
        raise RuntimeError("Default and layout PDF extraction observed different page counts.")

    default_parsed = parse_injury_report_text(default_text, 2026)
    layout_parsed = parse_injury_report_text(layout_text, 2026)

    output = {
        "data_type": "wnba_step7g_injury_report_structure_probe_v3",
        "started_at_eastern": started.isoformat(),
        "source_url": url,
        "discovered_report_slot_eastern": slot,
        "retrieved_at_utc": retrieved_at_utc,
        "discovery_cache_hit": discovery_cache_hit,
        "pdf_cache_hit": pdf_cache_hit,
        "page_count": page_count,
        "schedule_target": schedule,
        "target_matchup_from_schedule": target_matchup,
        "default_extraction": _summary(default_parsed, target_date=target_date),
        "layout_extraction": _summary(layout_parsed, target_date=target_date),
        "layout_structural_lines": _structural_lines(layout_text, target_matchup=target_matchup),
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
