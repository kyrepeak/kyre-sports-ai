from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from sports_api.wnba_availability import (
    EASTERN_TZ,
    _fetch_pdf_bytes,
    discover_latest_injury_report_url,
)
from sports_api.wnba_step7g_first_party_injury_report import (
    _extract_layout_pdf_text,
    _parse_layout_report,
)
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)

OUTPUT = Path("step7g-injury-report-probe.json")
TARGET_DATE = "2026-08-27"
TARGET_MATCHUP = "WAS@PHX"


def _exception_chain(exc: BaseException) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and len(rows) < 6 and id(current) not in seen:
        seen.add(id(current))
        rows.append({"type": type(current).__name__, "message": str(current)[:1000]})
        current = current.__cause__ or current.__context__
    return rows


def main() -> None:
    started = datetime.now(EASTERN_TZ)
    url, slot, discovery_cache_hit = discover_latest_injury_report_url(as_of_eastern=started)
    content, retrieved_at_utc, pdf_cache_hit = _fetch_pdf_bytes(url)
    layout_text, page_count = _extract_layout_pdf_text(content)
    schedule = get_step7g_step4n_season_schedule_dataset(2026)

    parsed = None
    errors: list[dict[str, str]] = []
    try:
        parsed = _parse_layout_report(layout_text, 2026, schedule)
    except Exception as exc:
        errors = _exception_chain(exc)

    if parsed is None:
        summary = {
            "parser_returned": False,
            "entry_count": None,
            "team_submission_count": None,
            "target_game_present": False,
            "target_submission_rows": [],
            "matchup_counts": {},
            "diagnostics": None,
        }
    else:
        entries = parsed.get("entries") if isinstance(parsed.get("entries"), list) else []
        submissions = parsed.get("team_submissions") if isinstance(parsed.get("team_submissions"), list) else []
        matchup_counts = Counter(str(row.get("matchup")) for row in entries if isinstance(row, dict))
        target_entries = [
            row for row in entries
            if isinstance(row, dict)
            and row.get("game_date") == TARGET_DATE
            and row.get("matchup") == TARGET_MATCHUP
        ]
        target_submissions = [
            {
                "game_date": row.get("game_date"),
                "matchup": row.get("matchup"),
                "team_key": row.get("team_key"),
                "submission_status": row.get("submission_status"),
            }
            for row in submissions
            if isinstance(row, dict)
            and row.get("game_date") == TARGET_DATE
            and row.get("matchup") == TARGET_MATCHUP
        ]
        summary = {
            "parser_returned": True,
            "entry_count": len(entries),
            "team_submission_count": len(submissions),
            "target_game_present": bool(target_entries or target_submissions),
            "target_entry_count": len(target_entries),
            "target_submission_rows": target_submissions,
            "matchup_counts": dict(sorted(matchup_counts.items())),
            "diagnostics": parsed.get("parser_diagnostics"),
        }

    output = {
        "data_type": "wnba_step7g_live_fixed_column_injury_adapter_probe_v6",
        "started_at_eastern": started.isoformat(),
        "source_url": url,
        "discovered_report_slot_eastern": slot,
        "retrieved_at_utc": retrieved_at_utc,
        "discovery_cache_hit": discovery_cache_hit,
        "pdf_cache_hit": pdf_cache_hit,
        "page_count": page_count,
        "summary": summary,
        "exception_chain": errors,
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
    if errors:
        raise RuntimeError("Live fixed-column injury adapter did not return; see sanitized exception_chain.")


if __name__ == "__main__":
    main()
