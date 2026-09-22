"""Step 7G read-only probe of official WNBA.com page/Next.js data.

The WNBA CDN JSON host is currently returning an HTML interstitial from GitHub
Actions while www.wnba.com remains reachable. This probe determines whether the
official website exposes enough structured page data to serve as an isolated
Step-7G fallback source.

No production state, Supabase object, sportsbook provider, scheduler, model, or
frozen shared WNBA adapter is modified by this diagnostic.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from typing import Any

import httpx

REPORT_PATH = Path("step7g-official-web-data-probe.json")
SCHEDULE_URL = "https://www.wnba.com/schedule"
TEAM_URL = "https://www.wnba.com/team/1611661319/las-vegas-aces"

HTTP_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
}

_INTERESTING_KEYS = {
    "gameid", "game_id", "gamedate", "gamedatetime", "gametimeutc",
    "gamestatustext", "gamestatus", "hometeam", "awayteam", "teamid",
    "teamtricode", "personid", "playerid", "player_id", "playername",
    "firstname", "familyname", "roster", "schedule", "games", "players",
}

_SAFE_SAMPLE_KEYS = {
    "gameId", "gameID", "game_id", "gameDate", "gameTimeUTC", "gameEt",
    "gameStatus", "gameStatusText", "personId", "playerId", "player_id",
    "playerName", "name", "firstName", "familyName", "teamId", "teamTricode",
    "teamName", "teamCity", "slug", "title", "date", "status",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        attributes = {str(key): value for key, value in attrs}
        if attributes.get("id") == "__NEXT_DATA__":
            self._capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._capture:
            self._capture = False

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    @property
    def next_data_text(self) -> str:
        return "".join(self._parts).strip()


def _fetch(url: str, *, timeout: float = 15.0) -> tuple[httpx.Response | None, dict[str, Any]]:
    started = time.monotonic()
    try:
        response = httpx.get(
            url,
            headers=HTTP_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )
        return response, {
            "reachable": True,
            "url": url,
            "final_url": str(response.url),
            "http_status": int(response.status_code),
            "http_success": 200 <= response.status_code < 300,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "content_type": response.headers.get("content-type"),
            "response_bytes": len(response.content),
        }
    except Exception as exc:
        return None, {
            "reachable": False,
            "url": url,
            "http_status": None,
            "http_success": False,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "error_type": type(exc).__name__,
            "error_message_returned": False,
        }


def _extract_next_data(html: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    parser = _NextDataParser()
    parser.feed(html)
    raw = parser.next_data_text
    if not raw:
        return None, {
            "next_data_marker_present": "__NEXT_DATA__" in html,
            "next_data_script_captured": False,
            "next_data_json_parse_success": False,
        }
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        return None, {
            "next_data_marker_present": True,
            "next_data_script_captured": True,
            "next_data_bytes": len(raw.encode("utf-8")),
            "next_data_json_parse_success": False,
            "next_data_json_error_type": type(exc).__name__,
        }
    return payload if isinstance(payload, dict) else None, {
        "next_data_marker_present": True,
        "next_data_script_captured": True,
        "next_data_bytes": len(raw.encode("utf-8")),
        "next_data_json_parse_success": isinstance(payload, dict),
        "next_data_top_level_keys": sorted(payload) if isinstance(payload, dict) else [],
    }


def _walk(value: Any, path: str = "root"):
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


def _primitive(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _safe_object_sample(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in _SAFE_SAMPLE_KEYS:
        item = value.get(key)
        if _primitive(item):
            result[key] = item
    return result


def _structure_summary(payload: dict[str, Any]) -> dict[str, Any]:
    key_counts: Counter[str] = Counter()
    interesting_paths: list[str] = []
    game_samples: list[dict[str, Any]] = []
    player_samples: list[dict[str, Any]] = []
    team_samples: list[dict[str, Any]] = []
    max_paths = 80
    max_samples = 5

    for path, value in _walk(payload):
        if not isinstance(value, dict):
            continue
        lowered = {str(key).casefold(): key for key in value}
        for key in value:
            normalized = str(key).casefold()
            if normalized in _INTERESTING_KEYS:
                key_counts[normalized] += 1
                if len(interesting_paths) < max_paths:
                    interesting_paths.append(f"{path}.{key}")

        sample = _safe_object_sample(value)
        if not sample:
            continue
        normalized_keys = set(lowered)
        if {"gameid", "game_id"} & normalized_keys and len(game_samples) < max_samples:
            game_samples.append(sample)
        if {"personid", "playerid", "player_id"} & normalized_keys and len(player_samples) < max_samples:
            player_samples.append(sample)
        if "teamid" in normalized_keys and len(team_samples) < max_samples:
            team_samples.append(sample)

    build_id = payload.get("buildId")
    page = payload.get("page")
    page_props = payload.get("props")
    if isinstance(page_props, dict):
        page_props = page_props.get("pageProps")
    return {
        "build_id": build_id if isinstance(build_id, str) else None,
        "page": page if isinstance(page, str) else None,
        "page_props_is_object": isinstance(page_props, dict),
        "page_props_top_level_keys": sorted(page_props)[:100] if isinstance(page_props, dict) else [],
        "interesting_key_counts": dict(sorted(key_counts.items())),
        "interesting_paths": interesting_paths,
        "game_object_samples": game_samples,
        "player_object_samples": player_samples,
        "team_object_samples": team_samples,
        "game_object_sample_count": len(game_samples),
        "player_object_sample_count": len(player_samples),
        "team_object_sample_count": len(team_samples),
    }


def _next_json_url(origin: str, build_id: str, page_path: str) -> str:
    path = page_path.strip("/")
    if not path:
        path = "index"
    return f"{origin}/_next/data/{build_id}/{path}.json"


def _probe_page(name: str, url: str, page_path: str) -> dict[str, Any]:
    response, request_meta = _fetch(url)
    result: dict[str, Any] = {
        "name": name,
        "page_path": page_path,
        "request": request_meta,
    }
    if response is None or not request_meta.get("http_success"):
        result["structured_page_data_available"] = False
        return result

    html = response.text
    payload, next_meta = _extract_next_data(html)
    result["html_markers"] = {
        "contains_wnba": "wnba" in html.casefold(),
        "contains_next_data": "__NEXT_DATA__" in html,
        "contains_next_static": "/_next/static/" in html,
        "contains_self_next_f": "self.__next_f.push" in html,
    }
    result["next_data"] = next_meta
    if payload is None:
        result["structured_page_data_available"] = False
        return result

    structure = _structure_summary(payload)
    result["next_data_structure"] = structure
    result["structured_page_data_available"] = True

    build_id = structure.get("build_id")
    if isinstance(build_id, str) and build_id:
        origin = f"{response.url.scheme}://{response.url.host}"
        next_url = _next_json_url(origin, build_id, page_path)
        next_response, next_request = _fetch(next_url)
        next_probe: dict[str, Any] = {"request": next_request}
        if next_response is not None and next_request.get("http_success"):
            try:
                next_payload = next_response.json()
            except ValueError as exc:
                next_probe.update(
                    {
                        "json_parse_success": False,
                        "json_error_type": type(exc).__name__,
                    }
                )
            else:
                next_probe["json_parse_success"] = isinstance(next_payload, dict)
                if isinstance(next_payload, dict):
                    next_probe["structure"] = _structure_summary(next_payload)
        result["next_data_json_route"] = next_probe
    else:
        result["next_data_json_route"] = {
            "attempted": False,
            "reason": "build_id_missing",
        }

    return result


def _usable_schedule_evidence(page: dict[str, Any]) -> bool:
    structures = []
    structure = page.get("next_data_structure")
    if isinstance(structure, dict):
        structures.append(structure)
    route = page.get("next_data_json_route")
    if isinstance(route, dict) and isinstance(route.get("structure"), dict):
        structures.append(route["structure"])
    for item in structures:
        counts = item.get("interesting_key_counts") or {}
        if int(counts.get("gameid", 0) or 0) + int(counts.get("game_id", 0) or 0) > 0:
            return True
        if int(counts.get("games", 0) or 0) > 0 and item.get("game_object_sample_count", 0) > 0:
            return True
    return False


def _usable_roster_evidence(page: dict[str, Any]) -> bool:
    structures = []
    structure = page.get("next_data_structure")
    if isinstance(structure, dict):
        structures.append(structure)
    route = page.get("next_data_json_route")
    if isinstance(route, dict) and isinstance(route.get("structure"), dict):
        structures.append(route["structure"])
    for item in structures:
        counts = item.get("interesting_key_counts") or {}
        ids = int(counts.get("personid", 0) or 0) + int(counts.get("playerid", 0) or 0) + int(counts.get("player_id", 0) or 0)
        if ids > 0 or int(counts.get("players", 0) or 0) > 0:
            return True
    return False


def build_report() -> dict[str, Any]:
    schedule = _probe_page("official_schedule_page", SCHEDULE_URL, "schedule")
    team = _probe_page(
        "official_team_page",
        TEAM_URL,
        "team/1611661319/las-vegas-aces",
    )

    schedule_evidence = _usable_schedule_evidence(schedule)
    roster_evidence = _usable_roster_evidence(team)

    if schedule_evidence and roster_evidence:
        next_step = (
            "Build a Step-7G-only WNBA.com web-data adapter for schedule/roster identity, then "
            "solve historical boxscore/rotation evidence separately before any activation."
        )
    elif schedule_evidence:
        next_step = (
            "Use structured official WNBA.com schedule data as the schedule fallback and separately "
            "resolve roster/player-history sources."
        )
    else:
        next_step = (
            "WNBA.com HTML is reachable but its Next.js payload does not directly expose enough "
            "structured schedule data; inspect the page's first-party data-fetch requests/build assets next."
        )

    return {
        "data_type": "wnba_step7g_official_web_data_probe_v1",
        "created_at_utc": _utc_now_iso(),
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "schedule_page": schedule,
        "team_page": team,
        "feasibility": {
            "official_schedule_page_reachable": bool(
                (schedule.get("request") or {}).get("http_success")
            ),
            "official_team_page_reachable": bool(
                (team.get("request") or {}).get("http_success")
            ),
            "structured_schedule_evidence_available": schedule_evidence,
            "structured_roster_evidence_available": roster_evidence,
            "production_activation_safe_now": False,
        },
        "recommended_next_step": next_step,
    }


def main() -> int:
    try:
        report = build_report()
    except Exception as exc:
        report = {
            "data_type": "wnba_step7g_official_web_data_probe_v1",
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
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if "schedule_page" in report and "team_page" in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
