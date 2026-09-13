"""Exact-ID NFL Receiving Yards player-vs-team history for Step 5.

Read-only ESPN history helper. Official ESPN team, opponent, event and athlete IDs
are authoritative. Names are never used for matching. The helper fails closed on
invalid or mismatched identity and never invents zero-stat games when the ESPN
receiving game book does not contain the athlete row.
"""
from __future__ import annotations

from functools import lru_cache
import json
import math
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
ESPN_SITE_ALTERNATE_BASE = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl"
ESPN_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI-NFL-Receiving-History/1.0; read-only)",
}
DEFAULT_TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 8_000_000
HISTORY_SEASONS = 3
HISTORY_GAME_LIMIT = 5
TARGET_LABELS = ("TGTS", "TGT", "TARGETS")
MODEL_VERSION = "NFL RECEIVING YARDS HISTORY V1 • EXACT-ID PLAYER VS TEAM"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


class NFLReceivingHistoryError(RuntimeError):
    """Raised when exact-ID history cannot be proven safely."""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _number(value: Any) -> float | None:
    text = _text(value).replace(",", "")
    if not text or text in {"--", "-"}:
        return None
    try:
        out = float(text)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _alternate_espn_target(target: str) -> str:
    if not target.startswith(ESPN_SITE_BASE):
        return ""
    return ESPN_SITE_ALTERNATE_BASE + target[len(ESPN_SITE_BASE):]


def _read_bytes(target: str) -> bytes:
    request = Request(target, headers=ESPN_HEADERS, method="GET")
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
        status = int(getattr(response, "status", 0) or 0)
        if status != 200:
            raise NFLReceivingHistoryError(f"ESPN GET returned HTTP {status}")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise NFLReceivingHistoryError("ESPN history response exceeded safe size limit")
    return raw


@lru_cache(maxsize=256)
def _get_json(url: str, query_items: tuple[tuple[str, str], ...] = ()) -> dict[str, Any]:
    query = urlencode(dict(query_items))
    target = f"{url}?{query}" if query else url
    try:
        raw = _read_bytes(target)
    except (HTTPError, URLError, TimeoutError, NFLReceivingHistoryError) as primary_exc:
        alternate = _alternate_espn_target(target)
        if not alternate:
            raise NFLReceivingHistoryError(f"ESPN history read failed: {type(primary_exc).__name__}") from primary_exc
        try:
            raw = _read_bytes(alternate)
        except (HTTPError, URLError, TimeoutError, NFLReceivingHistoryError) as alternate_exc:
            raise NFLReceivingHistoryError(
                "ESPN history read failed on both certified transports"
            ) from alternate_exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NFLReceivingHistoryError("ESPN history response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise NFLReceivingHistoryError("ESPN history response was not an object")
    return payload


def _query(**values: Any) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in values.items()))


def _event_team_ids(event: dict[str, Any]) -> set[str]:
    comps = event.get("competitions") or []
    comp = comps[0] if comps and isinstance(comps[0], dict) else {}
    competitors = comp.get("competitors") or []
    return {
        _text((row.get("team") or {}).get("id"))
        for row in competitors
        if isinstance(row, dict) and _text((row.get("team") or {}).get("id")).isdigit()
    }


def _is_completed_regular_season(event: dict[str, Any], season: int) -> bool:
    season_obj = event.get("season") or {}
    season_type = event.get("seasonType") or {}
    comps = event.get("competitions") or []
    comp = comps[0] if comps and isinstance(comps[0], dict) else {}
    status_type = (comp.get("status") or {}).get("type") or {}
    try:
        event_year = int(season_obj.get("year") or 0)
        event_type = int(season_type.get("type") or season_type.get("id") or 0)
    except (TypeError, ValueError):
        return False
    return (
        event_year == int(season)
        and event_type == 2
        and _text(status_type.get("state")).lower() == "post"
        and status_type.get("completed") is True
    )


@lru_cache(maxsize=64)
def _matchup_events(team_id: str, opponent_id: str, anchor_season: int) -> tuple[tuple[str, str, int], ...]:
    if not team_id.isdigit() or not opponent_id.isdigit() or team_id == opponent_id:
        raise NFLReceivingHistoryError("exact team/opponent identity is required")
    found: list[tuple[str, str, int]] = []
    for season in range(int(anchor_season), int(anchor_season) - HISTORY_SEASONS, -1):
        payload = _get_json(
            f"{ESPN_SITE_BASE}/teams/{team_id}/schedule",
            _query(season=season, seasontype=2),
        )
        for event in payload.get("events") or []:
            if not isinstance(event, dict) or not _is_completed_regular_season(event, season):
                continue
            event_id = _text(event.get("id"))
            if not event_id.isdigit():
                continue
            if _event_team_ids(event) != {team_id, opponent_id}:
                continue
            found.append((_text(event.get("date")), event_id, season))
    found.sort(reverse=True)
    deduped: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    for row in found:
        if row[1] in seen:
            continue
        seen.add(row[1])
        deduped.append(row)
    return tuple(deduped[:HISTORY_GAME_LIMIT])


def _receiving_row(summary: dict[str, Any], team_id: str, athlete_id: str) -> dict[str, Any] | None:
    header = summary.get("header") or {}
    comps = header.get("competitions") or []
    comp = comps[0] if comps and isinstance(comps[0], dict) else {}
    ids = {
        _text((row.get("team") or {}).get("id"))
        for row in comp.get("competitors") or []
        if isinstance(row, dict)
    }
    if team_id not in ids:
        return None

    players = ((summary.get("boxscore") or {}).get("players") or [])
    block = next(
        (x for x in players if isinstance(x, dict) and _text((x.get("team") or {}).get("id")) == team_id),
        None,
    )
    if not isinstance(block, dict):
        return None
    category = next(
        (x for x in block.get("statistics") or [] if isinstance(x, dict) and _text(x.get("name")).lower() == "receiving"),
        None,
    )
    if not isinstance(category, dict):
        return None
    labels = [str(x).upper() for x in (category.get("labels") or [])]
    target_label = next((label for label in TARGET_LABELS if label in labels), None)
    for row in category.get("athletes") or []:
        if not isinstance(row, dict):
            continue
        athlete = row.get("athlete") or {}
        if _text(athlete.get("id")) != athlete_id:
            continue
        stats = row.get("stats") or []
        if not isinstance(stats, list):
            return None
        values = {label: _number(stats[i]) if i < len(stats) else None for i, label in enumerate(labels)}
        receptions = values.get("REC")
        yards = values.get("YDS")
        touchdowns = values.get("TD")
        if receptions is None or yards is None:
            return None
        targets = values.get(target_label) if target_label else None
        return {
            "receptions": int(receptions),
            "receiving_yards": int(yards),
            "receiving_touchdowns": int(touchdowns or 0),
            "targets_data_available": target_label is not None and targets is not None,
            "targets": int(targets) if target_label is not None and targets is not None else None,
        }
    return None


def get_player_vs_team_history(
    official_athlete_id: Any,
    official_team_id: Any,
    opponent_official_team_id: Any,
    anchor_season: Any,
) -> dict[str, Any]:
    athlete_id = _text(official_athlete_id)
    team_id = _text(official_team_id)
    opponent_id = _text(opponent_official_team_id)
    try:
        season = int(anchor_season)
    except (TypeError, ValueError):
        season = 0
    if (
        not athlete_id.isdigit()
        or not team_id.isdigit()
        or not opponent_id.isdigit()
        or team_id == opponent_id
        or season < 2000
    ):
        return {
            "ready": False,
            "reason": "exact athlete/team/opponent identity and anchor season are required",
            "games": [],
            "sportsbook_influence": 0.0,
        }

    try:
        events = _matchup_events(team_id, opponent_id, season)
        games: list[dict[str, Any]] = []
        for date, event_id, event_season in events:
            summary = _get_json(f"{ESPN_SITE_BASE}/summary", _query(event=event_id))
            header = summary.get("header") or {}
            comps = header.get("competitions") or []
            comp = comps[0] if comps and isinstance(comps[0], dict) else {}
            ids = {
                _text((row.get("team") or {}).get("id"))
                for row in comp.get("competitors") or []
                if isinstance(row, dict)
            }
            if ids != {team_id, opponent_id}:
                continue
            row = _receiving_row(summary, team_id, athlete_id)
            if row is None:
                continue
            games.append({
                "official_event_id": event_id,
                "official_athlete_id": athlete_id,
                "official_team_id": team_id,
                "opponent_official_team_id": opponent_id,
                "season": event_season,
                "date": date,
                **row,
            })
        return {
            "ready": True,
            "reason": "",
            "official_athlete_id": athlete_id,
            "official_team_id": team_id,
            "opponent_official_team_id": opponent_id,
            "anchor_season": season,
            "games": games,
            "source": "ESPN exact-ID completed regular-season game books",
            "sportsbook_influence": 0.0,
        }
    except NFLReceivingHistoryError as exc:
        return {
            "ready": False,
            "reason": str(exc),
            "official_athlete_id": athlete_id,
            "official_team_id": team_id,
            "opponent_official_team_id": opponent_id,
            "games": [],
            "sportsbook_influence": 0.0,
        }


__all__ = [
    "HISTORY_GAME_LIMIT",
    "HISTORY_SEASONS",
    "MODEL_VERSION",
    "NFLReceivingHistoryError",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "get_player_vs_team_history",
]
