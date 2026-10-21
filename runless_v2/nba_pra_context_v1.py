"""Kyre Sports API NBA Page 1 context router.

Schedule and availability state are resolved server-side so Streamlit never
calls an individual NBA provider. This active router does not call ESPN or SGO.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel

from .nba_pra_market_v1 import router

PHOENIX = ZoneInfo("America/Phoenix")
NBA_SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
NBA_HEADERS = {
    "Accept": "application/json,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0)",
    "Referer": "https://www.nba.com/",
}
CBS_SCOREBOARD = "https://www.cbssports.com/nba/scoreboard/{date}/"
CBS_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0)",
}


class NbaPraContextRequest(BaseModel):
    now_utc: datetime | None = None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _utc(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _health(status: str, detail: str, attempted: bool) -> dict[str, Any]:
    return {"status": status, "detail": detail, "attempted": attempted}


def _normalize_official_schedule(payload: Mapping[str, Any], now_utc: datetime) -> list[dict[str, Any]]:
    root = payload.get("leagueSchedule") or payload.get("schedule") or {}
    date_blocks = root.get("gameDates") if isinstance(root, Mapping) else []
    games: list[dict[str, Any]] = []
    for block in date_blocks or []:
        if not isinstance(block, Mapping):
            continue
        for raw in block.get("games", []) or []:
            if not isinstance(raw, Mapping):
                continue
            tip = _utc(raw.get("gameDateTimeUTC") or raw.get("gameTimeUTC") or raw.get("gameDateTimeEst"))
            if tip is None or tip <= now_utc:
                continue
            away = raw.get("awayTeam") or {}
            home = raw.get("homeTeam") or {}
            away_code = _text(away.get("teamTricode") or away.get("tricode")).upper()
            home_code = _text(home.get("teamTricode") or home.get("tricode")).upper()
            if not away_code or not home_code:
                continue
            phoenix = tip.astimezone(PHOENIX)
            day = phoenix.date().isoformat()
            games.append({
                "source": "NBA Official",
                "source_game_id": _text(raw.get("gameId")),
                "game_key": f"{away_code}@{home_code}:{day}",
                "away_tricode": away_code,
                "away_name": _text(away.get("teamName") or away.get("teamCity")) or away_code,
                "home_tricode": home_code,
                "home_name": _text(home.get("teamName") or home.get("teamCity")) or home_code,
                "tip_utc": tip.isoformat().replace("+00:00", "Z"),
                "tip_iso_phoenix": phoenix.isoformat(),
                "tip_phoenix": phoenix.strftime("%-I:%M %p MST"),
                "game_date_phoenix": day,
                "status": "UPCOMING",
                "gameStatus": 1,
                "gameStatusText": "Scheduled",
            })
    games.sort(key=lambda row: (row["tip_utc"], row["game_key"]))
    return games


def _default_official_schedule_loader(now_utc: datetime) -> list[dict[str, Any]]:
    timeout = httpx.Timeout(4.0, connect=2.0)
    with httpx.Client(headers=NBA_HEADERS, timeout=timeout, follow_redirects=False) as client:
        response = client.get(NBA_SCHEDULE_URL)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("NBA_OFFICIAL_SCHEDULE_INVALID")
    games = _normalize_official_schedule(payload, now_utc)
    if not games:
        raise ValueError("NBA_OFFICIAL_SCHEDULE_EMPTY")
    return games


def _default_cbs_schedule_loader(now_utc: datetime) -> list[dict[str, Any]]:
    # Reuse the existing pure CBS parser only; do not invoke its legacy
    # multi-provider schedule loader.
    from nba_spread_schedule_provider_resilience_step2_r1 import parse_cbs_scoreboard_html

    today = now_utc.astimezone(PHOENIX).date()
    games: list[dict[str, Any]] = []
    timeout = httpx.Timeout(8.0, connect=3.0)
    with httpx.Client(headers=CBS_HEADERS, timeout=timeout, follow_redirects=True) as client:
        for offset in range(7):
            day = today + timedelta(days=offset)
            response = client.get(CBS_SCOREBOARD.format(date=day.strftime("%Y%m%d")))
            response.raise_for_status()
            parsed = parse_cbs_scoreboard_html(response.text, day.isoformat())
            for game in parsed.get("games", []) or []:
                tip = _utc(game.get("tip_utc"))
                if tip is None or tip <= now_utc:
                    continue
                row = dict(game)
                row["gameStatus"] = 1
                row["gameStatusText"] = "Scheduled"
                row["status"] = "UPCOMING"
                games.append(row)
            if games:
                # The Page 1 router needs the next eligible slate, not every
                # future date. Stop after the first date with scheduled games.
                break
    games.sort(key=lambda row: (row.get("tip_utc") or "", row.get("game_key") or ""))
    if not games:
        raise ValueError("CBS_SCHEDULE_EMPTY")
    return games


def _default_official_injury_loader(games: list[dict[str, Any]], now_utc: datetime) -> dict[str, Any]:
    # Keep the active Page 1 transport server-side. Until a verified injury
    # adapter is available in this deployment, return explicit unavailability
    # instead of calling a forbidden frontend fallback or fabricating status.
    del games, now_utc
    return {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "NO_VERIFIED_SERVER_INJURY_ADAPTER",
        "features": [],
        "fabrication": False,
    }


def build_nba_pra_context(
    now_utc: datetime | None = None,
    *,
    official_schedule_loader: Callable[[datetime], list[dict[str, Any]]] | None = None,
    cbs_schedule_loader: Callable[[datetime], list[dict[str, Any]]] | None = None,
    official_injury_loader: Callable[[list[dict[str, Any]], datetime], Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env_map = dict(os.environ if env is None else env)
    official_schedule_loader = official_schedule_loader or _default_official_schedule_loader
    cbs_schedule_loader = cbs_schedule_loader or _default_cbs_schedule_loader
    official_injury_loader = official_injury_loader or _default_official_injury_loader

    health: dict[str, dict[str, Any]] = {}
    games: list[dict[str, Any]] = []
    schedule_source = ""
    try:
        games = list(official_schedule_loader(now) or [])
        if not games:
            raise ValueError("EMPTY")
        schedule_source = "NBA Official"
        health["nba_official_schedule"] = _health("HEALTHY", "OK", True)
    except Exception as exc:
        health["nba_official_schedule"] = _health("DEGRADED", type(exc).__name__, True)

    sr = _text(env_map.get("SPORTRADAR_API_KEY"))
    sd = _text(env_map.get("SPORTSDATAIO_API_KEY"))
    health["sportradar_schedule"] = _health(
        "DEGRADED" if sr else "UNAVAILABLE",
        "ADAPTER_NOT_ENABLED" if sr else "CREDENTIAL_NOT_CONFIGURED",
        False,
    )
    health["sportsdataio_schedule"] = _health(
        "DEGRADED" if sd else "UNAVAILABLE",
        "ADAPTER_NOT_ENABLED" if sd else "CREDENTIAL_NOT_CONFIGURED",
        False,
    )

    if not games:
        try:
            games = list(cbs_schedule_loader(now) or [])
            if not games:
                raise ValueError("EMPTY")
            schedule_source = "CBS Sports"
            health["cbs_sports_schedule"] = _health("HEALTHY", "OK", True)
        except Exception as exc:
            health["cbs_sports_schedule"] = _health("UNAVAILABLE", type(exc).__name__, True)
    else:
        health["cbs_sports_schedule"] = _health("UNAVAILABLE", "NOT_NEEDED", False)

    schedule = {
        "verification": "VERIFIED" if games else "UNAVAILABLE",
        "diagnostic_state": "OK" if games else "DATA_UNAVAILABLE",
        "source": schedule_source or "DATA_UNAVAILABLE",
        "games": games,
        "fabrication": False,
    }
    try:
        injuries = dict(official_injury_loader(games, now) or {}) if games else {
            "verification": "UNAVAILABLE", "diagnostic_state": "NO_SCHEDULE", "features": [], "fabrication": False
        }
    except Exception as exc:
        injuries = {
            "verification": "UNAVAILABLE",
            "diagnostic_state": f"INJURY_PROVIDER_ERROR:{type(exc).__name__}",
            "features": [],
            "fabrication": False,
        }
    health["nba_official_injury"] = _health(
        "HEALTHY" if injuries.get("verification") == "VERIFIED" else "UNAVAILABLE",
        str(injuries.get("diagnostic_state") or "DATA_UNAVAILABLE"),
        bool(games),
    )
    return {
        "schema_version": "KYRE_NBA_CONTEXT_V1",
        "verification": schedule["verification"],
        "schedule": schedule,
        "injuries": injuries,
        "provider_health": health,
        "fabrication": False,
    }


@router.post("/context")
def nba_pra_context(req: NbaPraContextRequest) -> dict[str, Any]:
    return build_nba_pra_context(req.now_utc)
