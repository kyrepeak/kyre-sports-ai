"""Sanitized Step 6H probe: DK event pair/date vs both official WNBA team pages."""
from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
import json
from typing import Any

import httpx

from sports_api.collectors.wnba_draftkings_direct import (
    _get as _draftkings_get,
    _response_json as _draftkings_response_json,
)
from sports_api.wnba_draftkings_shadow_ingestion import frozen_draftkings_urls
from sports_api.wnba_official_reconciliation import _name_key, extract_draftkings_events
from sports_api.wnba_official_reconciliation_live import TEAM_ROSTER_HOSTS

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"

DK_TEAM_ALIASES = {
    "atl dream": "Atlanta Dream",
    "atlanta dream": "Atlanta Dream",
    "chi sky": "Chicago Sky",
    "chicago sky": "Chicago Sky",
    "con sun": "Connecticut Sun",
    "connecticut sun": "Connecticut Sun",
    "dal wings": "Dallas Wings",
    "dallas wings": "Dallas Wings",
    "gs valkyries": "Golden State Valkyries",
    "gsv valkyries": "Golden State Valkyries",
    "golden state valkyries": "Golden State Valkyries",
    "ind fever": "Indiana Fever",
    "indiana fever": "Indiana Fever",
    "lv aces": "Las Vegas Aces",
    "lva aces": "Las Vegas Aces",
    "las vegas aces": "Las Vegas Aces",
    "la sparks": "Los Angeles Sparks",
    "las sparks": "Los Angeles Sparks",
    "los angeles sparks": "Los Angeles Sparks",
    "min lynx": "Minnesota Lynx",
    "minnesota lynx": "Minnesota Lynx",
    "ny liberty": "New York Liberty",
    "nyl liberty": "New York Liberty",
    "new york liberty": "New York Liberty",
    "pho mercury": "Phoenix Mercury",
    "phx mercury": "Phoenix Mercury",
    "phoenix mercury": "Phoenix Mercury",
    "por fire": "Portland Fire",
    "portland fire": "Portland Fire",
    "sea storm": "Seattle Storm",
    "seattle storm": "Seattle Storm",
    "tor tempo": "Toronto Tempo",
    "toronto tempo": "Toronto Tempo",
    "was mystics": "Washington Mystics",
    "washington mystics": "Washington Mystics",
}


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data).strip()
        if text:
            self.parts.append(text)


def _resolve_team(value: Any) -> str | None:
    key = _name_key(value)
    if not key:
        return None
    if key in TEAM_ROSTER_HOSTS:
        return next(name for name in TEAM_ROSTER_HOSTS if name == key).title()
    return DK_TEAM_ALIASES.get(key)


def _event_teams(event: dict[str, Any]) -> list[str]:
    resolved: list[str] = []
    for raw in event.get("participants") or []:
        team = _resolve_team(raw)
        if team and team not in resolved:
            resolved.append(team)
    if len(resolved) != 2:
        name = str(event.get("event_name") or "")
        parts = [part.strip() for part in name.replace(" vs ", " @ ").split(" @ ") if part.strip()]
        for raw in parts:
            team = _resolve_team(raw)
            if team and team not in resolved:
                resolved.append(team)
    return resolved[:2]


def _date_markers(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        day = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return []
    month_full = day.strftime("%B").casefold()
    month_short = day.strftime("%b").casefold()
    weekday = day.strftime("%A").casefold()
    weekday_short = day.strftime("%a").casefold()
    d = str(day.day)
    return [
        f"{month_full} {d}",
        f"{month_short} {d}",
        f"{day.month}/{day.day}",
        f"{day.month:02d}/{day.day:02d}",
        f"{weekday} {month_full} {d}",
        f"{weekday_short} {month_short} {d}",
    ]


def _page(team_name: str) -> dict[str, Any]:
    host = TEAM_ROSTER_HOSTS[_name_key(team_name)]
    url = f"https://{host}/"
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": UA,
    }
    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
    parser = TextParser()
    parser.feed(response.text)
    visible = _name_key(" ".join(parser.parts))
    start = visible.find("upcoming games")
    if start < 0:
        start = visible.find("upcoming")
    if start < 0:
        start = visible.find("schedule")
    end = min(len(visible), start + 18000) if start >= 0 else 0
    upcoming = visible[start:end] if start >= 0 else ""
    return {
        "host": host,
        "status": response.status_code,
        "visible": visible,
        "upcoming": upcoming,
        "upcoming_marker_present": start >= 0,
    }


def main() -> int:
    events: dict[str, dict[str, Any]] = {}
    for url in frozen_draftkings_urls():
        response = _draftkings_get(url, timeout_seconds=12.0, requester=None)
        document = _draftkings_response_json(response, url=url)
        for event in extract_draftkings_events(document):
            events[event["source_event_id"]] = event

    rows = []
    page_cache: dict[str, dict[str, Any]] = {}
    for event_id, event in sorted(events.items()):
        participants = _event_teams(event)
        checks = []
        if len(participants) == 2:
            for team in participants:
                opponent = participants[1] if team == participants[0] else participants[0]
                page = page_cache.setdefault(team, _page(team))
                date_markers = [_name_key(v) for v in _date_markers(event.get("event_date"))]
                checks.append(
                    {
                        "team": team,
                        "host": page["host"],
                        "http_status": page["status"],
                        "upcoming_marker_present": page["upcoming_marker_present"],
                        "opponent_in_page": _name_key(opponent) in page["visible"],
                        "opponent_in_upcoming": _name_key(opponent) in page["upcoming"],
                        "date_in_page": any(marker in page["visible"] for marker in date_markers),
                        "date_in_upcoming": any(marker in page["upcoming"] for marker in date_markers),
                        "upcoming_section_chars": len(page["upcoming"]),
                    }
                )
        rows.append(
            {
                "source_event_id": event_id,
                "event_name": event.get("event_name"),
                "event_date": event.get("event_date"),
                "raw_participants": event.get("participants") or [],
                "resolved_participants": participants,
                "checks": checks,
                "both_team_pages_confirm_pair_and_date": len(checks) == 2
                and all(
                    row["http_status"] == 200
                    and row["opponent_in_upcoming"]
                    and row["date_in_upcoming"]
                    for row in checks
                ),
            }
        )

    report = {
        "data_type": "wnba_step6h_official_team_event_probe",
        "event_count": len(rows),
        "events": rows,
        "all_events_confirmed_by_both_official_team_pages": bool(rows)
        and all(row["both_team_pages_confirm_pair_and_date"] for row in rows),
        "safety": {
            "http_methods": ["GET"],
            "authentication_used": False,
            "raw_page_content_returned": False,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
