from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
import re

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
)
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)

OUTPUT = Path("step7g-injury-report-probe.json")
TARGET_GAME_ID = "1022600290"
HEADER_LABELS = (
    "Game Date",
    "Game Time",
    "Matchup",
    "Team",
    "Player Name",
    "Current Status",
    "Reason",
)


def _layout_text(content: bytes) -> tuple[str, int]:
    reader = PdfReader(BytesIO(content))
    texts = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    return "\n".join(texts), len(reader.pages)


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


def _span(match: re.Match[str] | None) -> list[int] | None:
    return list(match.span()) if match else None


def _header_geometry(lines: list[str]) -> dict[str, object]:
    for index, raw in enumerate(lines):
        positions = {label: raw.find(label) for label in HEADER_LABELS}
        present = {label: pos for label, pos in positions.items() if pos >= 0}
        if len(present) >= 5:
            return {
                "line_index": index,
                "line_length": len(raw),
                "label_starts": present,
            }
    return {"line_index": None, "line_length": None, "label_starts": {}}


def _structural_geometry(text: str, *, target_matchup: str | None) -> list[dict[str, object]]:
    _, teams_by_code = _team_maps(2026)
    # Build full-name geometry from the official registry, deduplicated by team key.
    teams_by_name, _ = _team_maps(2026)
    team_names: list[tuple[str, str]] = []
    seen: set[str] = set()
    for team in teams_by_name.values():
        key = str(team["team_key"])
        if key in seen:
            continue
        seen.add(key)
        team_names.append((str(team["full_name"]), key))
    team_names.sort(key=lambda row: len(row[0]), reverse=True)

    rows: list[dict[str, object]] = []
    for index, raw in enumerate(text.splitlines()):
        if not raw.strip():
            continue
        date_match = GAME_DATE_RE.search(raw)
        time_match = GAME_TIME_RE.search(raw)
        matchup_match = MATCHUP_RE.search(raw)
        status_match = STATUS_RE.search(raw)
        not_submitted_match = re.search(r"not\s+yet\s+submitted", raw, re.I)
        team_hits: list[dict[str, object]] = []
        folded = raw.casefold()
        for full_name, team_key in team_names:
            start = folded.find(full_name.casefold())
            if start >= 0:
                team_hits.append(
                    {
                        "team_key": team_key,
                        "span": [start, start + len(full_name)],
                    }
                )
        matchup = matchup_match.group(1).upper() if matchup_match else None
        if not (
            date_match
            or time_match
            or matchup_match
            or status_match
            or not_submitted_match
            or team_hits
        ):
            continue
        rows.append(
            {
                "line_index": index,
                "raw_line_length": len(raw),
                "leading_space_count": len(raw) - len(raw.lstrip(" ")),
                "date_span": _span(date_match),
                "time_span": _span(time_match),
                "matchup_span": _span(matchup_match),
                "status_span": _span(status_match),
                "not_yet_submitted_span": _span(not_submitted_match),
                "team_hits": team_hits,
                "matchup_token": matchup,
                "target_matchup_line": bool(target_matchup and matchup == target_matchup),
                "nonspace_run_starts": [
                    match.start()
                    for match in re.finditer(r"\S+", raw)
                ][:16],
            }
        )
    return rows


def main() -> None:
    started = datetime.now(EASTERN_TZ)
    schedule = _schedule_target()
    away_code = str(schedule.get("away_team_tricode") or "")
    home_code = str(schedule.get("home_team_tricode") or "")
    target_matchup = f"{away_code}@{home_code}" if away_code and home_code else None

    url, slot, discovery_cache_hit = discover_latest_injury_report_url(as_of_eastern=started)
    content, retrieved_at_utc, pdf_cache_hit = _fetch_pdf_bytes(url)
    layout_text, page_count = _layout_text(content)
    lines = layout_text.splitlines()

    output = {
        "data_type": "wnba_step7g_injury_report_column_geometry_probe_v4",
        "started_at_eastern": started.isoformat(),
        "source_url": url,
        "discovered_report_slot_eastern": slot,
        "retrieved_at_utc": retrieved_at_utc,
        "discovery_cache_hit": discovery_cache_hit,
        "pdf_cache_hit": pdf_cache_hit,
        "page_count": page_count,
        "schedule_target": schedule,
        "target_matchup_from_schedule": target_matchup,
        "header_geometry": _header_geometry(lines),
        "structural_rows": _structural_geometry(layout_text, target_matchup=target_matchup),
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "persistence_performed": False,
            "supabase_mutation_performed": False,
            "full_pdf_text_persisted": False,
            "player_names_persisted": False,
            "player_injury_details_persisted": False,
            "only_table_geometry_persisted": True,
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
