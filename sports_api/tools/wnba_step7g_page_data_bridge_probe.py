"""Probe WNBA.com server-rendered game/player pages as a Step 7G data bridge.

Direct cloud requests to stats.wnba.com, stats.nba.com, and cdn.wnba.com JSON
resources are blocked/intercepted in the current execution environments. The
public WNBA website itself remains reachable. This read-only probe asks whether
WNBA.com's own server-rendered Next.js pages expose the official box score,
play-by-play, player history, or rotation evidence needed by Step 7G.

It also inspects the route-specific public JavaScript chunks for first-party
fetch paths. No production state, Supabase data, sportsbook provider, scheduler,
model, or feed is changed.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urljoin

import httpx

REPORT_PATH = Path("step7g-page-data-bridge-probe.json")
SCHEDULE_PAGE = "https://www.wnba.com/schedule"
TARGET_GAME_ID = "1022600288"
TARGET_PLAYER_ID = "1629498"
PAGES = (
    ("game_summary", f"https://www.wnba.com/game/{TARGET_GAME_ID}"),
    ("game_box_score", f"https://www.wnba.com/game/{TARGET_GAME_ID}/box-score"),
    ("game_play_by_play", f"https://www.wnba.com/game/{TARGET_GAME_ID}/play-by-play"),
    ("player", f"https://www.wnba.com/player/{TARGET_PLAYER_ID}"),
)
ROUTE_KEYS = (
    "/game/[...slug]",
    "/player/[...slug]",
    "/player_legacy/[...id]",
)
INTERESTING_KEYS = {
    "gameid", "game_id", "gamecode", "gamestatus", "gamestatustext",
    "boxscore", "boxscoretraditional", "boxscoretraditionalv3", "players",
    "player", "personid", "playerid", "player_id", "statistics", "stats",
    "actions", "actionnumber", "periods", "playbyplay", "play_by_play",
    "rotation", "rotations", "gamerotation", "gamelog", "game_log",
    "recentgames", "recent_games", "games", "hometeam", "awayteam",
    "visitorteam", "teamid", "teamtricode", "minutes", "starter",
    "starters", "lineups", "lineup", "livegame", "game",
}
SAFE_PRIMITIVE_KEYS = {
    "gameId", "gameID", "game_id", "gameCode", "gameStatus", "gameStatusText",
    "gameTimeUTC", "gameDateTimeUTC", "personId", "playerId", "player_id",
    "id", "name", "displayName", "playerName", "firstName", "familyName",
    "lastName", "teamId", "teamID", "teamTricode", "teamName", "teamCity",
    "position", "starter", "played", "minutes", "points", "rebounds",
    "reboundsTotal", "assists", "turnovers", "fieldGoalsMade",
    "fieldGoalsAttempted", "threePointersMade", "threePointersAttempted",
    "freeThrowsMade", "freeThrowsAttempted", "actionNumber", "actionId",
    "actionType", "subType", "description", "period", "clock", "scoreHome",
    "scoreAway", "inTimeReal", "outTimeReal", "IN_TIME_REAL", "OUT_TIME_REAL",
    "PLAYER_PTS", "PT_DIFF", "USG_PCT", "GAME_ID", "PERSON_ID", "TEAM_ID",
}
SCRIPT_MARKERS = (
    "getServerSideProps", "getStaticProps", "getBoxscoreEndpoint",
    "getLivePlayByPlayEndpoint", "boxScoreTraditional", "boxscoretraditionalv3",
    "playbyplayv3", "playergamelog", "gameLog", "recentGames", "gamerotation",
    "rotation", "fetch(", "/api/", "STATS_API_HOST", "CDN_HOST",
)
MAX_PATHS = 120
MAX_SAMPLES = 8
MAX_SCRIPT_CONTEXTS = 5
CONTEXT_RADIUS = 1800

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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _NextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.script_srcs: list[str] = []
        self._capture_next = False
        self._next_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        data = {str(key): value for key, value in attrs}
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


def _fetch(url: str, *, timeout: float = 25.0) -> tuple[httpx.Response | None, dict[str, Any]]:
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


def _safe_sample(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"keys": sorted(map(str, value.keys()))[:100]}
    for key in SAFE_PRIMITIVE_KEYS:
        item = value.get(key)
        if item is None or isinstance(item, (str, int, float, bool)):
            if item is not None:
                result[key] = item
    return result


def _structure(payload: dict[str, Any]) -> dict[str, Any]:
    key_counts: Counter[str] = Counter()
    paths: list[str] = []
    game_samples: list[dict[str, Any]] = []
    player_samples: list[dict[str, Any]] = []
    action_samples: list[dict[str, Any]] = []
    rotation_samples: list[dict[str, Any]] = []

    for path, value in _walk(payload):
        if not isinstance(value, dict):
            continue
        lower = {str(key).casefold(): key for key in value}
        for normalized, original in lower.items():
            if normalized in INTERESTING_KEYS:
                key_counts[normalized] += 1
                if len(paths) < MAX_PATHS:
                    paths.append(f"{path}.{original}")
        if len(game_samples) < MAX_SAMPLES and any(key in lower for key in ("gameid", "game_id", "gamecode")):
            game_samples.append({"path": path, "sample": _safe_sample(value)})
        if len(player_samples) < MAX_SAMPLES and any(key in lower for key in ("personid", "playerid", "player_id")):
            player_samples.append({"path": path, "sample": _safe_sample(value)})
        if len(action_samples) < MAX_SAMPLES and any(key in lower for key in ("actionnumber", "actionid", "actiontype")):
            action_samples.append({"path": path, "sample": _safe_sample(value)})
        if len(rotation_samples) < MAX_SAMPLES and (
            any(key in lower for key in ("in_time_real", "out_time_real"))
            or {"in_time_real", "out_time_real"}.issubset(lower)
        ):
            rotation_samples.append({"path": path, "sample": _safe_sample(value)})

    props = payload.get("props")
    page_props = props.get("pageProps") if isinstance(props, dict) else None
    return {
        "top_level_keys": sorted(payload.keys()),
        "page": payload.get("page"),
        "build_id": payload.get("buildId"),
        "query": payload.get("query") if isinstance(payload.get("query"), dict) else None,
        "page_props_is_object": isinstance(page_props, dict),
        "page_props_keys": sorted(page_props.keys())[:120] if isinstance(page_props, dict) else [],
        "interesting_key_counts": dict(sorted(key_counts.items())),
        "interesting_paths": paths,
        "game_samples": game_samples,
        "player_samples": player_samples,
        "action_samples": action_samples,
        "rotation_samples": rotation_samples,
        "contains_target_game_id": TARGET_GAME_ID in json.dumps(payload, default=str),
        "contains_target_player_id": TARGET_PLAYER_ID in json.dumps(payload, default=str),
        "boxscore_evidence": any(key_counts.get(key, 0) for key in ("boxscore", "boxscoretraditional", "boxscoretraditionalv3")),
        "playbyplay_evidence": any(key_counts.get(key, 0) for key in ("actions", "playbyplay", "play_by_play")),
        "rotation_evidence": any(key_counts.get(key, 0) for key in ("rotation", "rotations", "gamerotation")) or bool(rotation_samples),
        "game_log_evidence": any(key_counts.get(key, 0) for key in ("gamelog", "game_log", "recentgames", "recent_games")),
    }


def _parse_next(response: httpx.Response) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    parser = _NextParser()
    parser.feed(response.text)
    raw = parser.next_data_text
    meta: dict[str, Any] = {
        "next_data_marker_present": "__NEXT_DATA__" in response.text,
        "script_src_count": len(parser.script_srcs),
    }
    if not raw:
        meta["next_data_parse_success"] = False
        return None, meta
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        meta.update({"next_data_parse_success": False, "error_type": type(exc).__name__})
        return None, meta
    meta["next_data_parse_success"] = isinstance(payload, dict)
    meta["next_data_bytes"] = len(raw.encode("utf-8"))
    return payload if isinstance(payload, dict) else None, meta


def _next_data_url(build_id: str, page_url: str) -> str:
    path = httpx.URL(page_url).path.strip("/")
    if not path:
        path = "index"
    return f"https://www.wnba.com/_next/data/{build_id}/{path}.json"


def _route_assets(manifest_text: str, route: str) -> list[str]:
    # Next build manifests are JS object literals. Find the quoted route key and
    # parse only its immediate array of quoted asset strings.
    candidates = [f'"{route}"', f"'{route}'"]
    index = next((manifest_text.find(token) for token in candidates if manifest_text.find(token) >= 0), -1)
    if index < 0:
        return []
    colon = manifest_text.find(":", index)
    start = manifest_text.find("[", colon)
    if colon < 0 or start < 0:
        return []
    depth = 0
    end = -1
    quote: str | None = None
    escaped = False
    for pos in range(start, min(len(manifest_text), start + 20000)):
        ch = manifest_text[pos]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in {"'", '"'}:
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = pos
                break
    if end < 0:
        return []
    segment = manifest_text[start : end + 1]
    assets = re.findall(r'["\']([^"\']+\.js)["\']', segment)
    return list(dict.fromkeys(assets))


def _contexts(text: str, marker: str) -> list[str]:
    result: list[str] = []
    start = 0
    while len(result) < MAX_SCRIPT_CONTEXTS:
        index = text.find(marker, start)
        if index < 0:
            break
        lo = max(0, index - CONTEXT_RADIUS)
        hi = min(len(text), index + len(marker) + CONTEXT_RADIUS)
        result.append(" ".join(text[lo:hi].replace("\\/", "/").split()))
        start = index + len(marker)
    return result


def _script_probe(build_id: str) -> dict[str, Any]:
    manifest_url = f"https://www.wnba.com/_next/static/{build_id}/_buildManifest.js"
    manifest, manifest_meta = _fetch(manifest_url)
    if manifest is None or manifest_meta.get("http_success") is not True:
        return {"manifest_request": manifest_meta, "routes": {}}
    routes: dict[str, Any] = {}
    for route in ROUTE_KEYS:
        assets = _route_assets(manifest.text, route)
        asset_rows: list[dict[str, Any]] = []
        aggregate_contexts: dict[str, list[str]] = {marker: [] for marker in SCRIPT_MARKERS}
        for asset in assets:
            url = urljoin("https://www.wnba.com/_next/", asset) if not asset.startswith("/") else urljoin("https://www.wnba.com", asset)
            # Manifest assets normally start with static/...; normalize explicitly.
            if asset.startswith("static/"):
                url = f"https://www.wnba.com/_next/{asset}"
            response, meta = _fetch(url, timeout=20.0)
            row: dict[str, Any] = {"asset": asset, "request": meta, "marker_counts": {}}
            if response is not None and meta.get("http_success") is True:
                text = response.text
                for marker in SCRIPT_MARKERS:
                    count = text.count(marker)
                    row["marker_counts"][marker] = count
                    if count and len(aggregate_contexts[marker]) < MAX_SCRIPT_CONTEXTS:
                        remaining = MAX_SCRIPT_CONTEXTS - len(aggregate_contexts[marker])
                        aggregate_contexts[marker].extend(_contexts(text, marker)[:remaining])
            asset_rows.append(row)
        routes[route] = {
            "assets": assets,
            "asset_fetches": asset_rows,
            "marker_contexts": {key: value for key, value in aggregate_contexts.items() if value},
        }
    return {"manifest_request": manifest_meta, "routes": routes}


def _page_probe(name: str, url: str, build_id: str) -> dict[str, Any]:
    response, request = _fetch(url, timeout=30.0)
    result: dict[str, Any] = {"name": name, "request": request}
    if response is None or request.get("http_success") is not True:
        return result
    payload, next_meta = _parse_next(response)
    result["html_next_data"] = next_meta
    result["html_contains_target_game_id"] = TARGET_GAME_ID in response.text
    result["html_contains_target_player_id"] = TARGET_PLAYER_ID in response.text
    if payload is not None:
        result["html_next_structure"] = _structure(payload)

    next_url = _next_data_url(build_id, str(response.url))
    next_response, next_request = _fetch(next_url, timeout=30.0)
    next_row: dict[str, Any] = {"request": next_request}
    if next_response is not None and next_request.get("http_success") is True:
        try:
            next_payload = next_response.json()
        except ValueError as exc:
            next_row.update({"json_parse_success": False, "error_type": type(exc).__name__})
        else:
            next_row["json_parse_success"] = isinstance(next_payload, dict)
            if isinstance(next_payload, dict):
                next_row["structure"] = _structure(next_payload)
    result["next_json_route"] = next_row
    return result


def build_report() -> dict[str, Any]:
    schedule, schedule_meta = _fetch(SCHEDULE_PAGE)
    if schedule is None or schedule_meta.get("http_success") is not True:
        raise RuntimeError("WNBA schedule page was not reachable to resolve build ID.")
    schedule_payload, schedule_next_meta = _parse_next(schedule)
    if schedule_payload is None:
        raise RuntimeError("WNBA schedule page did not expose parseable __NEXT_DATA__.")
    build_id = schedule_payload.get("buildId")
    if not isinstance(build_id, str) or not build_id:
        raise RuntimeError("WNBA schedule page did not expose a build ID.")

    pages = [_page_probe(name, url, build_id) for name, url in PAGES]
    scripts = _script_probe(build_id)

    def evidence(field: str) -> bool:
        for page in pages:
            for source in (page.get("html_next_structure"), (page.get("next_json_route") or {}).get("structure")):
                if isinstance(source, dict) and source.get(field) is True:
                    return True
        return False

    page_success = {page["name"]: (page.get("request") or {}).get("http_success") is True for page in pages}
    any_game_page = any(page_success.get(name) for name in ("game_summary", "game_box_score", "game_play_by_play"))
    return {
        "data_type": "wnba_step7g_page_data_bridge_probe_v1",
        "created_at_utc": _utc_now_iso(),
        "build_id": build_id,
        "target_game_id": TARGET_GAME_ID,
        "target_player_id": TARGET_PLAYER_ID,
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "schedule_page_request": schedule_meta,
        "schedule_next_data": schedule_next_meta,
        "pages": pages,
        "route_scripts": scripts,
        "feasibility": {
            "game_page_reachable": any_game_page,
            "player_page_reachable": page_success.get("player") is True,
            "server_rendered_boxscore_evidence": evidence("boxscore_evidence"),
            "server_rendered_playbyplay_evidence": evidence("playbyplay_evidence"),
            "server_rendered_rotation_evidence": evidence("rotation_evidence"),
            "server_rendered_player_game_log_evidence": evidence("game_log_evidence"),
            "production_activation_safe_now": False,
        },
        "next_required_step": (
            "If server-rendered boxscore/PBP/history evidence is present, build an isolated page-data "
            "adapter and parity-test official identities and statistics. If page props are thin, use "
            "the route-specific JavaScript contexts to identify the exact same-origin/server-side fetch "
            "path. Exact rotation evidence must still be validated separately before activation."
        ),
    }


def main() -> int:
    try:
        report = build_report()
    except Exception as exc:
        report = {
            "data_type": "wnba_step7g_page_data_bridge_probe_v1",
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
    return 0 if "pages" in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
