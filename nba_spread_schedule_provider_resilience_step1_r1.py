"""NBA Spread provider-resilience Step 1 R1.

Additive transport repair for the frozen NBA Spread schedule engine.
The schedule ownership and quorum remain unchanged: NBA Official + ESPN NBA.

Transport recovery stays inside those existing source families:
1. NBA Official first uses the current CDN schedule document with browser/WAF
   request metadata.
2. If the NBA CDN is blocked, the same NBA Official source family falls back
   to the NBA-owned data.nba.com full-season schedule feed and normalizes its
   legacy payload into the exact shape consumed by the frozen parser.
3. ESPN rolling date ranges are fanned out to supported single-day scoreboard
   requests and merged back into the frozen parser's payload shape.

Provider disagreement still fails closed. No third-party fallback provider is
activated in Step 1 and no model/projection/probability behavior changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

import nba_spread_schedule_v1 as frozen_schedule

MODEL_VERSION = "NBA_SPREAD_PROVIDER_RESILIENCE_STEP1_R1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SOURCE_OWNERSHIP = False
NETWORK_PROVIDER_COUNT_ADDED = 0
MAX_ESPN_RANGE_DAYS = 14

NBA_LEGACY_SCHEDULE_URL = (
    "https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/"
    "{season_start_year}/league/00_full_schedule.json"
)

NBA_CDN_HEADERS: dict[str, str] = {
    "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.nba.com",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://www.nba.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

NBA_LEGACY_HEADERS: dict[str, str] = {
    "User-Agent": NBA_CDN_HEADERS["User-Agent"],
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nba.com/",
    "Accept-Language": "en-US,en;q=0.9",
    "x-nba-stats-origin": "stats",
}


class _MergedJsonResponse:
    """Minimal requests.Response-compatible wrapper for normalized/merged JSON."""

    status_code = 200

    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def _espn_range_days(raw_dates: Any) -> tuple[str, ...] | None:
    """Expand ESPN YYYYMMDD-YYYYMMDD range syntax into supported single dates."""
    text = str(raw_dates or "").strip()
    if "-" not in text:
        return None
    start_text, end_text = text.split("-", 1)
    if len(start_text) != 8 or len(end_text) != 8:
        return None
    try:
        start = datetime.strptime(start_text, "%Y%m%d").date()
        end = datetime.strptime(end_text, "%Y%m%d").date()
    except ValueError:
        return None
    if end < start:
        return None
    span = (end - start).days + 1
    if span < 1 or span > MAX_ESPN_RANGE_DAYS:
        return None
    return tuple((start + timedelta(days=offset)).strftime("%Y%m%d") for offset in range(span))


def _season_start_year(now_utc: datetime | None) -> int:
    current = now_utc or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    return current.year if current.month >= 7 else current.year - 1


def _legacy_status_code(status_text: Any) -> int:
    text = str(status_text or "").strip().lower()
    if "final" in text:
        return 3
    if any(token in text for token in ("live", "in progress", "quarter", "qtr", "halftime")):
        return 2
    return 1


def _legacy_tip_utc(game: dict[str, Any]) -> str | None:
    date_text = str(game.get("gdtutc") or "").strip()
    time_text = str(game.get("utctm") or "").strip()
    if not date_text or not time_text:
        return None
    normalized_time = time_text.removesuffix("Z")
    if len(normalized_time) == 5:
        normalized_time = f"{normalized_time}:00"
    try:
        parsed = datetime.fromisoformat(f"{date_text}T{normalized_time}")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _legacy_schedule_nodes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = payload.get("lscd") if isinstance(payload, dict) else None
    if not isinstance(blocks, list):
        raise ValueError("NBA legacy schedule returned invalid lscd")
    nodes: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        month = block.get("mscd")
        if isinstance(month, dict):
            nodes.append(month)
        elif isinstance(month, list):
            nodes.extend(item for item in month if isinstance(item, dict))
    return nodes


def _normalize_legacy_official_schedule(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert NBA-owned data.nba.com schedule JSON into frozen V2 shape."""
    by_date: dict[str, list[dict[str, Any]]] = {}
    for month in _legacy_schedule_nodes(payload):
        games = month.get("g") or []
        if not isinstance(games, list):
            continue
        for game in games:
            if not isinstance(game, dict):
                continue
            tip_utc = _legacy_tip_utc(game)
            away = game.get("v") or {}
            home = game.get("h") or {}
            if tip_utc is None or not isinstance(away, dict) or not isinstance(home, dict):
                continue
            away_code = str(away.get("ta") or "").strip().upper()
            home_code = str(home.get("ta") or "").strip().upper()
            if not away_code or not home_code:
                continue
            game_date = str(game.get("gdte") or game.get("gdtutc") or "").strip()
            if not game_date:
                game_date = tip_utc[:10]
            status_text = str(game.get("stt") or "Scheduled").strip() or "Scheduled"
            by_date.setdefault(game_date, []).append(
                {
                    "gameId": str(game.get("gid") or "").strip(),
                    "gameDateTimeUTC": tip_utc,
                    "gameStatus": _legacy_status_code(status_text),
                    "gameStatusText": status_text,
                    "arenaName": str(game.get("an") or "").strip(),
                    "awayTeam": {
                        "teamTricode": away_code,
                        "teamCity": str(away.get("tc") or "").strip(),
                        "teamName": str(away.get("tn") or away_code).strip(),
                    },
                    "homeTeam": {
                        "teamTricode": home_code,
                        "teamCity": str(home.get("tc") or "").strip(),
                        "teamName": str(home.get("tn") or home_code).strip(),
                    },
                }
            )
    if not by_date:
        raise ValueError("NBA legacy schedule contained no usable games")
    return {
        "leagueSchedule": {
            "gameDates": [
                {"gameDate": date_key, "games": by_date[date_key]}
                for date_key in sorted(by_date)
            ]
        }
    }


class _NbaProviderTransportRepairSession:
    """Delegate HTTP while repairing only NBA Official and ESPN transport."""

    def __init__(self, delegate: Any, *, season_start_year: int):
        self._delegate = delegate
        self._season_start_year = int(season_start_year)
        self._legacy_attempted = False
        self._legacy_response: _MergedJsonResponse | None = None
        self._legacy_error: Exception | None = None

    def _get_legacy_official(self, *, timeout: Any) -> _MergedJsonResponse:
        if self._legacy_response is not None:
            return self._legacy_response
        if self._legacy_attempted:
            if self._legacy_error is not None:
                raise self._legacy_error
            raise RuntimeError("NBA legacy schedule fallback unavailable")

        self._legacy_attempted = True
        url = NBA_LEGACY_SCHEDULE_URL.format(season_start_year=self._season_start_year)
        try:
            response = self._delegate.get(
                url,
                headers=NBA_LEGACY_HEADERS,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("NBA legacy schedule returned non-object JSON")
            normalized = _normalize_legacy_official_schedule(payload)
            self._legacy_response = _MergedJsonResponse(normalized)
            return self._legacy_response
        except Exception as exc:
            self._legacy_error = exc
            raise

    def _get_nba_official(self, url: str, *, args: tuple[Any, ...], kwargs: dict[str, Any]):
        call_kwargs = dict(kwargs)
        headers = dict(call_kwargs.pop("headers", {}) or {})
        headers.update(NBA_CDN_HEADERS)
        timeout = call_kwargs.get("timeout")
        try:
            response = self._delegate.get(url, *args, headers=headers, **call_kwargs)
            response.raise_for_status()
            return response
        except Exception as cdn_error:
            try:
                return self._get_legacy_official(timeout=timeout)
            except Exception:
                raise cdn_error

    def _get_espn_range(self, url: str, *, days: tuple[str, ...], args: tuple[Any, ...], kwargs: dict[str, Any]):
        original_params = dict(kwargs.get("params") or {})
        merged_payload: dict[str, Any] = {}
        merged_events: list[dict[str, Any]] = []
        seen_event_ids: set[str] = set()

        for day in days:
            call_kwargs = dict(kwargs)
            params = dict(original_params)
            params["dates"] = day
            call_kwargs["params"] = params
            response = self._delegate.get(url, *args, **call_kwargs)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("ESPN scoreboard returned non-object JSON")
            if not merged_payload:
                merged_payload = dict(payload)
            for event in payload.get("events") or []:
                if not isinstance(event, dict):
                    continue
                event_id = str(event.get("id") or "").strip()
                dedupe_key = event_id or repr(event)
                if dedupe_key in seen_event_ids:
                    continue
                seen_event_ids.add(dedupe_key)
                merged_events.append(event)

        merged_payload["events"] = merged_events
        return _MergedJsonResponse(merged_payload)

    def get(self, url: str, *args: Any, **kwargs: Any):
        headers = dict(kwargs.pop("headers", {}) or {})
        normalized_url = str(url)

        if normalized_url.startswith("https://cdn.nba.com/"):
            kwargs["headers"] = headers
            return self._get_nba_official(url, args=args, kwargs=kwargs)

        if normalized_url.startswith(frozen_schedule.ESPN_SCOREBOARD_URL):
            params = dict(kwargs.get("params") or {})
            range_days = _espn_range_days(params.get("dates"))
            if range_days:
                kwargs["headers"] = headers
                return self._get_espn_range(url, days=range_days, args=args, kwargs=kwargs)

        return self._delegate.get(url, *args, headers=headers, **kwargs)


def load_verified_nba_schedule(
    *,
    now_utc: datetime | None = None,
    days: int = frozen_schedule.ROLLING_DAYS,
    session: Any | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Run the frozen verifier with repaired provider transport semantics."""
    delegate = session if session is not None else requests.Session()
    repaired = _NbaProviderTransportRepairSession(
        delegate,
        season_start_year=_season_start_year(now_utc),
    )
    return frozen_schedule.load_verified_nba_schedule(
        now_utc=now_utc,
        days=days,
        session=repaired,
        timeout=timeout,
    )


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_SOURCE_OWNERSHIP",
    "NETWORK_PROVIDER_COUNT_ADDED",
    "MAX_ESPN_RANGE_DAYS",
    "NBA_CDN_HEADERS",
    "NBA_LEGACY_HEADERS",
    "NBA_LEGACY_SCHEDULE_URL",
    "load_verified_nba_schedule",
]
