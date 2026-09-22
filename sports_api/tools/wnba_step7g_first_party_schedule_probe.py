"""Read-only probe of the first-party WNBA.com schedule proxy discovered in site JS.

The production WNBA frontend references ``/api/schedule?season=``. This probe
verifies that route independently before any frozen adapter or production path
is changed. It performs no Supabase writes, sportsbook calls, scheduler work,
model execution, feed publication, or production activation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

import httpx

REPORT_PATH = Path("step7g-first-party-schedule-probe.json")
SEASON = 2026
PROBES = (
    f"https://www.wnba.com/api/schedule?season={SEASON}",
    f"https://www.wnba.com/api/schedule?season={SEASON}&seasonType=Regular%20Season",
)

HTTP_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wnba.com/schedule",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
}

GAME_ID_KEYS = ("gameId", "gameID", "game_id", "GAME_ID")
DATE_KEYS = (
    "gameDate", "gameDateTimeUTC", "gameTimeUTC", "game_datetime_utc",
    "gameEt", "date", "gameDateEst", "gameDateTimeEst",
)
STATUS_KEYS = ("gameStatus", "gameStatusText", "status", "game_status")
SAFE_KEYS = {
    *GAME_ID_KEYS,
    *DATE_KEYS,
    *STATUS_KEYS,
    "homeTeam", "awayTeam", "home", "away",
    "homeTeamId", "awayTeamId", "homeTeamID", "awayTeamID",
    "homeTeamName", "awayTeamName", "homeTeamTricode", "awayTeamTricode",
    "teamId", "teamID", "teamName", "teamCity", "teamTricode",
    "arenaName", "arenaCity", "arenaState", "season", "seasonYear",
    "leagueId", "leagueID", "gameCode", "gameLabel", "gameSubLabel",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch(url: str, *, timeout: float = 20.0) -> tuple[httpx.Response | None, dict[str, Any]]:
    started = time.monotonic()
    try:
        response = httpx.get(
            url,
            headers=HTTP_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )
        return response, {
            "url": url,
            "final_url": str(response.url),
            "reachable": True,
            "http_status": int(response.status_code),
            "http_success": 200 <= response.status_code < 300,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "content_type": response.headers.get("content-type"),
            "response_bytes": len(response.content),
        }
    except Exception as exc:
        return None, {
            "url": url,
            "reachable": False,
            "http_status": None,
            "http_success": False,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "error_type": type(exc).__name__,
            "error_message_returned": False,
        }


def _walk(value: Any, path: str = "root"):
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


def _game_id(value: dict[str, Any]) -> str | None:
    for key in GAME_ID_KEYS:
        raw = value.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if len(text) == 10 and text.isdigit():
            return text
    return None


def _safe_value(value: Any, depth: int = 0) -> Any:
    if depth >= 2:
        if isinstance(value, dict):
            return {
                key: item
                for key, item in value.items()
                if key in SAFE_KEYS and item is None or isinstance(item, (str, int, float, bool))
            }
        if isinstance(value, list):
            return {"type": "array", "length": len(value)}
        return value if value is None or isinstance(value, (str, int, float, bool)) else None
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key not in SAFE_KEYS:
                continue
            if isinstance(item, (dict, list)):
                result[key] = _safe_value(item, depth + 1)
            elif item is None or isinstance(item, (str, int, float, bool)):
                result[key] = item
        return result
    if isinstance(value, list):
        return [_safe_value(item, depth + 1) for item in value[:5]]
    return value if value is None or isinstance(value, (str, int, float, bool)) else None


def _year_tokens(value: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for key in DATE_KEYS:
        raw = value.get(key)
        if raw is None:
            continue
        text = str(raw)
        if "2026" in text:
            found.add(key)
    return found


def _summarize_payload(payload: Any) -> dict[str, Any]:
    top_type = type(payload).__name__
    top_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
    top_length = len(payload) if isinstance(payload, list) else None

    games: list[tuple[str, dict[str, Any], str]] = []
    seen_ids: set[str] = set()
    date_paths: list[str] = []
    status_paths: list[str] = []
    league_10_markers = 0
    season_2026_markers = 0

    for path, value in _walk(payload):
        if isinstance(value, dict):
            gid = _game_id(value)
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                games.append((gid, value, path))
            for key in DATE_KEYS:
                if key in value and len(date_paths) < 50:
                    date_paths.append(f"{path}.{key}")
            for key in STATUS_KEYS:
                if key in value and len(status_paths) < 50:
                    status_paths.append(f"{path}.{key}")
            for key in ("leagueId", "leagueID", "league_id", "LeagueID"):
                if str(value.get(key) or "").strip() == "10":
                    league_10_markers += 1
            for key in ("season", "seasonYear", "season_year", "Season"):
                if str(value.get(key) or "").strip() == "2026":
                    season_2026_markers += 1

    samples = []
    games_with_2026_date = 0
    home_away_identity_count = 0
    for gid, row, path in games:
        if _year_tokens(row):
            games_with_2026_date += 1
        lower_keys = {str(key).casefold() for key in row}
        if (
            {"hometeam", "awayteam"}.issubset(lower_keys)
            or {"home", "away"}.issubset(lower_keys)
            or {"hometeamid", "awayteamid"}.issubset(lower_keys)
        ):
            home_away_identity_count += 1
        if len(samples) < 5:
            samples.append(
                {
                    "path": path,
                    "game_id": gid,
                    "sanitized": _safe_value(row),
                }
            )

    return {
        "top_level_type": top_type,
        "top_level_keys": top_keys[:100],
        "top_level_array_length": top_length,
        "distinct_valid_10_digit_game_id_count": len(games),
        "games_with_direct_2026_date_marker": games_with_2026_date,
        "games_with_direct_home_away_identity": home_away_identity_count,
        "league_id_10_marker_count": league_10_markers,
        "season_2026_marker_count": season_2026_markers,
        "date_field_paths": date_paths,
        "status_field_paths": status_paths,
        "game_samples": samples,
        "schema_feasible_for_schedule_adapter": (
            len(games) > 0
            and home_away_identity_count > 0
            and (games_with_2026_date > 0 or season_2026_markers > 0)
        ),
    }


def _probe(url: str) -> dict[str, Any]:
    response, meta = _fetch(url)
    row: dict[str, Any] = {"request": meta}
    if response is None or meta.get("http_success") is not True:
        row["json_parse_success"] = False
        row["schedule_schema_feasible"] = False
        return row
    try:
        payload = response.json()
    except ValueError as exc:
        row.update(
            {
                "json_parse_success": False,
                "json_error_type": type(exc).__name__,
                "body_class": (
                    "html_like" if response.content.lstrip()[:32].lower().startswith((b"<!doctype html", b"<html"))
                    else "other"
                ),
                "schedule_schema_feasible": False,
            }
        )
        return row
    summary = _summarize_payload(payload)
    row.update(
        {
            "json_parse_success": True,
            "payload": summary,
            "schedule_schema_feasible": summary["schema_feasible_for_schedule_adapter"],
        }
    )
    return row


def build_report() -> dict[str, Any]:
    probes = [_probe(url) for url in PROBES]
    selected_index = next(
        (index for index, row in enumerate(probes) if row.get("schedule_schema_feasible") is True),
        None,
    )
    selected = probes[selected_index] if selected_index is not None else None
    return {
        "data_type": "wnba_step7g_first_party_schedule_probe_v1",
        "created_at_utc": _utc_now_iso(),
        "season": SEASON,
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "probes": probes,
        "selected_probe_index": selected_index,
        "feasibility": {
            "first_party_schedule_proxy_reachable": any(
                (row.get("request") or {}).get("http_success") is True for row in probes
            ),
            "first_party_schedule_proxy_json": any(
                row.get("json_parse_success") is True for row in probes
            ),
            "schedule_adapter_schema_feasible": selected is not None,
            "valid_game_id_count": (
                ((selected or {}).get("payload") or {}).get("distinct_valid_10_digit_game_id_count", 0)
            ),
            "production_activation_safe_now": False,
        },
        "next_required_step": (
            "If schedule_adapter_schema_feasible is true, build an isolated Step-7G first-party "
            "schedule adapter and parity-test it against the frozen schedule contract. Do not "
            "activate production until history/rotation dependencies are also resolved."
        ),
    }


def main() -> int:
    try:
        report = build_report()
    except Exception as exc:
        report = {
            "data_type": "wnba_step7g_first_party_schedule_probe_v1",
            "created_at_utc": _utc_now_iso(),
            "read_only": True,
            "production_mutation_performed": False,
            "supabase_mutation_performed": False,
            "sportsbook_called": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "frozen_shared_provider_behavior_changed": False,
            "probe_completed": False,
            "error_type": type(exc).__name__,
            "error_message_returned": False,
            "production_activation_safe_now": False,
        }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if "probes" in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
