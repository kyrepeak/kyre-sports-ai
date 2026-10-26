"""Kyre Sports API production NBA PRA usage context owner.

Application pages never call this provider directly. The production Kyre Sports
API player-context route owns request, normalization, fallback, and delivery.
Only verified NBA Stats advanced usage is surfaced; missing values remain absent.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable, Mapping, Sequence

NBA_STATS_ADVANCED_URL = "https://stats.nba.com/stats/leaguedashplayerstats"
NBA_STATS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
}


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split())


def _norm(value: Any) -> str:
    return "".join(ch for ch in _text(value).casefold() if ch.isalnum())


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _season_end_year(day: date) -> int:
    return day.year + 1 if day.month >= 10 else day.year


def _season_label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _result_block(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = payload.get("resultSets") or payload.get("resultSet") or []
    blocks = [raw] if isinstance(raw, Mapping) else list(raw) if isinstance(raw, list) else []
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        headers = {str(item) for item in (block.get("headers") or [])}
        if {"PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN", "USG_PCT"}.issubset(headers):
            return block
    return {}


def normalize_nba_usage_payload(
    payload: Mapping[str, Any],
    *,
    season_label: str,
    season_type: str = "Regular Season",
) -> dict[str, dict[str, Any]]:
    block = _result_block(payload)
    headers = [str(item) for item in (block.get("headers") or [])]
    rows = block.get("rowSet") or []
    index = {name: idx for idx, name in enumerate(headers)}
    if not index:
        return {}

    normalized_rows: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, (list, tuple)):
            continue

        def value(name: str) -> Any:
            pos = index.get(name)
            return raw[pos] if pos is not None and pos < len(raw) else None

        name = _text(value("PLAYER_NAME"))
        team = _text(value("TEAM_ABBREVIATION")).upper()
        usage = _num(value("USG_PCT"))
        games = _num(value("GP"))
        minutes = _num(value("MIN"))
        if not name or not team or usage is None or games is None or games <= 0 or minutes is None or minutes <= 0:
            continue
        usage_points = usage * 100.0 if 0.0 <= usage <= 1.5 else usage
        normalized_rows.append(
            {
                "player_name": name,
                "team": team,
                "usage_pct": round(float(usage_points), 1),
                "usage_games": int(games),
                "usage_minutes": round(float(minutes), 1),
            }
        )

    out: dict[str, dict[str, Any]] = {}
    period = _text(season_type).upper() or "REGULAR SEASON"
    for row in normalized_rows:
        teammates = [candidate for candidate in normalized_rows if candidate["team"] == row["team"]]
        rank = 1 + sum(1 for candidate in teammates if float(candidate["usage_pct"]) > float(row["usage_pct"]))
        out[_norm(row["player_name"])] = {
            **row,
            "usage_rank": rank,
            "usage_team_size": len(teammates),
            "usage_period": f"{season_label} {period}",
            "usage_source": "NBA Stats",
            "usage_scope": "TEAM PLAYERS WITH VERIFIED NBA STATS USG%",
        }
    return out


def _load_season(
    end_year: int,
    *,
    season_type: str = "Regular Season",
    request_get: Callable[..., Any],
    timeout: float,
) -> dict[str, dict[str, Any]]:
    label = _season_label(end_year)
    response = request_get(
        NBA_STATS_ADVANCED_URL,
        params={
            "LeagueID": "00",
            "MeasureType": "Advanced",
            "PerMode": "PerGame",
            "PlusMinus": "N",
            "PaceAdjust": "N",
            "Rank": "N",
            "Season": label,
            "SeasonType": season_type,
        },
        headers=NBA_STATS_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        return {}
    return normalize_nba_usage_payload(payload, season_label=label, season_type=season_type)


def load_nba_usage_context(
    slate_date: date,
    player_names: Sequence[str],
    *,
    request_get: Callable[..., Any] | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Return verified usage/rank using bounded NBA Stats fallback periods."""
    if request_get is None:
        import requests
        request_get = requests.get

    requested: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in player_names:
        name = _text(raw)
        key = _norm(name)
        if name and key and key not in seen:
            requested.append((key, name))
            seen.add(key)
    if not requested:
        return {"status": "DEGRADED", "diagnostic_state": "NO_PLAYERS", "profiles": {}, "source": "NBA Stats", "fabrication": False}

    end_year = _season_end_year(slate_date)
    profiles: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    transport_failed = False

    def _transport_failure(exc: Exception) -> bool:
        name = type(exc).__name__.casefold()
        return isinstance(exc, (TimeoutError, ConnectionError)) or "timeout" in name or "connection" in name

    def merge_period(year: int, season_type: str, label: str) -> None:
        nonlocal transport_failed
        if transport_failed:
            return
        missing = [key for key, _name in requested if key not in profiles]
        if not missing:
            return
        try:
            rows = _load_season(year, season_type=season_type, request_get=request_get, timeout=timeout)
        except Exception as exc:
            errors.append(f"{label}_{type(exc).__name__}")
            if _transport_failure(exc):
                transport_failed = True
            return
        for key in missing:
            if key in rows:
                profiles[key] = dict(rows[key])

    merge_period(end_year, "Regular Season", "CURRENT_REGULAR")
    merge_period(end_year, "Pre Season", "CURRENT_PRESEASON")
    merge_period(end_year - 1, "Regular Season", "PRIOR_REGULAR")

    resolved = len(profiles)
    status = "HEALTHY" if resolved == len(requested) else "DEGRADED"
    detail = f"RESOLVED_{resolved}_OF_{len(requested)}"
    if errors:
        detail += ":" + ":".join(errors)
    return {
        "status": status,
        "diagnostic_state": detail,
        "profiles": profiles,
        "source": "NBA Stats",
        "fabrication": False,
    }
