"""Official WNBA injury, availability, and rotation verification context.

Step 4I is an observed-data layer only. It does not generate betting lines,
probabilities, projected minutes, or projected starters.

Primary official sources:
- WNBA/NBA official injury-report PDFs hosted at ak-static.cms.nba.com
- WNBA Stats current roster feed from Step 4B
- WNBA Stats recent player statistics from Step 4E
- WNBA Stats lineup combinations from Step 4G
- WNBA official schedule from Step 4C
- WNBA official box score from Step 4D for starters after a game begins

Pregame starter handling is deliberately fail-closed: a historical most-used
five-player lineup is exposed as observed context, but is never labeled as a
confirmed starting five. Official starters are only confirmed when the live/final
box score itself identifies them.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import re
from threading import Lock
from time import monotonic
from typing import Any, Iterable
import unicodedata
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from pypdf import PdfReader

from sports_api.wnba_game_history import (
    WNBAHistoryNotFoundError,
    WNBAHistoryUpstreamError,
    get_game_box_score_dataset,
)
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_lineup_context import (
    WNBALineupContextUpstreamError,
    get_lineups_dataset,
)
from sports_api.wnba_rosters import (
    WNBAStatsUpstreamError,
    get_current_players_dataset,
)
from sports_api.wnba_schedule import (
    EASTERN_TZ,
    WNBAScheduleUpstreamError,
    get_daily_schedule_dataset,
)
from sports_api.wnba_season_stats import (
    WNBASeasonStatsUpstreamError,
    get_player_season_stats_dataset,
)

WNBA_INJURY_REPORT_SOURCE = "WNBA Official Injury Report"
WNBA_INJURY_REPORT_BASE_URL = "https://ak-static.cms.nba.com/referee/wnba_injury"
INJURY_REPORT_CACHE_TTL_SECONDS = 60
DISCOVERY_CACHE_TTL_SECONDS = 60
MAX_DISCOVERY_LOOKBACK_HOURS = 48
DISCOVERY_WORKERS = 12

OFFICIAL_STATUSES = ("Available", "Probable", "Questionable", "Doubtful", "Out")
STATUS_RE = re.compile(r"\b(Available|Probable|Questionable|Doubtful|Out)\b", re.I)
REPORT_HEADER_RE = re.compile(
    r"Injury\s+Report:\s*(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})\s+(AM|PM)",
    re.I,
)
GAME_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
GAME_TIME_RE = re.compile(r"\b(\d{2}:\d{2})\s*\(ET\)")
MATCHUP_RE = re.compile(r"\b([A-Z]{2,4}@[A-Z]{2,4})\b")
PAGE_RE = re.compile(r"^Page\s+\d+\s+of\s+\d+$", re.I)

INJURY_URL_HOST = "ak-static.cms.nba.com"
INJURY_URL_PATH_PREFIX = "/referee/wnba_injury/"
REPORT_TRICODE_ALIASES = {
    "PDX": "portland-fire",
    "POR": "portland-fire",
    "GSV": "golden-state-valkyries",
    "GS": "golden-state-valkyries",
}

HTTP_HEADERS = {
    "Accept": "application/pdf,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
}

_DISCOVERY_CACHE: dict[str, dict[str, Any]] = {}
_PDF_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_LOCK = Lock()


class WNBAAvailabilityUpstreamError(RuntimeError):
    """Raised when official WNBA availability data cannot be consumed safely."""


class WNBAAvailabilityNotFoundError(LookupError):
    """Raised when requested WNBA game/report availability data is absent."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def _normalize_name(value: str | None) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    if "," in text:
        last, first = [part.strip() for part in text.split(",", 1)]
        text = f"{first} {last}".strip()
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", normalized.casefold()) or None


def _parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format.") from exc


def _normalize_last_n_games(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 20:
        raise ValueError("WNBA rotation last_n_games must be an integer from 1 through 20.")
    return value


def _validate_team_key(team_key: str, season: int) -> str:
    normalized = str(team_key).strip().casefold()
    for team in get_wnba_teams(season):
        if team["team_key"].casefold() == normalized:
            return team["team_key"]
    raise ValueError(f"WNBA team key {team_key!r} was not found for the {season} season.")


def _validate_report_url(report_url: str) -> str:
    parsed = urlparse(str(report_url).strip())
    if parsed.scheme != "https" or parsed.netloc.casefold() != INJURY_URL_HOST:
        raise ValueError("report_url must use the official WNBA injury-report host.")
    if not parsed.path.startswith(INJURY_URL_PATH_PREFIX) or not parsed.path.endswith(".pdf"):
        raise ValueError("report_url must point to an official WNBA injury-report PDF.")
    return parsed.geturl()


def _report_url_for_datetime(value: datetime) -> str:
    local = value.astimezone(EASTERN_TZ)
    suffix = local.strftime("%Y-%m-%d_%I_%M%p")
    return f"{WNBA_INJURY_REPORT_BASE_URL}/Injury-Report_{suffix}.pdf"


def _floor_quarter_hour(value: datetime) -> datetime:
    minute = (value.minute // 15) * 15
    return value.replace(minute=minute, second=0, microsecond=0)


def _candidate_report_datetimes(
    *,
    as_of_eastern: datetime,
    lookback_hours: int,
) -> list[datetime]:
    if lookback_hours < 1 or lookback_hours > MAX_DISCOVERY_LOOKBACK_HOURS:
        raise ValueError(
            f"WNBA injury-report lookback_hours must be from 1 through {MAX_DISCOVERY_LOOKBACK_HOURS}."
        )
    start = _floor_quarter_hour(as_of_eastern)
    slot_count = lookback_hours * 4 + 1
    return [start - timedelta(minutes=15 * index) for index in range(slot_count)]


def _probe_report_url(url: str) -> bool:
    try:
        response = httpx.head(
            url,
            headers=HTTP_HEADERS,
            timeout=4.0,
            follow_redirects=True,
        )
        if response.status_code == 200:
            return True
        if response.status_code not in (405, 501):
            return False
        response = httpx.get(
            url,
            headers={**HTTP_HEADERS, "Range": "bytes=0-7"},
            timeout=5.0,
            follow_redirects=True,
        )
        return response.status_code in (200, 206) and response.content.startswith(b"%PDF")
    except httpx.HTTPError:
        return False


def discover_latest_injury_report_url(
    *,
    as_of_eastern: datetime | None = None,
    lookback_hours: int = 36,
) -> tuple[str, str, bool]:
    """Find the latest quarter-hour WNBA injury report at or before ``as_of``."""

    if as_of_eastern is None:
        as_of_eastern = datetime.now(EASTERN_TZ)
    elif as_of_eastern.tzinfo is None:
        as_of_eastern = as_of_eastern.replace(tzinfo=EASTERN_TZ)
    else:
        as_of_eastern = as_of_eastern.astimezone(EASTERN_TZ)

    candidates = _candidate_report_datetimes(
        as_of_eastern=as_of_eastern,
        lookback_hours=lookback_hours,
    )
    cache_key = f"{candidates[0].isoformat()}|{lookback_hours}"
    now = monotonic()
    with _CACHE_LOCK:
        cached = _DISCOVERY_CACHE.get(cache_key)
        if cached and cached["expires_at"] > now:
            return cached["url"], cached["report_slot_eastern"], True
        if cached:
            _DISCOVERY_CACHE.pop(cache_key, None)

    batch_size = DISCOVERY_WORKERS * 2
    for start_index in range(0, len(candidates), batch_size):
        batch = candidates[start_index : start_index + batch_size]
        urls = {candidate: _report_url_for_datetime(candidate) for candidate in batch}
        found: list[datetime] = []
        with ThreadPoolExecutor(max_workers=DISCOVERY_WORKERS) as executor:
            future_to_dt = {
                executor.submit(_probe_report_url, url): candidate
                for candidate, url in urls.items()
            }
            for future in as_completed(future_to_dt):
                candidate = future_to_dt[future]
                try:
                    if future.result():
                        found.append(candidate)
                except Exception:
                    continue
        if found:
            latest = max(found)
            url = urls[latest]
            with _CACHE_LOCK:
                _DISCOVERY_CACHE[cache_key] = {
                    "url": url,
                    "report_slot_eastern": latest.isoformat(),
                    "expires_at": now + DISCOVERY_CACHE_TTL_SECONDS,
                }
            return url, latest.isoformat(), False

    raise WNBAAvailabilityNotFoundError(
        f"No official WNBA injury report was found in the prior {lookback_hours} hours."
    )


def _fetch_pdf_bytes(url: str) -> tuple[bytes, str, bool]:
    url = _validate_report_url(url)
    now = monotonic()
    with _CACHE_LOCK:
        cached = _PDF_CACHE.get(url)
        if cached and cached["expires_at"] > now:
            return bytes(cached["content"]), cached["retrieved_at_utc"], True
        if cached:
            _PDF_CACHE.pop(url, None)

    try:
        response = httpx.get(
            url,
            headers=HTTP_HEADERS,
            timeout=20.0,
            follow_redirects=True,
        )
        if response.status_code == 404:
            raise WNBAAvailabilityNotFoundError(
                "The requested official WNBA injury-report PDF was not found."
            )
        response.raise_for_status()
    except WNBAAvailabilityNotFoundError:
        raise
    except httpx.HTTPError as exc:
        raise WNBAAvailabilityUpstreamError(
            f"Official WNBA injury-report request failed: {exc}"
        ) from exc

    content = response.content
    if not content.startswith(b"%PDF"):
        raise WNBAAvailabilityUpstreamError(
            "Official WNBA injury-report URL did not return a PDF payload."
        )

    retrieved_at_utc = _utc_now_iso()
    with _CACHE_LOCK:
        if len(_PDF_CACHE) >= 32:
            _PDF_CACHE.pop(next(iter(_PDF_CACHE)), None)
        _PDF_CACHE[url] = {
            "content": bytes(content),
            "retrieved_at_utc": retrieved_at_utc,
            "expires_at": now + INJURY_REPORT_CACHE_TTL_SECONDS,
        }
    return content, retrieved_at_utc, False


def _extract_pdf_text(content: bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(BytesIO(content))
        texts = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise WNBAAvailabilityUpstreamError(
            f"Official WNBA injury-report PDF could not be parsed: {exc}"
        ) from exc
    text = "\n".join(texts).strip()
    if not text:
        raise WNBAAvailabilityUpstreamError(
            "Official WNBA injury-report PDF contained no extractable text."
        )
    return text, len(reader.pages)


def _team_maps(season: int) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    teams = get_wnba_teams(season)
    by_name = {team["full_name"].casefold(): team for team in teams}
    by_code: dict[str, str] = {team["abbreviation"].upper(): team["team_key"] for team in teams}
    by_code.update(REPORT_TRICODE_ALIASES)
    return by_name, by_code


def _match_team_prefix(
    text: str,
    teams_by_name: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    lowered = text.casefold()
    ordered = sorted(teams_by_name.values(), key=lambda team: len(team["full_name"]), reverse=True)
    for team in ordered:
        name = team["full_name"]
        if lowered.startswith(name.casefold()):
            return team, text[len(name) :].strip()
    return None, text


def _matchup_team_keys(matchup: str | None, by_code: dict[str, str]) -> dict[str, Any]:
    if not matchup or "@" not in matchup:
        return {"away_team_key": None, "home_team_key": None}
    away_code, home_code = matchup.split("@", 1)
    return {
        "away_team_key": by_code.get(away_code.upper()),
        "home_team_key": by_code.get(home_code.upper()),
    }


def _parse_report_timestamp(text: str) -> str | None:
    match = REPORT_HEADER_RE.search(text)
    if not match:
        return None
    raw_date, raw_time, meridiem = match.groups()
    try:
        parsed = datetime.strptime(
            f"{raw_date} {raw_time} {meridiem}", "%m/%d/%y %I:%M %p"
        ).replace(tzinfo=EASTERN_TZ)
    except ValueError:
        return None
    return parsed.isoformat()


def parse_injury_report_text(text: str, season: int) -> dict[str, Any]:
    get_wnba_teams(season)
    teams_by_name, matchup_codes = _team_maps(season)
    lines = [_clean_text(line) for line in str(text).splitlines()]
    lines = [line for line in lines if line]

    current_game_date: str | None = None
    current_game_time: str | None = None
    current_matchup: str | None = None
    current_team: dict[str, Any] | None = None
    last_entry: dict[str, Any] | None = None
    entries: list[dict[str, Any]] = []
    submissions: list[dict[str, Any]] = []
    ignored_lines: list[str] = []

    for line in lines:
        if REPORT_HEADER_RE.search(line) or PAGE_RE.match(line):
            continue
        if "Game Date Game Time Matchup Team Player Name Current Status Reason" in line:
            continue

        working = line
        date_match = GAME_DATE_RE.search(working)
        if date_match:
            current_game_date = datetime.strptime(date_match.group(1), "%m/%d/%Y").date().isoformat()
            working = (working[: date_match.start()] + working[date_match.end() :]).strip()

        time_match = GAME_TIME_RE.search(working)
        if time_match:
            current_game_time = time_match.group(1)
            working = (working[: time_match.start()] + working[time_match.end() :]).strip()

        matchup_match = MATCHUP_RE.search(working)
        if matchup_match:
            current_matchup = matchup_match.group(1).upper()
            current_team = None
            working = (working[: matchup_match.start()] + working[matchup_match.end() :]).strip()

        matched_team, remainder = _match_team_prefix(working, teams_by_name)
        if matched_team is not None:
            current_team = matched_team
            working = remainder

        if not working:
            last_entry = None
            continue

        if working.casefold() == "not yet submitted":
            submissions.append(
                {
                    "game_date": current_game_date,
                    "game_time_eastern": current_game_time,
                    "matchup": current_matchup,
                    **_matchup_team_keys(current_matchup, matchup_codes),
                    "team_key": current_team["team_key"] if current_team else None,
                    "team_full_name": current_team["full_name"] if current_team else None,
                    "submission_status": "not_yet_submitted",
                }
            )
            last_entry = None
            continue

        status_match = STATUS_RE.search(working)
        if status_match:
            player_name = working[: status_match.start()].strip(" -")
            reason = working[status_match.end() :].strip(" -") or None
            if not player_name:
                ignored_lines.append(line)
                last_entry = None
                continue
            status = status_match.group(1).title()
            matchup_keys = _matchup_team_keys(current_matchup, matchup_codes)
            entry = {
                "game_date": current_game_date,
                "game_time_eastern": current_game_time,
                "matchup": current_matchup,
                **matchup_keys,
                "team_key": current_team["team_key"] if current_team else None,
                "team_full_name": current_team["full_name"] if current_team else None,
                "player_name_report": player_name,
                "player_name_normalized": _normalize_name(player_name),
                "status": status,
                "reason": reason,
            }
            entries.append(entry)
            last_entry = entry
            continue

        if last_entry is not None and current_team is not None:
            last_entry["reason"] = " ".join(
                part for part in (last_entry.get("reason"), working) if part
            )
            continue

        ignored_lines.append(line)

    deduped_submissions: list[dict[str, Any]] = []
    seen_submissions: set[tuple[Any, ...]] = set()
    for submission in submissions:
        key = (
            submission.get("game_date"),
            submission.get("matchup"),
            submission.get("team_key"),
            submission.get("submission_status"),
        )
        if key not in seen_submissions:
            seen_submissions.add(key)
            deduped_submissions.append(submission)

    return {
        "report_timestamp_eastern": _parse_report_timestamp(text),
        "entry_count": len(entries),
        "entries": entries,
        "team_submission_count": len(deduped_submissions),
        "team_submissions": deduped_submissions,
        "parser_diagnostics": {
            "ignored_line_count": len(ignored_lines),
            "ignored_lines": ignored_lines[:25],
            "all_entries_have_team_mapping": all(entry["team_key"] is not None for entry in entries),
            "all_entries_have_matchup": all(entry["matchup"] is not None for entry in entries),
        },
    }


def _enrich_report_players(
    parsed: dict[str, Any],
    season: int,
) -> dict[str, Any]:
    try:
        roster_dataset = get_current_players_dataset(season, current_roster_only=True)
    except WNBAStatsUpstreamError as exc:
        enriched = deepcopy(parsed)
        for entry in enriched["entries"]:
            entry["player_id"] = None
            entry["roster_match"] = False
        enriched["roster_enrichment"] = {
            "available": False,
            "matched_player_count": 0,
            "unmatched_player_count": len(enriched["entries"]),
            "error": str(exc),
        }
        return enriched

    roster_by_team_and_name: dict[tuple[str, str], dict[str, Any]] = {}
    for player in roster_dataset.get("players", []):
        team_key = player.get("team_key")
        name_key = _normalize_name(player.get("full_name"))
        if team_key and name_key:
            roster_by_team_and_name[(team_key, name_key)] = player

    enriched = deepcopy(parsed)
    matched = 0
    for entry in enriched["entries"]:
        key = (entry.get("team_key"), entry.get("player_name_normalized"))
        player = roster_by_team_and_name.get(key)
        entry["player_id"] = player.get("player_id") if player else None
        entry["roster_match"] = player is not None
        if player:
            matched += 1
    enriched["roster_enrichment"] = {
        "available": True,
        "matched_player_count": matched,
        "unmatched_player_count": len(enriched["entries"]) - matched,
        "error": None,
    }
    return enriched


def get_latest_injury_report_dataset(
    season: int,
    *,
    report_url: str | None = None,
    lookback_hours: int = 36,
    as_of_eastern: datetime | None = None,
) -> dict[str, Any]:
    get_wnba_teams(season)

    discovery_cache_hit = False
    discovered_slot = None
    if report_url is None:
        report_url, discovered_slot, discovery_cache_hit = discover_latest_injury_report_url(
            as_of_eastern=as_of_eastern,
            lookback_hours=lookback_hours,
        )
    else:
        report_url = _validate_report_url(report_url)

    content, retrieved_at_utc, pdf_cache_hit = _fetch_pdf_bytes(report_url)
    text, page_count = _extract_pdf_text(content)
    parsed = _enrich_report_players(parse_injury_report_text(text, season), season)

    return {
        "source": WNBA_INJURY_REPORT_SOURCE,
        "source_url": report_url,
        "season": season,
        "retrieved_at_utc": retrieved_at_utc,
        "report_timestamp_eastern": parsed["report_timestamp_eastern"],
        "discovered_report_slot_eastern": discovered_slot,
        "discovery_cache_hit": discovery_cache_hit,
        "pdf_cache_hit": pdf_cache_hit,
        "cache_ttl_seconds": INJURY_REPORT_CACHE_TTL_SECONDS,
        "page_count": page_count,
        "entry_count": parsed["entry_count"],
        "entries": parsed["entries"],
        "team_submission_count": parsed["team_submission_count"],
        "team_submissions": parsed["team_submissions"],
        "roster_enrichment": parsed["roster_enrichment"],
        "verification": {
            "official_host_verified": True,
            "pdf_magic_verified": True,
            "report_timestamp_parsed": parsed["report_timestamp_eastern"] is not None,
            "all_entries_have_team_mapping": parsed["parser_diagnostics"]["all_entries_have_team_mapping"],
            "all_entries_have_matchup": parsed["parser_diagnostics"]["all_entries_have_matchup"],
            "ignored_line_count": parsed["parser_diagnostics"]["ignored_line_count"],
        },
    }


def _status_class(status: str | None) -> dict[str, Any]:
    normalized = (status or "").casefold()
    return {
        "availability_class": {
            "out": "unavailable",
            "doubtful": "uncertain",
            "questionable": "uncertain",
            "probable": "probable",
            "available": "available",
        }.get(normalized, "not_listed"),
        "availability_blocking": normalized == "out",
        "availability_uncertain": normalized in {"doubtful", "questionable"},
    }


def _team_report_entries(
    report: dict[str, Any],
    team_key: str,
    *,
    matchup: str | None = None,
    game_date: str | None = None,
) -> list[dict[str, Any]]:
    rows = [entry for entry in report.get("entries", []) if entry.get("team_key") == team_key]
    if matchup is not None:
        rows = [entry for entry in rows if entry.get("matchup") == matchup]
    if game_date is not None:
        rows = [entry for entry in rows if entry.get("game_date") == game_date]
    return rows


def _team_submission_rows(
    report: dict[str, Any],
    team_key: str,
    *,
    matchup: str | None = None,
    game_date: str | None = None,
) -> list[dict[str, Any]]:
    rows = [row for row in report.get("team_submissions", []) if row.get("team_key") == team_key]
    if matchup is not None:
        rows = [row for row in rows if row.get("matchup") == matchup]
    if game_date is not None:
        rows = [row for row in rows if row.get("game_date") == game_date]
    return rows


def _component_result(func, *args, **kwargs) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return func(*args, **kwargs), None
    except (
        WNBASeasonStatsUpstreamError,
        WNBALineupContextUpstreamError,
        WNBAStatsUpstreamError,
        WNBAScheduleUpstreamError,
        WNBAHistoryUpstreamError,
        WNBAHistoryNotFoundError,
    ) as exc:
        return None, str(exc)


def _build_team_rotation_context(
    team_key: str,
    season: int,
    report: dict[str, Any],
    *,
    last_n_games: int,
    matchup: str | None = None,
    game_date: str | None = None,
) -> dict[str, Any]:
    stable_key = _validate_team_key(team_key, season)
    last_n_games = _normalize_last_n_games(last_n_games)

    roster, roster_error = _component_result(
        get_current_players_dataset,
        season,
        current_roster_only=True,
    )
    if roster is None:
        raise WNBAAvailabilityUpstreamError(
            f"Current WNBA roster is required for availability context: {roster_error}"
        )

    recent, recent_error = _component_result(
        get_player_season_stats_dataset,
        season,
        season_type="Regular Season",
        last_n_games=last_n_games,
        per_mode="PerGame",
        team_key=stable_key,
    )
    lineups, lineups_error = _component_result(
        get_lineups_dataset,
        season,
        season_type="Regular Season",
        group_quantity=5,
        last_n_games=last_n_games,
        per_mode="PerGame",
        team_key=stable_key,
    )

    recent_by_id = {
        row.get("player_id"): row
        for row in (recent or {}).get("players", [])
        if row.get("player_id") is not None
    }
    injuries = _team_report_entries(
        report,
        stable_key,
        matchup=matchup,
        game_date=game_date,
    )
    injury_by_id = {
        row.get("player_id"): row
        for row in injuries
        if row.get("player_id") is not None
    }
    injury_by_name = {
        row.get("player_name_normalized"): row
        for row in injuries
        if row.get("player_name_normalized")
    }

    most_used_lineup = None
    lineup_rows = (lineups or {}).get("lineups", [])
    if lineup_rows:
        most_used_lineup = lineup_rows[0]
    most_used_ids = set((most_used_lineup or {}).get("player_ids", []))

    players: list[dict[str, Any]] = []
    for player in roster.get("players", []):
        if player.get("team_key") != stable_key:
            continue
        player_id = player.get("player_id")
        injury = injury_by_id.get(player_id)
        if injury is None:
            injury = injury_by_name.get(_normalize_name(player.get("full_name")))
        recent_row = recent_by_id.get(player_id)
        recent_minutes = (recent_row or {}).get("stats", {}).get("minutes")
        status = injury.get("status") if injury else None
        status_meta = _status_class(status)
        players.append(
            {
                "player_id": player_id,
                "player_name": player.get("full_name"),
                "position": player.get("position"),
                "jersey_number": player.get("jersey_number"),
                "injury_report_status": status,
                "injury_reason": injury.get("reason") if injury else None,
                "listed_on_injury_report": injury is not None,
                **status_meta,
                "recent_window_games": last_n_games,
                "recent_minutes_per_game": recent_minutes,
                "recent_points_per_game": (recent_row or {}).get("stats", {}).get("points"),
                "recent_rebounds_per_game": (recent_row or {}).get("stats", {}).get("rebounds"),
                "recent_assists_per_game": (recent_row or {}).get("stats", {}).get("assists"),
                "member_of_most_used_five_player_lineup": player_id in most_used_ids,
            }
        )

    players.sort(
        key=lambda row: (
            -(row["recent_minutes_per_game"] or -1.0),
            row["player_name"] or "",
        )
    )
    for index, player in enumerate(players, start=1):
        player["observed_rotation_rank_by_recent_minutes"] = index

    submissions = _team_submission_rows(
        report,
        stable_key,
        matchup=matchup,
        game_date=game_date,
    )
    not_submitted = any(row.get("submission_status") == "not_yet_submitted" for row in submissions)

    return {
        "team_key": stable_key,
        "season": season,
        "last_n_games": last_n_games,
        "injury_report_entries": injuries,
        "team_submission_rows": submissions,
        "team_report_not_yet_submitted": not_submitted,
        "current_roster_player_count": len(players),
        "players": players,
        "most_used_five_player_lineup_observed": most_used_lineup,
        "starter_verification": {
            "official_starters_confirmed": False,
            "status": "pregame_not_confirmed_from_central_official_sources",
            "historical_lineup_is_confirmation": False,
        },
        "component_availability": {
            "roster": True,
            "recent_stats": recent is not None,
            "recent_stats_error": recent_error,
            "five_player_lineups": lineups is not None,
            "five_player_lineups_error": lineups_error,
        },
        "verification": {
            "no_projected_minutes": True,
            "no_projected_starters": True,
            "rotation_rank_is_observed_recent_minutes_only": True,
        },
    }


def get_team_availability_context_dataset(
    team_key: str,
    season: int,
    *,
    last_n_games: int = 5,
    report_url: str | None = None,
    lookback_hours: int = 36,
) -> dict[str, Any]:
    stable_key = _validate_team_key(team_key, season)
    last_n_games = _normalize_last_n_games(last_n_games)
    report = get_latest_injury_report_dataset(
        season,
        report_url=report_url,
        lookback_hours=lookback_hours,
    )
    context = _build_team_rotation_context(
        stable_key,
        season,
        report,
        last_n_games=last_n_games,
    )
    return {
        "source": "Kyre Sports API verified WNBA availability context",
        "season": season,
        "team_key": stable_key,
        "retrieved_at_utc": _utc_now_iso(),
        "injury_report": {
            "source": report["source"],
            "source_url": report["source_url"],
            "report_timestamp_eastern": report["report_timestamp_eastern"],
            "retrieved_at_utc": report["retrieved_at_utc"],
        },
        "team": context,
    }


def _game_matchup_code(game: dict[str, Any]) -> str | None:
    away = game.get("away", {}).get("team_tricode")
    home = game.get("home", {}).get("team_tricode")
    if not away or not home:
        return None
    away_code = "PDX" if game.get("away", {}).get("team_key") == "portland-fire" else away
    home_code = "PDX" if game.get("home", {}).get("team_key") == "portland-fire" else home
    return f"{away_code}@{home_code}"


def _confirmed_starters_from_box_score(
    game_id: str,
    season: int,
    status_category: str,
) -> dict[str, Any]:
    if status_category not in {"live", "final"}:
        return {
            "official_starters_confirmed": False,
            "confirmation_source": None,
            "home": [],
            "away": [],
            "note": "Pregame central official data does not confirm the starting five.",
        }

    box, error = _component_result(get_game_box_score_dataset, game_id, season)
    if box is None:
        return {
            "official_starters_confirmed": False,
            "confirmation_source": None,
            "home": [],
            "away": [],
            "note": f"Game is {status_category}, but official box-score starters were unavailable: {error}",
        }

    def starters(team: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "player_id": player.get("player_id"),
                "player_name": player.get("full_name"),
                "start_position": player.get("start_position"),
            }
            for player in team.get("players", [])
            if player.get("is_starter")
        ]

    home = starters(box["home"])
    away = starters(box["away"])
    return {
        "official_starters_confirmed": len(home) == 5 and len(away) == 5,
        "confirmation_source": box.get("source_endpoint"),
        "home": home,
        "away": away,
        "note": "Starter flags come directly from the official live/final box score.",
    }


def get_game_availability_context_dataset(
    game_id: str,
    target_date: str,
    season: int,
    *,
    last_n_games: int = 5,
    report_url: str | None = None,
    lookback_hours: int = 36,
) -> dict[str, Any]:
    _parse_iso_date(target_date)
    last_n_games = _normalize_last_n_games(last_n_games)
    schedule = get_daily_schedule_dataset(target_date, season)
    matching = [game for game in schedule.get("games", []) if game.get("game_id") == str(game_id)]
    if not matching:
        raise WNBAAvailabilityNotFoundError(
            f"WNBA game {game_id!r} was not found on the official {target_date} schedule."
        )
    if len(matching) > 1:
        raise WNBAAvailabilityUpstreamError(
            f"Official WNBA schedule returned duplicate rows for game {game_id}."
        )
    game = matching[0]
    matchup = _game_matchup_code(game)

    report = get_latest_injury_report_dataset(
        season,
        report_url=report_url,
        lookback_hours=lookback_hours,
    )
    away_key = game.get("away", {}).get("team_key")
    home_key = game.get("home", {}).get("team_key")
    if not away_key or not home_key:
        raise WNBAAvailabilityUpstreamError(
            "Official WNBA schedule game does not map both teams to the verified registry."
        )

    away = _build_team_rotation_context(
        away_key,
        season,
        report,
        last_n_games=last_n_games,
        matchup=matchup,
        game_date=target_date,
    )
    home = _build_team_rotation_context(
        home_key,
        season,
        report,
        last_n_games=last_n_games,
        matchup=matchup,
        game_date=target_date,
    )

    starters = _confirmed_starters_from_box_score(
        str(game_id),
        season,
        game.get("status", {}).get("category") or "unknown",
    )
    if starters["official_starters_confirmed"]:
        away["starter_verification"] = {
            "official_starters_confirmed": True,
            "status": "confirmed_from_official_box_score",
            "historical_lineup_is_confirmation": False,
            "starters": starters["away"],
        }
        home["starter_verification"] = {
            "official_starters_confirmed": True,
            "status": "confirmed_from_official_box_score",
            "historical_lineup_is_confirmation": False,
            "starters": starters["home"],
        }

    report_has_game = any(
        row.get("matchup") == matchup and row.get("game_date") == target_date
        for row in report.get("entries", []) + report.get("team_submissions", [])
    )
    submission_complete = (
        report_has_game
        and not away["team_report_not_yet_submitted"]
        and not home["team_report_not_yet_submitted"]
    )

    return {
        "source": "Kyre Sports API verified WNBA game availability context",
        "season": season,
        "date": target_date,
        "game_id": str(game_id),
        "matchup": matchup,
        "retrieved_at_utc": _utc_now_iso(),
        "game": game,
        "injury_report": {
            "source": report["source"],
            "source_url": report["source_url"],
            "report_timestamp_eastern": report["report_timestamp_eastern"],
            "retrieved_at_utc": report["retrieved_at_utc"],
            "game_present_in_report": report_has_game,
            "both_teams_submitted_or_no_not_submitted_flag": submission_complete,
        },
        "away": away,
        "home": home,
        "starting_lineups": starters,
        "verification": {
            "official_schedule_game_found": True,
            "teams_mapped_to_registry": True,
            "injury_report_game_present": report_has_game,
            "injury_report_submission_complete": submission_complete,
            "official_starters_confirmed": starters["official_starters_confirmed"],
            "no_projected_starters": True,
            "no_projected_minutes": True,
        },
    }
