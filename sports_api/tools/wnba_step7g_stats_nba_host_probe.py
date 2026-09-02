"""Read-only Step 7G probe of WNBA data through the current frontend Stats host.

WNBA.com's production frontend currently configures STATS_API_HOST as
``https://stats.nba.com`` and its Stats namespace as ``/stats``. The frozen API
code predates that frontend configuration and calls ``stats.wnba.com``.

This diagnostic tests the exact WNBA core requests needed by Step 7G against
the current frontend host, with LeagueID=10 where applicable. It performs no
production mutation, scheduler work, sportsbook call, model execution, or
Supabase write.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

import httpx

REPORT_PATH = Path("step7g-stats-nba-host-probe.json")
SEASON = 2026
LEAGUE_ID = "10"
SAMPLE_PLAYER_ID = 1629498  # Jackie Young; official ID from WNBA.com team roster data.
SCHEDULE_URL = f"https://www.wnba.com/api/schedule?season={SEASON}"
CURRENT_STATS_HOST = "https://stats.nba.com/stats"
LEGACY_STATS_HOST = "https://stats.wnba.com/stats"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
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


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _fetch_json(
    url: str,
    *,
    params: list[tuple[str, Any]] | None = None,
    timeout: float = 12.0,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    started = time.monotonic()
    try:
        response = httpx.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )
        meta: dict[str, Any] = {
            "reachable": True,
            "url": url,
            "final_url": str(response.url),
            "http_status": int(response.status_code),
            "http_success": 200 <= response.status_code < 300,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "content_type": response.headers.get("content-type"),
            "response_bytes": len(response.content),
        }
        try:
            payload = response.json()
        except ValueError as exc:
            meta.update(
                {
                    "json_parse_success": False,
                    "json_error_type": type(exc).__name__,
                    "body_class": (
                        "html_like"
                        if response.content.lstrip()[:32].lower().startswith((b"<!doctype html", b"<html"))
                        else "other"
                    ),
                }
            )
            return None, meta
        meta["json_parse_success"] = isinstance(payload, dict)
        if not isinstance(payload, dict):
            return None, meta
        return payload, meta
    except Exception as exc:
        return None, {
            "reachable": False,
            "url": url,
            "http_status": None,
            "http_success": False,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "error_type": type(exc).__name__,
            "error_message_returned": False,
            "json_parse_success": False,
        }


def _date_text(block: dict[str, Any]) -> str:
    raw = _clean(block.get("gameDate")) or ""
    return raw[:10] if len(raw) >= 10 and raw[4:5] == "-" else raw


def _select_final_game() -> tuple[str, str]:
    payload, meta = _fetch_json(SCHEDULE_URL, timeout=20.0)
    if payload is None or meta.get("http_success") is not True:
        raise RuntimeError("Could not load WNBA.com first-party schedule to select a final game.")
    root = payload.get("leagueSchedule")
    if not isinstance(root, dict):
        raise RuntimeError("WNBA.com schedule is missing leagueSchedule.")
    candidates: list[tuple[str, str]] = []
    for block in root.get("gameDates") or []:
        if not isinstance(block, dict):
            continue
        day = _date_text(block)
        for game in block.get("games") or []:
            if not isinstance(game, dict):
                continue
            gid = _clean(game.get("gameId"))
            try:
                status = int(game.get("gameStatus"))
            except (TypeError, ValueError):
                status = -1
            if gid and len(gid) == 10 and gid.isdigit() and status == 3:
                candidates.append((day, gid))
    if not candidates:
        raise RuntimeError("WNBA.com schedule contained no final game for the probe.")
    candidates.sort(reverse=True)
    return candidates[0][1], candidates[0][0]


def _result_sets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("resultSets", payload.get("resultSet"))
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    return []


def _flat_summary(payload: dict[str, Any]) -> dict[str, Any]:
    sets = _result_sets(payload)
    return {
        "top_level_keys": sorted(payload.keys()),
        "result_set_count": len(sets),
        "result_sets": [
            {
                "name": row.get("name"),
                "header_count": len(row.get("headers") or []) if isinstance(row.get("headers"), list) else None,
                "row_count": len(row.get("rowSet") or []) if isinstance(row.get("rowSet"), list) else None,
                "headers": (row.get("headers") or [])[:80] if isinstance(row.get("headers"), list) else [],
            }
            for row in sets[:12]
        ],
    }


def _box_summary(payload: dict[str, Any]) -> dict[str, Any]:
    box = payload.get("boxScoreTraditional")
    if not isinstance(box, dict):
        return {"top_level_keys": sorted(payload.keys()), "box_score_present": False}
    home = box.get("homeTeam") if isinstance(box.get("homeTeam"), dict) else {}
    away = box.get("awayTeam") if isinstance(box.get("awayTeam"), dict) else {}
    return {
        "top_level_keys": sorted(payload.keys()),
        "box_score_present": True,
        "game_id": box.get("gameId"),
        "home_team_id": home.get("teamId"),
        "away_team_id": away.get("teamId"),
        "home_player_count": len(home.get("players") or []) if isinstance(home.get("players"), list) else 0,
        "away_player_count": len(away.get("players") or []) if isinstance(away.get("players"), list) else 0,
    }


def _pbp_summary(payload: dict[str, Any]) -> dict[str, Any]:
    game = payload.get("game")
    if isinstance(game, dict):
        actions = game.get("actions")
        return {
            "top_level_keys": sorted(payload.keys()),
            "game_object_present": True,
            "game_id": game.get("gameId"),
            "action_count": len(actions) if isinstance(actions, list) else None,
        }
    # Some Stats v3 responses are flat result sets rather than liveData-style objects.
    return {**_flat_summary(payload), "game_object_present": False}


def _probe(
    name: str,
    endpoint: str,
    params: list[tuple[str, Any]],
    *,
    summary_kind: str = "flat",
    timeout: float = 12.0,
    host: str = CURRENT_STATS_HOST,
) -> dict[str, Any]:
    payload, request = _fetch_json(f"{host}/{endpoint}", params=params, timeout=timeout)
    row: dict[str, Any] = {
        "name": name,
        "host": host,
        "endpoint": endpoint,
        "request": request,
        "parameter_names": [key for key, _ in params],
    }
    if payload is None:
        row["schema_pass"] = False
        return row
    if summary_kind == "box":
        summary = _box_summary(payload)
        schema_pass = summary.get("box_score_present") is True
    elif summary_kind == "pbp":
        summary = _pbp_summary(payload)
        schema_pass = bool(
            summary.get("game_object_present") is True
            or int(summary.get("result_set_count") or 0) > 0
        )
    else:
        summary = _flat_summary(payload)
        schema_pass = int(summary.get("result_set_count") or 0) > 0
    row["payload_summary"] = summary
    row["schema_pass"] = schema_pass
    return row


def build_report() -> dict[str, Any]:
    game_id, game_date = _select_final_game()

    probes = [
        _probe(
            "commonallplayers_current_host",
            "commonallplayers",
            [
                ("LeagueID", LEAGUE_ID),
                ("Season", str(SEASON)),
                ("IsOnlyCurrentSeason", "1"),
            ],
        ),
        _probe(
            "playergamelog_current_host",
            "playergamelog",
            [
                ("PlayerID", str(SAMPLE_PLAYER_ID)),
                ("Season", str(SEASON)),
                ("SeasonType", "Regular Season"),
                ("LeagueID", LEAGUE_ID),
                ("DateFrom", ""),
                ("DateTo", ""),
            ],
        ),
        _probe(
            "boxscoretraditionalv3_current_host",
            "boxscoretraditionalv3",
            [
                ("EndPeriod", "14"),
                ("EndRange", "0"),
                ("GameID", game_id),
                ("RangeType", "0"),
                ("StartPeriod", "0"),
                ("StartRange", "0"),
            ],
            summary_kind="box",
        ),
        _probe(
            "gamerotation_current_host",
            "gamerotation",
            [
                ("LeagueID", LEAGUE_ID),
                ("GameID", game_id),
                ("RotationStat", "PLAYER_PTS"),
            ],
        ),
        _probe(
            "playbyplayv3_current_host",
            "playbyplayv3",
            [
                ("GameID", game_id),
                ("StartPeriod", "0"),
                ("EndPeriod", "0"),
            ],
            summary_kind="pbp",
        ),
        # Control: one short legacy-host request confirms whether the old hostname remains blocked.
        _probe(
            "playergamelog_legacy_host_control",
            "playergamelog",
            [
                ("PlayerID", str(SAMPLE_PLAYER_ID)),
                ("Season", str(SEASON)),
                ("SeasonType", "Regular Season"),
                ("LeagueID", LEAGUE_ID),
                ("DateFrom", ""),
                ("DateTo", ""),
            ],
            timeout=5.0,
            host=LEGACY_STATS_HOST,
        ),
    ]

    by_name = {row["name"]: row for row in probes}
    current_core_names = (
        "playergamelog_current_host",
        "boxscoretraditionalv3_current_host",
        "gamerotation_current_host",
    )
    current_core_green = all(
        (by_name[name].get("request") or {}).get("http_success") is True
        and (by_name[name].get("request") or {}).get("json_parse_success") is True
        and by_name[name].get("schema_pass") is True
        for name in current_core_names
    )
    roster_green = (
        (by_name["commonallplayers_current_host"].get("request") or {}).get("http_success") is True
        and by_name["commonallplayers_current_host"].get("schema_pass") is True
    )
    pbp_green = (
        (by_name["playbyplayv3_current_host"].get("request") or {}).get("http_success") is True
        and by_name["playbyplayv3_current_host"].get("schema_pass") is True
    )
    legacy_green = (
        (by_name["playergamelog_legacy_host_control"].get("request") or {}).get("http_success") is True
        and by_name["playergamelog_legacy_host_control"].get("schema_pass") is True
    )

    return {
        "data_type": "wnba_step7g_stats_nba_host_probe_v1",
        "created_at_utc": _utc_now_iso(),
        "season": SEASON,
        "league_id": LEAGUE_ID,
        "sample_player_id": SAMPLE_PLAYER_ID,
        "selected_final_game_id": game_id,
        "selected_final_game_date": game_date,
        "frontend_config_evidence": {
            "production_stats_api_host": "https://stats.nba.com",
            "stats_namespace": "stats",
            "source": "public WNBA.com production JavaScript endpoint builder",
        },
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "probes": probes,
        "feasibility": {
            "current_stats_host_core_history_and_rotation_green": current_core_green,
            "current_stats_host_roster_green": roster_green,
            "current_stats_host_playbyplay_green": pbp_green,
            "legacy_stats_host_control_green": legacy_green,
            "stats_host_migration_candidate": current_core_green and not legacy_green,
            "production_activation_safe_now": False,
        },
        "next_required_step": (
            "If the current stats host core probes are green, build a Step-7G-only Stats-host "
            "adapter by changing only the injected base host, then run frozen-schema parity and "
            "recent-history/rotation integrity tests before any production one-shot."
        ),
    }


def main() -> int:
    try:
        report = build_report()
    except Exception as exc:
        report = {
            "data_type": "wnba_step7g_stats_nba_host_probe_v1",
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
