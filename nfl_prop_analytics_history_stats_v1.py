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
from functools import lru_cache
import math
import re
from statistics import mean, median
from typing import Any

import requests

from nfl_prop_analytics_schedule_v1 import _canon_team

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 STEP 3 • EXACT-ID HISTORY STATS V1"
SOURCE = "ESPN exact-ID completed regular-season game books"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
REQUEST_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "KyreSportsAI-PropAnalytics-History/1.0",
}
REQUEST_TIMEOUT_SECONDS = 8
HISTORY_SEASONS = 3
MAX_RECENT_GAMES = 20
MAX_H2H_GAMES = 5
MAX_WORKERS = 6
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_ENABLED = False
MARKET_ENABLED = False
WAGER_ACTIONS = False

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


@lru_cache(maxsize=512)
def _get_json(url: str, query_items: tuple[tuple[str, str], ...] = ()) -> dict[str, Any]:
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


def _query(**values: Any) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(k), str(v)) for k, v in values.items()))


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


@lru_cache(maxsize=96)
def _team_schedule(team_id: str, season: int) -> tuple[dict[str, Any], ...]:
    if not _text(team_id).isdigit():
        raise PropHistoryError("official ESPN team id is required")
    payload = _get_json(
        f"{ESPN_BASE}/teams/{team_id}/schedule",
        _query(season=int(season), seasontype=2),
    )
    out: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        if not _regular_season(event) or not _completed(event):
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
            "season": _season_year(event, season),
            "team_ids": tuple(sorted(ids)),
            "opponent_abbr": _opponent_abbr(event, team_id),
        })
    out.sort(key=lambda row: (row["date"], row["event_id"]), reverse=True)
    return tuple(out)


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
        if not rushing and not receiving:
            return None
        return float(rushing.get("rushing_touchdowns", 0.0) + receiving.get("receiving_touchdowns", 0.0))
    return None


def _candidate_events(team_id: str, anchor_season: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for season in range(int(anchor_season), int(anchor_season) - HISTORY_SEASONS, -1):
        for row in _team_schedule(team_id, season):
            if row["event_id"] in seen:
                continue
            seen.add(row["event_id"])
            rows.append(dict(row))
    rows.sort(key=lambda row: (row["date"], row["event_id"]), reverse=True)
    return rows


def _select_events(
    rows: list[dict[str, Any]],
    history_key: str,
    opponent_id: str,
) -> list[dict[str, Any]]:
    key = _text(history_key).upper()
    if key == "H2H":
        selected = [
            row for row in rows
            if opponent_id in set(row.get("team_ids") or ())
        ]
        return selected[:MAX_H2H_GAMES]
    if key in {"L5", "L10", "L20"}:
        return rows[: int(key[1:])]
    if key.isdigit() and len(key) == 4:
        season = int(key)
        return [row for row in rows if int(row.get("season") or 0) == season]
    raise PropHistoryError(f"unsupported history window: {history_key}")


def _fetch_game_value(
    row: dict[str, Any],
    team_id: str,
    athlete_id: str,
    market_key: str,
) -> dict[str, Any] | None:
    event_id = _text(row.get("event_id"))
    summary = _get_json(f"{ESPN_BASE}/summary", _query(event=event_id))
    value = _market_value(summary, team_id, athlete_id, market_key)
    if value is None or not math.isfinite(float(value)):
        return None
    return {
        "official_event_id": event_id,
        "official_athlete_id": athlete_id,
        "official_team_id": team_id,
        "date": _text(row.get("date")),
        "season": int(row.get("season") or 0),
        "opponent_abbr": _text(row.get("opponent_abbr")).upper(),
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
        team_id, opponent_id = _team_identity_from_summary(event_id, team_abbr, opponent_abbr)
        candidates = _candidate_events(team_id, season)
        selected = _select_events(candidates, history, opponent_id)

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
