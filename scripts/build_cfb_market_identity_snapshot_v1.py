"""Build an official ESPN CFB identity snapshot for the live FanDuel market horizon.

This publisher exists for hosted runtimes that can read GitHub but cannot reach
ESPN scoreboards directly. FanDuel is used only to discover which future dates
need identity coverage. ESPN remains the authority for event/team identity.

Safety contract:
- official ESPN event IDs only
- FBS + FCS exact-date scoreboards
- no synthetic IDs
- no fuzzy matching
- no sportsbook input to projection math
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cfb_market_identity_snapshot_v1.json"

ET = ZoneInfo("America/New_York")
TIMEOUT_SECONDS = 25
MAX_RESPONSE_BYTES = 20_000_000

FANDUEL_URL = "https://api.sportsbook.fanduel.com/sbapi/content-managed-page"
FANDUEL_PUBLIC_WEB_KEY = "FhMFpcPWXMeyZxOx"
ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
)

FANDUEL_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI-CFB-IdentityPublisher/1.0)",
    "Origin": "https://sportsbook.fanduel.com",
    "Referer": "https://sportsbook.fanduel.com/",
    "x-sportsbook-region": "NJ",
}
ESPN_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI-CFB-IdentityPublisher/1.0)",
    "Referer": "https://www.espn.com/",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        result: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("_attachment_key", str(key))
                result.append(row)
        return result
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _parse_utc(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def get_json(
    url: str,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    query = urlencode({str(k): str(v) for k, v in dict(params or {}).items()})
    full_url = url + (("?" + query) if query else "")
    request = Request(full_url, headers=dict(headers or {}), method="GET")
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        status = int(getattr(response, "status", 0) or 0)
        if status != 200:
            raise RuntimeError(f"GET {url} returned HTTP {status}")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"GET {url} exceeded {MAX_RESPONSE_BYTES} bytes")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"GET {url} returned a non-object JSON payload")
    return payload


def fanduel_market_dates(
    *,
    now_utc: datetime,
    fetch_json=get_json,
) -> tuple[list[str], int]:
    payload = fetch_json(
        FANDUEL_URL,
        {
            "_ak": FANDUEL_PUBLIC_WEB_KEY,
            "page": "CUSTOM",
            "customPageId": "ncaaf",
            "timezone": "America/New_York",
        },
        FANDUEL_HEADERS,
    )
    attachments = payload.get("attachments")
    if not isinstance(attachments, Mapping):
        raise RuntimeError("FanDuel NCAAF page has no attachments object")

    dates: set[str] = set()
    future_matchups = 0
    for event in _rows(attachments.get("events")):
        name = _clean(
            event.get("name") or event.get("eventName") or event.get("displayName")
        )
        if " @ " not in name:
            continue
        start = _parse_utc(event.get("openDate"))
        if start is None or start <= now_utc:
            continue
        future_matchups += 1
        dates.add(start.astimezone(ET).date().isoformat())

    if not dates:
        raise RuntimeError("FanDuel NCAAF board produced no future matchup dates")
    return sorted(dates), future_matchups


def _espn_event_date(event: Mapping[str, Any], requested_day: str) -> str:
    parsed = _parse_utc(event.get("date"))
    return parsed.astimezone(ET).date().isoformat() if parsed is not None else requested_day


def _team_info(competitor: Mapping[str, Any]) -> tuple[str, str]:
    team = competitor.get("team") if isinstance(competitor.get("team"), Mapping) else {}
    name = _clean(
        team.get("displayName")
        or team.get("shortDisplayName")
        or team.get("location")
        or team.get("name")
    )
    return name, _clean(team.get("id"))


def espn_games_for_date(
    requested_day: str,
    *,
    fetch_json=get_json,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}

    for group_id, division in ((80, "FBS"), (81, "FCS")):
        payload = fetch_json(
            ESPN_SCOREBOARD_URL,
            {
                "dates": requested_day.replace("-", ""),
                "limit": 500,
                "groups": group_id,
            },
            ESPN_HEADERS,
        )
        for event in payload.get("events") or []:
            if not isinstance(event, Mapping):
                continue
            event_id = _clean(event.get("id"))
            if not event_id or not event_id.isdigit():
                continue
            if _espn_event_date(event, requested_day) != requested_day:
                continue

            competitions = event.get("competitions") or []
            if not competitions or not isinstance(competitions[0], Mapping):
                continue
            comp = competitions[0]
            sides: dict[str, Mapping[str, Any]] = {}
            for competitor in comp.get("competitors") or []:
                if not isinstance(competitor, Mapping):
                    continue
                side = _clean(competitor.get("homeAway")).casefold()
                if side in {"away", "home"}:
                    sides[side] = competitor
            if "away" not in sides or "home" not in sides:
                continue

            away_name, away_id = _team_info(sides["away"])
            home_name, home_id = _team_info(sides["home"])
            if not away_name or not home_name or not away_id or not home_id:
                continue

            venue_obj = comp.get("venue") if isinstance(comp.get("venue"), Mapping) else {}
            broadcasts: list[str] = []
            for row in comp.get("broadcasts") or []:
                if not isinstance(row, Mapping):
                    continue
                for name in row.get("names") or []:
                    text = _clean(name)
                    if text:
                        broadcasts.append(text)

            status_obj = event.get("status") if isinstance(event.get("status"), Mapping) else {}
            status_type = status_obj.get("type") if isinstance(status_obj.get("type"), Mapping) else {}

            existing = by_id.get(event_id)
            source_divisions = list((existing or {}).get("source_divisions") or [])
            if division not in source_divisions:
                source_divisions.append(division)

            by_id[event_id] = {
                "event_id": event_id,
                "game_date": requested_day,
                "away_team": away_name,
                "home_team": home_name,
                "away_team_id": away_id,
                "home_team_id": home_id,
                "venue": _clean(venue_obj.get("fullName") or venue_obj.get("name")),
                "broadcast": ", ".join(dict.fromkeys(broadcasts)),
                "status": _clean(
                    status_type.get("description")
                    or status_type.get("detail")
                    or status_type.get("shortDetail")
                ),
                "source_divisions": source_divisions,
                "sources": ["ESPN college-football FBS/FCS scoreboards"],
            }

    return sorted(by_id.values(), key=lambda row: row["event_id"])


def build_snapshot(
    *,
    now_utc: datetime | None = None,
    fetch_json=get_json,
) -> dict[str, Any]:
    now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    market_dates, future_matchups = fanduel_market_dates(
        now_utc=now,
        fetch_json=fetch_json,
    )

    games_by_id: dict[str, dict[str, Any]] = {}
    date_counts: dict[str, int] = {}
    for day in market_dates:
        rows = espn_games_for_date(day, fetch_json=fetch_json)
        if not rows:
            raise RuntimeError(f"ESPN returned zero official CFB identities for market date {day}")
        date_counts[day] = len(rows)
        for row in rows:
            event_id = row["event_id"]
            if event_id in games_by_id and games_by_id[event_id] != row:
                raise RuntimeError(f"conflicting official ESPN identity for event {event_id}")
            games_by_id[event_id] = row

    games = sorted(
        games_by_id.values(),
        key=lambda row: (row["game_date"], row["event_id"]),
    )
    if not games:
        raise RuntimeError("official CFB identity snapshot would be empty")

    return {
        "version": 1,
        "generated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "purpose": (
            "Official ESPN identity coverage for the complete live FanDuel NCAAF "
            "market-date horizon; market data never enters projection math."
        ),
        "window": {"start": market_dates[0], "end": market_dates[-1]},
        "market_dates": market_dates,
        "provider_future_matchups": future_matchups,
        "date_counts": date_counts,
        "identity_policy": {
            "authority": "ESPN",
            "official_event_ids_only": True,
            "synthetic_ids": False,
            "fuzzy_matching": False,
            "sportsbook_projection_weight": 0.0,
        },
        "games": games,
    }


def _normalized_for_compare(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    value.pop("generated_at", None)
    value.pop("provider_future_matchups", None)
    return value


def write_snapshot(payload: Mapping[str, Any], path: Path = OUT) -> bool:
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            previous = None
        if isinstance(previous, Mapping) and _normalized_for_compare(previous) == _normalized_for_compare(payload):
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


def main() -> int:
    snapshot = build_snapshot()
    changed = write_snapshot(snapshot)
    print(
        "CFB_MARKET_IDENTITY_SNAPSHOT_V1",
        f"changed={str(changed).lower()}",
        f"market_dates={len(snapshot['market_dates'])}",
        f"games={len(snapshot['games'])}",
        f"window={snapshot['window']['start']}..{snapshot['window']['end']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
