"""NBA Spread Step 9 — verified score-derived performance history transport.

Source ownership is deliberately narrow: NBA Official + ESPN NBA must agree on
completed-game identity and score margin. No sportsbook, public betting, sharp
money, or injury provider can become a projection source here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

import requests

import nba_spread_schedule_v1 as schedule
from nba_spread_fair_spread_probability_v1 import reconcile_performance_sources
from nba_spread_schedule_provider_resilience_step1_r1 import (
    ESPN_TO_NBA_TRICODE,
    NBA_CDN_HEADERS,
    NBA_LEGACY_HEADERS,
    NBA_LEGACY_SCHEDULE_URL,
)

MODEL_VERSION = "NBA_SPREAD_STEP9_PERFORMANCE_HISTORY_V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
SOURCE_OWNERS = ("NBA Official", "ESPN NBA")
PHOENIX_TZ = ZoneInfo("America/Phoenix")
MAX_HISTORY_GAME_DATES = 14


def _number(value: object) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def _iso_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _phoenix_date(value: object) -> str | None:
    parsed = _iso_datetime(value)
    return parsed.astimezone(PHOENIX_TZ).date().isoformat() if parsed is not None else None


def _canonical_code(value: object) -> str:
    raw = str(value or "").strip().upper()
    return ESPN_TO_NBA_TRICODE.get(raw, raw)


def _append_game_rows(
    rows: list[dict[str, object]],
    *,
    game_date: str,
    away: str,
    home: str,
    away_score: float,
    home_score: float,
) -> None:
    game_id = f"{game_date}:{away}@{home}"
    rows.append({
        "game_id": game_id,
        "team_tricode": away,
        "margin": float(away_score - home_score),
        "game_date": game_date,
        "is_home": False,
    })
    rows.append({
        "game_id": game_id,
        "team_tricode": home,
        "margin": float(home_score - away_score),
        "game_date": game_date,
        "is_home": True,
    })


def parse_nba_official_history(payload: Mapping[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    league = payload.get("leagueSchedule") if isinstance(payload, Mapping) else None
    blocks = league.get("gameDates") if isinstance(league, Mapping) else None
    if not isinstance(blocks, list):
        return rows
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        for game in block.get("games") or []:
            if not isinstance(game, Mapping):
                continue
            status = str(game.get("gameStatusText") or "").lower()
            try:
                status_code = int(game.get("gameStatus"))
            except (TypeError, ValueError):
                status_code = 0
            if status_code != 3 and "final" not in status:
                continue
            away = game.get("awayTeam") or {}
            home = game.get("homeTeam") or {}
            if not isinstance(away, Mapping) or not isinstance(home, Mapping):
                continue
            away_code = _canonical_code(away.get("teamTricode"))
            home_code = _canonical_code(home.get("teamTricode"))
            away_score = _number(away.get("score") if away.get("score") is not None else away.get("points"))
            home_score = _number(home.get("score") if home.get("score") is not None else home.get("points"))
            game_date = _phoenix_date(game.get("gameDateTimeUTC"))
            if not away_code or not home_code or away_score is None or home_score is None or not game_date:
                continue
            _append_game_rows(
                rows,
                game_date=game_date,
                away=away_code,
                home=home_code,
                away_score=away_score,
                home_score=home_score,
            )
    return rows


def _legacy_tip(game: Mapping[str, Any]) -> str | None:
    date_text = str(game.get("gdtutc") or "").strip()
    time_text = str(game.get("utctm") or "").strip().removesuffix("Z")
    if not date_text:
        return None
    if not time_text:
        time_text = "12:00:00"
    elif len(time_text) == 5:
        time_text += ":00"
    return f"{date_text}T{time_text}Z"


def parse_nba_legacy_history(payload: Mapping[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    blocks = payload.get("lscd") if isinstance(payload, Mapping) else None
    if not isinstance(blocks, list):
        return rows
    for block in blocks:
        month = block.get("mscd") if isinstance(block, Mapping) else None
        months = month if isinstance(month, list) else [month]
        for node in months:
            if not isinstance(node, Mapping):
                continue
            for game in node.get("g") or []:
                if not isinstance(game, Mapping) or "final" not in str(game.get("stt") or "").lower():
                    continue
                away = game.get("v") or {}
                home = game.get("h") or {}
                if not isinstance(away, Mapping) or not isinstance(home, Mapping):
                    continue
                away_code = _canonical_code(away.get("ta"))
                home_code = _canonical_code(home.get("ta"))
                away_score = _number(away.get("s"))
                home_score = _number(home.get("s"))
                game_date = _phoenix_date(_legacy_tip(game))
                if not away_code or not home_code or away_score is None or home_score is None or not game_date:
                    continue
                _append_game_rows(
                    rows,
                    game_date=game_date,
                    away=away_code,
                    home=home_code,
                    away_score=away_score,
                    home_score=home_score,
                )
    return rows


def parse_espn_history(payload: Mapping[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        status_type = ((event.get("status") or {}).get("type") or {}) if isinstance(event.get("status") or {}, Mapping) else {}
        if str(status_type.get("state") or "").lower() != "post" and "final" not in str(status_type.get("description") or "").lower():
            continue
        competitions = event.get("competitions") or []
        competition = competitions[0] if competitions and isinstance(competitions[0], Mapping) else {}
        competitors = competition.get("competitors") or []
        by_side = {
            str(item.get("homeAway") or "").lower(): item
            for item in competitors
            if isinstance(item, Mapping)
        }
        away = by_side.get("away") or {}
        home = by_side.get("home") or {}
        away_team = away.get("team") or {}
        home_team = home.get("team") or {}
        away_code = _canonical_code(away_team.get("abbreviation") if isinstance(away_team, Mapping) else None)
        home_code = _canonical_code(home_team.get("abbreviation") if isinstance(home_team, Mapping) else None)
        away_score = _number(away.get("score"))
        home_score = _number(home.get("score"))
        game_date = _phoenix_date(competition.get("date") or event.get("date"))
        if not away_code or not home_code or away_score is None or home_score is None or not game_date:
            continue
        _append_game_rows(
            rows,
            game_date=game_date,
            away=away_code,
            home=home_code,
            away_score=away_score,
            home_score=home_score,
        )
    return rows


def _request_json(
    request_get: Callable[..., Any],
    url: str,
    *,
    timeout: float,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    response = request_get(url, timeout=timeout, headers=dict(headers or {}), params=dict(params or {}))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("provider returned non-object JSON")
    return payload


def _season_start_year(target_date: str) -> int:
    year = int(target_date[:4])
    month = int(target_date[5:7])
    return year if month >= 7 else year - 1


def _official_history(
    *,
    target_date: str,
    request_get: Callable[..., Any],
    timeout: float,
) -> list[dict[str, object]]:
    for url in schedule.NBA_OFFICIAL_SCHEDULE_URLS:
        try:
            payload = _request_json(request_get, url, timeout=timeout, headers=NBA_CDN_HEADERS)
            rows = parse_nba_official_history(payload)
            if rows:
                return rows
        except Exception:
            continue
    try:
        payload = _request_json(
            request_get,
            NBA_LEGACY_SCHEDULE_URL.format(season_start_year=_season_start_year(target_date)),
            timeout=timeout,
            headers=NBA_LEGACY_HEADERS,
        )
        return parse_nba_legacy_history(payload)
    except Exception:
        return []


def load_verified_performance_history(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    request_get: Callable[..., Any] = requests.get,
    timeout: float = 8.0,
) -> dict[str, object]:
    target_dates = sorted(
        str(game.get("game_date_phoenix") or "")[:10]
        for game in schedule_games
        if len(str(game.get("game_date_phoenix") or "")[:10]) == 10
    )
    if not target_dates:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "TARGET_DATE_UNAVAILABLE",
            "official_history": [],
            "espn_history": [],
        }
    target_date = target_dates[0]
    official_all = _official_history(target_date=target_date, request_get=request_get, timeout=timeout)
    if not official_all:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "NBA_OFFICIAL_PERFORMANCE_UNAVAILABLE",
            "official_history": [],
            "espn_history": [],
        }

    dates = sorted({str(row["game_date"]) for row in official_all if str(row["game_date"]) < target_date})[-MAX_HISTORY_GAME_DATES:]
    if not dates:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "NO_COMPLETED_OFFICIAL_HISTORY",
            "official_history": [],
            "espn_history": [],
        }
    official = [dict(row) for row in official_all if str(row["game_date"]) in set(dates)]

    espn: list[dict[str, object]] = []
    try:
        for day in dates:
            payload = _request_json(
                request_get,
                schedule.ESPN_SCOREBOARD_URL,
                timeout=timeout,
                params={"dates": day.replace("-", ""), "limit": 1000},
            )
            espn.extend(parse_espn_history(payload))
    except Exception as exc:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": f"ESPN_PERFORMANCE_UNAVAILABLE:{type(exc).__name__}",
            "official_history": official,
            "espn_history": [],
        }

    canonical, diagnostic = reconcile_performance_sources(official, espn)
    if canonical is None:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": diagnostic,
            "official_history": official,
            "espn_history": espn,
        }
    return {
        "verification": "VERIFIED",
        "diagnostic_state": "SOURCE_CONSENSUS",
        "source_count": 2,
        "sources": list(SOURCE_OWNERS),
        "official_history": official,
        "espn_history": espn,
        "canonical_history": canonical,
        "history_game_dates": dates,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE_OWNERS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "load_verified_performance_history",
    "parse_espn_history",
    "parse_nba_legacy_history",
    "parse_nba_official_history",
]
