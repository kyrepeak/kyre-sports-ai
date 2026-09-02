"""Read-only Step 7G probe for the exact official WNBA GameRotation host.

The frozen Step 4R contract already matches the official GameRotation result
schema. This diagnostic tests both official Stats hosts with LeagueID=10 to
determine whether host routing, rather than the endpoint/schema, is the actual
blocker in our infrastructure.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import monotonic
from typing import Any

import httpx

GAME_ID = "1022600288"
LEAGUE_ID = "10"
REPORT_PATH = Path("step7g-gamerotation-host-probe.json")
EXPECTED_FIELDS = {
    "GAME_ID", "TEAM_ID", "TEAM_CITY", "TEAM_NAME", "PERSON_ID",
    "PLAYER_FIRST", "PLAYER_LAST", "IN_TIME_REAL", "OUT_TIME_REAL",
    "PLAYER_PTS", "PT_DIFF", "USG_PCT",
}
HOSTS = (
    "https://stats.wnba.com/stats/gamerotation",
    "https://stats.nba.com/stats/gamerotation",
)
OFF_ENV = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.wnba.com",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result_sets(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get("resultSets")
    if raw is None:
        raw = payload.get("resultSet")
    if isinstance(raw, dict):
        return [raw]
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _inspect(url: str) -> dict[str, Any]:
    started = monotonic()
    result: dict[str, Any] = {"url": url}
    try:
        response = httpx.get(
            url,
            params={"GameID": GAME_ID, "LeagueID": LEAGUE_ID},
            headers=HEADERS,
            timeout=20.0,
            follow_redirects=True,
        )
        result.update({
            "status_code": response.status_code,
            "elapsed_seconds": round(monotonic() - started, 3),
            "final_url": str(response.url),
            "content_type": response.headers.get("content-type"),
            "bytes": len(response.content),
        })
        if response.status_code != 200:
            result["passed"] = False
            result["failure_kind"] = "http_status"
            return result
        try:
            payload = response.json()
        except ValueError:
            result["passed"] = False
            result["failure_kind"] = "non_json"
            return result
        sets = _result_sets(payload)
        summaries = []
        exact_shape_count = 0
        total_rows = 0
        for item in sets:
            headers = item.get("headers")
            rows = item.get("rowSet")
            header_set = {str(value) for value in headers} if isinstance(headers, list) else set()
            row_count = len(rows) if isinstance(rows, list) else 0
            exact = EXPECTED_FIELDS.issubset(header_set)
            exact_shape_count += int(exact)
            total_rows += row_count
            summaries.append({
                "name": item.get("name"),
                "header_count": len(header_set),
                "row_count": row_count,
                "has_exact_step4r_fields": exact,
                "missing_step4r_fields": sorted(EXPECTED_FIELDS - header_set),
            })
        result["result_sets"] = summaries
        result["result_set_count"] = len(sets)
        result["exact_shape_result_set_count"] = exact_shape_count
        result["total_rows"] = total_rows
        result["passed"] = exact_shape_count >= 2 and total_rows > 0
        if not result["passed"]:
            result["failure_kind"] = "schema_or_empty_rows"
        return result
    except httpx.TimeoutException as exc:
        result.update({
            "elapsed_seconds": round(monotonic() - started, 3),
            "passed": False,
            "failure_kind": "timeout",
            "error_type": type(exc).__name__,
        })
        return result
    except httpx.HTTPError as exc:
        result.update({
            "elapsed_seconds": round(monotonic() - started, 3),
            "passed": False,
            "failure_kind": "http_error",
            "error_type": type(exc).__name__,
        })
        return result


def main() -> None:
    off_state = {key: os.getenv(key, "").strip().casefold() == "false" for key in OFF_ENV}
    if not all(off_state.values()):
        raise RuntimeError("GameRotation host probe refused because production is not fully OFF.")

    hosts = [_inspect(url) for url in HOSTS]
    working = [item for item in hosts if item.get("passed")]
    preferred = working[0]["url"] if working else None

    report = {
        "data_type": "wnba_step7g_gamerotation_host_probe",
        "created_at_utc": _now(),
        "read_only": True,
        "game_id": GAME_ID,
        "league_id": LEAGUE_ID,
        "required_step4r_fields": sorted(EXPECTED_FIELDS),
        "production_flags_off": off_state,
        "hosts": hosts,
        "decision": {
            "exact_rotation_source_reachable": bool(working),
            "preferred_working_url": preferred,
            "working_host_count": len(working),
            "production_activation_allowed": False,
        },
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "working_host_count": len(working),
        "preferred_working_url": preferred,
        "stats_wnba_passed": hosts[0].get("passed"),
        "stats_nba_passed": hosts[1].get("passed"),
        "production_activation_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
