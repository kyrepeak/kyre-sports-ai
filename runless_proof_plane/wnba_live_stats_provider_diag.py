from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"
TARGET_DAY = "2026-10-07"
TARGET_SEASON = 2026


def _completed(event: dict) -> bool:
    status = (event.get("status") or {}).get("type") or {}
    return bool(
        status.get("completed")
        or str(status.get("state") or "").lower() == "post"
        or "final" in str(status.get("description") or status.get("detail") or "").lower()
    )


def _event_day(event: dict) -> str:
    raw = str(event.get("date") or "")
    return raw[:10]


def _summary_probe(payload: dict) -> dict:
    result = {
        "player_blocks": 0,
        "athlete_rows": 0,
        "rows_with_min_pts_reb_ast_labels": 0,
        "sample_labels": [],
        "sample_player": {},
    }
    blocks = ((payload or {}).get("boxscore") or {}).get("players") or []
    result["player_blocks"] = len(blocks)
    for block in blocks:
        for group in block.get("statistics") or []:
            labels = [str(x).upper() for x in (group.get("labels") or [])]
            keys = [str(x).upper() for x in (group.get("keys") or group.get("names") or [])]
            names = set(labels + keys)
            if labels and not result["sample_labels"]:
                result["sample_labels"] = labels[:24]
            athletes = group.get("athletes") or []
            result["athlete_rows"] += len(athletes)
            if {"MIN", "PTS", "REB", "AST"}.issubset(names):
                result["rows_with_min_pts_reb_ast_labels"] += len(athletes)
            if athletes and not result["sample_player"]:
                item = athletes[0]
                athlete = item.get("athlete") or {}
                result["sample_player"] = {
                    "name": athlete.get("displayName") or athlete.get("fullName") or "",
                    "didNotPlay": bool(item.get("didNotPlay")),
                    "stats": (item.get("stats") or [])[:24],
                }
            if athletes:
                break
    return result


def run_diagnostic() -> dict:
    out = {
        "target_day": TARGET_DAY,
        "season": TARGET_SEASON,
        "season_http": None,
        "season_events": 0,
        "completed_before_target": 0,
        "status_samples": [],
        "latest_completed_game_id": "",
        "latest_completed_game_day": "",
        "summary_http": None,
        "summary_probe": {},
        "classification": "UNKNOWN",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
            season = client.get(ESPN_SCOREBOARD, params={"dates": str(TARGET_SEASON), "limit": 1000})
            out["season_http"] = season.status_code
            season.raise_for_status()
            payload = season.json()
            events = payload.get("events") or []
            out["season_events"] = len(events)
            samples = []
            completed = []
            for event in events:
                status = (event.get("status") or {}).get("type") or {}
                if len(samples) < 8:
                    samples.append({
                        "id": str(event.get("id") or ""),
                        "date": _event_day(event),
                        "state": status.get("state"),
                        "completed": status.get("completed"),
                        "description": status.get("description") or status.get("detail"),
                    })
                day = _event_day(event)
                if day and day < TARGET_DAY and _completed(event):
                    completed.append(event)
            out["status_samples"] = samples
            out["completed_before_target"] = len(completed)
            if not completed:
                out["classification"] = "SEASON_HISTORY_EMPTY"
                return out
            completed.sort(key=lambda e: str(e.get("date") or ""), reverse=True)
            latest = completed[0]
            gid = str(latest.get("id") or "")
            out["latest_completed_game_id"] = gid
            out["latest_completed_game_day"] = _event_day(latest)
            summary = client.get(ESPN_SUMMARY, params={"event": gid})
            out["summary_http"] = summary.status_code
            summary.raise_for_status()
            probe = _summary_probe(summary.json())
            out["summary_probe"] = probe
            if probe.get("athlete_rows", 0) <= 0:
                out["classification"] = "SUMMARY_PLAYER_ROWS_EMPTY"
            elif probe.get("rows_with_min_pts_reb_ast_labels", 0) <= 0:
                out["classification"] = "SUMMARY_STAT_LABEL_MISMATCH"
            else:
                out["classification"] = "ESPN_HISTORY_AND_SUMMARY_HEALTHY"
            return out
    except Exception as exc:
        out["classification"] = "PROVIDER_EXCEPTION"
        out["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        return out


def install_startup_diagnostic(app) -> None:
    @app.on_event("startup")
    def _run_wnba_live_stats_provider_diag() -> None:
        result = run_diagnostic()
        app.state.wnba_live_stats_provider_diag = result
        print("WNBA_LIVE_STATS_PROVIDER_DIAG=" + json.dumps(result, sort_keys=True), flush=True)
