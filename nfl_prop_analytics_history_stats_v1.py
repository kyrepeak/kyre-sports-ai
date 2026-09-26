"""NFL Prop Analytics Page 3 Step 3 — exact-ID historical stats + hit-rate engine.

Read-only ESPN completed regular-season game books are the only data source.
Exact ESPN event/team/athlete IDs are authoritative; names are display-only.

This module intentionally does not load sportsbook lines, odds, projections,
probabilities, recommendations, rankings, staking, or wager actions. The
hit-rate engine accepts an explicit line only when a later UI step supplies one.
Without a line it returns "awaiting-line" rather than inventing a threshold.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from functools import lru_cache
import math
import re
from statistics import mean, median
import time
from typing import Any

import requests

import nfl_passing_yards_profile_v1 as passing_profile
from nfl_prop_analytics_schedule_v1 import TEAM_NAMES, _canon_team

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 STEP 3 • EXACT-ID HISTORY STATS V1"
SOURCE = "ESPN exact-ID completed regular-season game books"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
REQUEST_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "KyreSportsAI-PropAnalytics-History/1.0",
}
REQUEST_TIMEOUT_SECONDS = 8
ACTIVE_CACHE_TTL_SECONDS = 300
HISTORY_SEASONS = 3
MAX_RECENT_GAMES = 20
MAX_H2H_GAMES = 5
MAX_WORKERS = 6
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_ENABLED = False
MARKET_ENABLED = False
WAGER_ACTIONS = False

PASSING_GAMELOG_MARKETS = frozenset({
    "passing_yards",
    "passing_touchdowns",
    "interceptions",
    "completions",
    "attempts",
})

SUPPORTED_MARKETS = frozenset({
    "passing_yards",
    "passing_touchdowns",
    "interceptions",
    "completions",
    "attempts",
    "rushing_yards",
    "carries",
    "receptions",
    "receiving_yards",
    "longest_reception",
    "anytime_touchdown",
})


class PropHistoryError(RuntimeError):
    """Raised when exact-ID historical truth cannot be established safely."""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _number(value: Any) -> float | None:
    raw = _text(value).replace(",", "")
    if not raw or raw in {"--", "-"}:
        return None
    match = re.match(r"^-?\d+(?:\.\d+)?", raw)
    if not match:
        return None
    try:
        out = float(match.group(0))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _query_number(values: dict[str, float | None], *keys: str) -> float | None:
    for key in keys:
        if key in values and values[key] is not None:
            return values[key]
    return None


def _request_json(url: str, query_items: tuple[tuple[str, str], ...] = ()) -> dict[str, Any]:
    try:
        response = requests.get(
            url,
            params=dict(query_items),
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise PropHistoryError(f"ESPN history read failed: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise PropHistoryError("ESPN history response was not an object")
    return payload


@lru_cache(maxsize=512)
def _get_json(url: str, query_items: tuple[tuple[str, str], ...] = ()) -> dict[str, Any]:
    return _request_json(url, query_items)


def _active_season_year(now: datetime | None = None) -> int:
    stamp = now or datetime.now(timezone.utc)
    return stamp.year if stamp.month >= 3 else stamp.year - 1


def _freshness_bucket(season: int) -> int:
    if int(season) != _active_season_year():
        return 0
    return int(time.time() // ACTIVE_CACHE_TTL_SECONDS)


def _query(**values: Any) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(k), str(v)) for k, v in values.items()))


def _canon_opponent(value: Any) -> str:
    raw = _text(value)
    canonical = _canon_team(raw)
    if canonical in TEAM_NAMES:
        return canonical
    upper = raw.upper()
    for abbr, name in TEAM_NAMES.items():
        if upper == name.upper() or upper.endswith(" " + name.upper()):
            return abbr
    return canonical


def _passing_value(row: dict[str, Any], market_key: str) -> float | None:
    source_key = {
        "passing_yards": "passing_yards",
        "passing_touchdowns": "passing_tds",
        "interceptions": "interceptions",
        "completions": "completions",
        "attempts": "attempts",
    }.get(market_key, "")
    if not source_key:
        return None
    return _number(row.get(source_key))


@lru_cache(maxsize=192)
def _passing_gamelog_season_cached(
    athlete_id: str,
    season: int,
    freshness_bucket: int,
) -> tuple[dict[str, Any], ...]:
    del freshness_bucket
    payload, diag = passing_profile._gamelog_payload(int(season), athlete_id)
    if not diag.get("ok"):
        raise PropHistoryError(
            "ESPN athlete game log failed: "
            + _text(diag.get("error") or diag.get("http") or "unknown")
        )
    rows = passing_profile.parse_recent_passing(payload)
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        event_id = _text(row.get("event_id"))
        if not event_id.isdigit():
            continue
        out.append({
            "official_event_id": event_id,
            "date": _text(row.get("date")),
            "season": int(season),
            "opponent_abbr": _canon_opponent(row.get("opponent")),
            **dict(row),
        })
    out.sort(key=lambda row: (row.get("date") or "", row.get("official_event_id") or ""), reverse=True)
    return tuple(out)


def _passing_gamelog_season(athlete_id: str, season: int) -> tuple[dict[str, Any], ...]:
    return _passing_gamelog_season_cached(
        athlete_id,
        int(season),
        _freshness_bucket(int(season)),
    )


_passing_gamelog_season.cache_clear = _passing_gamelog_season_cached.cache_clear


def _passing_history_games(
    athlete_id: str,
    opponent_abbr: str,
    anchor_season: int,
    history_key: str,
    market_key: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[str] = []
    for season in range(int(anchor_season), int(anchor_season) - HISTORY_SEASONS, -1):
        try:
            season_rows = _passing_gamelog_season(athlete_id, season)
        except PropHistoryError as exc:
            errors.append(str(exc))
            continue
        for row in season_rows:
            event_id = _text(row.get("official_event_id"))
            if not event_id or event_id in seen:
                continue
            value = _passing_value(row, market_key)
            if value is None:
                continue
            seen.add(event_id)
            rows.append({
                "official_event_id": event_id,
                "official_athlete_id": athlete_id,
                "date": _text(row.get("date")),
                "season": int(row.get("season") or season),
                "opponent_abbr": _canon_opponent(row.get("opponent_abbr") or row.get("opponent")),
                "market_key": market_key,
                "value": float(value),
            })

    rows.sort(key=lambda row: (row["date"], row["official_event_id"]), reverse=True)
    key = _text(history_key).upper()
    if key == "H2H":
        return [row for row in rows if row.get("opponent_abbr") == opponent_abbr][:MAX_H2H_GAMES]
    if key in {"L5", "L10", "L20"}:
        return rows[: int(key[1:])]
    if key.isdigit() and len(key) == 4:
        season = int(key)
        return [row for row in rows if int(row.get("season") or 0) == season]
    if errors and not rows:
        raise PropHistoryError(errors[0])
    raise PropHistoryError(f"unsupported history window: {history_key}")


def _competition(event: dict[str, Any]) -> dict[str, Any]:
    comps = event.get("competitions") or []
    return comps[0] if comps and isinstance(comps[0], dict) else {}


def _competitor_rows(container: dict[str, Any]) -> list[dict[str, Any]]:
    rows = container.get("competitors") or []
    return [row for row in rows if isinstance(row, dict)]


def _team_identity_from_summary(
    event_id: str,
    player_team: str,
    opponent: str,
) -> tuple[str, str]:
    summary = _get_json(f"{ESPN_BASE}/summary", _query(event=event_id))
    header = summary.get("header") or {}
    comp = _competition(header)
    by_abbr: dict[str, str] = {}
    for row in _competitor_rows(comp):
        team = row.get("team") or {}
        team_id = _text(team.get("id"))
        abbr = _canon_team(team.get("abbreviation"))
        if team_id.isdigit() and abbr:
            by_abbr[abbr] = team_id
    player_abbr = _canon_team(player_team)
    opponent_abbr = _canon_team(opponent)
    team_id = by_abbr.get(player_abbr, "")
    opponent_id = by_abbr.get(opponent_abbr, "")
    if not team_id.isdigit() or not opponent_id.isdigit() or team_id == opponent_id:
        raise PropHistoryError("current event exact team/opponent identity could not be proven")
    return team_id, opponent_id


def _season_year(event: dict[str, Any], fallback: int) -> int:
    raw = event.get("season") or {}
    value = raw.get("year") if isinstance(raw, dict) else raw
    try:
        out = int(value)
    except (TypeError, ValueError):
        out = int(fallback)
    return out


def _regular_season(event: dict[str, Any]) -> bool:
    season_type = event.get("seasonType") or {}
    value = (
        season_type.get("type")
        or season_type.get("id")
        or ((event.get("season") or {}).get("type") if isinstance(event.get("season"), dict) else None)
    )
    try:
        return int(value or 0) == 2
    except (TypeError, ValueError):
        return False


def _completed(event: dict[str, Any]) -> bool:
    comp = _competition(event)
    status = (comp.get("status") or {}).get("type") or (event.get("status") or {}).get("type") or {}
    return status.get("completed") is True or _text(status.get("state")).lower() == "post"


def _event_team_ids(event: dict[str, Any]) -> set[str]:
    comp = _competition(event)
    return {
        _text((row.get("team") or {}).get("id"))
        for row in _competitor_rows(comp)
        if _text((row.get("team") or {}).get("id")).isdigit()
    }


def _opponent_abbr(event: dict[str, Any], team_id: str) -> str:
    comp = _competition(event)
    for row in _competitor_rows(comp):
        team = row.get("team") or {}
        if _text(team.get("id")) == team_id:
            continue
        abbr = _canon_team(team.get("abbreviation"))
        if abbr:
            return abbr
    return ""


@lru_cache(maxsize=192)
def _team_schedule_cached(
    team_id: str,
    season: int,
    freshness_bucket: int,
) -> tuple[dict[str, Any], ...]:
    if not _text(team_id).isdigit():
        raise PropHistoryError("official ESPN team id is required")
    query = _query(season=int(season), seasontype=2)
    url = f"{ESPN_BASE}/teams/{team_id}/schedule"
    payload = (
        _request_json(url, query)
        if freshness_bucket
        else _get_json(url, query)
    )
    out: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        # The request itself is scoped to seasontype=2. Some ESPN schedule
        # payloads omit the redundant event["seasonType"] object, so requiring
        # it here can incorrectly discard every valid regular-season game.
        # Keep the contract strict with season year + completed state + exact
        # team identity instead of relying on that optional duplicate field.
        event_season = _season_year(event, season)
        if event_season != int(season) or not _completed(event):
            continue
        event_id = _text(event.get("id"))
        if not event_id.isdigit():
            continue
        ids = _event_team_ids(event)
        if team_id not in ids or len(ids) != 2:
            continue
        out.append({
            "event_id": event_id,
            "date": _text(event.get("date")),
            "season": event_season,
            "team_ids": tuple(sorted(ids)),
            "opponent_abbr": _opponent_abbr(event, team_id),
        })
    out.sort(key=lambda row: (row["date"], row["event_id"]), reverse=True)
    return tuple(out)


def _team_schedule(team_id: str, season: int) -> tuple[dict[str, Any], ...]:
    return _team_schedule_cached(
        team_id,
        int(season),
        _freshness_bucket(int(season)),
    )


_team_schedule.cache_clear = _team_schedule_cached.cache_clear


def _category_row(
    summary: dict[str, Any],
    team_id: str,
    athlete_id: str,
    category_name: str,
) -> tuple[list[str], list[Any]] | None:
    players = ((summary.get("boxscore") or {}).get("players") or [])
    block = next(
        (
            x for x in players
            if isinstance(x, dict)
            and _text((x.get("team") or {}).get("id")) == team_id
        ),
        None,
    )
    if not isinstance(block, dict):
        return None
    category = next(
        (
            x for x in block.get("statistics") or []
            if isinstance(x, dict)
            and _text(x.get("name")).lower() == category_name.lower()
        ),
        None,
    )
    if not isinstance(category, dict):
        return None
    labels = [str(x).upper() for x in (category.get("labels") or [])]
    for row in category.get("athletes") or []:
        if not isinstance(row, dict):
            continue
        athlete = row.get("athlete") or {}
        if _text(athlete.get("id")) != athlete_id:
            continue
        stats = row.get("stats") or []
        if isinstance(stats, list):
            return labels, stats
    return None


def _labeled_values(labels: list[str], stats: list[Any]) -> dict[str, float | None]:
    return {
        label: _number(stats[i]) if i < len(stats) else None
        for i, label in enumerate(labels)
    }


def _passing_stats(row: tuple[list[str], list[Any]] | None) -> dict[str, float]:
    if row is None:
        return {}
    labels, stats = row
    values = _labeled_values(labels, stats)
    out: dict[str, float] = {}

    catt_index = next(
        (i for i, label in enumerate(labels) if label in {"C/ATT", "CMP/ATT", "COMP/ATT"}),
        None,
    )
    if catt_index is not None and catt_index < len(stats):
        raw = _text(stats[catt_index])
        match = re.match(r"^(\d+)\s*/\s*(\d+)$", raw)
        if match:
            out["completions"] = float(match.group(1))
            out["attempts"] = float(match.group(2))

    yards = _query_number(values, "YDS", "PASS YDS", "PASSYDS")
    touchdowns = _query_number(values, "TD", "TDS")
    interceptions = _query_number(values, "INT", "INTS")
    if yards is not None:
        out["passing_yards"] = yards
    if touchdowns is not None:
        out["passing_touchdowns"] = touchdowns
    if interceptions is not None:
        out["interceptions"] = interceptions
    return out


def _rushing_stats(row: tuple[list[str], list[Any]] | None) -> dict[str, float]:
    if row is None:
        return {}
    labels, stats = row
    values = _labeled_values(labels, stats)
    out: dict[str, float] = {}
    carries = _query_number(values, "CAR", "ATT")
    yards = _query_number(values, "YDS", "RUSH YDS", "RUSHYDS")
    touchdowns = _query_number(values, "TD", "TDS")
    if carries is not None:
        out["carries"] = carries
    if yards is not None:
        out["rushing_yards"] = yards
    if touchdowns is not None:
        out["rushing_touchdowns"] = touchdowns
    return out


def _receiving_stats(row: tuple[list[str], list[Any]] | None) -> dict[str, float]:
    if row is None:
        return {}
    labels, stats = row
    values = _labeled_values(labels, stats)
    out: dict[str, float] = {}
    receptions = _query_number(values, "REC")
    yards = _query_number(values, "YDS", "REC YDS", "RECYDS")
    touchdowns = _query_number(values, "TD", "TDS")
    longest = _query_number(values, "LONG", "LG")
    if receptions is not None:
        out["receptions"] = receptions
    if yards is not None:
        out["receiving_yards"] = yards
    if touchdowns is not None:
        out["receiving_touchdowns"] = touchdowns
    if longest is not None:
        out["longest_reception"] = longest
    return out


def _market_value(
    summary: dict[str, Any],
    team_id: str,
    athlete_id: str,
    market_key: str,
    *,
    participated: bool = False,
) -> float | None:
    passing = _passing_stats(_category_row(summary, team_id, athlete_id, "passing"))
    rushing = _rushing_stats(_category_row(summary, team_id, athlete_id, "rushing"))
    receiving = _receiving_stats(_category_row(summary, team_id, athlete_id, "receiving"))

    if market_key in passing:
        return passing[market_key]
    if market_key in rushing:
        return rushing[market_key]
    if market_key in receiving:
        return receiving[market_key]
    if market_key == "anytime_touchdown":
        if rushing or receiving:
            return float(rushing.get("rushing_touchdowns", 0.0) + receiving.get("receiving_touchdowns", 0.0))
        return 0.0 if participated else None
    if participated and market_key in {
        "rushing_yards",
        "carries",
        "receptions",
        "receiving_yards",
        "longest_reception",
    }:
        return 0.0
    return None


def _gamelog_event_meta(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = (payload or {}).get("events") or {}
    if isinstance(raw, dict):
        items = raw.get("items") if isinstance(raw.get("items"), list) else None
        if items is None:
            return {
                _text(key): dict(value)
                for key, value in raw.items()
                if _text(key).isdigit() and isinstance(value, dict)
            }
        raw = items
    out: dict[str, dict[str, Any]] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            event = item.get("event") if isinstance(item.get("event"), dict) else item
            event_id = _text(event.get("id") or item.get("id") or item.get("eventId"))
            if not event_id.isdigit():
                continue
            merged = dict(event)
            merged.update({k: v for k, v in item.items() if k not in merged})
            out[event_id] = merged
    return out


def _gamelog_team_id(value: Any) -> str:
    if isinstance(value, dict):
        candidate = _text(value.get("id") or value.get("teamId"))
    else:
        candidate = _text(value)
    return candidate if candidate.isdigit() else ""


def _gamelog_opponent(meta: dict[str, Any], item: dict[str, Any]) -> str:
    opponent = meta.get("opponent") or item.get("opponent") or {}
    if isinstance(opponent, dict):
        return _canon_opponent(
            opponent.get("abbreviation")
            or opponent.get("displayName")
            or opponent.get("name")
        )
    return _canon_opponent(opponent or meta.get("opponentName") or item.get("opponentName"))


def _iter_proven_gamelog_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    meta_map = _gamelog_event_meta(payload)
    rows: list[dict[str, Any]] = []

    def add(item: Any) -> None:
        if not isinstance(item, dict):
            return
        if "stats" not in item and "statistics" not in item:
            return
        event_obj = item.get("event") if isinstance(item.get("event"), dict) else {}
        event_id = _text(item.get("eventId") or item.get("id") or event_obj.get("id"))
        if not event_id.isdigit():
            return
        meta = meta_map.get(event_id) or event_obj or {}
        team_id = (
            _gamelog_team_id(item.get("team"))
            or _gamelog_team_id(meta.get("team"))
            or _text(item.get("teamId"))
            or _text(meta.get("teamId"))
        )
        if not team_id.isdigit():
            team_id = ""
        rows.append({
            "event_id": event_id,
            "date": _text(
                meta.get("gameDate")
                or meta.get("date")
                or item.get("gameDate")
                or item.get("date")
            ),
            "opponent_abbr": _gamelog_opponent(meta, item),
            "official_team_id": team_id,
            "participation_proven": True,
        })

    for season_type in (payload or {}).get("seasonTypes") or []:
        if not isinstance(season_type, dict):
            continue
        label = _text(season_type.get("displayName") or season_type.get("name")).lower()
        type_value = _text(season_type.get("type") or season_type.get("id"))
        if label and "regular" not in label:
            continue
        if type_value.isdigit() and int(type_value) != 2:
            continue
        for category in season_type.get("categories") or []:
            if not isinstance(category, dict):
                continue
            if _text(category.get("type")).lower() not in {"", "event"}:
                continue
            events = category.get("events") or []
            if isinstance(events, dict):
                events = [
                    dict(value, eventId=key)
                    for key, value in events.items()
                    if isinstance(value, dict)
                ]
            for item in events if isinstance(events, list) else []:
                add(item)

    for category in (payload or {}).get("categories") or []:
        if not isinstance(category, dict):
            continue
        events = category.get("events") or []
        if isinstance(events, dict):
            events = [
                dict(value, eventId=key)
                for key, value in events.items()
                if isinstance(value, dict)
            ]
        for item in events if isinstance(events, list) else []:
            add(item)

    raw_top = (payload or {}).get("events")
    if isinstance(raw_top, list):
        for item in raw_top:
            add(item)
    elif isinstance(raw_top, dict) and isinstance(raw_top.get("items"), list):
        for item in raw_top.get("items") or []:
            add(item)

    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        event_id = row["event_id"]
        previous = dedup.get(event_id)
        if previous is None:
            dedup[event_id] = row
            continue
        for key in ("date", "opponent_abbr", "official_team_id"):
            if not previous.get(key) and row.get(key):
                previous[key] = row[key]
    return list(dedup.values())


@lru_cache(maxsize=192)
def _athlete_gamelog_season_cached(
    athlete_id: str,
    season: int,
    freshness_bucket: int,
) -> tuple[dict[str, Any], ...]:
    del freshness_bucket
    payload, diag = passing_profile._gamelog_payload(int(season), athlete_id)
    if not diag.get("ok"):
        raise PropHistoryError(
            "ESPN athlete game log failed: "
            + _text(diag.get("error") or diag.get("http") or "unknown")
        )
    rows = _iter_proven_gamelog_events(payload)
    out = []
    for row in rows:
        item = dict(row)
        item["season"] = int(season)
        out.append(item)
    out.sort(key=lambda row: (row.get("date") or "", row.get("event_id") or ""), reverse=True)
    return tuple(out)


def _athlete_gamelog_season(athlete_id: str, season: int) -> tuple[dict[str, Any], ...]:
    return _athlete_gamelog_season_cached(
        athlete_id,
        int(season),
        _freshness_bucket(int(season)),
    )


_athlete_gamelog_season.cache_clear = _athlete_gamelog_season_cached.cache_clear


def _candidate_events(athlete_id: str, anchor_season: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[str] = []
    for season in range(int(anchor_season), int(anchor_season) - HISTORY_SEASONS, -1):
        try:
            season_rows = _athlete_gamelog_season(athlete_id, season)
        except PropHistoryError as exc:
            errors.append(str(exc))
            continue
        for row in season_rows:
            event_id = _text(row.get("event_id"))
            if not event_id or event_id in seen:
                continue
            seen.add(event_id)
            rows.append(dict(row))
    rows.sort(key=lambda row: (row.get("date") or "", row["event_id"]), reverse=True)
    if not rows and errors:
        raise PropHistoryError(errors[0])
    return rows


def _select_events(
    rows: list[dict[str, Any]],
    history_key: str,
    opponent_id: str,
    opponent_abbr: str = "",
) -> list[dict[str, Any]]:
    key = _text(history_key).upper()
    if key == "H2H":
        target_abbr = _canon_team(opponent_abbr)
        selected = [
            row for row in rows
            if (
                opponent_id in set(row.get("team_ids") or ())
                or (
                    target_abbr
                    and _canon_team(row.get("opponent_abbr")) == target_abbr
                )
            )
        ]
        return selected[:MAX_H2H_GAMES]
    if key in {"L5", "L10", "L20"}:
        return rows[: int(key[1:])]
    if key.isdigit() and len(key) == 4:
        season = int(key)
        return [row for row in rows if int(row.get("season") or 0) == season]
    raise PropHistoryError(f"unsupported history window: {history_key}")


def _athlete_team_id_from_summary(summary: dict[str, Any], athlete_id: str) -> str:
    players = ((summary.get("boxscore") or {}).get("players") or [])
    for block in players:
        if not isinstance(block, dict):
            continue
        team_id = _text((block.get("team") or {}).get("id"))
        if not team_id.isdigit():
            continue
        for category in block.get("statistics") or []:
            if not isinstance(category, dict):
                continue
            for row in category.get("athletes") or []:
                if not isinstance(row, dict):
                    continue
                athlete = row.get("athlete") or {}
                if _text(athlete.get("id")) == athlete_id:
                    return team_id

    for block in summary.get("rosters") or []:
        if not isinstance(block, dict):
            continue
        team_id = _text((block.get("team") or {}).get("id"))
        if not team_id.isdigit():
            continue
        roster = block.get("roster") or block.get("athletes") or []
        for row in roster if isinstance(roster, list) else []:
            if not isinstance(row, dict):
                continue
            athlete = row.get("athlete") if isinstance(row.get("athlete"), dict) else row
            if _text(athlete.get("id")) == athlete_id:
                return team_id
    return ""


def _summary_team_ids(summary: dict[str, Any]) -> set[str]:
    header = summary.get("header") or {}
    comp = _competition(header)
    return _event_team_ids({"competitions": [comp]}) if comp else set()


def _fetch_game_value(
    row: dict[str, Any],
    team_id: str,
    athlete_id: str,
    market_key: str,
) -> dict[str, Any] | None:
    event_id = _text(row.get("event_id"))
    summary = _get_json(f"{ESPN_BASE}/summary", _query(event=event_id))
    game_team_id = _text(row.get("official_team_id"))
    if not game_team_id.isdigit():
        game_team_id = _athlete_team_id_from_summary(summary, athlete_id)
    if not game_team_id.isdigit():
        return None
    proven = row.get("participation_proven") is True
    value = _market_value(
        summary,
        game_team_id,
        athlete_id,
        market_key,
        participated=proven,
    )
    if value is None or not math.isfinite(float(value)):
        return None
    team_ids = _summary_team_ids(summary)
    opponent_abbr = _text(row.get("opponent_abbr")).upper()
    if not opponent_abbr and game_team_id in team_ids:
        opponent_abbr = _opponent_abbr(
            {"competitions": [_competition(summary.get("header") or {})]},
            game_team_id,
        )
    return {
        "official_event_id": event_id,
        "official_athlete_id": athlete_id,
        "official_team_id": game_team_id,
        "date": _text(row.get("date")),
        "season": int(row.get("season") or 0),
        "opponent_abbr": opponent_abbr,
        "market_key": market_key,
        "value": float(value),
    }


def load_player_history(
    *,
    official_event_id: Any,
    official_athlete_id: Any,
    player_team: Any,
    opponent: Any,
    anchor_season: Any,
    history_key: Any,
    market_key: Any,
) -> dict[str, Any]:
    event_id = _text(official_event_id)
    athlete_id = _text(official_athlete_id)
    team_abbr = _canon_team(player_team)
    opponent_abbr = _canon_team(opponent)
    history = _text(history_key).upper()
    market = _text(market_key)

    try:
        season = int(anchor_season)
    except (TypeError, ValueError):
        season = 0

    base = {
        "ready": False,
        "data_available": False,
        "reason": "",
        "official_event_id": event_id,
        "official_athlete_id": athlete_id,
        "player_team": team_abbr,
        "opponent": opponent_abbr,
        "anchor_season": season,
        "history_key": history,
        "market_key": market,
        "games": [],
        "source": SOURCE,
        "sportsbook_influence": 0.0,
        "projection_enabled": False,
        "market_enabled": False,
        "wager_actions": False,
    }

    if not event_id.isdigit() or not athlete_id.isdigit():
        base["reason"] = "exact ESPN event and athlete IDs are required"
        return base
    if not team_abbr or not opponent_abbr or team_abbr == opponent_abbr:
        base["reason"] = "exact player team and opponent are required"
        return base
    if season < 2000:
        base["reason"] = "anchor season is required"
        return base
    if market not in SUPPORTED_MARKETS:
        base["reason"] = "selected market is outside the certified historical stat set"
        return base

    try:
        if market in PASSING_GAMELOG_MARKETS:
            games = _passing_history_games(
                athlete_id,
                opponent_abbr,
                season,
                history,
                market,
            )
            base.update({
                "ready": True,
                "data_available": bool(games),
                "reason": "" if games else "no exact-ID athlete game-log rows for selected window/market",
                "games": games,
                "source": "ESPN exact-ID athlete game log",
            })
            return base

        team_id, opponent_id = _team_identity_from_summary(event_id, team_abbr, opponent_abbr)
        candidates = _candidate_events(athlete_id, season)
        selected = _select_events(
            candidates,
            history,
            opponent_id,
            opponent_abbr,
        )

        games: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(selected)))) as pool:
            futures = {
                pool.submit(_fetch_game_value, row, team_id, athlete_id, market): row
                for row in selected
            }
            for future in as_completed(futures):
                try:
                    game = future.result()
                except PropHistoryError:
                    game = None
                if game is not None:
                    games.append(game)
        games.sort(key=lambda row: (row["date"], row["official_event_id"]), reverse=True)

        base.update({
            "ready": True,
            "data_available": bool(games),
            "reason": "" if games else "no exact-ID completed game-book rows for selected window/market",
            "official_team_id": team_id,
            "opponent_official_team_id": opponent_id,
            "candidate_game_count": len(selected),
            "games": games,
        })
        return base
    except PropHistoryError as exc:
        base["reason"] = str(exc)
        return base


def summarize_history(
    games: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    line: Any = None,
) -> dict[str, Any]:
    values = [
        float(row["value"])
        for row in games
        if isinstance(row, dict)
        and _number(row.get("value")) is not None
    ]
    if not values:
        return {
            "ready": False,
            "sample_size": 0,
            "average": None,
            "median": None,
            "high": None,
            "low": None,
            "last": None,
            "hit_rate_state": "no-data",
            "hit_count": None,
            "hit_rate_pct": None,
            "line": None,
        }

    line_value = _number(line)
    hit_count = None
    hit_rate = None
    hit_state = "awaiting-line"
    if line_value is not None:
        hit_count = sum(1 for value in values if value > line_value)
        hit_rate = (hit_count / len(values)) * 100.0
        hit_state = "ready"

    return {
        "ready": True,
        "sample_size": len(values),
        "average": mean(values),
        "median": median(values),
        "high": max(values),
        "low": min(values),
        "last": values[0],
        "hit_rate_state": hit_state,
        "hit_count": hit_count,
        "hit_rate_pct": hit_rate,
        "line": line_value,
    }


__all__ = [
    "HISTORY_SEASONS",
    "MAX_H2H_GAMES",
    "MAX_RECENT_GAMES",
    "MARKET_ENABLED",
    "PASSING_GAMELOG_MARKETS",
    "MODEL_VERSION",
    "PROJECTION_ENABLED",
    "PropHistoryError",
    "SOURCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SUPPORTED_MARKETS",
    "WAGER_ACTIONS",
    "load_player_history",
    "summarize_history",
]
