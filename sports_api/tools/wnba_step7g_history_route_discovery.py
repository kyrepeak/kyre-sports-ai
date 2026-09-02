"""Discover first-party WNBA.com routes for Step 7G history/rotation inputs.

This is a read-only source-discovery probe. It scans public WNBA.com Next.js
payloads and same-origin JavaScript chunks for first-party API routes related to
player history, box scores, play-by-play, rotations, lineups, and stats.

No production adapters are changed and no Supabase/sportsbook/scheduler/model
mutation is performed.
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
from urllib.parse import urljoin, urlparse

import httpx

REPORT_PATH = Path("step7g-history-route-discovery.json")
PAGES = (
    ("schedule", "https://www.wnba.com/schedule"),
    ("aces_team", "https://www.wnba.com/team/1611661319/las-vegas-aces"),
    ("stats_players", "https://www.wnba.com/stats/players/traditional"),
)
MAX_SCRIPTS_PER_PAGE = 48
MAX_CANDIDATES = 500

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

KEYWORDS = (
    "/api/",
    "playergamelog",
    "player-game-log",
    "gamerotation",
    "game-rotation",
    "rotation",
    "boxscore",
    "box-score",
    "playbyplay",
    "play-by-play",
    "liveData",
    "staticData",
    "stats.wnba.com",
    "playerprofile",
    "player-profile",
    "playerstats",
    "player-stats",
    "teamgamelog",
    "team-game-log",
    "lineups",
    "leagueDash",
    "scoreboard",
)

QUOTED_RE = re.compile(r"(?:\"([^\"\\]*(?:\\.[^\"\\]*)*)\"|'([^'\\]*(?:\\.[^'\\]*)*)')")
ABSOLUTE_RE = re.compile(r"https?://[^\"'`\\\s<>]+", re.I)
API_PATH_RE = re.compile(r"/api/[A-Za-z0-9_?&=.%{}\[\]/:\-+]+")
PLAYER_LINK_RE = re.compile(r"/player/[A-Za-z0-9_?&=.%{}\[\]/:\-+]+")


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


def _fetch(url: str, *, timeout: float = 15.0) -> tuple[httpx.Response | None, dict[str, Any]]:
    started = time.monotonic()
    try:
        response = httpx.get(url, headers=HTTP_HEADERS, timeout=timeout, follow_redirects=True)
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


def _clean_candidate(raw: str) -> str:
    return (
        raw.replace("\\/", "/")
        .replace("\\u002F", "/")
        .replace("\\u0026", "&")
        .strip()
    )


def _interesting(text: str) -> bool:
    lower = text.casefold()
    return any(keyword.casefold() in lower for keyword in KEYWORDS)


def _extract_candidates(text: str, source: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(raw: str, kind: str) -> None:
        value = _clean_candidate(raw)
        if not value or len(value) > 900 or not _interesting(value):
            return
        key = f"{kind}|{value}"
        if key in seen:
            return
        seen.add(key)
        result.append({"source": source, "kind": kind, "candidate": value})

    for match in ABSOLUTE_RE.finditer(text):
        add(match.group(0), "absolute_url")
    for match in API_PATH_RE.finditer(text):
        add(match.group(0), "api_path")
    for match in QUOTED_RE.finditer(text):
        add(match.group(1) or match.group(2) or "", "quoted_string")
    return result[:MAX_CANDIDATES]


def _walk(value: Any, path: str = "root"):
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


def _payload_candidates(payload: Any, source: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for path, value in _walk(payload):
        if not isinstance(value, str):
            continue
        cleaned = _clean_candidate(value)
        if _interesting(cleaned) or PLAYER_LINK_RE.search(cleaned):
            result.append(
                {
                    "source": source,
                    "kind": "next_data_string",
                    "path": path,
                    "candidate": cleaned[:900],
                }
            )
            if len(result) >= MAX_CANDIDATES:
                break
    return result


def _safe_roster_rows(payload: Any) -> list[dict[str, Any]]:
    target = payload
    if isinstance(payload, dict) and "props" in payload:
        target = payload.get("props")
    if isinstance(target, dict) and "pageProps" in target:
        target = target.get("pageProps")
    team = target.get("team") if isinstance(target, dict) else None
    roster = team.get("roster") if isinstance(team, dict) else None
    if not isinstance(roster, list):
        return []
    safe = []
    for row in roster[:5]:
        if not isinstance(row, dict):
            continue
        item: dict[str, Any] = {
            "keys": sorted(map(str, row.keys())),
        }
        for key in (
            "id", "playerId", "playerID", "personId", "PERSON_ID",
            "firstName", "lastName", "familyName", "fullName", "name",
            "slug", "position", "jersey", "jerseyNum", "profileUrl", "url", "link",
        ):
            value = row.get(key)
            if value is None or isinstance(value, (str, int, float, bool)):
                if value is not None:
                    item[key] = value
        stats = row.get("stats")
        if isinstance(stats, dict):
            item["stats_keys"] = sorted(map(str, stats.keys()))
            season = stats.get("season")
            if isinstance(season, dict):
                item["season_stats_keys"] = sorted(map(str, season.keys()))
        safe.append(item)
    return safe


def _script_rank(url: str) -> tuple[int, str]:
    lower = url.casefold()
    if any(token in lower for token in ("team", "stats", "player", "schedule")):
        return 0, url
    if "pages" in lower:
        return 1, url
    if "_app" in lower:
        return 2, url
    return 3, url


def _page_probe(name: str, url: str) -> dict[str, Any]:
    response, request = _fetch(url)
    result: dict[str, Any] = {"name": name, "request": request}
    if response is None or request.get("http_success") is not True:
        return result

    parser = _Parser()
    parser.feed(response.text)
    next_payload = None
    if parser.next_data_text:
        try:
            parsed = json.loads(parser.next_data_text)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            next_payload = parsed

    result["next_data_present"] = next_payload is not None
    result["page_route"] = next_payload.get("page") if isinstance(next_payload, dict) else None
    result["build_id"] = next_payload.get("buildId") if isinstance(next_payload, dict) else None
    result["roster_samples"] = _safe_roster_rows(next_payload) if next_payload else []

    payload_candidates = _payload_candidates(next_payload, f"{name}:next_data") if next_payload else []
    html_candidates = _extract_candidates(response.text, f"{name}:html")

    script_urls: list[str] = []
    seen: set[str] = set()
    for src in parser.script_srcs:
        candidate = urljoin(str(response.url), src)
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != "www.wnba.com":
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        script_urls.append(candidate)
    script_urls.sort(key=_script_rank)

    script_rows: list[dict[str, Any]] = []
    script_candidates: list[dict[str, str]] = []
    for script_url in script_urls[:MAX_SCRIPTS_PER_PAGE]:
        script, meta = _fetch(script_url, timeout=12.0)
        row: dict[str, Any] = {"request": meta}
        if script is not None and meta.get("http_success") is True:
            found = _extract_candidates(script.text, script_url)
            row["candidate_count"] = len(found)
            row["candidates"] = found[:80]
            script_candidates.extend(found)
        script_rows.append(row)
        if len(script_candidates) >= MAX_CANDIDATES:
            break

    combined = payload_candidates + html_candidates + script_candidates
    deduped: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()
    for row in combined:
        candidate = row.get("candidate")
        if not isinstance(candidate, str):
            continue
        key = candidate
        if key in seen_candidates:
            continue
        seen_candidates.add(key)
        deduped.append(row)
        if len(deduped) >= MAX_CANDIDATES:
            break

    result["script_url_count"] = len(script_urls)
    result["script_fetch_count"] = len(script_rows)
    result["scripts"] = script_rows
    result["candidates"] = deduped
    return result


def _classify(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    classes = {
        "api_paths": [],
        "player_history": [],
        "boxscore": [],
        "playbyplay": [],
        "rotation": [],
        "lineup": [],
        "stats_host": [],
        "live_data": [],
        "player_links": [],
    }
    seen: dict[str, set[str]] = {key: set() for key in classes}

    def add(kind: str, row: dict[str, Any]) -> None:
        value = str(row.get("candidate") or "")
        if not value or value in seen[kind] or len(classes[kind]) >= 80:
            return
        seen[kind].add(value)
        classes[kind].append(row)

    for row in candidates:
        value = str(row.get("candidate") or "")
        lower = value.casefold()
        if "/api/" in lower:
            add("api_paths", row)
        if any(token in lower for token in ("playergamelog", "player-game-log", "playerstats", "player-stats", "playerprofile", "player-profile")):
            add("player_history", row)
        if "boxscore" in lower or "box-score" in lower:
            add("boxscore", row)
        if "playbyplay" in lower or "play-by-play" in lower:
            add("playbyplay", row)
        if "rotation" in lower:
            add("rotation", row)
        if "lineup" in lower:
            add("lineup", row)
        if "stats.wnba.com" in lower:
            add("stats_host", row)
        if "livedata" in lower:
            add("live_data", row)
        if "/player/" in lower:
            add("player_links", row)
    return classes


def build_report() -> dict[str, Any]:
    pages = [_page_probe(name, url) for name, url in PAGES]
    candidates: list[dict[str, Any]] = []
    roster_samples: list[dict[str, Any]] = []
    for page in pages:
        candidates.extend(page.get("candidates") or [])
        roster_samples.extend(page.get("roster_samples") or [])
    classified = _classify(candidates)

    api_values = [str(row.get("candidate") or "") for row in classified["api_paths"]]
    lower_api = "\n".join(api_values).casefold()
    first_party_core_candidate = any(
        token in lower_api
        for token in (
            "playergamelog", "player-game-log", "boxscore", "playbyplay",
            "play-by-play", "rotation", "playerstats", "player-stats",
        )
    )

    return {
        "data_type": "wnba_step7g_history_route_discovery_v1",
        "created_at_utc": _utc_now_iso(),
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "pages": pages,
        "roster_samples": roster_samples[:10],
        "classification_counts": {key: len(rows) for key, rows in classified.items()},
        "classified_candidates": classified,
        "discovery": {
            "first_party_core_history_api_candidate_found": first_party_core_candidate,
            "first_party_api_path_count": len(classified["api_paths"]),
            "player_link_candidate_count": len(classified["player_links"]),
            "production_activation_safe_now": False,
        },
        "next_required_step": (
            "Probe any discovered same-origin WNBA.com history/boxscore/PBP/rotation route with "
            "official IDs. If no core route exists, inspect the exact first-party stats fetch "
            "wrapper and game/player page data before considering deterministic reconstruction."
        ),
    }


def main() -> int:
    try:
        report = build_report()
    except Exception as exc:
        report = {
            "data_type": "wnba_step7g_history_route_discovery_v1",
            "created_at_utc": _utc_now_iso(),
            "read_only": True,
            "production_mutation_performed": False,
            "supabase_mutation_performed": False,
            "sportsbook_called": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "frozen_shared_provider_behavior_changed": False,
            "discovery_completed": False,
            "error_type": type(exc).__name__,
            "error_message_returned": False,
            "production_activation_safe_now": False,
        }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if "pages" in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
