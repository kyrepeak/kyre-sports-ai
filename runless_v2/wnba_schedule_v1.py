"""Official WNBA schedule transport for Kyre Sports API — Vercel."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba-schedule"])
PUBLIC_URL = "https://www.wnba.com/api/schedule"
CDN_URL = "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json"
EASTERN = ZoneInfo("America/New_York")


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _fetch(*, season: int) -> dict[str, Any]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.wnba.com",
        "Referer": "https://www.wnba.com/",
        "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-WNBA/2.0; read-only)",
    }
    errors: list[str] = []
    for url, params in ((PUBLIC_URL, {"season": str(season), "regionId": "1"}), (CDN_URL, None)):
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=18.0, follow_redirects=True)
            response.raise_for_status()
            body = response.json()
            if isinstance(body, dict) and isinstance(body.get("leagueSchedule"), dict):
                return body
            errors.append(f"{url}:shape")
        except Exception as exc:
            errors.append(f"{url}:{type(exc).__name__}")
    raise RuntimeError("Official WNBA schedule unavailable:" + ",".join(errors))


def _block_date(value: Any) -> str | None:
    text = _text(value)
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _team(raw: Any) -> dict[str, Any]:
    row = raw if isinstance(raw, Mapping) else {}
    city, name = _text(row.get("teamCity")), _text(row.get("teamName"))
    return {
        "official_team_id": int(row.get("teamId")) if str(row.get("teamId") or "").isdigit() else None,
        "full_name": " ".join(x for x in (city, name) if x),
        "team_city": city or None,
        "team_name": name or None,
        "team_tricode": _text(row.get("teamTricode")) or None,
        "wins": row.get("wins"),
        "losses": row.get("losses"),
    }


def _eastern_iso(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    # WNBA's *Est field is an Eastern wall-clock value even when suffixed Z.
    wall = text.rstrip("Z")
    try:
        parsed = datetime.fromisoformat(wall)
        return parsed.replace(tzinfo=EASTERN).isoformat()
    except ValueError:
        return None


def build_daily_schedule(
    *,
    date: str,
    season: int = 2026,
    payload_fetcher: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    datetime.strptime(date, "%Y-%m-%d")
    if int(season) != 2026:
        raise ValueError("WNBA schedule currently supports season 2026.")
    payload = (payload_fetcher or _fetch)(season=season)
    root = payload.get("leagueSchedule") if isinstance(payload, Mapping) else None
    if not isinstance(root, Mapping) or _text(root.get("leagueId")) != "10":
        raise RuntimeError("Official WNBA schedule payload failed league identity validation.")
    games: list[dict[str, Any]] = []
    for block in root.get("gameDates") or []:
        if not isinstance(block, Mapping) or _block_date(block.get("gameDate")) != date:
            continue
        for game in block.get("games") or []:
            if not isinstance(game, Mapping):
                continue
            status_code = int(game.get("gameStatus")) if str(game.get("gameStatus") or "").isdigit() else None
            games.append({
                "game_id": _text(game.get("gameId")),
                "game_code": _text(game.get("gameCode")) or None,
                "season": int(season),
                "official_schedule_date": date,
                "game_datetime_utc": _text(game.get("gameDateTimeUTC")) or None,
                "game_datetime_eastern": _eastern_iso(game.get("gameDateTimeEst")),
                "status": {
                    "code": status_code,
                    "text": _text(game.get("gameStatusText")) or None,
                    "category": "scheduled" if status_code == 1 else ("live" if status_code == 2 else "final" if status_code == 3 else "unknown"),
                },
                "competition": {
                    "game_label": _text(game.get("gameLabel")) or None,
                    "game_sub_label": _text(game.get("gameSubLabel")) or None,
                    "series_text": _text(game.get("seriesText")) or None,
                    "series_game_number": _text(game.get("seriesGameNumber")) or None,
                    "if_necessary": bool(game.get("ifNecessary")),
                },
                "away": _team(game.get("awayTeam")),
                "home": _team(game.get("homeTeam")),
            })
    return {
        "service": "Kyre Sports API — Vercel",
        "source": "WNBA Official Schedule",
        "source_url": PUBLIC_URL,
        "season": int(season),
        "date": date,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_count": len(games),
        "games": games,
    }


@router.get("/games")
def games(date: str = Query(...), season: int = Query(2026)) -> dict[str, Any]:
    try:
        return build_daily_schedule(date=date, season=season)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WNBA official schedule unavailable:{type(exc).__name__}") from exc
