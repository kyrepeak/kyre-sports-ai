"""Map WNBA.com's public game/player route surface for Step 7G.

This read-only diagnostic combines four first-party artifacts that remain
reachable from GitHub Actions:

* the WNBA schedule page ``__NEXT_DATA__`` build id;
* the public Next.js build manifest;
* the same-origin ``/api/schedule`` season payload; and
* the public ``_app`` JavaScript containing game-card URL construction.

The objective is to derive exact WNBA.com page routes for a known final game
and player without guessing. No production state, feed, Supabase object,
sportsbook, scheduler, or model is touched.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

REPORT_PATH = Path("step7g-www-route-surface-probe.json")
SEASON = 2026
TARGET_GAME_ID = "1022600288"
TARGET_PLAYER_ID = 1629498
SCHEDULE_PAGE = "https://www.wnba.com/schedule"
SCHEDULE_API = f"https://www.wnba.com/api/schedule?season={SEASON}"
TEAM_PAGE = "https://www.wnba.com/team/1611661319/las-vegas-aces"
CONTEXT_RADIUS = 2600

HTTP_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/json,text/javascript,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
}

ROUTE_STRING_RE = re.compile(r"[\"'](/[^\"']+)[\"']")
SAFE_GAME_KEYS = {
    "gameId", "gameCode", "gameStatus", "gameStatusText", "gameLabel",
    "gameSubLabel", "gameTimeUTC", "gameEt", "gameDateTimeUTC", "gameDate",
    "seriesText", "seriesGameNumber", "ifNecessary", "arenaName", "arenaCity",
    "arenaState", "branchLink", "gameDetailsUrl", "boxScoreUrl", "boxscoreUrl",
    "leaguePassUrl", "leaguePassURL", "homeTeam", "awayTeam", "broadcasters",
}
SAFE_TEAM_KEYS = {
    "teamId", "teamName", "teamCity", "teamTricode", "wins", "losses",
    "score", "seed", "record",
}
SAFE_PLAYER_KEYS = {
    "id", "playerId", "personId", "firstName", "lastName", "displayName",
    "name", "number", "position", "merchUrl", "supplementalStatus",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.script_srcs: list[str] = []
        self._capture_next = False
        self._next_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        data = {str(k): v for k, v in attrs}
        src = data.get("src")
        if isinstance(src, str) and src.strip():
            self.script_srcs.append(src.strip())
        if data.get("id") == "__NEXT_DATA__":
            self._capture_next = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._capture_next:
            self._capture_next = False

    def handle_data(self, data: str) -> None:
        if self._capture_next:
            self._next_parts.append(data)

    @property
    def next_data_text(self) -> str:
        return "".join(self._next_parts).strip()


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


def _json(url: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    response, meta = _fetch(url)
    if response is None or meta.get("http_success") is not True:
        meta["json_parse_success"] = False
        return None, meta
    try:
        payload = response.json()
    except ValueError as exc:
        meta["json_parse_success"] = False
        meta["json_error_type"] = type(exc).__name__
        return None, meta
    meta["json_parse_success"] = isinstance(payload, dict)
    return (payload if isinstance(payload, dict) else None), meta


def _sanitize_team(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, Any] = {}
    for key in SAFE_TEAM_KEYS:
        item = value.get(key)
        if item is None or isinstance(item, (str, int, float, bool)):
            if item is not None:
                result[key] = item
    return result


def _sanitize_game(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"all_keys": sorted(map(str, value.keys()))}
    for key in SAFE_GAME_KEYS:
        item = value.get(key)
        if key in {"homeTeam", "awayTeam"}:
            team = _sanitize_team(item)
            if team is not None:
                result[key] = team
        elif isinstance(item, list):
            result[key] = {"type": "array", "length": len(item)}
        elif item is None or isinstance(item, (str, int, float, bool)):
            if item is not None:
                result[key] = item
    # Surface every primitive URL/path/code-ish field, even when the exact key is new.
    for key, item in value.items():
        lower = str(key).casefold()
        if not isinstance(item, (str, int, float, bool)) or item is None:
            continue
        if any(token in lower for token in ("url", "link", "slug", "path", "code", "label")):
            result.setdefault(str(key), item)
    return result


def _find_game(payload: dict[str, Any], game_id: str) -> dict[str, Any] | None:
    root = payload.get("leagueSchedule")
    if not isinstance(root, dict):
        return None
    for block in root.get("gameDates") or []:
        if not isinstance(block, dict):
            continue
        for game in block.get("games") or []:
            if isinstance(game, dict) and str(game.get("gameId") or "").strip() == game_id:
                return game
    return None


def _find_player(payload: dict[str, Any], player_id: int) -> dict[str, Any] | None:
    props = payload.get("props")
    page_props = props.get("pageProps") if isinstance(props, dict) else None
    team = page_props.get("team") if isinstance(page_props, dict) else None
    roster = team.get("roster") if isinstance(team, dict) else None
    if not isinstance(roster, list):
        return None
    for row in roster:
        if isinstance(row, dict) and int(row.get("id") or -1) == player_id:
            return row
    return None


def _sanitize_player(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, Any] = {"all_keys": sorted(map(str, value.keys()))}
    for key in SAFE_PLAYER_KEYS:
        item = value.get(key)
        if item is None or isinstance(item, (str, int, float, bool)):
            if item is not None:
                result[key] = item
    for key, item in value.items():
        lower = str(key).casefold()
        if not isinstance(item, (str, int, float, bool)) or item is None:
            continue
        if any(token in lower for token in ("url", "link", "slug", "path")):
            result.setdefault(str(key), item)
    return result


def _manifest_routes(text: str) -> list[str]:
    routes: list[str] = []
    seen: set[str] = set()
    for match in ROUTE_STRING_RE.finditer(text):
        route = match.group(1).replace("\\/", "/")
        lower = route.casefold()
        if not any(token in lower for token in ("game", "box", "play", "player", "stats", "team", "schedule")):
            continue
        if route in seen:
            continue
        seen.add(route)
        routes.append(route)
    return routes


def _contexts(text: str, marker: str, limit: int = 8) -> list[str]:
    result: list[str] = []
    start = 0
    while len(result) < limit:
        index = text.find(marker, start)
        if index < 0:
            break
        lo = max(0, index - CONTEXT_RADIUS)
        hi = min(len(text), index + len(marker) + CONTEXT_RADIUS)
        result.append(" ".join(text[lo:hi].replace("\\/", "/").split()))
        start = index + len(marker)
    return result


def _script_url(parser: _Parser, base_url: str, token: str) -> str | None:
    for src in parser.script_srcs:
        if token in src:
            return urljoin(base_url, src)
    return None


def build_report() -> dict[str, Any]:
    schedule_page, schedule_page_meta = _fetch(SCHEDULE_PAGE)
    if schedule_page is None or schedule_page_meta.get("http_success") is not True:
        raise RuntimeError("WNBA schedule page was not reachable.")
    schedule_parser = _Parser()
    schedule_parser.feed(schedule_page.text)
    if not schedule_parser.next_data_text:
        raise RuntimeError("WNBA schedule page did not expose __NEXT_DATA__.")
    schedule_next = json.loads(schedule_parser.next_data_text)
    if not isinstance(schedule_next, dict):
        raise RuntimeError("WNBA schedule __NEXT_DATA__ was not an object.")
    build_id = schedule_next.get("buildId")
    if not isinstance(build_id, str) or not build_id:
        raise RuntimeError("WNBA schedule page is missing buildId.")

    manifest_url = f"https://www.wnba.com/_next/static/{build_id}/_buildManifest.js"
    manifest, manifest_meta = _fetch(manifest_url)
    manifest_routes = _manifest_routes(manifest.text) if manifest is not None else []

    schedule_payload, schedule_api_meta = _json(SCHEDULE_API)
    if schedule_payload is None:
        raise RuntimeError("WNBA first-party schedule API was not available.")
    game = _find_game(schedule_payload, TARGET_GAME_ID)
    if game is None:
        raise RuntimeError(f"Target WNBA game {TARGET_GAME_ID} was not found in first-party schedule.")

    team_page, team_page_meta = _fetch(TEAM_PAGE)
    team_next = None
    team_parser = _Parser()
    if team_page is not None and team_page_meta.get("http_success") is True:
        team_parser.feed(team_page.text)
        if team_parser.next_data_text:
            parsed = json.loads(team_parser.next_data_text)
            if isinstance(parsed, dict):
                team_next = parsed
    player = _find_player(team_next, TARGET_PLAYER_ID) if isinstance(team_next, dict) else None

    app_url = _script_url(schedule_parser, str(schedule_page.url), "/pages/_app-")
    app_response, app_meta = _fetch(app_url) if app_url else (None, {"reachable": False, "reason": "_app_script_not_found"})
    app_text = app_response.text if app_response is not None else ""
    markers = (
        "gameDetailsUrl",
        "boxScoreUrl",
        "getBoxscoreEndpoint",
        "getLivePlayByPlayEndpoint",
        "playerLink",
        "gameID",
        "/game/",
        "/box-score/",
        "/play-by-play/",
        "/player/",
    )
    app_contexts = {marker: _contexts(app_text, marker) for marker in markers}

    route_classes = {
        "game": [r for r in manifest_routes if "game" in r.casefold()],
        "player": [r for r in manifest_routes if "player" in r.casefold()],
        "team": [r for r in manifest_routes if "team" in r.casefold()],
        "stats": [r for r in manifest_routes if "stats" in r.casefold()],
        "schedule": [r for r in manifest_routes if "schedule" in r.casefold()],
    }

    game_sanitized = _sanitize_game(game)
    primitive_values = [
        str(value)
        for key, value in game_sanitized.items()
        if key != "all_keys" and isinstance(value, (str, int, float, bool))
    ]
    direct_game_page_hint = next(
        (
            value for value in primitive_values
            if TARGET_GAME_ID in value and (value.startswith("/") or "wnba.com" in value)
        ),
        None,
    )

    return {
        "data_type": "wnba_step7g_www_route_surface_probe_v1",
        "created_at_utc": _utc_now_iso(),
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "build_id": build_id,
        "schedule_page_request": schedule_page_meta,
        "manifest_request": manifest_meta,
        "schedule_api_request": schedule_api_meta,
        "team_page_request": team_page_meta,
        "app_script_request": app_meta,
        "manifest_routes": manifest_routes,
        "route_classes": route_classes,
        "target_game": game_sanitized,
        "target_player": _sanitize_player(player),
        "app_contexts": app_contexts,
        "discovery": {
            "dynamic_game_route_count": len(route_classes["game"]),
            "dynamic_player_route_count": len(route_classes["player"]),
            "direct_game_page_hint": direct_game_page_hint,
            "game_details_url_field_present": any(
                key.casefold() == "gamedetailsurl" for key in game.keys()
            ),
            "box_score_url_field_present": any(
                key.casefold() in {"boxscoreurl", "box_score_url"} for key in game.keys()
            ),
            "production_activation_safe_now": False,
        },
    }


def main() -> int:
    try:
        report = build_report()
    except Exception as exc:
        report = {
            "data_type": "wnba_step7g_www_route_surface_probe_v1",
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
    return 0 if "manifest_routes" in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
