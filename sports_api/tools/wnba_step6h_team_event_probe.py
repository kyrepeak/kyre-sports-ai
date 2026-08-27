"""Sanitized Step 6H probe: timezone-aware DK events vs official WNBA schedules."""
from __future__ import annotations

from datetime import datetime, timedelta
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
MAX_PAIR_DATE_DISTANCE = 1200

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


def _candidate_local_dates(utc_calendar_date: str | None) -> list[str]:
    if not utc_calendar_date:
        return []
    try:
        day = datetime.strptime(utc_calendar_date, "%Y-%m-%d")
    except ValueError:
        return []
    # WNBA games are in North American time zones. A late local game can fall
    # on the following UTC calendar date, so Step 6H checks both values.
    return [(day - timedelta(days=1)).strftime("%Y-%m-%d"), day.strftime("%Y-%m-%d")]


def _date_markers(value: str) -> list[str]:
    day = datetime.strptime(value, "%Y-%m-%d")
    raw = [
        value,
        day.strftime("%B %d"),
        day.strftime("%B %-d"),
        day.strftime("%b %d"),
        day.strftime("%b %-d"),
        f"{day.month}/{day.day}",
        f"{day.month:02d}/{day.day:02d}",
        f"{day.month}-{day.day}",
        f"{day.month:02d}-{day.day:02d}",
    ]
    return sorted({_name_key(marker) for marker in raw if _name_key(marker)})


def _positions(text: str, token: str) -> list[int]:
    out: list[int] = []
    start = 0
    while token:
        pos = text.find(token, start)
        if pos < 0:
            break
        out.append(pos)
        start = pos + 1
    return out


def _pair_date_distance(text: str, opponent: str, local_date: str) -> int | None:
    opponent_key = _name_key(opponent)
    opponent_tokens = {opponent_key, _name_key(opponent.split()[-1])}
    opponent_positions = [
        pos for token in opponent_tokens if token for pos in _positions(text, token)
    ]
    date_positions = [
        pos for marker in _date_markers(local_date) for pos in _positions(text, marker)
    ]
    if not opponent_positions or not date_positions:
        return None
    return min(abs(a - b) for a in opponent_positions for b in date_positions)


def _page(team_name: str) -> dict[str, Any]:
    host = TEAM_ROSTER_HOSTS[_name_key(team_name)]
    url = f"https://{host}/schedule"
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": UA,
    }
    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
    parser = TextParser()
    parser.feed(response.text)
    return {
        "host": host,
        "status": response.status_code,
        "visible": _name_key(" ".join(parser.parts)),
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
        candidate_dates = _candidate_local_dates(event.get("event_date"))
        checks = []
        if len(participants) == 2:
            for team in participants:
                opponent = participants[1] if team == participants[0] else participants[0]
                page = page_cache.setdefault(team, _page(team))
                date_rows = []
                for local_date in candidate_dates:
                    distance = _pair_date_distance(page["visible"], opponent, local_date)
                    date_rows.append({
                        "local_date": local_date,
                        "pair_date_distance": distance,
                        "pair_date_near": distance is not None and distance <= MAX_PAIR_DATE_DISTANCE,
                    })
                near_dates = [row["local_date"] for row in date_rows if row["pair_date_near"]]
                checks.append({
                    "team": team,
                    "host": page["host"],
                    "http_status": page["status"],
                    "opponent_in_schedule_page": _name_key(opponent) in page["visible"],
                    "candidate_dates": date_rows,
                    "near_local_dates": near_dates,
                })
        common_dates = set(candidate_dates)
        for check in checks:
            common_dates &= set(check["near_local_dates"])
        rows.append({
            "source_event_id": event_id,
            "event_name": event.get("event_name"),
            "draftkings_utc_calendar_date": event.get("event_date"),
            "resolved_participants": participants,
            "candidate_local_dates": candidate_dates,
            "checks": checks,
            "common_official_local_dates": sorted(common_dates),
            "unique_mutual_local_date": len(common_dates) == 1,
            "mutual_official_local_date": sorted(common_dates)[0] if len(common_dates) == 1 else None,
        })

    report = {
        "data_type": "wnba_step6h_timezone_aware_official_schedule_probe",
        "event_count": len(rows),
        "events": rows,
        "all_events_have_unique_mutual_official_local_date": bool(rows)
        and all(row["unique_mutual_local_date"] for row in rows),
        "max_pair_date_distance": MAX_PAIR_DATE_DISTANCE,
        "safety": {
            "http_methods": ["GET"],
            "authentication_used": False,
            "raw_page_content_returned": False,
            "production_feed_written": False,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
