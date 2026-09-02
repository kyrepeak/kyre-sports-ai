"""Read-only inspection of WNBA.com's public endpoint builder.

The public WNBA frontend exposes methods such as ``getBoxscoreEndpoint`` and
``getLivePlayByPlayEndpoint``. This diagnostic extracts small public-JavaScript
contexts around those methods and URL/base-host constants so Step 7G can test
exact first-party routes instead of guessing.

No secrets, cookies, auth state, production data, Supabase writes, sportsbook
calls, scheduler work, model execution, or feed publication are involved.
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

REPORT_PATH = Path("step7g-public-endpoint-builder-probe.json")
SCHEDULE_URL = "https://www.wnba.com/schedule"
CONTEXT_RADIUS = 2200
MAX_CONTEXTS_PER_MARKER = 6
MAX_URLS = 120

MARKERS = (
    "getPublicEndpoint",
    "getBoxscoreEndpoint",
    "getLivePlayByPlayEndpoint",
    "/stats/boxscoresummaryv3",
    "/stats/boxscoretraditionalv3",
    "/stats/playbyplayv3",
    "/liveData/scoreboard/todaysScoreboard_10.json",
    "/staticData/rollingSchedule.json",
    "PUBLIC_ENDPOINT",
    "NBA_PUBLIC",
)

HTTP_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,text/javascript,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
}

URL_RE = re.compile(r"https?://[^\"'`\\\s<>]+", re.I)
HOSTISH_RE = re.compile(
    r"(?:https?:)?//[A-Za-z0-9.-]+(?:/[A-Za-z0-9_?&=.%{}\[\]/:\-+]*)?",
    re.I,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.script_srcs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        data = {str(k): v for k, v in attrs}
        src = data.get("src")
        if isinstance(src, str) and src.strip():
            self.script_srcs.append(src.strip())


def _fetch(url: str, *, timeout: float = 20.0) -> tuple[httpx.Response | None, dict[str, Any]]:
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


def _clean_context(value: str) -> str:
    # Public minified JS only. Collapse whitespace to keep evidence compact.
    return " ".join(value.replace("\x00", "").split())


def _contexts(text: str, marker: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    start = 0
    while len(result) < MAX_CONTEXTS_PER_MARKER:
        index = text.find(marker, start)
        if index < 0:
            break
        lo = max(0, index - CONTEXT_RADIUS)
        hi = min(len(text), index + len(marker) + CONTEXT_RADIUS)
        context = _clean_context(text[lo:hi])
        urls = []
        seen_urls: set[str] = set()
        for regex in (URL_RE, HOSTISH_RE):
            for match in regex.finditer(context):
                value = match.group(0).replace("\\/", "/")
                if value in seen_urls:
                    continue
                seen_urls.add(value)
                urls.append(value)
                if len(urls) >= 30:
                    break
            if len(urls) >= 30:
                break
        result.append(
            {
                "index": index,
                "context": context,
                "urls_or_hosts_in_context": urls,
            }
        )
        start = index + len(marker)
    return result


def _interesting_script(url: str) -> tuple[int, str]:
    lower = url.casefold()
    if "/pages/_app-" in lower:
        return 0, url
    if "schedule" in lower:
        return 1, url
    if "main-" in lower:
        return 2, url
    return 3, url


def build_report() -> dict[str, Any]:
    page, page_meta = _fetch(SCHEDULE_URL)
    if page is None or page_meta.get("http_success") is not True:
        raise RuntimeError("WNBA schedule page was not reachable.")

    parser = _Parser()
    parser.feed(page.text)
    urls: list[str] = []
    seen: set[str] = set()
    for src in parser.script_srcs:
        url = urljoin(str(page.url), src)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != "www.wnba.com":
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    urls.sort(key=_interesting_script)

    scripts: list[dict[str, Any]] = []
    aggregate: dict[str, list[dict[str, Any]]] = {marker: [] for marker in MARKERS}
    all_urls: list[str] = []
    all_url_seen: set[str] = set()

    for url in urls[:20]:
        response, meta = _fetch(url)
        row: dict[str, Any] = {"request": meta, "marker_counts": {}}
        if response is not None and meta.get("http_success") is True:
            text = response.text
            any_marker = False
            for marker in MARKERS:
                count = text.count(marker)
                row["marker_counts"][marker] = count
                if count:
                    any_marker = True
                    extracted = _contexts(text, marker)
                    for item in extracted:
                        item["source_script"] = url
                    aggregate[marker].extend(extracted)
            for match in URL_RE.finditer(text):
                value = match.group(0).replace("\\/", "/")
                lower = value.casefold()
                if not any(token in lower for token in ("wnba", "nba", "stats", "cdn", "api")):
                    continue
                if value in all_url_seen:
                    continue
                all_url_seen.add(value)
                all_urls.append(value)
                if len(all_urls) >= MAX_URLS:
                    break
            row["contains_target_marker"] = any_marker
        scripts.append(row)

    compact_aggregate: dict[str, list[dict[str, Any]]] = {}
    for marker, rows in aggregate.items():
        compact_aggregate[marker] = rows[:MAX_CONTEXTS_PER_MARKER]

    joined = "\n".join(
        item.get("context", "")
        for rows in compact_aggregate.values()
        for item in rows
    )
    hosts = sorted(
        {
            urlparse(value if value.startswith("http") else "https:" + value).netloc
            for value in all_urls
            if value.startswith(("http://", "https://", "//"))
        }
    )

    return {
        "data_type": "wnba_step7g_public_endpoint_builder_probe_v1",
        "created_at_utc": _utc_now_iso(),
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "schedule_page_request": page_meta,
        "script_count": len(urls),
        "scripts": scripts,
        "marker_contexts": compact_aggregate,
        "discovered_absolute_urls": all_urls,
        "discovered_hosts": hosts,
        "builder_evidence": {
            "get_public_endpoint_found": "getPublicEndpoint" in joined,
            "get_boxscore_endpoint_found": "getBoxscoreEndpoint" in joined,
            "get_live_play_by_play_endpoint_found": "getLivePlayByPlayEndpoint" in joined,
            "boxscoretraditionalv3_found": "/stats/boxscoretraditionalv3" in joined,
            "playbyplayv3_found": "/stats/playbyplayv3" in joined,
            "production_activation_safe_now": False,
        },
    }


def main() -> int:
    try:
        report = build_report()
    except Exception as exc:
        report = {
            "data_type": "wnba_step7g_public_endpoint_builder_probe_v1",
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
    return 0 if "marker_contexts" in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
