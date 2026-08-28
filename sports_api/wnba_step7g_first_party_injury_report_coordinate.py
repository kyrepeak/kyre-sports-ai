"""Coordinate-safe Step 7G adapter for the official WNBA injury-report PDF.

The 2026 official WNBA injury report is a landscape table whose physical PDF
columns are stable, but pypdf's layout-string indentation is not stable across
pages.  This adapter therefore reads the actual PDF text matrix coordinates and
reconstructs table rows from certified x bands instead of slicing rendered text
by character offset.

Every semantic identity is still reconciled against the certified Step 4N
WNBA.com schedule.  Printed date/time/matchup/team values are never rewritten.
Page-break continuation can inherit only an already-resolved game/team state;
meaningful orphan rows or unknown geometry fail closed.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from io import BytesIO
from typing import Any

from pypdf import PdfReader

import sports_api.wnba_availability as frozen
from sports_api.wnba_schedule_context import WNBARestTravelUpstreamError
from sports_api.wnba_step7g_first_party_injury_report import (
    _clean,
    _extract_layout_pdf_text,
    _game_team_keys,
    _game_time_matches_report,
    _parse_game_date,
    _parse_game_time,
    _parse_matchup,
    _parse_status,
    _parse_team,
    _resolve_schedule_game,
    _resolved_identity,
    _schedule_window_games,
)
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)

SOURCE_VARIANT = "official_wnba_injury_pdf_coordinate_rows_step7g_schedule_reconciled"

# Certified from the live 2026 official WNBA injury PDF physical x positions.
# These are deliberately wider than the exact observed starts so ordinary text
# width changes inside a cell do not change column identity.
COLUMN_BANDS: dict[str, tuple[float, float | None]] = {
    "game_date": (0.0, 100.0),
    "game_time": (100.0, 180.0),
    "matchup": (180.0, 240.0),
    "team": (240.0, 400.0),
    "player": (400.0, 560.0),
    "status": (560.0, 650.0),
    "reason": (650.0, None),
}
EXPECTED_HEADER_X = {
    "matchup": 199.95,
    "team": 264.24,
    "player": 424.98,
    "status": 585.71,
    "reason": 666.07,
}
HEADER_X_TOLERANCE = 9.0
PLAYER_START_X_RANGE = (410.0, 445.0)
STATUS_START_X_RANGE = (575.0, 605.0)
REASON_START_X_RANGE = (655.0, 680.0)
REASON_VERTICAL_TOLERANCE = 9.5
MIN_PAGE_WIDTH = 800.0
MAX_PAGE_WIDTH = 900.0
MIN_PAGE_HEIGHT = 540.0
MAX_PAGE_HEIGHT = 700.0


def _join_tokens(tokens: list[str]) -> str | None:
    clean_tokens = [_clean(token) for token in tokens]
    values = [token for token in clean_tokens if token]
    if not values:
        return None
    output = values[0]
    for token in values[1:]:
        if output.endswith("-") and token and token[0].isalnum():
            output += token
        elif token in {",", ";", ":"}:
            output += token
        else:
            output += " " + token
    return _clean(output)


def _cell_text(fragments: list[dict[str, Any]], column: str) -> str | None:
    lower, upper = COLUMN_BANDS[column]
    selected = []
    for fragment in sorted(fragments, key=lambda item: float(item["x"])):
        x = float(fragment["x"])
        if x < lower or (upper is not None and x >= upper):
            continue
        selected.append(str(fragment["text"]))
    return _join_tokens(selected)


def _row_text(fragments: list[dict[str, Any]]) -> str:
    return _join_tokens(
        [str(item["text"]) for item in sorted(fragments, key=lambda item: float(item["x"]))]
    ) or ""


def _is_metadata_row(fragments: list[dict[str, Any]]) -> bool:
    clean = _row_text(fragments)
    folded = clean.casefold()
    if folded.startswith("injury report:"):
        return True
    if folded.startswith("page ") and " of " in folded:
        return True
    required = ("game", "date", "time", "matchup", "team", "player", "current", "status", "reason")
    return all(token in folded for token in required)


def _extract_coordinate_rows(content: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        reader = PdfReader(BytesIO(content))
    except Exception as exc:
        raise frozen.WNBAAvailabilityUpstreamError(
            f"Official WNBA injury-report PDF coordinate extraction failed: {exc}"
        ) from exc

    rows: list[dict[str, Any]] = []
    header_geometry_verified = False
    pages_with_status_rows: set[int] = set()
    pages_with_player_band: set[int] = set()
    pages_with_reason_band: set[int] = set()

    for page_number, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        rotation = int(getattr(page, "rotation", 0) or 0) % 360
        if rotation != 0 or not (MIN_PAGE_WIDTH <= width <= MAX_PAGE_WIDTH) or not (
            MIN_PAGE_HEIGHT <= height <= MAX_PAGE_HEIGHT
        ):
            raise frozen.WNBAAvailabilityUpstreamError(
                "Official WNBA injury-report PDF geometry changed outside the certified "
                f"Step 7G coordinate envelope (page={page_number}, width={width:.2f}, "
                f"height={height:.2f}, rotation={rotation})."
            )

        fragments: list[dict[str, Any]] = []

        def visitor(
            text: str,
            cm: list[float],
            tm: list[float],
            font_dict: Any,
            font_size: float,
        ) -> None:
            clean = _clean(text)
            if clean is None:
                return
            try:
                x = float(tm[4])
                y = float(tm[5])
            except (TypeError, ValueError, IndexError) as exc:
                raise frozen.WNBAAvailabilityUpstreamError(
                    "Official WNBA injury-report text matrix lacked numeric coordinates."
                ) from exc
            fragments.append({"x": x, "y": y, "text": clean})

        try:
            page.extract_text(visitor_text=visitor)
        except frozen.WNBAAvailabilityUpstreamError:
            raise
        except Exception as exc:
            raise frozen.WNBAAvailabilityUpstreamError(
                f"Official WNBA injury-report coordinate visitor failed: {exc}"
            ) from exc

        grouped: dict[float, list[dict[str, Any]]] = {}
        for fragment in fragments:
            key = round(float(fragment["y"]), 1)
            grouped.setdefault(key, []).append(fragment)

        for y in sorted(grouped):
            row_fragments = sorted(grouped[y], key=lambda item: float(item["x"]))
            clean = _row_text(row_fragments)
            if not clean:
                continue

            token_positions = {str(item["text"]).casefold(): float(item["x"]) for item in row_fragments}
            if {
                "matchup",
                "team",
                "player",
                "current",
                "reason",
            }.issubset(token_positions):
                checks = {
                    "matchup": token_positions["matchup"],
                    "team": token_positions["team"],
                    "player": token_positions["player"],
                    "status": token_positions["current"],
                    "reason": token_positions["reason"],
                }
                if not all(
                    abs(checks[name] - EXPECTED_HEADER_X[name]) <= HEADER_X_TOLERANCE
                    for name in EXPECTED_HEADER_X
                ):
                    raise frozen.WNBAAvailabilityUpstreamError(
                        "Official WNBA injury-report table header moved outside certified "
                        "coordinate columns."
                    )
                header_geometry_verified = True

            status_text = _parse_status(_cell_text(row_fragments, "status"))
            if status_text is not None:
                pages_with_status_rows.add(page_number)
            if any(
                PLAYER_START_X_RANGE[0] <= float(item["x"]) <= PLAYER_START_X_RANGE[1]
                for item in row_fragments
            ):
                pages_with_player_band.add(page_number)
            if any(
                REASON_START_X_RANGE[0] <= float(item["x"]) <= REASON_START_X_RANGE[1]
                for item in row_fragments
            ):
                pages_with_reason_band.add(page_number)

            rows.append(
                {
                    "page_number": page_number,
                    "y": y,
                    "fragments": row_fragments,
                }
            )

    if not rows or not header_geometry_verified:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Official WNBA injury-report coordinate table header could not be certified."
        )
    if not pages_with_status_rows:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Official WNBA injury-report coordinate extraction exposed no recognized status rows."
        )
    for page_number in pages_with_status_rows:
        if page_number not in pages_with_player_band or page_number not in pages_with_reason_band:
            raise frozen.WNBAAvailabilityUpstreamError(
                "Official WNBA injury-report page exposed status rows without the certified "
                f"player/reason coordinate bands (page={page_number})."
            )

    return rows, {
        "page_count": len(reader.pages),
        "header_geometry_verified": header_geometry_verified,
        "pages_with_status_rows": sorted(pages_with_status_rows),
        "coordinate_bands": deepcopy(COLUMN_BANDS),
    }


def _reason_for_anchor(
    anchor: dict[str, Any],
    all_rows: list[dict[str, Any]],
    anchor_rows: set[tuple[int, float]],
) -> str | None:
    page_number = int(anchor["page_number"])
    anchor_y = float(anchor["y"])
    pieces: list[tuple[float, str]] = []
    for row in all_rows:
        if int(row["page_number"]) != page_number:
            continue
        y = float(row["y"])
        if abs(y - anchor_y) > REASON_VERTICAL_TOLERANCE:
            continue
        reason = _cell_text(row["fragments"], "reason")
        if reason is None:
            continue
        # Nearby rows that are themselves semantic anchors may contribute only
        # their same-row reason. Never steal reason text from another player.
        row_key = (int(row["page_number"]), float(row["y"]))
        if row_key in anchor_rows and row_key != (page_number, anchor_y):
            continue
        pieces.append((y, reason))
    return _join_tokens([text for _, text in sorted(pieces, key=lambda item: item[0])])


def _parse_coordinate_report(
    content: bytes,
    season: int,
    schedule: dict[str, Any],
) -> dict[str, Any]:
    frozen.get_wnba_teams(season)
    teams_by_name, _ = frozen._team_maps(season)

    layout_text, _ = _extract_layout_pdf_text(content)
    report_timestamp_iso = frozen._parse_report_timestamp(layout_text)
    if report_timestamp_iso is None:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Official WNBA injury report timestamp could not be parsed."
        )
    try:
        report_timestamp = datetime.fromisoformat(report_timestamp_iso).astimezone(frozen.EASTERN_TZ)
    except ValueError as exc:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Official WNBA injury report timestamp was malformed."
        ) from exc

    schedule_candidates = _schedule_window_games(schedule, report_timestamp)
    if not schedule_candidates:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Certified Step 4N schedule exposed no games in the injury-report reconciliation window."
        )

    rows, geometry = _extract_coordinate_rows(content)
    semantic_rows: list[dict[str, Any]] = []
    anchor_keys: set[tuple[int, float]] = set()
    reason_only_rows: list[dict[str, Any]] = []

    for row in rows:
        fragments = row["fragments"]
        if _is_metadata_row(fragments):
            continue
        cells = {
            name: _cell_text(fragments, name)
            for name in COLUMN_BANDS
        }
        status = _parse_status(cells["status"])
        non_reason = any(cells[name] for name in COLUMN_BANDS if name != "reason")
        if status is not None or non_reason:
            semantic = {**row, "cells": cells, "status": status}
            semantic_rows.append(semantic)
            anchor_keys.add((int(row["page_number"]), float(row["y"])))
        elif cells["reason"]:
            reason_only_rows.append(row)

    for row in reason_only_rows:
        page_number = int(row["page_number"])
        y = float(row["y"])
        if not any(
            int(anchor["page_number"]) == page_number
            and abs(float(anchor["y"]) - y) <= REASON_VERTICAL_TOLERANCE
            for anchor in semantic_rows
        ):
            raise frozen.WNBAAvailabilityUpstreamError(
                "Official WNBA injury-report exposed meaningful reason text without a nearby "
                "coordinate row anchor."
            )

    entries: list[dict[str, Any]] = []
    submissions: list[dict[str, Any]] = []
    current_game: dict[str, Any] | None = None
    current_team: dict[str, Any] | None = None
    resolved_blank_date_count = 0
    explicit_identity_count = 0
    page_break_carry_count = 0
    previous_page: int | None = None

    for row in semantic_rows:
        cells = row["cells"]
        page_number = int(row["page_number"])
        if previous_page is not None and page_number != previous_page:
            if current_game is not None and current_team is not None:
                page_break_carry_count += 1
        previous_page = page_number

        date_value = _parse_game_date(cells["game_date"])
        time_value = _parse_game_time(cells["game_time"])
        matchup_value = _parse_matchup(cells["matchup"])
        team = _parse_team(cells["team"], teams_by_name) if cells["team"] else None
        player_name = cells["player"]
        status = row["status"]
        reason = _reason_for_anchor(row, rows, anchor_keys)
        not_submitted = bool(reason and reason.casefold() == "not yet submitted")

        has_identity = any((date_value, time_value, matchup_value, team is not None))
        has_payload = bool(player_name or status or reason)
        if not has_identity and not has_payload:
            continue

        if matchup_value is not None:
            current_game = _resolve_schedule_game(
                schedule_candidates,
                explicit_date=date_value,
                report_time=time_value,
                matchup=matchup_value,
                team_key=team.get("team_key") if team else None,
                context="coordinate explicit matchup row",
            )
            current_team = team
            explicit_identity_count += 1
            if date_value is None:
                resolved_blank_date_count += 1
        elif current_game is None or date_value is not None or time_value is not None:
            current_game = _resolve_schedule_game(
                schedule_candidates,
                explicit_date=date_value,
                report_time=time_value,
                matchup=None,
                team_key=team.get("team_key") if team else None,
                context="coordinate standalone identity row",
            )
            current_team = team
            if date_value is None:
                resolved_blank_date_count += 1
        elif team is not None:
            if team.get("team_key") not in _game_team_keys(current_game):
                current_game = _resolve_schedule_game(
                    schedule_candidates,
                    explicit_date=date_value,
                    report_time=time_value,
                    matchup=None,
                    team_key=team.get("team_key"),
                    context="coordinate team-only row",
                )
            current_team = team

        if current_game is None:
            raise frozen.WNBAAvailabilityUpstreamError(
                "Official WNBA injury-report coordinate payload lacked a safely resolved game identity."
            )
        identity = _resolved_identity(current_game)

        if date_value is not None and identity["game_date"] != date_value:
            raise frozen.WNBAAvailabilityUpstreamError(
                "Explicit WNBA injury-report date conflicted with the certified Step 4N schedule."
            )
        if matchup_value is not None and identity["matchup"] != matchup_value:
            raise frozen.WNBAAvailabilityUpstreamError(
                "Explicit WNBA injury-report matchup conflicted with the certified Step 4N schedule."
            )
        if time_value is not None and not _game_time_matches_report(current_game, time_value):
            raise frozen.WNBAAvailabilityUpstreamError(
                "Explicit WNBA injury-report time conflicted with the certified Step 4N schedule."
            )

        if not_submitted:
            if current_team is None:
                raise frozen.WNBAAvailabilityUpstreamError(
                    "Official WNBA injury-report submission row lacked a safely resolved team identity."
                )
            submissions.append(
                {
                    **identity,
                    "team_key": current_team["team_key"],
                    "team_full_name": current_team["full_name"],
                    "submission_status": "not_yet_submitted",
                }
            )
            continue

        if status is not None:
            if current_team is None or not player_name:
                raise frozen.WNBAAvailabilityUpstreamError(
                    "Official WNBA injury-report player row lacked team or player identity."
                )
            if current_team.get("team_key") not in _game_team_keys(current_game):
                raise frozen.WNBAAvailabilityUpstreamError(
                    "Official WNBA injury-report team conflicted with the reconciled game identity."
                )
            entries.append(
                {
                    **identity,
                    "team_key": current_team["team_key"],
                    "team_full_name": current_team["full_name"],
                    "player_name_report": player_name,
                    "player_name_normalized": frozen._normalize_name(player_name),
                    "status": status,
                    "reason": reason,
                }
            )
            continue

        # A coordinate row containing a player but no recognized status is not a
        # harmless label; refuse to guess its meaning.
        if player_name:
            raise frozen.WNBAAvailabilityUpstreamError(
                "Official WNBA injury-report coordinate player row had no recognized status."
            )

    deduped_submissions: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in submissions:
        key = (
            row.get("game_date"),
            row.get("matchup"),
            row.get("team_key"),
            row.get("submission_status"),
        )
        if key not in seen:
            seen.add(key)
            deduped_submissions.append(row)

    return {
        "report_timestamp_eastern": report_timestamp_iso,
        "entry_count": len(entries),
        "entries": entries,
        "team_submission_count": len(deduped_submissions),
        "team_submissions": deduped_submissions,
        "parser_diagnostics": {
            "ignored_line_count": 0,
            "ignored_lines": [],
            "all_entries_have_team_mapping": all(row.get("team_key") for row in entries),
            "all_entries_have_matchup": all(row.get("matchup") for row in entries),
            "all_entries_schedule_reconciled": all(row.get("game_date") for row in entries),
            "resolved_blank_date_count": resolved_blank_date_count,
            "explicit_identity_count": explicit_identity_count,
            "page_break_carry_count": page_break_carry_count,
            "coordinate_geometry_verified": bool(geometry["header_geometry_verified"]),
            "coordinate_bands": geometry["coordinate_bands"],
            "pages_with_status_rows": geometry["pages_with_status_rows"],
        },
    }


def get_step7g_coordinate_injury_report_dataset(
    season: int,
    *,
    report_url: str | None = None,
    lookback_hours: int = 36,
    as_of_eastern: datetime | None = None,
) -> dict[str, Any]:
    frozen.get_wnba_teams(season)
    if season != 2026:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Step 7G coordinate injury adapter is certified only for the 2026 WNBA season."
        )

    discovery_cache_hit = False
    discovered_slot = None
    if report_url is None:
        report_url, discovered_slot, discovery_cache_hit = frozen.discover_latest_injury_report_url(
            as_of_eastern=as_of_eastern,
            lookback_hours=lookback_hours,
        )
    else:
        report_url = frozen._validate_report_url(report_url)

    content, retrieved_at_utc, pdf_cache_hit = frozen._fetch_pdf_bytes(report_url)
    try:
        schedule = get_step7g_step4n_season_schedule_dataset(season)
    except WNBARestTravelUpstreamError as exc:
        raise frozen.WNBAAvailabilityUpstreamError(
            f"Certified Step 4N schedule was unavailable for injury-report reconciliation: {exc}"
        ) from exc

    parsed = _parse_coordinate_report(content, season, schedule)
    enriched = frozen._enrich_report_players(deepcopy(parsed), season)
    diagnostics = enriched.get("parser_diagnostics") or parsed["parser_diagnostics"]

    return {
        "source": frozen.WNBA_INJURY_REPORT_SOURCE,
        "source_url": report_url,
        "source_variant": SOURCE_VARIANT,
        "season": season,
        "retrieved_at_utc": retrieved_at_utc,
        "report_timestamp_eastern": enriched["report_timestamp_eastern"],
        "discovered_report_slot_eastern": discovered_slot,
        "discovery_cache_hit": discovery_cache_hit,
        "pdf_cache_hit": pdf_cache_hit,
        "cache_ttl_seconds": frozen.INJURY_REPORT_CACHE_TTL_SECONDS,
        "page_count": len(diagnostics.get("pages_with_status_rows", [])) or None,
        "entry_count": enriched["entry_count"],
        "entries": enriched["entries"],
        "team_submission_count": enriched["team_submission_count"],
        "team_submissions": enriched["team_submissions"],
        "roster_enrichment": enriched["roster_enrichment"],
        "verification": {
            "official_host_verified": True,
            "pdf_magic_verified": True,
            "report_timestamp_parsed": enriched["report_timestamp_eastern"] is not None,
            "all_entries_have_team_mapping": bool(diagnostics["all_entries_have_team_mapping"]),
            "all_entries_have_matchup": bool(diagnostics["all_entries_have_matchup"]),
            "ignored_line_count": diagnostics["ignored_line_count"],
            "layout_extraction_used": False,
            "fixed_column_geometry_verified": False,
            "coordinate_extraction_used": True,
            "coordinate_geometry_verified": bool(
                diagnostics.get("coordinate_geometry_verified", False)
            ),
            "schedule_reconciliation_used": True,
            "all_entries_schedule_reconciled": bool(
                diagnostics.get("all_entries_schedule_reconciled", False)
            ),
            "explicit_pdf_identity_never_rewritten": True,
            "blank_identity_requires_unique_schedule_match": True,
            "page_break_state_requires_prior_resolved_identity": True,
            "frozen_step4i_source_modified": False,
            "production_provider_replaced": False,
        },
        "step7g_adapter": {
            "resolved_blank_date_count": diagnostics.get("resolved_blank_date_count", 0),
            "explicit_identity_count": diagnostics.get("explicit_identity_count", 0),
            "page_break_carry_count": diagnostics.get("page_break_carry_count", 0),
            "schedule_source": schedule.get("source"),
            "schedule_source_variant": schedule.get("source_variant"),
        },
    }
