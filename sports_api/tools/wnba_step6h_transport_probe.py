"""Sanitized GET-only transport probe for WNBA Step 6H hosted-runner compatibility."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
from typing import Any
from urllib.request import Request, urlopen

import httpx

TARGETS = [
    {
        "id": "schedule_cdn",
        "url": "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json",
        "expect": "leagueSchedule",
    },
    {
        "id": "aces_team_page",
        "url": "https://www.wnba.com/team/1611661319/las-vegas-aces",
        "expect": "2026 Team Roster",
    },
    {
        "id": "aces_roster_page",
        "url": "https://aces.wnba.com/roster",
        "expect": "2026 Team Roster",
    },
    {
        "id": "aces_home_page",
        "url": "https://aces.wnba.com/",
        "expect": "Las Vegas Aces",
    },
]

BROWSER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
}


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data).strip()
        if text:
            self.parts.append(text)


def _summary(target_id: str, transport: str, status: int | None, headers: Any, body: bytes, expect: str, error: str | None = None) -> dict[str, Any]:
    content_type = None
    if headers is not None:
        try:
            content_type = headers.get("content-type") or headers.get("Content-Type")
        except Exception:
            content_type = None
    text = body.decode("utf-8", errors="ignore") if body else ""
    parser = TextParser()
    try:
        parser.feed(text)
        visible = " ".join(parser.parts)
    except Exception:
        visible = text
    json_object = False
    json_has_league_schedule = False
    try:
        document = json.loads(text)
        json_object = isinstance(document, dict)
        json_has_league_schedule = json_object and isinstance(document.get("leagueSchedule"), dict)
    except Exception:
        pass
    return {
        "target_id": target_id,
        "transport": transport,
        "status": status,
        "content_type": content_type,
        "body_bytes": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest() if body else None,
        "json_object": json_object,
        "json_has_league_schedule": json_has_league_schedule,
        "expected_marker_present": expect.casefold() in visible.casefold(),
        "error_type": error,
    }


def probe_httpx(target: dict[str, str], *, headers: dict[str, str] | None, name: str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True, headers=headers) as client:
            response = client.get(target["url"])
        return _summary(target["id"], name, response.status_code, response.headers, response.content, target["expect"])
    except Exception as exc:
        return _summary(target["id"], name, None, None, b"", target["expect"], type(exc).__name__)


def probe_urllib(target: dict[str, str]) -> dict[str, Any]:
    try:
        req = Request(target["url"], headers={"User-Agent": BROWSER_HEADERS["User-Agent"]})
        with urlopen(req, timeout=12.0) as response:
            body = response.read(20_000_001)
            status = getattr(response, "status", None)
            headers = response.headers
        return _summary(target["id"], "urllib_browser_ua", status, headers, body, target["expect"])
    except Exception as exc:
        return _summary(target["id"], "urllib_browser_ua", None, None, b"", target["expect"], type(exc).__name__)


def main() -> int:
    rows: list[dict[str, Any]] = []
    for target in TARGETS:
        rows.append(probe_httpx(target, headers=None, name="httpx_default"))
        rows.append(probe_httpx(target, headers=BROWSER_HEADERS, name="httpx_browser"))
        rows.append(probe_urllib(target))
    report = {
        "data_type": "wnba_step6h_transport_probe",
        "rows": rows,
        "safety": {"http_methods": ["GET"], "body_content_returned": False, "authentication_used": False},
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
