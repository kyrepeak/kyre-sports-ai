"""OFF-only structural probe for first-party WNBA officiating surfaces.

This probe never enables production, scheduler, feed, sportsbook, persistence,
or Supabase behavior. It inspects only sanitized structure from official
WNBA.com server-rendered game data so Step 7G can prove whether referee/official
assignment fields exist before any adapter is written.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api.wnba_step7g_first_party_history import _game_page
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)

SEASON = 2026
KEYWORDS = ("official", "referee", "referee", "crew")
TEAM_STAT_KEYS = (
    "fieldGoalsAttempted",
    "freeThrowsMade",
    "freeThrowsAttempted",
    "freeThrowsPercentage",
    "foulsPersonal",
    "points",
    "minutes",
)
OFF_SWITCHES = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    "WNBA_STEP7G_FIRST_PARTY_ENABLED",
)


def _parse_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _status_category(game: dict[str, Any]) -> str:
    status = game.get("status")
    if not isinstance(status, dict):
        return ""
    return str(status.get("category") or "").strip().casefold()


def _select_games(schedule: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    now = datetime.now(timezone.utc)
    rows = [row for row in schedule.get("games", []) if isinstance(row, dict)]

    finals = []
    future = []
    for row in rows:
        dt = _parse_utc(row.get("game_datetime_utc"))
        category = _status_category(row)
        if category == "final" and dt is not None and dt <= now:
            finals.append((dt, row))
        if category == "scheduled" and dt is not None and dt > now:
            future.append((dt, row))

    if not finals:
        raise RuntimeError("No completed 2026 WNBA game was available for officiating probe.")
    if not future:
        raise RuntimeError("No future scheduled 2026 WNBA game was available for officiating probe.")

    finals.sort(key=lambda item: item[0], reverse=True)
    future.sort(key=lambda item: item[0])
    return finals[0][1], future[0][1]


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        return text[:160] if len(text) <= 160 else text[:157] + "..."
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    if isinstance(value, dict):
        return {"type": "dict", "keys": sorted(str(key) for key in value.keys())[:40]}
    return {"type": type(value).__name__}


def _keyword_hits(value: Any, path: str = "root") -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if any(token in key_text.casefold() for token in KEYWORDS):
                hits.append({"path": child_path, "value": _safe_scalar(child)})
            hits.extend(_keyword_hits(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_keyword_hits(child, f"{path}[{index}]"))
    return hits


def _team_stat_shape(game: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for side in ("awayTeam", "homeTeam"):
        team = game.get(side)
        if not isinstance(team, dict):
            result[side] = {"present": False}
            continue
        stats = team.get("statistics")
        if not isinstance(stats, dict):
            result[side] = {"present": True, "statistics_present": False}
            continue
        result[side] = {
            "present": True,
            "teamId": team.get("teamId"),
            "teamTricode": team.get("teamTricode"),
            "statistics_present": True,
            "required_keys": {key: stats.get(key) for key in TEAM_STAT_KEYS},
            "required_keys_present": {key: key in stats for key in TEAM_STAT_KEYS},
        }
    return result


def _probe_game(label: str, schedule_game: dict[str, Any]) -> dict[str, Any]:
    game_id = str(schedule_game.get("game_id") or "")
    props, game, retrieved_at, cache_hit, ttl, url = _game_page(game_id, ttl_seconds=1)
    return {
        "label": label,
        "game_id": game_id,
        "scheduled_datetime_utc": schedule_game.get("game_datetime_utc"),
        "schedule_status": schedule_game.get("status"),
        "source_url": url,
        "retrieved_at_utc": retrieved_at,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": ttl,
        "page_props_top_level_keys": sorted(str(key) for key in props.keys()),
        "game_top_level_keys": sorted(str(key) for key in game.keys()),
        "officiating_keyword_hits": _keyword_hits(props, "pageProps"),
        "team_stat_shape": _team_stat_shape(game),
    }


def main() -> int:
    bad_switches = {
        name: os.environ.get(name)
        for name in OFF_SWITCHES
        if str(os.environ.get(name, "false")).strip().casefold() not in {"", "0", "false", "no", "off"}
    }
    if bad_switches:
        raise RuntimeError(f"OFF-only probe refused to run with enabled switches: {bad_switches}")

    schedule = get_step7g_step4n_season_schedule_dataset(SEASON)
    final_game, future_game = _select_games(schedule)
    payload = {
        "probe": "WNBA Step 7G officiating first-party surface",
        "season": SEASON,
        "production_off_asserted": True,
        "full_html_captured": False,
        "headers_or_cookies_captured": False,
        "completed_game": _probe_game("latest_completed", final_game),
        "future_game": _probe_game("next_scheduled", future_game),
    }

    output = Path("/tmp/wnba_step7g_officiating_surface_probe.json")
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"OFFICIATING_SURFACE_PROBE_ARTIFACT={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
