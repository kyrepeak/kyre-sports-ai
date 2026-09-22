"""Step 7G read-only official WNBA network matrix.

This diagnostic deliberately bypasses all production adapters so a failure in
one official source cannot hide connectivity to another source. It performs no
Supabase writes, sportsbook calls, scheduler work, model execution, or runtime
activation.

The historic game ID below is used only as a stable connectivity/schema probe.
It is not a production slate input and is never used to make a current claim.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

import httpx

REPORT_PATH = Path("step7g-official-network-matrix.json")
HISTORIC_CONNECTIVITY_GAME_ID = "1022500168"

PROBES = (
    {
        "name": "wnba_static_schedule_cdn",
        "url": "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json",
        "kind": "json",
        "schema": "schedule",
        "timeout_seconds": 12.0,
    },
    {
        "name": "wnba_live_boxscore_cdn",
        "url": (
            "https://cdn.wnba.com/static/json/liveData/boxscore/"
            f"boxscore_{HISTORIC_CONNECTIVITY_GAME_ID}.json"
        ),
        "kind": "json",
        "schema": "boxscore",
        "timeout_seconds": 12.0,
    },
    {
        "name": "wnba_live_playbyplay_cdn",
        "url": (
            "https://cdn.wnba.com/static/json/liveData/playbyplay/"
            f"playbyplay_{HISTORIC_CONNECTIVITY_GAME_ID}.json"
        ),
        "kind": "json",
        "schema": "playbyplay",
        "timeout_seconds": 12.0,
    },
    {
        "name": "wnba_official_schedule_web",
        "url": "https://www.wnba.com/schedule",
        "kind": "html",
        "schema": "official_web",
        "timeout_seconds": 12.0,
    },
    {
        "name": "wnba_official_roster_web",
        "url": "https://www.wnba.com/team/las-vegas-aces/roster",
        "kind": "html",
        "schema": "official_web",
        "timeout_seconds": 12.0,
    },
    {
        "name": "wnba_stats_commonallplayers_known_blocker",
        "url": (
            "https://stats.wnba.com/stats/commonallplayers"
            "?LeagueID=10&Season=2026&IsOnlyCurrentSeason=1"
        ),
        "kind": "json",
        "schema": "stats_api",
        "timeout_seconds": 8.0,
        "known_blocker": True,
    },
)

HTTP_HEADERS = {
    "Accept": "application/json,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.wnba.com",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_class(content: bytes) -> str:
    stripped = content.lstrip()
    if not stripped:
        return "empty"
    lower = stripped[:256].lower()
    if lower.startswith((b"{", b"[")):
        return "json_like"
    if lower.startswith(b"<!doctype html") or lower.startswith(b"<html"):
        return "html_like"
    if lower.startswith(b"%pdf"):
        return "pdf_like"
    if lower.startswith(b"<?xml"):
        return "xml_like"
    return "other"


def _safe_prefix_classification(content: bytes) -> dict[str, Any]:
    """Return classification metadata without leaking arbitrary response bodies."""
    stripped = content.lstrip()
    return {
        "content_class": _content_class(content),
        "starts_with_json_object": stripped.startswith(b"{"),
        "starts_with_json_array": stripped.startswith(b"["),
        "starts_with_html": stripped[:32].lower().startswith((b"<!doctype html", b"<html")),
        "empty_body": len(stripped) == 0,
    }


def _schema_markers(schema: str, payload: Any) -> dict[str, Any]:
    result = {
        "schema_checked": schema,
        "schema_marker_pass": False,
        "markers": {},
    }
    if not isinstance(payload, dict):
        result["markers"]["top_level_object"] = False
        return result
    result["markers"]["top_level_object"] = True

    if schema == "schedule":
        league_schedule = payload.get("leagueSchedule")
        result["markers"].update(
            {
                "leagueSchedule_object": isinstance(league_schedule, dict),
                "gameDates_list": isinstance(
                    league_schedule.get("gameDates") if isinstance(league_schedule, dict) else None,
                    list,
                ),
            }
        )
        result["schema_marker_pass"] = all(result["markers"].values())
    elif schema == "boxscore":
        game = payload.get("game")
        result["markers"].update(
            {
                "game_object": isinstance(game, dict),
                "game_id_present": bool(
                    isinstance(game, dict) and str(game.get("gameId") or "").strip()
                ),
                "home_team_object": isinstance(
                    game.get("homeTeam") if isinstance(game, dict) else None, dict
                ),
                "away_team_object": isinstance(
                    game.get("awayTeam") if isinstance(game, dict) else None, dict
                ),
            }
        )
        result["schema_marker_pass"] = all(result["markers"].values())
    elif schema == "playbyplay":
        game = payload.get("game")
        actions = game.get("actions") if isinstance(game, dict) else None
        result["markers"].update(
            {
                "game_object": isinstance(game, dict),
                "game_id_present": bool(
                    isinstance(game, dict) and str(game.get("gameId") or "").strip()
                ),
                "actions_list": isinstance(actions, list),
                "actions_nonempty": isinstance(actions, list) and len(actions) > 0,
            }
        )
        result["schema_marker_pass"] = all(result["markers"].values())
    elif schema == "stats_api":
        result_sets = payload.get("resultSets", payload.get("resultSet"))
        result["markers"]["result_set_present"] = isinstance(result_sets, (dict, list))
        result["schema_marker_pass"] = result["markers"]["result_set_present"]
    else:
        result["markers"]["object_received"] = True
        result["schema_marker_pass"] = True
    return result


def _probe(spec: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    row: dict[str, Any] = {
        "name": spec["name"],
        "url": spec["url"],
        "kind": spec["kind"],
        "expected_schema": spec["schema"],
        "known_blocker": bool(spec.get("known_blocker")),
        "request_method": "GET",
    }
    try:
        response = httpx.get(
            spec["url"],
            headers=HTTP_HEADERS,
            timeout=float(spec["timeout_seconds"]),
            follow_redirects=True,
        )
        elapsed = round(time.monotonic() - started, 3)
        content = response.content
        row.update(
            {
                "reachable": True,
                "elapsed_seconds": elapsed,
                "http_status": int(response.status_code),
                "http_success": 200 <= response.status_code < 300,
                "final_url": str(response.url),
                "content_type": response.headers.get("content-type"),
                "content_length_header": response.headers.get("content-length"),
                "response_bytes": len(content),
                **_safe_prefix_classification(content),
            }
        )
        if spec["kind"] == "json":
            try:
                payload = response.json()
            except ValueError as exc:
                row.update(
                    {
                        "json_parse_success": False,
                        "json_error_type": type(exc).__name__,
                        "schema_marker_pass": False,
                    }
                )
            else:
                row["json_parse_success"] = True
                row.update(_schema_markers(spec["schema"], payload))
        else:
            text = response.text.casefold()
            row.update(
                {
                    "html_parse_attempted": False,
                    "html_body_contains_wnba_marker": "wnba" in text,
                    "html_body_contains_next_data_marker": "__next_data__" in text,
                    "html_body_contains_next_static_marker": "/_next/static/" in text,
                    "schema_marker_pass": (
                        200 <= response.status_code < 300
                        and len(content) > 0
                        and _content_class(content) == "html_like"
                    ),
                }
            )
        return row
    except Exception as exc:
        row.update(
            {
                "reachable": False,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "http_status": None,
                "http_success": False,
                "error_type": type(exc).__name__,
                "error_message_returned": False,
                "schema_marker_pass": False,
            }
        )
        return row


def build_report() -> dict[str, Any]:
    probes = [_probe(dict(spec)) for spec in PROBES]
    by_name = {row["name"]: row for row in probes}

    static_schedule = by_name["wnba_static_schedule_cdn"]
    boxscore = by_name["wnba_live_boxscore_cdn"]
    pbp = by_name["wnba_live_playbyplay_cdn"]
    schedule_web = by_name["wnba_official_schedule_web"]
    roster_web = by_name["wnba_official_roster_web"]
    stats = by_name["wnba_stats_commonallplayers_known_blocker"]

    live_data_green = (
        boxscore.get("http_success") is True
        and boxscore.get("json_parse_success") is True
        and boxscore.get("schema_marker_pass") is True
        and pbp.get("http_success") is True
        and pbp.get("json_parse_success") is True
        and pbp.get("schema_marker_pass") is True
    )
    static_schedule_green = (
        static_schedule.get("http_success") is True
        and static_schedule.get("json_parse_success") is True
        and static_schedule.get("schema_marker_pass") is True
    )
    official_web_green = (
        schedule_web.get("http_success") is True
        and schedule_web.get("schema_marker_pass") is True
        and roster_web.get("http_success") is True
        and roster_web.get("schema_marker_pass") is True
    )
    stats_green = (
        stats.get("http_success") is True
        and stats.get("json_parse_success") is True
        and stats.get("schema_marker_pass") is True
    )

    if live_data_green and not static_schedule_green:
        recommended_path = (
            "Keep official liveData CDN for boxscore/PBP history reconstruction, but replace the "
            "staticData schedule dependency with a separately validated official-web schedule source."
        )
    elif live_data_green and static_schedule_green:
        recommended_path = (
            "Official CDN paths are network-feasible; continue with a Step-7G-only history/rotation "
            "adapter and frozen-schema parity tests."
        )
    elif official_web_green:
        recommended_path = (
            "Official WNBA web pages remain reachable while CDN/Stats paths are not fully reliable; "
            "next inspect official page/Next.js data for schedule, roster, and historical identifiers."
        )
    else:
        recommended_path = (
            "GitHub Actions cannot reliably reach enough official WNBA sources; do not activate. "
            "Test the same matrix from another controlled execution path or add a vetted official-data relay."
        )

    return {
        "data_type": "wnba_step7g_official_network_matrix_v1",
        "created_at_utc": _utc_now_iso(),
        "historic_connectivity_game_id": HISTORIC_CONNECTIVITY_GAME_ID,
        "historic_connectivity_game_id_semantics": (
            "Stable historical probe only; not a current slate or production model input."
        ),
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "probes": probes,
        "matrix_summary": {
            "static_schedule_cdn_green": static_schedule_green,
            "live_data_boxscore_and_pbp_green": live_data_green,
            "official_web_schedule_and_roster_green": official_web_green,
            "stats_api_green": stats_green,
            "stats_api_expected_to_be_blocked_from_prior_evidence": True,
        },
        "production_activation_safe_now": False,
        "recommended_next_path": recommended_path,
    }


def main() -> int:
    report: dict[str, Any]
    try:
        report = build_report()
    except Exception as exc:
        report = {
            "data_type": "wnba_step7g_official_network_matrix_v1",
            "created_at_utc": _utc_now_iso(),
            "read_only": True,
            "production_mutation_performed": False,
            "supabase_mutation_performed": False,
            "sportsbook_called": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "frozen_shared_provider_behavior_changed": False,
            "matrix_completed": False,
            "error_type": type(exc).__name__,
            "error_message_returned": False,
            "production_activation_safe_now": False,
        }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if isinstance(report.get("probes"), list) else 1


if __name__ == "__main__":
    raise SystemExit(main())
