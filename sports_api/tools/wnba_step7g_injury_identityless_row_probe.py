"""OFF-only structural probe for current official WNBA injury-report parsing.

This diagnostic compares the existing layout-preserving extraction with pypdf's
logical reading-order extraction. It records only bounded normalized line samples
and identity-less fixed-column cells so the Step 7G parser can be repaired from
first-party evidence without weakening fail-closed identity rules.

No full PDF text, HTTP headers, cookies, sportsbook data, persistence, scheduler,
or production state is recorded.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
from typing import Any

from pypdf import PdfReader

import sports_api.wnba_availability as frozen
from sports_api.wnba_step7g_first_party_injury_report import (
    COL_GAME_DATE,
    COL_GAME_TIME,
    COL_MATCHUP,
    COL_PLAYER,
    COL_REASON,
    COL_STATUS,
    COL_TEAM,
    _clean,
    _extract_layout_pdf_text,
    _parse_game_date,
    _parse_game_time,
    _parse_matchup,
    _parse_status,
    _parse_team,
    _slice,
)

REPORT_PATH = Path("step7g-injury-identityless-row-probe.json")
SEASON = 2026
MAX_LOGICAL_LINES_PER_PAGE = 90
MAX_LINE_CHARS = 360
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    "WNBA_STEP7G_FIRST_PARTY_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _assert_safe() -> None:
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError("Injury-report structure probe requires all runtime flags OFF: " + ", ".join(bad))


def _header_like(text: str | None) -> bool:
    folded = str(text or "").casefold()
    tokens = ("game date", "game time", "matchup", "team", "player name", "current status", "reason")
    return any(token in folded for token in tokens)


def _logical_samples(content: bytes) -> list[dict[str, Any]]:
    reader = PdfReader(BytesIO(content))
    pages: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        logical_text = page.extract_text() or ""
        lines: list[dict[str, Any]] = []
        for source_line_number, raw in enumerate(logical_text.splitlines(), start=1):
            clean = _clean(raw)
            if clean is None:
                continue
            lines.append(
                {
                    "source_line_number": source_line_number,
                    "text": clean[:MAX_LINE_CHARS],
                    "truncated": len(clean) > MAX_LINE_CHARS,
                }
            )
            if len(lines) >= MAX_LOGICAL_LINES_PER_PAGE:
                break
        pages.append(
            {
                "page_number": page_number,
                "sampled_line_count": len(lines),
                "lines": lines,
            }
        )
    return pages


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    teams_by_name, _ = frozen._team_maps(SEASON)
    report_url, discovered_slot, discovery_cache_hit = frozen.discover_latest_injury_report_url(
        lookback_hours=36
    )
    content, retrieved_at_utc, pdf_cache_hit = frozen._fetch_pdf_bytes(report_url)
    text, page_count = _extract_layout_pdf_text(content)

    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(str(text).splitlines(), start=1):
        if not raw.strip():
            continue
        clean_line = _clean(raw) or ""
        if frozen.REPORT_HEADER_RE.search(clean_line) or frozen.PAGE_RE.match(clean_line):
            continue
        folded = clean_line.casefold()
        if (
            "game date" in folded
            and "game time" in folded
            and "matchup" in folded
            and "current status" in folded
        ):
            continue

        date_cell = _slice(raw, COL_GAME_DATE)
        time_cell = _slice(raw, COL_GAME_TIME)
        matchup_cell = _slice(raw, COL_MATCHUP)
        team_cell = _slice(raw, COL_TEAM)
        player_cell = _slice(raw, COL_PLAYER)
        status_cell = _slice(raw, COL_STATUS)
        reason_cell = _slice(raw, COL_REASON)

        date_value = _parse_game_date(date_cell)
        time_value = _parse_game_time(time_cell)
        matchup_value = _parse_matchup(matchup_cell)
        try:
            team = _parse_team(team_cell, teams_by_name)
            team_error = None
        except Exception as exc:
            team = None
            team_error = f"{type(exc).__name__}: {str(exc)[:300]}"
        status_value = _parse_status(status_cell)

        has_identity = any((date_value, time_value, matchup_value, team is not None))
        has_payload = bool(player_cell or status_value or reason_cell)
        if has_identity or not has_payload:
            continue

        rows.append(
            {
                "line_number": line_number,
                "date_cell": date_cell,
                "time_cell": time_cell,
                "matchup_cell": matchup_cell,
                "team_cell": team_cell,
                "player_cell": player_cell,
                "status_cell": status_cell,
                "parsed_status": status_value,
                "reason_cell": reason_cell,
                "team_parse_error": team_error,
                "classification": {
                    "clean_line_header_like": _header_like(clean_line),
                    "player_cell_header_like": _header_like(player_cell),
                    "status_cell_header_like": _header_like(status_cell),
                    "reason_cell_header_like": _header_like(reason_cell),
                    "reason_not_yet_submitted": bool(
                        reason_cell and reason_cell.casefold() == "not yet submitted"
                    ),
                    "status_recognized": status_value is not None,
                },
            }
        )

    report = {
        "data_type": "wnba_step7g_injury_structure_probe_v2",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "retrieved_at_utc": retrieved_at_utc,
        "report_url": report_url,
        "discovered_slot": discovered_slot.isoformat() if hasattr(discovered_slot, "isoformat") else str(discovered_slot),
        "page_count": page_count,
        "identityless_payload_row_count": len(rows),
        "identityless_rows": rows,
        "logical_reading_order_samples": _logical_samples(content),
        "cache": {
            "discovery_cache_hit": discovery_cache_hit,
            "pdf_cache_hit": pdf_cache_hit,
        },
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "persistence_performed": False,
            "supabase_mutation_performed": False,
            "full_pdf_text_persisted": False,
            "bounded_logical_line_samples_only": True,
            "http_headers_persisted": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
