"""Discover the first-party schedule data source used by WNBA.com.

Step 7G remains fail-closed. This diagnostic only reads public WNBA.com HTML,
Next.js JSON, and same-origin JavaScript assets. It performs no sportsbook,
Supabase, scheduler, model, feed, or production-runtime mutation.
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

REPORT_PATH = Path("step7g-schedule-source-discovery.json")
SCHEDULE_URL = "https://www.wnba.com/schedule"
MAX_SCRIPT_FETCHES = 24
MAX_CANDIDATES = 250

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

URL_RE = re.compile(r"https?://[^\"'`\\\s<>]+", re.I)
QUOTED_RE = re.compile(r"(?:\"([^\"\\]*(?:\\.[^\"\\]*)*)\"|'([^'\\]*(?:\\.[^'\\]*)*)')")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _HTMLProbeParser(HTMLParser):
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


def _safe_shape(value: Any, depth: int = 0) -> Any:
    if depth >= 3:
        if isinstance(value, dict):
            return {"type": "object", "key_count": len(value), "keys": sorted(map(str, value.keys()))[:50]}
        if isinstance(value, list):
            return {"type": "array", "length": len(value)}
        return value if value is None or isinstance(value, (bool, int, float)) else str(value)[:300]
    if isinstance(value, dict):
        return {
            "type": "object",
            "key_count": len(value),
            "keys": sorted(map(str, value.keys()))[:80],
            "children": {str(k): _safe_shape(v, depth + 1) for k, v in list(value.items())[:20]},
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "length": len(value),
            "samples": [_safe_shape(item, depth + 1) for item in value[:3]],
        }
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    return text[:500]


def _dig(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _candidate_strings(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        value = raw.replace("\\/", "/").replace("\\u002F", "/").strip()
        if not value or len(value) > 600:
            return
        lower = value.casefold()
        interesting = any(
            token in lower
            for token in (
                "schedule", "scoreboard", "gamelog", "game-log", "boxscore",
                "playbyplay", "play-by-play", "stats.wnba", "cdn.wnba", "nba.com",
                "wnba.com/api", "/api/", "graphql", "league", "staticdata", "livedata",
            )
        )
        if not interesting:
            return
        if value in seen:
            return
        seen.add(value)
        found.append(value)

    for match in URL_RE.finditer(text):
        add(match.group(0))
    for match in QUOTED_RE.finditer(text):
        add(match.group(1) or match.group(2) or "")
    return found[:MAX_CANDIDATES]


def _payload_candidates(value: Any, path: str = "root", out: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if out is None:
        out = []
    if len(out) >= MAX_CANDIDATES:
        return out
    if isinstance(value, dict):
        for key, item in value.items():
            _payload_candidates(item, f"{path}.{key}", out)
            if len(out) >= MAX_CANDIDATES:
                break
    elif isinstance(value, list):
        for index, item in enumerate(value[:200]):
            _payload_candidates(item, f"{path}[{index}]", out)
            if len(out) >= MAX_CANDIDATES:
                break
    elif isinstance(value, str):
        lower = value.casefold()
        if any(token in lower for token in ("schedule", "api", "stats", "cdn", "league", "scoreboard", "boxscore", "playbyplay")):
            out.append({"path": path, "value": value[:600]})
    return out


def _rank_script(src: str) -> tuple[int, str]:
    lower = src.casefold()
    if "schedule" in lower:
        score = 0
    elif "pages" in lower:
        score = 1
    elif "_app" in lower:
        score = 2
    else:
        score = 3
    return score, src


def build_report() -> dict[str, Any]:
    page, page_meta = _fetch(SCHEDULE_URL)
    if page is None or page_meta.get("http_success") is not True:
        raise RuntimeError("Official WNBA schedule page was not reachable for source discovery.")

    parser = _HTMLProbeParser()
    parser.feed(page.text)
    if not parser.next_data_text:
        raise RuntimeError("Official WNBA schedule page did not expose __NEXT_DATA__.")
    next_data = json.loads(parser.next_data_text)
    if not isinstance(next_data, dict):
        raise RuntimeError("Official WNBA __NEXT_DATA__ was not an object.")

    build_id = next_data.get("buildId")
    next_json_meta: dict[str, Any] = {"attempted": False}
    next_json: dict[str, Any] | None = None
    if isinstance(build_id, str) and build_id:
        next_url = f"https://www.wnba.com/_next/data/{build_id}/schedule.json"
        response, next_json_meta = _fetch(next_url)
        next_json_meta["attempted"] = True
        if response is not None and next_json_meta.get("http_success"):
            try:
                parsed = response.json()
            except ValueError as exc:
                next_json_meta["json_parse_success"] = False
                next_json_meta["json_error_type"] = type(exc).__name__
            else:
                next_json_meta["json_parse_success"] = isinstance(parsed, dict)
                if isinstance(parsed, dict):
                    next_json = parsed

    current_season_html = _dig(next_data, "props", "currentSeason")
    current_season_json = _dig(next_json, "currentSeason") if isinstance(next_json, dict) else None
    page_props = _dig(next_data, "props", "pageProps")

    script_urls: list[str] = []
    seen_urls: set[str] = set()
    for src in sorted(parser.script_srcs, key=_rank_script):
        url = urljoin(SCHEDULE_URL, src)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != "www.wnba.com":
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        script_urls.append(url)

    script_results: list[dict[str, Any]] = []
    aggregate_candidates: list[dict[str, Any]] = []
    aggregate_seen: set[str] = set()
    for url in script_urls[:MAX_SCRIPT_FETCHES]:
        response, meta = _fetch(url, timeout=12.0)
        row: dict[str, Any] = {"request": meta}
        if response is not None and meta.get("http_success"):
            candidates = _candidate_strings(response.text)
            row["candidate_count"] = len(candidates)
            row["candidates"] = candidates[:80]
            for candidate in candidates:
                if candidate in aggregate_seen:
                    continue
                aggregate_seen.add(candidate)
                aggregate_candidates.append({"source_script": url, "candidate": candidate})
                if len(aggregate_candidates) >= MAX_CANDIDATES:
                    break
        script_results.append(row)
        if len(aggregate_candidates) >= MAX_CANDIDATES:
            break

    html_candidates = _candidate_strings(page.text)
    payload_candidates = _payload_candidates(next_data)
    if isinstance(next_json, dict):
        payload_candidates.extend(_payload_candidates(next_json, path="next_json"))
        payload_candidates = payload_candidates[:MAX_CANDIDATES]

    all_candidate_text = "\n".join(
        html_candidates
        + [row["value"] for row in payload_candidates if isinstance(row.get("value"), str)]
        + [row["candidate"] for row in aggregate_candidates]
    ).casefold()
    direct_official_schedule_endpoint_found = any(
        token in all_candidate_text
        for token in (
            "scheduleleaguev2", "scheduleleague", "/api/schedule", "schedule.json",
            "scoreboard/todaysscoreboard", "staticdata/schedule",
        )
    )

    return {
        "data_type": "wnba_step7g_schedule_source_discovery_v1",
        "created_at_utc": _utc_now_iso(),
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "schedule_page_request": page_meta,
        "build_id": build_id,
        "next_json_request": next_json_meta,
        "current_season_from_html_shape": _safe_shape(current_season_html),
        "current_season_from_next_json_shape": _safe_shape(current_season_json),
        "page_props_shape": _safe_shape(page_props),
        "next_data_candidate_strings": payload_candidates,
        "html_candidate_strings": html_candidates,
        "script_src_count": len(script_urls),
        "script_fetch_count": len(script_results),
        "scripts": script_results,
        "aggregate_script_candidates": aggregate_candidates,
        "discovery": {
            "direct_official_schedule_endpoint_candidate_found": direct_official_schedule_endpoint_found,
            "candidate_count": len(aggregate_candidates),
            "production_activation_safe_now": False,
        },
    }


def main() -> int:
    try:
        report = build_report()
    except Exception as exc:
        report = {
            "data_type": "wnba_step7g_schedule_source_discovery_v1",
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
    return 0 if "schedule_page_request" in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
