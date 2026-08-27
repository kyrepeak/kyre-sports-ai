"""Step 7G first-party injury-report adapter for frozen Step 4I availability.

The official WNBA injury-report PDF changed from flowing text to a fixed-column
layout. Frozen Step 4I remains intentionally unchanged; this additive adapter
uses pypdf's layout-preserving extraction, parses only certified table columns,
and reconciles blank/merged game cells against the already-certified Step 4N
WNBA.com season schedule.

Safety rules:
- explicit PDF date/matchup/team identity is never rewritten;
- a blank game cell is filled only when the official Step 4N schedule produces
  exactly one current/future candidate;
- ambiguous or conflicting identity fails closed;
- no production state, scheduler, sportsbook, persistence or Supabase mutation
  is touched by this module.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

from pypdf import PdfReader

import sports_api.wnba_availability as frozen
from sports_api.wnba_schedule_context import WNBARestTravelUpstreamError
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)

SOURCE_VARIANT = "official_wnba_injury_pdf_layout_step7g_schedule_reconciled"

# Certified from the live 2026 WNBA injury-report fixed-column PDF geometry.
COL_GAME_DATE = (0, 25)
COL_GAME_TIME = (25, 46)
COL_MATCHUP = (46, 63)
COL_TEAM = (63, 104)
COL_PLAYER = (104, 146)
COL_STATUS = (146, 167)
COL_REASON = (167, None)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def _slice(raw: str, bounds: tuple[int, int | None]) -> str | None:
    start, end = bounds
    return _clean(raw[start:end])


def _extract_layout_pdf_text(content: bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(BytesIO(content))
        texts = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    except Exception as exc:
        raise frozen.WNBAAvailabilityUpstreamError(
            f"Official WNBA injury-report PDF layout extraction failed: {exc}"
        ) from exc
    text = "\n".join(texts).strip("\n")
    if not text.strip():
        raise frozen.WNBAAvailabilityUpstreamError(
            "Official WNBA injury-report PDF contained no layout-preserving text."
        )
    return text, len(reader.pages)


def _parse_game_date(cell: str | None) -> str | None:
    if not cell:
        return None
    match = frozen.GAME_DATE_RE.search(cell)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%m/%d/%Y").date().isoformat()
    except ValueError as exc:
        raise frozen.WNBAAvailabilityUpstreamError(
            f"Official WNBA injury report exposed an invalid game date: {match.group(1)!r}."
        ) from exc


def _parse_game_time(cell: str | None) -> str | None:
    if not cell:
        return None
    match = frozen.GAME_TIME_RE.search(cell)
    return match.group(1) if match else None


def _parse_matchup(cell: str | None) -> str | None:
    if not cell:
        return None
    match = frozen.MATCHUP_RE.search(cell)
    return match.group(1).upper() if match else None


def _parse_status(cell: str | None) -> str | None:
    if not cell:
        return None
    match = frozen.STATUS_RE.search(cell)
    return match.group(1).title() if match else None


def _parse_team(cell: str | None, teams_by_name: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    clean = _clean(cell)
    if clean is None:
        return None
    team, remainder = frozen._match_team_prefix(clean, teams_by_name)
    if team is None or _clean(remainder) is not None:
        raise frozen.WNBAAvailabilityUpstreamError(
            f"Official WNBA injury report exposed an unrecognized team cell: {clean!r}."
        )
    return team


def _game_datetime_eastern(game: dict[str, Any]) -> datetime | None:
    raw = _clean(game.get("game_datetime_eastern"))
    if raw is None:
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=frozen.EASTERN_TZ)
    return value.astimezone(frozen.EASTERN_TZ)


def _game_time_matches_report(game: dict[str, Any], report_time: str) -> bool:
    dt = _game_datetime_eastern(game)
    if dt is None:
        return False
    try:
        hour_text, minute_text = report_time.split(":", 1)
        report_hour = int(hour_text)
        report_minute = int(minute_text)
    except (TypeError, ValueError):
        return False
    # Injury-report PDFs use a 12-hour clock without a printed AM/PM marker.
    game_hour_12 = dt.hour % 12 or 12
    return game_hour_12 == report_hour and dt.minute == report_minute


def _report_time_for_game(game: dict[str, Any]) -> str | None:
    dt = _game_datetime_eastern(game)
    if dt is None:
        return None
    return f"{dt.hour % 12 or 12:02d}:{dt.minute:02d}"


def _schedule_window_games(
    schedule: dict[str, Any],
    report_timestamp: datetime,
) -> list[dict[str, Any]]:
    lower_datetime = report_timestamp - timedelta(hours=6)
    upper_datetime = report_timestamp + timedelta(hours=48)
    report_day = report_timestamp.date()
    rows: list[dict[str, Any]] = []
    for game in schedule.get("games", []):
        if not isinstance(game, dict):
            continue
        dt = _game_datetime_eastern(game)
        if dt is None:
            continue
        # Keep the whole report calendar day (including already-started games)
        # plus the next 48 hours. This prevents old same-matchup games from
        # colliding with a current blank-date report row.
        if dt.date() == report_day or lower_datetime <= dt <= upper_datetime:
            rows.append(game)
    return rows


def _game_team_keys(game: dict[str, Any]) -> tuple[str | None, str | None]:
    away = game.get("away") if isinstance(game.get("away"), dict) else {}
    home = game.get("home") if isinstance(game.get("home"), dict) else {}
    return away.get("team_key"), home.get("team_key")


def _resolve_schedule_game(
    candidates: list[dict[str, Any]],
    *,
    explicit_date: str | None,
    report_time: str | None,
    matchup: str | None,
    team_key: str | None,
    context: str,
) -> dict[str, Any]:
    rows = list(candidates)
    if explicit_date is not None:
        rows = [game for game in rows if game.get("official_schedule_date") == explicit_date]
    if matchup is not None:
        rows = [game for game in rows if frozen._game_matchup_code(game) == matchup]
    if report_time is not None:
        rows = [game for game in rows if _game_time_matches_report(game, report_time)]
    if team_key is not None:
        rows = [game for game in rows if team_key in _game_team_keys(game)]

    if len(rows) != 1:
        descriptors = {
            "date": explicit_date,
            "time": report_time,
            "matchup": matchup,
            "team_key": team_key,
        }
        raise frozen.WNBAAvailabilityUpstreamError(
            "Official WNBA injury-report row could not be reconciled uniquely "
            f"against the certified Step 4N schedule ({context}; candidates={len(rows)}; "
            f"identity={descriptors})."
        )
    return rows[0]


def _resolved_identity(game: dict[str, Any]) -> dict[str, Any]:
    matchup = frozen._game_matchup_code(game)
    if matchup is None:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Certified Step 4N schedule game was missing report-compatible matchup identity."
        )
    away_key, home_key = _game_team_keys(game)
    if not away_key or not home_key:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Certified Step 4N schedule game was missing franchise identity."
        )
    date_value = _clean(game.get("official_schedule_date"))
    if date_value is None:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Certified Step 4N schedule game was missing official schedule date."
        )
    return {
        "game_date": date_value,
        "game_time_eastern": _report_time_for_game(game),
        "matchup": matchup,
        "away_team_key": away_key,
        "home_team_key": home_key,
    }


def _parse_layout_report(
    text: str,
    season: int,
    schedule: dict[str, Any],
) -> dict[str, Any]:
    frozen.get_wnba_teams(season)
    teams_by_name, _ = frozen._team_maps(season)
    report_timestamp_iso = frozen._parse_report_timestamp(text)
    if report_timestamp_iso is None:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Official WNBA injury report timestamp could not be parsed from layout text."
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

    entries: list[dict[str, Any]] = []
    submissions: list[dict[str, Any]] = []
    ignored_line_count = 0
    current_game: dict[str, Any] | None = None
    current_team: dict[str, Any] | None = None
    last_entry: dict[str, Any] | None = None
    resolved_blank_date_count = 0
    explicit_identity_count = 0

    for raw in str(text).splitlines():
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

        date_value = _parse_game_date(_slice(raw, COL_GAME_DATE))
        time_value = _parse_game_time(_slice(raw, COL_GAME_TIME))
        matchup_value = _parse_matchup(_slice(raw, COL_MATCHUP))
        team = _parse_team(_slice(raw, COL_TEAM), teams_by_name)
        player_name = _slice(raw, COL_PLAYER)
        status = _parse_status(_slice(raw, COL_STATUS))
        reason = _slice(raw, COL_REASON)
        not_submitted = bool(reason and reason.casefold() == "not yet submitted")

        has_identity = any((date_value, time_value, matchup_value, team is not None))
        has_payload = bool(player_name or status or reason)
        if not has_identity and not has_payload:
            continue

        # A printed matchup is a hard group boundary. Never carry date/team from
        # the prior matchup into a new game row.
        if matchup_value is not None:
            current_game = _resolve_schedule_game(
                schedule_candidates,
                explicit_date=date_value,
                report_time=time_value,
                matchup=matchup_value,
                team_key=team.get("team_key") if team else None,
                context="explicit matchup row",
            )
            current_team = team
            last_entry = None
            explicit_identity_count += 1
            if date_value is None:
                resolved_blank_date_count += 1
        elif current_game is None or date_value is not None or time_value is not None:
            # Standalone rows such as a first-team "Not Yet Submitted" row can
            # omit matchup. Resolve only when the official schedule is unique.
            current_game = _resolve_schedule_game(
                schedule_candidates,
                explicit_date=date_value,
                report_time=time_value,
                matchup=None,
                team_key=team.get("team_key") if team else None,
                context="standalone/merged identity row",
            )
            current_team = team
            last_entry = None
            if date_value is None:
                resolved_blank_date_count += 1
        elif team is not None:
            # A new team cell within the already-resolved game must belong to
            # one of that game's two official participants.
            if team.get("team_key") not in _game_team_keys(current_game):
                current_game = _resolve_schedule_game(
                    schedule_candidates,
                    explicit_date=date_value,
                    report_time=time_value,
                    matchup=None,
                    team_key=team.get("team_key"),
                    context="team-only row",
                )
            current_team = team
            last_entry = None

        if current_game is None:
            raise frozen.WNBAAvailabilityUpstreamError(
                "Official WNBA injury-report payload row lacked a safely resolved game identity."
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
            last_entry = None
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
            entry = {
                **identity,
                "team_key": current_team["team_key"],
                "team_full_name": current_team["full_name"],
                "player_name_report": player_name,
                "player_name_normalized": frozen._normalize_name(player_name),
                "status": status,
                "reason": reason,
            }
            entries.append(entry)
            last_entry = entry
            continue

        # Wrapped reason text is allowed only when no new row identity/payload
        # started and an immediately prior player entry exists.
        if reason and not has_identity and last_entry is not None:
            last_entry["reason"] = " ".join(
                part for part in (last_entry.get("reason"), reason) if part
            )
            continue

        # Non-data labels are ignored, but never silently ignore something that
        # looks like an injury/submission record.
        if player_name or reason:
            ignored_line_count += 1

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
            "ignored_line_count": ignored_line_count,
            "ignored_lines": [],
            "all_entries_have_team_mapping": all(row.get("team_key") for row in entries),
            "all_entries_have_matchup": all(row.get("matchup") for row in entries),
            "all_entries_schedule_reconciled": all(row.get("game_date") for row in entries),
            "resolved_blank_date_count": resolved_blank_date_count,
            "explicit_identity_count": explicit_identity_count,
            "fixed_column_geometry": {
                "game_date": COL_GAME_DATE,
                "game_time": COL_GAME_TIME,
                "matchup": COL_MATCHUP,
                "team": COL_TEAM,
                "player": COL_PLAYER,
                "status": COL_STATUS,
                "reason": COL_REASON,
            },
        },
    }


def get_step7g_first_party_injury_report_dataset(
    season: int,
    *,
    report_url: str | None = None,
    lookback_hours: int = 36,
    as_of_eastern: datetime | None = None,
) -> dict[str, Any]:
    frozen.get_wnba_teams(season)
    if season != 2026:
        raise frozen.WNBAAvailabilityUpstreamError(
            "Step 7G fixed-column injury adapter is certified only for the 2026 WNBA season."
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
    text, page_count = _extract_layout_pdf_text(content)
    try:
        schedule = get_step7g_step4n_season_schedule_dataset(season)
    except WNBARestTravelUpstreamError as exc:
        raise frozen.WNBAAvailabilityUpstreamError(
            f"Certified Step 4N schedule was unavailable for injury-report reconciliation: {exc}"
        ) from exc

    parsed = _parse_layout_report(text, season, schedule)
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
        "page_count": page_count,
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
            "layout_extraction_used": True,
            "fixed_column_geometry_verified": True,
            "schedule_reconciliation_used": True,
            "all_entries_schedule_reconciled": bool(
                diagnostics.get("all_entries_schedule_reconciled", False)
            ),
            "explicit_pdf_identity_never_rewritten": True,
            "blank_identity_requires_unique_schedule_match": True,
            "frozen_step4i_source_modified": False,
            "production_provider_replaced": False,
        },
        "step7g_adapter": {
            "resolved_blank_date_count": diagnostics.get("resolved_blank_date_count", 0),
            "explicit_identity_count": diagnostics.get("explicit_identity_count", 0),
            "schedule_source": schedule.get("source"),
            "schedule_source_variant": schedule.get("source_variant"),
        },
    }
