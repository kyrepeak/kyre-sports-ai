"""Sanitized Step 6H probe: DK events vs official WNBA team/game-page evidence."""
from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from sports_api.collectors.wnba_draftkings_direct import (
    _get as _draftkings_get,
    _response_json as _draftkings_response_json,
)
from sports_api.wnba_draftkings_shadow_ingestion import frozen_draftkings_urls
from sports_api.wnba_official_reconciliation import _name_key, extract_draftkings_events
from sports_api.wnba_official_reconciliation_live import TEAM_ROSTER_HOSTS

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
GAME_ID_RE = re.compile(r"(?<!\d)(10\d{8})(?!\d)")

DK_TEAM_ALIASES = {
    "atl dream": "Atlanta Dream", "atlanta dream": "Atlanta Dream",
    "chi sky": "Chicago Sky", "chicago sky": "Chicago Sky",
    "con sun": "Connecticut Sun", "connecticut sun": "Connecticut Sun",
    "dal wings": "Dallas Wings", "dallas wings": "Dallas Wings",
    "gs valkyries": "Golden State Valkyries", "gsv valkyries": "Golden State Valkyries",
    "golden state valkyries": "Golden State Valkyries",
    "ind fever": "Indiana Fever", "indiana fever": "Indiana Fever",
    "lv aces": "Las Vegas Aces", "lva aces": "Las Vegas Aces", "las vegas aces": "Las Vegas Aces",
    "la sparks": "Los Angeles Sparks", "las sparks": "Los Angeles Sparks",
    "los angeles sparks": "Los Angeles Sparks",
    "min lynx": "Minnesota Lynx", "minnesota lynx": "Minnesota Lynx",
    "ny liberty": "New York Liberty", "nyl liberty": "New York Liberty", "new york liberty": "New York Liberty",
    "pho mercury": "Phoenix Mercury", "phx mercury": "Phoenix Mercury", "phoenix mercury": "Phoenix Mercury",
    "por fire": "Portland Fire", "portland fire": "Portland Fire",
    "sea storm": "Seattle Storm", "seattle storm": "Seattle Storm",
    "tor tempo": "Toronto Tempo", "toronto tempo": "Toronto Tempo",
    "was mystics": "Washington Mystics", "washington mystics": "Washington Mystics",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a":
            for key, value in attrs:
                if key.casefold() == "href" and value:
                    self.hrefs.append(str(value))

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
    return [
        value.casefold(),
        day.strftime("%B %-d").casefold(),
        day.strftime("%b %-d").casefold(),
        f"{day.month}/{day.day}",
        f"{day.month:02d}/{day.day:02d}",
    ]


def _page(team_name: str, path: str) -> dict[str, Any]:
    host = TEAM_ROSTER_HOSTS[_name_key(team_name)]
    url = f"https://{host}{path}"
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": UA,
    }
    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
    parser = PageParser()
    parser.feed(response.text)
    visible = _name_key(" ".join(parser.parts))
    raw = response.text.casefold()
    start = visible.find("upcoming games")
    if start < 0:
        start = visible.find("upcoming")
    if start < 0:
        start = visible.find("schedule")
    end = min(len(visible), start + 18000) if start >= 0 else 0
    upcoming = visible[start:end] if start >= 0 else ""

    game_links: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for href in parser.hrefs:
        absolute = urljoin(str(response.url), href)
        parsed = urlparse(absolute)
        if "/game/" not in parsed.path.casefold():
            continue
        match = GAME_ID_RE.search(parsed.path)
        item = ((parsed.hostname or "").casefold(), parsed.path)
        if item in seen:
            continue
        seen.add(item)
        game_links.append({"host": item[0], "path": item[1], "game_id": match.group(1) if match else None})
        if len(game_links) >= 80:
            break

    raw_game_ids = sorted(set(GAME_ID_RE.findall(raw)))[:100]
    return {
        "host": host,
        "path": path,
        "status": response.status_code,
        "visible": visible,
        "raw": raw,
        "upcoming": upcoming,
        "upcoming_marker_present": start >= 0,
        "game_links": game_links,
        "raw_game_ids": raw_game_ids,
        "serialized_markers": {
            "game_id_token": "gameid" in raw or "game_id" in raw,
            "schedule_league_v2": "scheduleleaguev2" in raw,
            "cdn_wnba": "cdn.wnba.com" in raw,
            "stats_wnba": "stats.wnba.com" in raw,
            "next_data": "__next_data__" in raw,
        },
    }


def main() -> int:
    events: dict[str, dict[str, Any]] = {}
    for url in frozen_draftkings_urls():
        response = _draftkings_get(url, timeout_seconds=12.0, requester=None)
        document = _draftkings_response_json(response, url=url)
        for event in extract_draftkings_events(document):
            events[event["source_event_id"]] = event

    rows = []
    page_cache: dict[tuple[str, str], dict[str, Any]] = {}
    for event_id, event in sorted(events.items()):
        participants = _event_teams(event)
        checks = []
        discovered_game_ids: set[str] = set()
        if len(participants) == 2:
            for team in participants:
                opponent = participants[1] if team == participants[0] else participants[0]
                root = page_cache.setdefault((team, "/"), _page(team, "/"))
                schedule = page_cache.setdefault((team, "/schedule"), _page(team, "/schedule"))
                date_markers = _date_markers(event.get("event_date"))
                ids = sorted(set(root["raw_game_ids"]) | set(schedule["raw_game_ids"]))
                discovered_game_ids.update(ids)
                checks.append({
                    "team": team,
                    "host": root["host"],
                    "root_http_status": root["status"],
                    "schedule_http_status": schedule["status"],
                    "opponent_in_root": _name_key(opponent) in root["visible"],
                    "opponent_in_upcoming": _name_key(opponent) in root["upcoming"],
                    "opponent_in_schedule_page": _name_key(opponent) in schedule["visible"],
                    "dk_utc_date_marker_in_root": any(marker in root["raw"] for marker in date_markers),
                    "dk_utc_date_marker_in_schedule": any(marker in schedule["raw"] for marker in date_markers),
                    "anchor_game_link_count": len(root["game_links"]) + len(schedule["game_links"]),
                    "raw_game_id_count": len(ids),
                    "raw_game_ids": ids[:40],
                    "root_serialized_markers": root["serialized_markers"],
                    "schedule_serialized_markers": schedule["serialized_markers"],
                })
        rows.append({
            "source_event_id": event_id,
            "event_name": event.get("event_name"),
            "draftkings_utc_calendar_date": event.get("event_date"),
            "raw_participants": event.get("participants") or [],
            "resolved_participants": participants,
            "checks": checks,
            "discovered_game_ids": sorted(discovered_game_ids),
            "both_team_pages_confirm_opponent": len(checks) == 2 and all(
                row["root_http_status"] == 200 and row["schedule_http_status"] == 200
                and (row["opponent_in_upcoming"] or row["opponent_in_schedule_page"])
                for row in checks
            ),
        })

    report = {
        "data_type": "wnba_step6h_official_team_event_probe",
        "event_count": len(rows),
        "events": rows,
        "all_events_confirmed_by_both_official_team_pages": bool(rows)
        and all(row["both_team_pages_confirm_opponent"] for row in rows),
        "safety": {
            "http_methods": ["GET"],
            "authentication_used": False,
            "raw_page_content_returned": False,
            "only_sanitized_identifiers_returned": True,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
